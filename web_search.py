"""
Web search module menggunakan Tavily API.

Tavily dirancang khusus untuk LLM agents - hasilnya sudah clean & summarized,
bukan HTML mentah. Free tier: 1000 searches/bulan.

Setup:
1. Signup di https://tavily.com (gratis)
2. Copy API key
3. Tambah ke .env: TAVILY_API_KEY=tvly-xxxxx
"""
import os
from typing import Any

from tavily import TavilyClient
from dotenv import load_dotenv

load_dotenv()

# Inisialisasi lazy - client baru dibuat saat pertama dipakai
_client: TavilyClient | None = None


def _get_client() -> TavilyClient | None:
    """Lazy init Tavily client. Return None kalau API key tidak ada."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None

    _client = TavilyClient(api_key=api_key)
    return _client


def search_web(query: str, max_results: int = 5) -> dict[str, Any]:
    """
    Cari informasi di internet menggunakan Tavily.

    Args:
        query: query pencarian
        max_results: jumlah hasil (default 5, max 10)

    Returns:
        {
            "success": bool,
            "query": str,
            "answer": str | None,       # ringkasan AI dari Tavily
            "results": list[dict],      # daftar sumber
            "error": str | None
        }
    """
    base = {
        "success": False,
        "query": query,
        "answer": None,
        "results": [],
        "error": None,
    }

    client = _get_client()
    if client is None:
        return {
            **base,
            "error": (
                "Web search tidak tersedia: TAVILY_API_KEY tidak ditemukan di .env. "
                "Signup gratis di https://tavily.com untuk dapat API key."
            )
        }

    max_results = max(1, min(max_results, 10))

    try:
        # include_answer=True minta Tavily generate ringkasan jawaban
        response = client.search(
            query=query,
            max_results=max_results,
            include_answer=True,
            search_depth="basic",  # "basic" lebih cepat & murah dari "advanced"
        )

        # Extract hasil yang relevan
        results = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                # Potong content biar hemat token (LLM nggak butuh full page)
                "content": item.get("content", "")[:500],
                "score": round(item.get("score", 0), 3),
            })

        return {
            **base,
            "success": True,
            "answer": response.get("answer"),
            "results": results,
        }

    except Exception as e:
        return {
            **base,
            "error": f"Web search error: {type(e).__name__}: {e}"
        }


def is_available() -> bool:
    """Cek apakah web search bisa dipakai (API key ada)."""
    return _get_client() is not None


if __name__ == "__main__":
    print("Testing web search...")
    if not is_available():
        print("❌ TAVILY_API_KEY tidak ditemukan. Set dulu di .env")
    else:
        result = search_web("typical Li-ion battery degradation rate per cycle", max_results=3)
        if result["success"]:
            print(f"✅ Search berhasil!")
            print(f"\n📝 Answer: {result['answer']}")
            print(f"\n🔗 Sources ({len(result['results'])}):")
            for r in result["results"]:
                print(f"  • {r['title']} ({r['url']})")
        else:
            print(f"❌ Error: {result['error']}")