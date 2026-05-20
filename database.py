"""
Module untuk operasi database SQLite — Battery Research domain.

Sebagian besar logic SAMA dengan versi e-commerce.
Yang berubah hanya DB_PATH dan beberapa hint message.
"""
import re
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path("data/battery.db")

FORBIDDEN_KEYWORDS = [
    "insert", "update", "delete", "drop", "alter", "truncate",
    "create", "replace", "attach", "detach", "pragma", "vacuum"
]


def get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database tidak ditemukan di {DB_PATH}. "
            "Jalankan dulu: python load_battery_data.py"
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_schema() -> str:
    """Schema lengkap + sample rows untuk system prompt."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]

    schema_lines = []
    for table in tables:
        schema_lines.append(f"\nTABLE: {table}")
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        for col in columns:
            pk_marker = " [PRIMARY KEY]" if col[5] else ""
            notnull = " NOT NULL" if col[3] else ""
            schema_lines.append(f"  - {col[1]}: {col[2]}{notnull}{pk_marker}")

        cursor.execute(f"SELECT * FROM {table} LIMIT 3")
        sample_rows = cursor.fetchall()
        if sample_rows:
            schema_lines.append(f"  Sample rows:")
            for row in sample_rows:
                schema_lines.append(f"    {dict(row)}")

    conn.close()
    return "\n".join(schema_lines)


def validate_query(sql: str) -> tuple[bool, str | None]:
    sql_clean = sql.strip()
    if not sql_clean:
        return False, "Query kosong"

    sql_lower = sql_clean.lower()
    if not (sql_lower.startswith("select") or sql_lower.startswith("with")):
        return False, "Query harus dimulai dengan SELECT atau WITH. Tool ini read-only."

    for keyword in FORBIDDEN_KEYWORDS:
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_lower):
            return False, f"Keyword '{keyword.upper()}' tidak diizinkan."

    sql_no_strings = re.sub(r"'[^']*'", "''", sql_clean)
    sql_no_strings = re.sub(r'"[^"]*"', '""', sql_no_strings)
    sql_no_strings = sql_no_strings.rstrip(";").rstrip()
    if ";" in sql_no_strings:
        return False, "Multiple statements tidak diizinkan."

    return True, None


def execute_query(sql: str) -> dict[str, Any]:
    base = {
        "success": False,
        "rows": None,
        "row_count": 0,
        "columns": None,
        "error": None,
        "hint": None,
        "sql_executed": sql,
    }

    is_valid, validation_error = validate_query(sql)
    if not is_valid:
        return {**base, "error": validation_error}

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        return {
            **base,
            "success": True,
            "rows": [dict(row) for row in rows],
            "row_count": len(rows),
            "columns": columns,
        }
    except sqlite3.Error as e:
        return {
            **base,
            "error": f"SQL Error: {e}",
            "hint": _generate_error_hint(str(e)),
        }
    finally:
        conn.close()


def _generate_error_hint(error_msg: str) -> str:
    error_lower = error_msg.lower()

    if "no such table" in error_lower:
        return "Hanya ada satu tabel: battery_cycles. Lihat schema."

    if "no such column" in error_lower:
        return ("Kolom salah. Yang tersedia: battery_id, cycle, charge_current, "
                "charge_voltage, charge_temperature, discharge_current, "
                "discharge_voltage, discharge_temperature, capacity, soh, rul.")

    if "syntax error" in error_lower:
        return ("Syntax SQL tidak valid. Ingat: SQLite, bukan PostgreSQL. "
                "Untuk window functions pakai ROW_NUMBER() OVER (...).")

    if "ambiguous column" in error_lower:
        return "Kolom ambigu. Pakai alias tabel untuk disambiguate."

    return "Periksa query SQL, lalu coba lagi dengan perbaikan."


def get_distinct_values(table: str, column: str, limit: int = 20) -> dict[str, Any]:
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
        return {"success": False, "error": f"Nama tabel tidak valid: '{table}'"}
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', column):
        return {"success": False, "error": f"Nama kolom tidak valid: '{column}'"}

    limit = max(1, min(limit, 100))

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        cols_info = cursor.fetchall()
        if not cols_info:
            return {"success": False, "error": f"Tabel '{table}' tidak ditemukan"}

        col_names = [c[1] for c in cols_info]
        if column not in col_names:
            return {
                "success": False,
                "error": f"Kolom '{column}' tidak ada. Kolom: {col_names}"
            }

        cursor.execute(
            f"SELECT DISTINCT {column} FROM {table} "
            f"WHERE {column} IS NOT NULL "
            f"ORDER BY {column} LIMIT ?",
            (limit,)
        )
        values = [row[0] for row in cursor.fetchall()]

        cursor.execute(f"SELECT COUNT(DISTINCT {column}) FROM {table}")
        total_distinct = cursor.fetchone()[0]

        return {
            "success": True,
            "table": table,
            "column": column,
            "distinct_values": values,
            "total_distinct": total_distinct,
            "showing": len(values),
        }
    except sqlite3.Error as e:
        return {"success": False, "error": f"SQL Error: {e}"}
    finally:
        conn.close()