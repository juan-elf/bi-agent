"""
Agent loop utama — Battery Research Domain + Hybrid Web Search.

UPDATED: system prompt mengatur prioritas DB-first, web-fallback, combine.
"""
import json
import os
import time
from typing import Any
from openai import OpenAI, APIError, RateLimitError, APIConnectionError
from dotenv import load_dotenv

from database import get_schema
from tools import TOOLS_SCHEMA, call_tool
from logger import ConversationLogger
from web_search import is_available as web_available
import ui

load_dotenv()

MODEL_NAME = "MiniMax-M2.7"
MAX_ITERATIONS = 10
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

client = OpenAI(
    api_key=os.getenv("MINIMAX_API_KEY"),
    base_url="https://api.minimax.io/v1"
)


def build_system_prompt() -> str:
    """System prompt: domain context + hybrid DB/web strategy."""
    schema = get_schema()
    web_status = ("TERSEDIA" if web_available()
                  else "TIDAK TERSEDIA (TAVILY_API_KEY belum di-set)")

    return f"""You are a research assistant specialized in Li-ion battery aging analysis.
You help researchers query a battery degradation dataset using natural language,
and can also search the web for external context when needed.

═══════════════════════════════════════════════════════════════
DOMAIN GLOSSARY:
═══════════════════════════════════════════════════════════════
- Cycle: satu pasangan charge + discharge complete
- SOH (State of Health): kondisi battery sebagai % dari nominal capacity
- RUL (Remaining Useful Life): sisa cycles sebelum End of Life
- EOL (End of Life): umumnya SOH = 80%
- Capacity: kapasitas energi battery saat ini (Ah)
- Degradation rate: kecepatan penurunan SOH/capacity per cycle
- Knee point: cycle di mana degradasi mendadak akselerasi

═══════════════════════════════════════════════════════════════
SUMBER DATA & STRATEGI (PENTING!):
═══════════════════════════════════════════════════════════════
Kamu punya DUA sumber pengetahuan:

1. DATABASE (battery_cycles) — sumber UTAMA untuk data battery kita.
2. WEB SEARCH — untuk konteks eksternal. Status: {web_status}

ATURAN PRIORITAS:
• Untuk pertanyaan tentang DATA battery kita (SOH, capacity, cycle, RUL,
  temperature, degradation di dataset kita) → SELALU pakai execute_sql DULU.
• Pakai web_search HANYA jika:
   (a) Data yang ditanya TIDAK ADA di database (sudah dicek via SQL dan
       hasilnya kosong atau kolomnya memang tidak ada), ATAU
   (b) User minta konteks eksternal: benchmark industri, nilai "normal/typical",
       definisi konsep, perbandingan dengan standar, harga pasar, dll.
• KOMBINASI (paling powerful): kalau pertanyaan butuh data internal DAN
  konteks eksternal — misal "apakah degradasi B5 di dataset kita normal?" —
  maka: (1) query DB untuk angka kita, (2) web_search untuk benchmark,
  (3) gabungkan jadi satu jawaban yang kontekstual.

CONTOH KEPUTUSAN:
- "Berapa SOH B5 di cycle 100?" → execute_sql saja (data internal)
- "Apa itu knee point?" → web_search atau jawab dari pengetahuan (konsep)
- "Apakah degradasi 0.12%/cycle itu normal untuk Li-ion?" → execute_sql untuk
  konfirmasi angka kita + web_search untuk benchmark → gabungkan
- "Berapa harga battery 18650 di pasaran?" → web_search (tidak ada di DB)

Saat menggabungkan, BEDAKAN dengan jelas mana data dari dataset kita dan mana
dari sumber web (sebutkan sumbernya).

═══════════════════════════════════════════════════════════════
ATURAN UMUM:
═══════════════════════════════════════════════════════════════
1. Gunakan SQLite syntax.
2. EOL = SOH < 80%.
3. Untuk perbandingan antar battery, GROUP BY battery_id.
4. Sertakan UNIT pada jawaban (Ah, °C, V, A, cycles, %).
5. Kalau query SQL error, baca 'hint' dan perbaiki.
6. Jawaban dalam Bahasa Indonesia, istilah teknis tetap English (SOH, RUL, cycle).
7. Gunakan markdown untuk format.

═══════════════════════════════════════════════════════════════
DATABASE SCHEMA:
═══════════════════════════════════════════════════════════════
{schema}

═══════════════════════════════════════════════════════════════
EXAMPLE QUERIES:
═══════════════════════════════════════════════════════════════
Q: "Pada cycle berapa B5 mencapai EOL?"
SQL: SELECT MIN(cycle) FROM battery_cycles WHERE battery_id='B5' AND soh < 80

Q: "Degradation rate per battery"
SQL: SELECT battery_id, (MAX(soh)-MIN(soh))/(MAX(cycle)-MIN(cycle)) AS rate
     FROM battery_cycles GROUP BY battery_id
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
                ui.warning(f"{type(e).__name__}, retry dalam {wait}s "
                          f"({attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
            else:
                raise
    raise last_exception


class Agent:
    def __init__(self, verbose: bool = True, enable_logging: bool = True):
        self.verbose = verbose
        self.system_prompt = build_system_prompt()
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.logger = ConversationLogger() if enable_logging else None
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        if self.verbose:
            if web_available():
                ui.dim("🌐 Web search: aktif (Tavily)")
            else:
                ui.dim("🌐 Web search: nonaktif (set TAVILY_API_KEY untuk aktifkan)")
            if self.logger:
                ui.dim(f"📁 Log: {self.logger.get_log_path()}")

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
                error_msg = (f"API gagal setelah {MAX_RETRIES} retry: "
                            f"{type(e).__name__}: {e}")
                if self.verbose:
                    ui.error(error_msg)
                if self.logger:
                    self.logger.log_error("api_failure", error_msg)
                return f"⚠️ {error_msg}. Coba lagi nanti."

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
                            "error": f"Argumen tool tidak valid JSON: {e}"
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

        msg = "⚠️ Melebihi batas iterasi. Coba pertanyaan yang lebih spesifik."
        if self.logger:
            self.logger.log_error("max_iterations", msg)
        return msg

    def reset(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.logger = ConversationLogger() if self.logger else None