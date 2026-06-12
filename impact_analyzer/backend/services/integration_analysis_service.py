"""
Stage 2: Integration Specification Analysis

Cross-references the Stage 1 impact report against an uploaded Integration
Specification document (Excel / CSV) and classifies each integration by risk:

  CRITICAL  — uses deleted or deprecated components (immediate action)
  HIGH      — uses updated objects/fields found in the impact report
  REVIEW    — partial overlap; validate before upgrade
  UNAFFECTED — no overlap with impacted components

The rule-based engine always runs. When Bedrock is configured, the output is
enhanced with per-integration narrative and remediation guidance.
"""

from __future__ import annotations

import re
import pandas as pd

_API_NAME = re.compile(r'\b[\w]+__(?:v|c|sys|rim|r|bac|frd|oa|mim|f)\b', re.IGNORECASE)


# ── Utilities ─────────────────────────────────────────────────────────────────

def _apis(text: str) -> set[str]:
    return {m.group().lower() for m in _API_NAME.finditer(str(text))}


def _col(df: pd.DataFrame, *keywords: str) -> str | None:
    for kw in keywords:
        for c in df.columns:
            if kw.lower() in str(c).lower():
                return c
    return None


def _val(row, col: str | None) -> str:
    if col is None:
        return ""
    v = row.get(col, "")
    return "" if pd.isna(v) else str(v).strip()


# ── Integration spec parser ───────────────────────────────────────────────────

def _parse_spec(sheets: dict) -> list[dict]:
    """
    Extract one record per integration/interface row from the spec.

    Looks for columns matching common naming patterns:
      Name:   Integration, Interface, Name
      Source: Source, Src, From, Origin
      Target: Target, Destination, Dest, To, Sink
      Type:   Type, Direction, Mode
      Notes:  Notes, Description, Comments, Remarks
    """
    records: list[dict] = []

    for sheet_name, df in sheets.items():
        if df.empty:
            continue

        c_name   = _col(df, "integration", "interface", "name")
        c_source = _col(df, "source", "src", "from", "origin")
        c_target = _col(df, "target", "destination", "dest", "sink")
        c_type   = _col(df, "type", "direction", "mode")
        c_notes  = _col(df, "notes", "description", "comments", "remarks")

        if c_name is None:
            # Sheet has no name column — treat the whole sheet as one integration
            row_text = df.fillna("").astype(str).to_string(index=False)
            records.append({
                "name":    sheet_name,
                "source":  "",
                "target":  "",
                "itype":   "",
                "notes":   "",
                "apis":    _apis(row_text),
                "sheet":   sheet_name,
            })
            continue

        for _, row in df.iterrows():
            name = _val(row, c_name)
            if not name:
                continue
            row_text = " ".join(str(v) for v in row.values if pd.notna(v))
            records.append({
                "name":   name,
                "source": _val(row, c_source),
                "target": _val(row, c_target),
                "itype":  _val(row, c_type),
                "notes":  _val(row, c_notes),
                "apis":   _apis(row_text),
                "sheet":  sheet_name,
            })

    return records


# ── Impact report parser ──────────────────────────────────────────────────────

def _extract_impact_apis(report: str) -> dict[str, set[str]]:
    """
    Parse the Stage 1 markdown report and bucket impacted API names by section.
    Returns: { 'high', 'medium', 'integration', 'risk', 'config' }
    """
    buckets: dict[str, set[str]] = {
        "high": set(), "medium": set(),
        "integration": set(), "risk": set(), "config": set(),
    }
    markers = {
        "1. high impact":              "high",
        "2. medium impact":            "medium",
        "3. integration impact":       "integration",
        "4. deprecated":               "risk",
        "5. configuration changes":    "config",
    }
    current = None
    for line in report.splitlines():
        ll = line.lower()
        for marker, key in markers.items():
            if marker in ll:
                current = key
                break
        if current:
            buckets[current].update(_apis(line))
    return buckets


# ── Classification ────────────────────────────────────────────────────────────

def _classify(rec: dict, buckets: dict[str, set[str]]) -> tuple[str, set[str]]:
    """
    Returns (risk_level, overlapping_apis).
    CRITICAL > HIGH > REVIEW > UNAFFECTED
    """
    danger   = buckets["high"] | buckets["risk"]
    elevated = buckets["integration"] | buckets["medium"]
    all_imp  = danger | elevated | buckets["config"]

    overlap_danger   = rec["apis"] & danger
    overlap_elevated = rec["apis"] & elevated
    overlap_any      = rec["apis"] & all_imp

    if overlap_danger:
        return "CRITICAL", overlap_danger
    if overlap_elevated:
        return "HIGH", overlap_elevated
    if overlap_any:
        return "REVIEW", overlap_any
    return "UNAFFECTED", set()


# ── Markdown table helpers ────────────────────────────────────────────────────

def _api_list(apis: set[str], limit: int = 6) -> str:
    items = sorted(apis)[:limit]
    suffix = f" *(+{len(apis)-limit} more)*" if len(apis) > limit else ""
    return ", ".join(f"`{a}`" for a in items) + suffix


def _row_line(rec: dict, overlap: set[str]) -> str:
    flow = f"{rec['source']} → {rec['target']}" if rec["source"] or rec["target"] else "—"
    return f"| {rec['name']} | {flow} | {rec['itype'] or '—'} | {_api_list(overlap)} |"


# ── Main entry point ──────────────────────────────────────────────────────────

