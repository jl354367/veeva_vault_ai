"""
Help content resolver for the Help Assistant.

Priority order:
  1. Local TF-IDF search  (fast, no network, from scraped data)
  2. Live web fetch        (fallback if local index not ready)
  3. Built-in KB           (handled in claude_service._kb_lookup)

Local data is built by services/scraper.py and searched via services/help_search.py.
"""

import re
import asyncio
import warnings
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from services.help_search import get_engine

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ── Config ─────────────────────────────────────────────────────────────────────

_SUBDOMAINS = [
    "platform", "quality", "regulatory",
    "safety", "clinical", "medical", "commercial",
]
_BASE    = "https://{sub}.veevavault.help/en/gr"
_TIMEOUT = httpx.Timeout(connect=8.0, read=15.0, write=3.0, pool=3.0)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_index_cache: dict[str, list[dict]] = {}


# ── Helpers shared with live fetch ────────────────────────────────────────────

def _keywords(text: str) -> list[str]:
    stops = {
        "what","is","are","the","a","an","in","of","to","how","do","does","can",
        "i","me","for","and","or","with","this","that","which","was","be","it",
        "its","on","at","by","from","as","tell","show","explain","about","all",
        "get","give","find","list","display","check","use","using",
    }
    return [w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in stops]


def _score_title(title: str, kws: list[str], query: str) -> int:
    low, score = title.lower(), 0
    if query.lower().strip() in low: score += 30
    if kws and all(k in low for k in kws): score += 15
    hits = 0
    for k in kws:
        if k in low:            score += 4; hits += 1
        elif len(k) > 4 and k[:-1] in low: score += 2; hits += 1
    if kws and hits >= max(1, len(kws) - 1): score += 5
    return score


def _page_url(sub: str, raw: str) -> str:
    raw = str(raw).strip()
    if raw.startswith("http"):    return raw
    if raw.startswith("/"):       return f"https://{sub}.veevavault.help{raw}"
    if "/" in raw or re.search(r"\.\w{2,4}$", raw):
        return urljoin(_BASE.format(sub=sub) + "/", raw)
    url = _BASE.format(sub=sub) + "/" + raw
    if not re.search(r"\.\w{2,4}$", url):
        url = url.rstrip("/") + "/"
    return url


def _extract_content(html: str, max_chars: int = 5000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script","style","nav","footer","header",
                      "aside","form","button","figure","iframe","noscript"]):
        tag.decompose()
    for tag in soup.find_all(True, class_=re.compile(
            r"breadcrumb|toc|sidebar|menu|navigation|toolbar|banner|feedback", re.I)):
        tag.decompose()
    main = (
        soup.find("div", class_=re.compile(r"\btopic\b|\bcontent\b|\barticle\b", re.I))
        or soup.find("main") or soup.find("article") or soup.find("body")
    )
    if not main: return ""
    parts = [
        elem.get_text(separator=" ", strip=True)
        for elem in main.find_all(["h1","h2","h3","h4","p","li","td","dt","dd"])
        if len(elem.get_text(strip=True)) > 20
    ]
    text = " ".join(parts) if parts else main.get_text(separator=" ", strip=True)
    return re.sub(r"\s{2,}", " ", text).strip()[:max_chars]


# ── Path 1: Local TF-IDF search ───────────────────────────────────────────────

def _local_search(query: str) -> list[str]:
    """
    Search the scraped local data store using TF-IDF.
    Returns chunks in the same format as fetch_vault_help.
    """
    engine = get_engine()
    if not engine.ready:
        return []

    results = engine.search(query, top_k=5)
    chunks  = []
    for doc in results:
        chunk = f"[Source: {doc['url']}]\n{doc['title']}\n\n{doc['content']}"
        chunks.append(chunk)
    return chunks


# ── Path 2: Live web fetch (fallback) ─────────────────────────────────────────

async def _load_index(sub: str, client: httpx.AsyncClient) -> list[dict]:
    if sub in _index_cache and _index_cache[sub]:
        return _index_cache[sub]
    url = _BASE.format(sub=sub) + "/search.json"
    try:
        r = await client.get(url, headers=_HEADERS)
        if r.status_code == 200:
            data    = r.json()
            entries = [d for d in data if d.get("title") and d.get("url")]
            if entries:
                _index_cache[sub] = entries
                return entries
    except Exception:
        pass
    return []


async def _live_fetch(query: str) -> list[str]:
    """Live fetch from veevavault.help — used when local index is not ready."""
    kws = _keywords(query)
    if not kws:
        return []

    async with httpx.AsyncClient(
        timeout=_TIMEOUT, follow_redirects=True, verify=False
    ) as client:
        indexes = await asyncio.gather(
            *[_load_index(sub, client) for sub in _SUBDOMAINS],
            return_exceptions=True,
        )

        candidates: list[tuple[int, str, str, str]] = []
        for sub, index in zip(_SUBDOMAINS, indexes):
            if isinstance(index, Exception) or not index:
                continue
            bonus = 3 if sub == "platform" else 0
            for entry in index:
                sc = _score_title(entry["title"], kws, query) + bonus
                if sc > 0:
                    candidates.append((sc, sub, str(entry["url"]), entry["title"]))

        candidates.sort(key=lambda x: x[0], reverse=True)
        seen: set[str] = set()
        top:  list[tuple[int, str, str, str]] = []
        for sc, sub, raw_url, title in candidates:
            clean = re.sub(r"&amp;", "&", title).strip()
            if clean not in seen:
                seen.add(clean)
                top.append((sc, sub, raw_url, clean))
            if len(top) >= 6:
                break

        async def fetch_one(sub: str, raw_url: str, title: str) -> str:
            url = _page_url(sub, raw_url)
            try:
                r = await client.get(url, headers=_HEADERS)
                if r.status_code == 200:
                    text = _extract_content(r.text)
                    if len(text) > 100:
                        return f"[Source: {url}]\n{title}\n\n{text}"
            except Exception:
                pass
            return ""

        results = await asyncio.gather(
            *[fetch_one(sub, raw_url, title) for _, sub, raw_url, title in top],
            return_exceptions=True,
        )

    return [r for r in results if isinstance(r, str) and r]


# ── Public API ────────────────────────────────────────────────────────────────

async def fetch_vault_help(query: str) -> list[str]:
    """
    Return relevant text chunks for the given query.

    Step 1: Search local scraped data (TF-IDF, instant)
    Step 2: If local index empty, fall back to live web fetch
    """
    # Try local first — fast, no network needed
    chunks = _local_search(query)
    if chunks:
        return chunks

    # Fallback: live fetch (requires network + backend restart for SSL fix)
    return await _live_fetch(query)
