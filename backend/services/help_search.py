"""
TF-IDF search engine for the scraped Vault help data.
No external ML libraries — pure Python standard library.

Usage:
    engine = VaultHelpSearch()
    engine.build(docs)          # docs from scraper.load_docs()
    results = engine.search("what is a workflow", top_k=3)
"""

import re
import math
from collections import Counter

# ── Stop words ─────────────────────────────────────────────────────────────────

_STOPS = {
    "what", "is", "are", "the", "a", "an", "in", "of", "to", "how", "do",
    "does", "can", "i", "me", "for", "and", "or", "with", "this", "that",
    "which", "was", "be", "it", "its", "on", "at", "by", "from", "as",
    "tell", "show", "explain", "about", "all", "get", "give", "find",
    "list", "display", "check", "use", "using", "used", "has", "have",
    "will", "would", "should", "also", "when", "where", "who", "why",
    "not", "but", "if", "then", "than", "more", "some", "any", "its",
    "they", "them", "their", "you", "your", "we", "our",
}


def _tokenise(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return [w for w in words if w not in _STOPS]


# ── Search engine ──────────────────────────────────────────────────────────────

class VaultHelpSearch:
    def __init__(self) -> None:
        self._docs:     list[dict]          = []
        self._doc_tfs:  list[Counter]       = []
        self._idf:      dict[str, float]    = {}
        self._ready:    bool                = False

    # ── Build index ────────────────────────────────────────────────────────────

    def build(self, docs: list[dict]) -> None:
        """Build TF-IDF index from a list of {title, url, content, subdomain} dicts."""
        self._docs    = docs
        self._doc_tfs = []

        N  = len(docs)
        df: Counter = Counter()

        # Pass 1: term frequencies per document
        for doc in docs:
            text   = doc["title"] + " " + doc.get("content", "")
            tokens = _tokenise(text)
            tf     = Counter(tokens)
            self._doc_tfs.append(tf)
            for term in set(tokens):
                df[term] += 1

        # IDF = log((N+1) / (df+1))  — smoothed to avoid div-by-zero
        self._idf   = {term: math.log((N + 1) / (cnt + 1)) for term, cnt in df.items()}
        self._ready = True
        print(f"[HelpSearch] Index built: {N} docs, {len(self._idf)} unique terms")

    @property
    def ready(self) -> bool:
        return self._ready and bool(self._docs)

    # ── Query ──────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Return top_k most relevant documents for the query.
        Each result dict has: title, url, content, subdomain, score (added).
        """
        if not self.ready:
            return []

        kws = _tokenise(query)
        if not kws:
            return []

        query_low = query.lower().strip()
        scores: list[tuple[float, int]] = []

        for idx, (doc, tf) in enumerate(zip(self._docs, self._doc_tfs)):
            score      = 0.0
            total_toks = max(sum(tf.values()), 1)
            title_low  = doc["title"].lower()

            # TF-IDF score
            for kw in kws:
                tf_val  = tf.get(kw, 0) / total_toks
                idf_val = self._idf.get(kw, 0)
                score  += tf_val * idf_val

            # Title bonuses (strong signals)
            if query_low in title_low:
                score += 2.0                     # exact phrase in title
            if all(k in title_low for k in kws):
                score += 1.5                     # all keywords in title
            for kw in kws:
                if kw in title_low:
                    score += 0.5                 # per-keyword title hit

            # Platform subdomain bonus (primary source)
            if doc.get("subdomain") == "platform":
                score += 0.1

            if score > 0:
                scores.append((score, idx))

        scores.sort(reverse=True)
        results = []
        for sc, idx in scores[:top_k]:
            doc = dict(self._docs[idx])
            doc["score"] = round(sc, 4)
            results.append(doc)
        return results


# ── Module-level singleton ─────────────────────────────────────────────────────

_engine = VaultHelpSearch()


def get_engine() -> VaultHelpSearch:
    return _engine