def analyze_integration_spec(impact_report: str, spec_sheets: dict) -> str:
    """
    Cross-reference the Stage 1 impact report with the uploaded Integration Spec.
    Returns a structured markdown report (Stage 2).
    """
    records = _parse_spec(spec_sheets)

    if not records:
        return (
            "## Stage 2 — Integration Specification Analysis\n\n"
            "> Could not extract integration definitions from the uploaded file.\n\n"
            "Ensure the file contains a column named **Integration** or **Interface** "
            "with Vault API names (e.g. `submission__v`) in the same row or nearby columns."
        )

    buckets = _extract_impact_apis(impact_report)

    critical, high, review, unaffected = [], [], [], []

    for rec in records:
        level, overlap = _classify(rec, buckets)
        entry = {**rec, "level": level, "overlap": overlap}
        if level == "CRITICAL":   critical.append(entry)
        elif level == "HIGH":     high.append(entry)
        elif level == "REVIEW":   review.append(entry)
        else:                     unaffected.append(entry)

    total    = len(records)
    affected = len(critical) + len(high) + len(review)

    lines: list[str] = []
    lines.append("## Stage 2 — Integration Specification Analysis\n")
    lines.append(
        f"Cross-referenced **{total} integration(s)** from the specification "
        f"against the Stage 1 impact report. "
        f"**{affected} integration(s) require attention before upgrade.**\n"
    )
    lines.append(
        "| Critical | High | Needs Review | Unaffected |\n"
        "| :---: | :---: | :---: | :---: |\n"
        f"| {len(critical)} | {len(high)} | {len(review)} | {len(unaffected)} |"
    )

    # ── CRITICAL ─────────────────────────────────────────────────────────────
    lines.append("\n---\n")
    lines.append(f"### Critical Integrations ({len(critical)})\n")
    if critical:
        lines.append(
            "Use components that are **deleted or significantly changed**. "
            "Remediation required **before** the upgrade window.\n"
        )
        lines.append("| Integration | Flow | Type | Impacted APIs |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for e in critical:
            lines.append(_row_line(e, e["overlap"]))
        lines.append("")
        lines.append("**Recommended action:** Review each integration's field mappings and "
                     "connection config. Coordinate with the integration team and test in sandbox.")
    else:
        lines.append("_No critical integration impacts identified._")

    # ── HIGH ─────────────────────────────────────────────────────────────────
    lines.append("\n---\n")
    lines.append(f"### High Risk Integrations ({len(high)})\n")
    if high:
        lines.append(
            "Reference objects/fields that are **updated** in this release. "
            "Validate payloads and field mappings in a sandbox before upgrading production.\n"
        )
        lines.append("| Integration | Flow | Type | Impacted APIs |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for e in high:
            lines.append(_row_line(e, e["overlap"]))
    else:
        lines.append("_No high-risk integration impacts identified._")

    # ── REVIEW ────────────────────────────────────────────────────────────────
    lines.append("\n---\n")
    lines.append(f"### Needs Review ({len(review)})\n")
    if review:
        lines.append(
            "Partial overlap with impacted components — validate these integrations "
            "but they are lower priority than Critical/High.\n"
        )
        names = " · ".join(f"**{e['name']}**" for e in review)
        lines.append(names)
    else:
        lines.append("_No integrations flagged for review._")

    # ── UNAFFECTED ────────────────────────────────────────────────────────────
    if unaffected:
        lines.append("\n---\n")
        lines.append(f"### Unaffected Integrations ({len(unaffected)})\n")
        names = " · ".join(f"**{e['name']}**" for e in unaffected)
        lines.append(f"No overlap with impacted components: {names}")

    # ── Actions ───────────────────────────────────────────────────────────────
    lines.append("\n---\n")
    lines.append("### Stage 2 Recommended Actions\n")
    if critical:
        lines.append(
            f"1. **Immediate** — {len(critical)} critical integration(s) must be remediated "
            "before upgrade. Escalate to integration team."
        )
    if high:
        lines.append(
            f"2. **Pre-upgrade** — Validate {len(high)} high-risk integration(s) in sandbox. "
            "Update field mappings where needed."
        )
    if review:
        lines.append(
            f"3. **Spot-check** — {len(review)} integration(s) need a quick review but are "
            "lower risk."
        )
    if not affected:
        lines.append("No integration remediation required for this release.")

    return "\n".join(lines)


# ── Simple keyword fallback for Q&A (no Bedrock) ─────────────────────────────

def keyword_search(question: str, *reports: str) -> str:
    """
    Lightweight fallback answer when Bedrock is not configured.
    Scores paragraphs from all reports by keyword overlap and returns
    the most relevant excerpts.
    """
    stopwords = {
        "what", "is", "are", "the", "a", "an", "in", "of", "to", "how",
        "do", "does", "can", "i", "me", "for", "and", "or", "with",
        "this", "that", "which", "was", "be", "it", "its", "on", "at",
        "by", "from", "tell", "show", "explain", "about", "will", "my",
    }
    words = [
        w for w in re.findall(r"[a-zA-Z_]{3,}", question.lower())
        if w not in stopwords
    ]
    if not words:
        return "_Please ask a more specific question about the report._"

    full_text = "\n\n".join(r for r in reports if r)
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", full_text) if len(p.strip()) > 40]

    scored: list[tuple[int, str]] = []
    for para in paragraphs:
        pl = para.lower()
        score = sum(3 if w in pl else (1 if any(w[:4] in pl for _ in [1]) else 0) for w in words)
        if score > 0:
            scored.append((score, para))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [p for _, p in scored[:3]]

    if not top:
        return (
            f"No specific information found for **\"{question}\"** in the current reports.\n\n"
            "Connect Amazon Bedrock (see `.env.example`) for full natural-language Q&A."
        )

    note = (
        "\n\n---\n> *Keyword match — connect Amazon Bedrock for full natural-language answers.*"
    )
    return "\n\n---\n\n".join(top) + note
