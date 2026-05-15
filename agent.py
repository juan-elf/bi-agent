import json
import os
import time
from typing import Any
from openai import OpenAI, APIError, RateLimitError, APIConnectionError
from dotenv import load_dotenv

from database import get_schema
from tools import TOOLS_SCHEMA, call_tool
from logger import ConversationLogger
import ui

load_dotenv()

MODEL_NAME = "MiniMax-M2.1"
MAX_ITERATIONS = 10
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

client = OpenAI(
    api_key=os.getenv("MINIMAX_API_KEY"),
    base_url="https://api.minimax.io/v1"
)


def build_system_prompt() -> str:
    schema = get_schema()
    return f"""You are a Business Intelligence assistant for an e-commerce database.

Your job: help the user answer business questions by generating and \
executing SQL queries using the tools provided.

AVAILABLE TOOLS:
- execute_sql: run a SELECT SQL query
- get_distinct_values: inspect unique values in a column (use BEFORE filtering if unsure)

IMPORTANT RULES:
1. Always check the database schema below before writing a query.
2. Use SQLite syntax. For monthly grouping use strftime('%Y-%m', order_date).
3. For revenue/sales questions, default to status = 'completed'
   unless the user asks otherwise.
4. Prices are in Rupiah (integer). Format answers with dot separators,
   e.g. Rp 1.500.000.
5. Dates are stored as TEXT in ISO format (YYYY-MM-DD).
6. If a query errors, READ the 'hint' field in the response and fix the query.
   DO NOT repeat the exact same query - always fix it based on the hint.
7. If unsure about the values in a column (e.g. what "status" values exist),
   use get_distinct_values first instead of guessing.
8. If the user's question is ambiguous, ask for clarification before querying.
9. Answer in clear, informative English.
10. Use markdown to format answers (bold, lists, tables where appropriate).

DATABASE SCHEMA:
{schema}
"""


def _call_api_with_retry(messages: list, tools: list) -> Any:
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            return client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
        except (RateLimitError, APIConnectionError, APIError) as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                wait = INITIAL_BACKOFF * (2 ** attempt)
                ui.warning(f"{type(e).__name__}, retrying in {wait}s "
                          f"({attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
            else:
                raise
    raise last_exception


class Agent:
    def __init__(self, verbose: bool = True, enable_logging: bool = True):
        self.verbose = verbose
        self.system_prompt = build_system_prompt()
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        self.logger = ConversationLogger() if enable_logging else None
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        if self.logger and self.verbose:
            ui.dim(f"Log: {self.logger.get_log_path()}")

    def get_stats(self) -> dict:
        return {
            "session_id": self.logger.session_id if self.logger else None,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "messages_in_history": len(self.messages),
        }

    def chat(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        if self.logger:
            self.logger.log_user_message(user_message)

        for iteration in range(MAX_ITERATIONS):
            if self.verbose:
                ui.print_iteration(iteration + 1)

            try:
                if self.verbose:
                    with ui.thinking_spinner("Agent thinking..."):
                        response = _call_api_with_retry(self.messages, TOOLS_SCHEMA)
                else:
                    response = _call_api_with_retry(self.messages, TOOLS_SCHEMA)
            except Exception as e:
                error_msg = (f"API failed after {MAX_RETRIES} retries: "
                            f"{type(e).__name__}: {e}")
                if self.verbose:
                    ui.error(error_msg)
                if self.logger:
                    self.logger.log_error("api_failure", error_msg)
                return f"{error_msg}. Please try again later."

            if response.usage:
                self.total_input_tokens += response.usage.prompt_tokens
                self.total_output_tokens += response.usage.completion_tokens

            assistant_msg = response.choices[0].message

            if assistant_msg.tool_calls:
                self.messages.append({
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in assistant_msg.tool_calls
                    ]
                })

                for tool_call in assistant_msg.tool_calls:
                    tool_name = tool_call.function.name

                    try:
                        tool_args = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError as e:
                        error_result = json.dumps({
                            "success": False,
                            "error": f"Tool arguments are not valid JSON: {e}"
                        })
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": error_result
                        })
                        continue

                    if self.verbose:
                        ui.print_tool_call(tool_name, tool_args)

                    result = call_tool(tool_name, tool_args)

                    if self.verbose:
                        ui.print_tool_result(result)

                    if self.logger:
                        self.logger.log_tool_call(tool_name, tool_args, result)

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })

                continue

            final_answer = assistant_msg.content
            self.messages.append({"role": "assistant", "content": final_answer})

            if self.logger:
                self.logger.log_assistant_message(
                    final_answer,
                    token_usage={
                        "total_input": self.total_input_tokens,
                        "total_output": self.total_output_tokens,
                    }
                )
            return final_answer

        msg = "Max iterations exceeded. Try a more specific question."
        if self.logger:
            self.logger.log_error("max_iterations", msg)
        return msg

    def reset(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.logger = ConversationLogger() if self.logger else None
