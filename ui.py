"""
UI module - centralisasi presentation logic.

Pakai library `rich` untuk:
- Pretty tables untuk query results
- Syntax-highlighted SQL
- Spinner / progress indicator
- Markdown rendering
- Color-coded panels

Filosofi: agent.py focus ke logic, ui.py focus ke tampilan.
Pisahkan concerns supaya code lebih maintainable.
"""
import json
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.align import Align


# Single console instance dipakai di seluruh app
console = Console()


# ============================================================
# WELCOME SCREEN
# ============================================================
def print_welcome():
    """Banner aplikasi yang eye-catching."""
    title = Text("🤖 BI AGENT", style="bold cyan", justify="center")
    subtitle = Text(
        "Database E-commerce Assistant",
        style="dim",
        justify="center"
    )

    welcome_panel = Panel(
        Align.center(Text.assemble(title, "\n", subtitle)),
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(welcome_panel)

    help_text = Text()
    help_text.append("💡 Contoh pertanyaan:\n", style="bold yellow")
    help_text.append("   • Berapa total revenue bulan April 2026?\n", style="dim")
    help_text.append("   • Produk apa yang paling laris di kategori Fashion?\n", style="dim")
    help_text.append("   • Siapa 5 customer dengan pembelian terbesar?\n", style="dim")
    help_text.append("\n⚙️  Perintah:\n", style="bold yellow")
    help_text.append("   /reset   ", style="cyan")
    help_text.append("- mulai conversation baru\n", style="dim")
    help_text.append("   /stats   ", style="cyan")
    help_text.append("- lihat token usage\n", style="dim")
    help_text.append("   /logs    ", style="cyan")
    help_text.append("- tampilkan path file log\n", style="dim")
    help_text.append("   /quit    ", style="cyan")
    help_text.append("- keluar", style="dim")

    console.print(help_text)
    console.print()


# ============================================================
# USER INPUT PROMPT
# ============================================================
def prompt_user() -> str:
    """Tampilkan prompt input yang konsisten."""
    console.print()
    return console.input("[bold green]💬 Kamu:[/bold green] ").strip()


# ============================================================
# ITERATION INDICATOR
# ============================================================
def print_iteration(iteration: int):
    """Print header untuk iterasi agent."""
    console.print(
        f"\n[dim]─── Iterasi {iteration} ───[/dim]"
    )


# ============================================================
# TOOL CALL DISPLAY
# ============================================================
def print_tool_call(tool_name: str, arguments: dict):
    """Tampilkan tool yang sedang dipanggil agent."""
    if tool_name == "execute_sql":
        sql = arguments.get("sql", "")
        # Syntax-highlight SQL pakai rich
        syntax = Syntax(
            sql,
            "sql",
            theme="monokai",
            line_numbers=False,
            word_wrap=True,
            background_color="default",
        )
        panel = Panel(
            syntax,
            title=f"[bold]🔧 {tool_name}[/bold]",
            border_style="blue",
            padding=(0, 1),
        )
        console.print(panel)

    elif tool_name == "get_distinct_values":
        table = arguments.get("table", "")
        column = arguments.get("column", "")
        console.print(
            f"[blue]🔍 [bold]{tool_name}[/bold][/blue] "
            f"→ eksplorasi [yellow]{table}.{column}[/yellow]"
        )

    elif tool_name == "web_search":
        query = arguments.get("query", "")
        console.print(
            f"[cyan]🌐 [bold]{tool_name}[/bold][/cyan] "
            f"→ [yellow]\"{query}\"[/yellow]"
        )

    else:
        # Generic display untuk tool lain di masa depan
        args_str = ", ".join(f"{k}={v}" for k, v in arguments.items())
        console.print(f"[blue]🔧 {tool_name}({args_str})[/blue]")


# ============================================================
# TOOL RESULT DISPLAY
# ============================================================
def print_tool_result(result_json: str):
    """Parse dan tampilkan hasil tool dengan pretty formatting."""
    try:
        result = json.loads(result_json)
    except json.JSONDecodeError:
        console.print(f"[red]❌ Result tidak valid JSON[/red]")
        return

    if not result.get("success"):
        # Error - tampilkan error + hint
        error_text = Text()
        error_text.append("❌ Error: ", style="bold red")
        error_text.append(result.get("error", "unknown"), style="red")

        if result.get("hint"):
            error_text.append("\n💡 Hint: ", style="bold yellow")
            error_text.append(result["hint"], style="yellow")

        console.print(Panel(error_text, border_style="red", padding=(0, 1)))
        return

    # Success - kasus get_distinct_values
    if "distinct_values" in result:
        values = result["distinct_values"]
        total = result.get("total_distinct", len(values))
        console.print(
            f"[green]✅[/green] Found [bold]{total}[/bold] distinct values: "
            f"[cyan]{values}[/cyan]"
        )
        return

    # Success - kasus web_search (punya field 'results' & 'answer')
    if "results" in result and "query" in result:
        answer = result.get("answer")
        sources = result.get("results", [])

        web_text = Text()
        if answer:
            web_text.append("🌐 Web summary:\n", style="bold cyan")
            web_text.append(answer[:600], style="default")
            web_text.append("\n\n")
        web_text.append(f"🔗 Sources ({len(sources)}):\n", style="bold")
        for src in sources[:5]:
            web_text.append(f"  • {src.get('title', 'untitled')}\n", style="cyan")
            web_text.append(f"    {src.get('url', '')}\n", style="dim")

        console.print(Panel(
            web_text,
            title="[bold cyan]🌐 web_search[/bold cyan]",
            border_style="cyan",
            padding=(0, 1),
        ))
        return

    # Success - kasus execute_sql
    rows = result.get("rows", [])
    row_count = result.get("row_count", 0)

    if row_count == 0:
        console.print("[green]✅[/green] [dim](no rows returned)[/dim]")
        return

    # Render tabel
    table = _build_results_table(rows, result.get("columns", []))
    console.print(table)

    # Info tambahan
    info_text = f"[green]✅[/green] {row_count} row(s)"
    if result.get("note"):
        info_text += f" — [yellow]{result['note']}[/yellow]"
    console.print(info_text)


def _build_results_table(rows: list[dict], columns: list[str]) -> Table:
    """Build pretty table dari list of dicts."""
    table = Table(
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
        padding=(0, 1),
    )

    # Tentukan kolom dari first row kalau columns kosong
    if not columns and rows:
        columns = list(rows[0].keys())

    for col in columns:
        # Heuristik: kolom yang namanya mengandung "id", "count",
        # "total", "amount", "price", "qty" probably numerik → right align
        is_numeric = any(
            keyword in col.lower()
            for keyword in ["id", "count", "total", "amount",
                            "price", "qty", "quantity", "sum", "avg"]
        )
        justify = "right" if is_numeric else "left"
        table.add_column(col, justify=justify, overflow="fold")

    # Limit display ke 20 baris pertama biar tidak banjir terminal
    # (LLM masih dapat 50 rows untuk reasoning, tapi user lihat 20)
    DISPLAY_LIMIT = 20
    for row in rows[:DISPLAY_LIMIT]:
        formatted_values = [_format_cell_value(row.get(col)) for col in columns]
        table.add_row(*formatted_values)

    if len(rows) > DISPLAY_LIMIT:
        ellipsis = ["..."] * len(columns)
        table.add_row(*ellipsis, style="dim")
        # Footer note akan dicetak terpisah

    return table


def _format_cell_value(value: Any) -> str:
    """Format value untuk display di tabel."""
    if value is None:
        return "[dim]NULL[/dim]"

    # Format angka besar dengan separator
    if isinstance(value, int) and abs(value) >= 1000:
        return f"{value:,}".replace(",", ".")

    if isinstance(value, float):
        if abs(value) >= 1000:
            return f"{value:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
        return f"{value:.2f}"

    # String panjang dipotong untuk tampilan
    s = str(value)
    if len(s) > 60:
        return s[:57] + "..."
    return s


# ============================================================
# ASSISTANT FINAL ANSWER
# ============================================================
def print_assistant_answer(content: str):
    """Render jawaban final agent sebagai markdown."""
    console.print()
    # Render sebagai markdown supaya bold/list/code blocks tampil cantik
    md = Markdown(content)
    panel = Panel(
        md,
        title="[bold cyan]🤖 Agent[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


# ============================================================
# SPINNER / LOADING INDICATOR
# ============================================================
def thinking_spinner(text: str = "Thinking..."):
    """
    Context manager yang menampilkan spinner saat agent processing.

    Usage:
        with thinking_spinner("Generating SQL..."):
            response = api_call()
    """
    return console.status(f"[cyan]{text}[/cyan]", spinner="dots")


# ============================================================
# STATS DISPLAY
# ============================================================
def print_stats(stats: dict):
    """Tampilkan token usage stats dalam tabel kecil."""
    table = Table(
        title="📊 Session Stats",
        show_header=True,
        header_style="bold",
        border_style="dim",
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="yellow")

    table.add_row("Session ID", str(stats.get("session_id") or "n/a"))
    table.add_row("Input tokens", f"{stats['total_input_tokens']:,}")
    table.add_row("Output tokens", f"{stats['total_output_tokens']:,}")
    table.add_row("Total tokens", f"{stats['total_tokens']:,}")
    table.add_row("Messages", f"{stats['messages_in_history']:,}")

    console.print(table)


# ============================================================
# MESSAGES (info, success, error, warning)
# ============================================================
def info(message: str):
    console.print(f"[cyan]ℹ️  {message}[/cyan]")


def success(message: str):
    console.print(f"[green]✅ {message}[/green]")


def warning(message: str):
    console.print(f"[yellow]⚠️  {message}[/yellow]")


def error(message: str):
    console.print(f"[red]❌ {message}[/red]")


def dim(message: str):
    console.print(f"[dim]{message}[/dim]")


# ============================================================
# DEMO MODE - untuk test rich output tanpa LLM
# ============================================================
if __name__ == "__main__":
    print_welcome()

    info("Demo mode - test semua komponen UI")
    console.print()

    print_iteration(1)
    print_tool_call("execute_sql", {
        "sql": """SELECT p.name, p.category, SUM(oi.quantity) as total_sold
FROM order_items oi
JOIN products p ON p.product_id = oi.product_id
JOIN orders o ON o.order_id = oi.order_id
WHERE o.status = 'completed'
GROUP BY p.product_id
ORDER BY total_sold DESC
LIMIT 5"""
    })

    # Simulasi result
    fake_result = json.dumps({
        "success": True,
        "row_count": 5,
        "columns": ["name", "category", "total_sold"],
        "rows": [
            {"name": "Kabel Charger Type-C", "category": "Elektronik", "total_sold": 245},
            {"name": "Masker Wajah Sheet Mask", "category": "Kecantikan", "total_sold": 198},
            {"name": "Keripik Singkong Original", "category": "Makanan", "total_sold": 187},
            {"name": "Hijab Pashmina Voal", "category": "Fashion", "total_sold": 156},
            {"name": "Earphone Bluetooth TWS", "category": "Elektronik", "total_sold": 134},
        ]
    })
    print_tool_result(fake_result)

    print_iteration(2)
    print_tool_call("get_distinct_values", {"table": "orders", "column": "status"})
    fake_distinct = json.dumps({
        "success": True,
        "distinct_values": ["cancelled", "completed", "pending", "shipped"],
        "total_distinct": 4,
    })
    print_tool_result(fake_distinct)

    # Simulasi error
    print_iteration(3)
    print_tool_call("execute_sql", {"sql": "SELECT * FROM customer LIMIT 1"})
    fake_error = json.dumps({
        "success": False,
        "error": "SQL Error: no such table: customer",
        "hint": "Nama tabel salah. Tabel yang tersedia: customers, products, orders, order_items."
    })
    print_tool_result(fake_error)

    # Final answer
    print_assistant_answer(
        "**Top 5 produk terlaris** (status completed):\n\n"
        "1. Kabel Charger Type-C — 245 terjual\n"
        "2. Masker Wajah Sheet Mask — 198 terjual\n"
        "3. Keripik Singkong Original — 187 terjual\n\n"
        "Insight: Produk-produk kategori `Elektronik` dan `Kecantikan` "
        "mendominasi top 5, dengan **fast-moving consumer goods** "
        "(harga rendah, volume tinggi) sebagai pola yang paling jelas."
    )

    print_stats({
        "session_id": "abc123",
        "total_input_tokens": 4521,
        "total_output_tokens": 312,
        "total_tokens": 4833,
        "messages_in_history": 7,
    })