"""
Tool definitions untuk agent — Battery Research domain + Web Search.

UPDATED: tambah tool web_search (Tavily) untuk info yang tidak ada di database.
"""
import json
from database import execute_query, get_distinct_values
from web_search import search_web, is_available as web_available


# ============================================================
# SCHEMA - format yang dikirim ke LLM
# ============================================================
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "Eksekusi query SQL SELECT terhadap database battery degradation. "
                "GUNAKAN INI DULU untuk pertanyaan apapun tentang data battery "
                "(SOH, capacity, cycle, RUL, temperature, dll). "
                "Hanya SELECT/WITH yang diizinkan. "
                "Kalau error, response punya field 'hint' untuk memperbaiki query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Query SQL SELECT. SQLite syntax."
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
                "Ambil nilai unik dari sebuah kolom. Pakai SEBELUM filter "
                "kalau belum yakin value apa yang ada di kolom."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "Nama tabel"},
                    "column": {"type": "string", "description": "Nama kolom"},
                    "limit": {"type": "integer", "description": "Max values (default 20)"}
                },
                "required": ["table", "column"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Cari informasi di internet. GUNAKAN INI HANYA KALAU: "
                "(a) data yang ditanya TIDAK ADA di database (sudah dicek via execute_sql), ATAU "
                "(b) user minta konteks eksternal seperti benchmark industri, "
                "definisi konsep, nilai 'normal/typical', perbandingan dengan standar, "
                "atau informasi yang memang berada di luar dataset battery kita. "
                "JANGAN pakai web_search untuk data yang ada di database. "
                "Selalu coba database dulu untuk pertanyaan tentang data battery kita."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Query pencarian dalam Bahasa Inggris (hasil lebih baik). "
                            "Contoh: 'typical Li-ion battery capacity fade rate per cycle'"
                        )
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Jumlah hasil (default 5, max 10)"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# ============================================================
# IMPLEMENTASI
# ============================================================
def _execute_sql_tool(sql: str) -> str:
    result = execute_query(sql)
    if result["success"] and result["row_count"] > 50:
        result = {
            **result,
            "rows": result["rows"][:50],
            "note": (
                f"Total {result['row_count']} rows, hanya 50 pertama ditampilkan. "
                f"Pertimbangkan agregasi (AVG/MIN/MAX) untuk dataset besar."
            )
        }
    return json.dumps(result, ensure_ascii=False, default=str)


def _get_distinct_values_tool(table: str, column: str, limit: int = 20) -> str:
    result = get_distinct_values(table, column, limit)
    return json.dumps(result, ensure_ascii=False, default=str)


def _web_search_tool(query: str, max_results: int = 5) -> str:
    result = search_web(query, max_results)
    return json.dumps(result, ensure_ascii=False, default=str)


TOOL_FUNCTIONS = {
    "execute_sql": _execute_sql_tool,
    "get_distinct_values": _get_distinct_values_tool,
    "web_search": _web_search_tool,
}


def call_tool(tool_name: str, arguments: dict) -> str:
    if tool_name not in TOOL_FUNCTIONS:
        return json.dumps({
            "success": False,
            "error": f"Tool tidak dikenal: {tool_name}"
        })

    try:
        func = TOOL_FUNCTIONS[tool_name]
        return func(**arguments)
    except TypeError as e:
        return json.dumps({
            "success": False,
            "error": f"Argumen tool {tool_name} tidak valid: {e}"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Error tool {tool_name}: {type(e).__name__}: {e}"
        })