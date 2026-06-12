"""
AI service — demo mode (no API key required).
Help mode  : keyword-based extraction from live veevavault.help content.
Config mode: intent-driven direct answers from uploaded DataFrames.
"""

import re
from services.vault_kb import VAULT_KB, KB_ALIASES


# ══════════════════════════════════════════════════════════════════════════
# SHARED UTILITIES
# ══════════════════════════════════════════════════════════════════════════

def _keywords(text: str) -> list[str]:
    stopwords = {
        "what", "is", "are", "the", "a", "an", "in", "of", "to", "how",
        "do", "does", "can", "i", "me", "for", "and", "or", "with",
        "this", "that", "which", "was", "be", "it", "its", "on", "at",
        "by", "from", "as", "tell", "show", "explain", "about", "all",
        "get", "give", "find", "list", "display", "check",
    }
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return [w for w in words if w not in stopwords]


def _score(text: str, kws: list[str]) -> int:
    low = text.lower()
    s = 0
    for k in kws:
        if k in low:                        s += 2
        elif len(k) > 4 and k[:-1] in low: s += 1
        elif len(k) > 5 and k[:-2] in low: s += 1
    return s


# ══════════════════════════════════════════════════════════════════════════
# HELP MODE — keyword-scored content from veevavault.help
# ══════════════════════════════════════════════════════════════════════════

def _phrase_in(text: str, phrase: str) -> bool:
    """Check if all words of a phrase appear close together in text."""
    low = text.lower()
    words = phrase.lower().split()
    return all(w in low for w in words) if words else False


def _chunk_relevance(body: str, title: str, kws: list[str], query: str) -> int:
    """
    Score how relevant a chunk is to the query.
    - Full phrase match in title: very high
    - Full phrase match in body: high
    - Each keyword in title: moderate
    - Each keyword in body: low
    """
    score = 0
    query_low  = query.lower().strip()
    title_low  = title.lower()
    body_low   = body.lower()

    # Exact phrase hits
    if query_low in title_low:   score += 30
    if query_low in body_low:    score += 15

    # All keywords present in title
    if all(k in title_low for k in kws): score += 20

    # Per-keyword scores
    for k in kws:
        if k in title_low: score += 6
        if k in body_low:  score += 2

    return score


def _first_sentences(text: str, n: int = 3, min_len: int = 50) -> str:
    """Return first n substantial sentences joined as a paragraph."""
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) >= min_len]
    return " ".join(parts[:n])


def _bullet_sentences(text: str, kws: list[str], query: str, skip_intro: str, top_n: int = 5) -> list[str]:
    """Return keyword-relevant sentences not already in the intro paragraph."""
    intro_low = skip_intro.lower()
    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored = []
    for s in sentences:
        s = s.strip()
        if len(s) < 40 or s.lower() in intro_low:
            continue
        sc = _score(s, kws)
        if query.lower() in s.lower():
            sc += 10
        if sc > 0:
            scored.append((sc, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:top_n]]


def _source_label(chunk: str) -> tuple[str, str]:
    if chunk.startswith("[Source:"):
        end = chunk.index("]")
        return chunk[8:end].strip(" :"), chunk[end + 1:].strip()
    return "veevavault.help", chunk.strip()


def _format_help(message: str, chunks: list[str]) -> str:
    kws = _keywords(message)

    # ── 1. Try built-in knowledge base first ─────────────────────────────
    kb_answer = _kb_lookup(kws, message)

    # ── 2. Score live chunks (may be empty if web fetch failed) ──────────
    scored_chunks: list[tuple[int, str, str, str]] = []
    for chunk in chunks:
        label, body = _source_label(chunk)
        page_title = body.split("\n")[0].strip()
        relevance  = _chunk_relevance(body, page_title, kws, message)
        if relevance > 0:
            scored_chunks.append((relevance, label, page_title, body))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    if scored_chunks:
        best = scored_chunks[0][0]
        scored_chunks = [(sc, lb, tt, bd) for sc, lb, tt, bd in scored_chunks
                         if sc >= max(3, best * 0.25)]
    scored_chunks = scored_chunks[:2]

    # ── 3. Build live-web sections ────────────────────────────────────────
    live_sections: list[str] = []
    for _, label, page_title, body in scored_chunks:
        parts_split = body.split("\n\n", 1)
        content = parts_split[1].strip() if len(parts_split) > 1 else body.strip()
        display = page_title or (
            label.rstrip("/").split("/")[-1].replace("-", " ").title()
            if label.startswith("http") else "veevavault.help"
        )
        header  = f"### [{display}]({label})" if label.startswith("http") else f"### {display}"
        intro   = _first_sentences(content, n=3)
        bullets = _bullet_sentences(content, kws, message, intro, top_n=5)
        block   = [header]
        if intro:
            block.append(intro)
        if bullets:
            block.append("**Key points:**\n" + "\n".join(f"- {s}" for s in bullets))
        if len(block) > 1:
            live_sections.append("\n\n".join(block))

    # ── 4. Combine: KB answer + live supplement (if any) ─────────────────
    if kb_answer and live_sections:
        return kb_answer + "\n\n---\n\n" + "\n\n---\n\n".join(live_sections)

    if kb_answer:
        return kb_answer

    if live_sections:
        return "\n\n---\n\n".join(live_sections)

    # Build a direct search URL for veevavault.help
    from urllib.parse import quote
    encoded = quote(message, safe="")
    search_url = f"https://platform.veevavault.help/en/gr/search.htm#q={encoded}"

    return (
        f"I don't have a local answer for **\"{message}\"**.\n\n"
        f"**Search directly on Veeva Help:**  \n"
        f"[Search veevavault.help for this topic]({search_url})\n\n"
        "Or try asking about one of these topics — I have detailed answers ready:\n\n"
        "| Category | Topics |\n"
        "| :--- | :--- |\n"
        "| **Platform** | vault, document, object, binder, field, picklist, relationship, rendition, annotation, subscription, sandbox, validation, SSO, data model, data integrity |\n"
        "| **Access & Security** | lifecycle, workflow, role, user, group, security profile, atomic security, permission, layout, dynamic access control, electronic signature |\n"
        "| **Admin / Config** | document type, audit trail, formula field, configuration, VQL, report |\n"
        "| **Integration** | API, SDK, integration, connection, loader, spark, crosslink, Veeva CRM, Veeva Network |\n"
        "| **RIM** | RIM, registration, submission, content plan, eCTD |\n"
        "| **Clinical** | eTMF, inspection readiness, CTMS, site management, patient tracking, site monitoring, grant management |\n"
        "| **Quality** | QualityDocs, QMS, quality, training, station manager |\n"
        "| **PromoMats** | PromoMats, MLR review, claims management, content plan, content expiry, auto-approval |\n"
        "| **Safety / Medical** | Safety, signal management, MedInquiry, Engage |\n"
        "| **Compliance** | 21 CFR Part 11, Annex 11 |"
    )



