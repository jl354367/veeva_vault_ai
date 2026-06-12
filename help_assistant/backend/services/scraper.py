"""
Veeva Vault Help Site Scraper
Crawls all pages from veevavault.help subdomains and saves clean text to a local JSON store.

Run once on startup (if data is stale) or via POST /api/help/refresh.
Data file: backend/data/vault_help.json
"""

import re
import json
import asyncio
import warnings
import os
from datetime import datetime, timezone
from urllib.parse import urljoin
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ── Config ─────────────────────────────────────────────────────────────────────

_SUBDOMAINS = [
    "platform",
    "quality",
    "regulatory",
    "safety",
    "clinical",
    "medical",
    "commercial",
]

_BASE     = "https://{sub}.veevavault.help/en/gr"
_TIMEOUT  = httpx.Timeout(connect=8.0, read=20.0, write=3.0, pool=3.0)
_HEADERS  = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DATA_FILE  = Path(__file__).parent.parent / "data" / "vault_help.json"
MAX_PAGES  = 300          # cap per subdomain to avoid very long scrapes
STALE_DAYS = 7            # re-scrape if data is older than this


# ── URL helpers ────────────────────────────────────────────────────────────────

def _page_url(sub: str, raw: str) -> str:
    raw = str(raw).strip()
    if raw.startswith("http"):
        return raw
    if raw.startswith("/"):
        return f"https://{sub}.veevavault.help{raw}"
    if "/" in raw or re.search(r"\.\w{2,4}$", raw):
        return urljoin(_BASE.format(sub=sub) + "/", raw)
    url = _BASE.format(sub=sub) + "/" + raw
    if not re.search(r"\.\w{2,4}$", url):
        url = url.rstrip("/") + "/"
    return url


# ── Content extraction ─────────────────────────────────────────────────────────

def _extract(html: str, max_chars: int = 4000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header",
                      "aside", "form", "button", "figure", "iframe", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(True, class_=re.compile(
            r"breadcrumb|toc|sidebar|menu|navigation|toolbar|banner|feedback", re.I)):
        tag.decompose()
    main = (
        soup.find("div", class_=re.compile(r"\btopic\b|\bcontent\b|\barticle\b", re.I))
        or soup.find("main")
        or soup.find("article")
        or soup.find("body")
    )
    if not main:
        return ""
    parts = [
        elem.get_text(separator=" ", strip=True)
        for elem in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "dt", "dd"])
        if len(elem.get_text(strip=True)) > 20
    ]
    text = " ".join(parts) if parts else main.get_text(separator=" ", strip=True)
    return re.sub(r"\s{2,}", " ", text).strip()[:max_chars]


# ── Core scraper ───────────────────────────────────────────────────────────────

async def _scrape_subdomain(
    sub: str,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    """Fetch search.json index then scrape each page (capped at MAX_PAGES)."""
    index_url = _BASE.format(sub=sub) + "/search.json"
    try:
        r = await client.get(index_url, headers=_HEADERS)
        if r.status_code != 200:
            return []
        data    = r.json()
        entries = [d for d in data if d.get("title") and d.get("url")]
    except Exception as e:
        print(f"[Scraper] {sub}: index load failed — {e}")
        return []

    print(f"[Scraper] {sub}: {len(entries)} pages found")
    entries = entries[:MAX_PAGES]

    async def fetch_page(entry: dict) -> dict | None:
        url = _page_url(sub, str(entry["url"]))
        async with semaphore:
            try:
                r = await client.get(url, headers=_HEADERS)
                if r.status_code != 200:
                    return None
                content = _extract(r.text)
                if len(content) < 60:
                    return None
                return {
                    "subdomain": sub,
                    "title":     re.sub(r"&amp;", "&", entry["title"]).strip(),
                    "url":       url,
                    "content":   content,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                }
            except Exception:
                return None

    tasks   = [fetch_page(e) for e in entries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    docs    = [r for r in results if isinstance(r, dict)]
    print(f"[Scraper] {sub}: {len(docs)} pages scraped successfully")
    return docs


async def run_scrape(subdomains: list[str] | None = None) -> int:
    """
    Scrape all (or specified) subdomains and save to DATA_FILE.
    Returns total number of documents saved.
    """
    subs = subdomains or _SUBDOMAINS
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Semaphore limits concurrent page fetches to avoid overloading the server
    semaphore = asyncio.Semaphore(5)

    all_docs: list[dict] = []
    async with httpx.AsyncClient(
        timeout=_TIMEOUT, follow_redirects=True, verify=False
    ) as client:
        for sub in subs:
            docs = await _scrape_subdomain(sub, client, semaphore)
            all_docs.extend(docs)

    DATA_FILE.write_text(
        json.dumps(all_docs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[Scraper] Saved {len(all_docs)} documents to {DATA_FILE}")
    return len(all_docs)


# ── Status helpers ─────────────────────────────────────────────────────────────

def data_exists() -> bool:
    return DATA_FILE.exists() and DATA_FILE.stat().st_size > 1000


def data_is_stale() -> bool:
    if not data_exists():
        return True
    try:
        docs = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not docs:
            return True
        ts  = docs[0].get("scraped_at", "")
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts)).days
        return age >= STALE_DAYS
    except Exception:
        return True


def load_docs() -> list[dict]:
    if not data_exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
