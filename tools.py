import json
from database import execute_query, get_distinct_values


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "Execute a SELECT SQL query against the e-commerce database. "
                "Only SELECT/WITH is allowed (read-only). "
                "If the query errors, the response will include a 'hint' field "
                "to help you fix the query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "The SQL query to execute. SQLite syntax. "
                            "Example: SELECT name, price FROM products "
                            "WHERE category = 'Fashion' LIMIT 10"
                        )
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_distinct_values",
            "description": (
                "Get unique values from a categorical column. "
                "Use this BEFORE filtering with WHERE when you are unsure "
                "what values exist in the column. "
                "Example use cases: check what statuses exist in orders, "
                "or which product categories are valid."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Table name (customers, products, orders, order_items)"
                    },
                    "column": {
                        "type": "string",
                        "description": "Column name to inspect"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max values to return (default 20, max 100)"
                    }
                },
                "required": ["table", "column"]
            }
        }
    }
]


def _execute_sql_tool(sql: str) -> str:
    result = execute_query(sql)

    if result["success"] and result["row_count"] > 50:
        result = {
            **result,
            "rows": result["rows"][:50],
            "note": (
                f"Total {result['row_count']} rows, only the first 50 "
                f"are shown. Consider adding LIMIT or aggregation "
                f"(COUNT/SUM/AVG) for large datasets."
            )
        }

    return json.dumps(result, ensure_ascii=False, default=str)


def _get_distinct_values_tool(table: str, column: str, limit: int = 20) -> str:
    result = get_distinct_values(table, column, limit)
    return json.dumps(result, ensure_ascii=False, default=str)


TOOL_FUNCTIONS = {
    "execute_sql": _execute_sql_tool,
    "get_distinct_values": _get_distinct_values_tool,
}


def call_tool(tool_name: str, arguments: dict) -> str:
    if tool_name not in TOOL_FUNCTIONS:
        return json.dumps({
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        })

    try:
        func = TOOL_FUNCTIONS[tool_name]
        return func(**arguments)
    except TypeError as e:
        return json.dumps({
            "success": False,
            "error": f"Invalid arguments for tool {tool_name}: {e}"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Error in tool {tool_name}: {type(e).__name__}: {e}"
        })