# ══════════════════════════════════════════════════════════════════════════
# BUILT-IN VAULT KNOWLEDGE BASE  (data lives in vault_kb.py)
# ══════════════════════════════════════════════════════════════════════════

def _kb_lookup(kws: list[str], query: str) -> str | None:
    """
    Match the query against VAULT_KB (from vault_kb.py).
    1. Resolve alias keywords via KB_ALIASES first.
    2. Score every VAULT_KB key; return the best match or None.
    """
    query_low = query.lower()

    # Resolve alias keywords to canonical keys (e.g. "apis"→"api", "promomats"→"promomat")
    resolved_kws: list[str] = list(kws)
    for kw in kws:
        if kw in KB_ALIASES:
            resolved_kws.append(KB_ALIASES[kw])
    # Also check multi-word aliases against the full query (e.g. "change control", "quality docs")
    for alias, canonical in KB_ALIASES.items():
        if " " in alias and alias in query_low:
            resolved_kws.append(canonical)

    best_key, best_score = None, 0

    for key in VAULT_KB:
        score     = 0
        key_words = key.split()

        # Multi-word key: all words present in query → strong signal
        if len(key_words) > 1 and all(kw in query_low for kw in key_words):
            score += len(key_words) * 5

        # Full key string in query
        if key in query_low:
            score += 6

        # Canonical alias hit: a resolved keyword exactly matches the key
        for r_kw in resolved_kws:
            if r_kw == key:
                score += 8                                               # direct alias→key match

        # Per-keyword overlap with prefix stemming
        for q_kw in resolved_kws:
            for k_word in key_words:
                if q_kw == k_word:
                    score += 4
                elif q_kw.startswith(k_word) or k_word.startswith(q_kw):
                    score += 3
                elif len(q_kw) >= 3 and len(k_word) >= 3 and q_kw[:3] == k_word[:3]:
                    score += 2

        if score > best_score:
            best_score, best_key = score, key

    return VAULT_KB[best_key] if best_key and best_score > 0 else None


# ══════════════════════════════════════════════════════════════════════════
# GREETING RESPONSES
# ══════════════════════════════════════════════════════════════════════════

_GREETINGS = {"hi", "hello", "hey", "what can you do", "help me", "who are you"}

_INTROS = {
    "help": (
        "Hi! I'm **VaultBot — Help Assistant**.\n\n"
        "I answer questions using a built-in Vault knowledge base, with live veevavault.help as fallback.\n\n"
        "**Try asking:**\n"
        "- *What are the modules in RIM Vault?*\n"
        "- *How do I configure a document lifecycle?*\n"
        "- *What is Atomic Security?*\n"
        "- *What is the Vault SDK?*"
    ),
    "config": (
        "Hi! I'm **VaultBot — Config Analyst**.\n\n"
        "Upload your Vault Config Report (.xlsx/.csv) and ask anything about it.\n\n"
        "**Examples:**\n"
        "- *Show all object lifecycles*\n"
        "- *Document fields*\n"
        "- *Workflows for submission*\n"
        "- *How many security profiles are configured?*"
    ),
}


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════

def chat(message: str, context_chunks: list[str], mode: str = "help") -> str:
    msg_lower = message.lower().strip()
    if any(g in msg_lower for g in _GREETINGS):
        return _INTROS.get(mode, _INTROS["help"])
    return _format_help(message, context_chunks)
