"""
Veeva RIM Data Model Impact Analyzer.

Rules:
- ONLY generates analysis when BOTH release doc AND config report are provided.
- ONLY reports impact where overlap exists between the two files.
- Output: 5 sections — High Impact, Medium Impact, Integration Impact,
  Deprecated/Risk Items, Configuration Changes Required.
"""

import re
import pandas as pd

_API_NAME = re.compile(r'\b[\w]+__(?:v|c|sys|rim|r|bac|frd|oa|mim|f)\b', re.IGNORECASE)

# Type column values that indicate an integration component
_INTEGRATION_CTYPES = {
    "connection", "loader", "etl", "vaulttoexternal", "externaltovault",
    "integrationrule", "integration", "dataloader", "sparkloader",
}

_CONFIG_CHANGE_TYPES = {"pagelayout", "layoutrule", "picklist", "picklistentry",
                         "picklist.picklistentry", "field", "docfield", "attribute",
                         "permissionset", "objectaction"}


# ── Column resolver ───────────────────────────────────────────────────────────

def _col(df: pd.DataFrame, *candidates: str) -> str | None:
    for cand in candidates:
        for col in df.columns:
            if cand.lower() in str(col).lower():
                return col
    return None


def _get(row, col: str | None) -> str:
    if col is None:
        return ""
    val = row.get(col, "")
    return "" if pd.isna(val) else str(val).strip()


# ── API name extraction ───────────────────────────────────────────────────────

def _apis_from_string(text: str) -> set[str]:
    return {m.group().lower() for m in _API_NAME.finditer(text)}


def _apis_from_df(df: pd.DataFrame) -> set[str]:
    return _apis_from_string(df.fillna("").astype(str).to_string(index=False))


# ── Release document parser ───────────────────────────────────────────────────

def _find_updates_sheet(sheets: dict) -> pd.DataFrame | None:
    for name, df in sheets.items():
        if "update" in name.lower():
            return df
    return None


def _parse_release(sheets: dict) -> list[dict]:
    df = _find_updates_sheet(sheets)
    if df is None or df.empty:
        return []

    c_parent  = _col(df, "parent object", "parent")
    c_type    = _col(df, "type")
    c_name    = _col(df, "component name")
    c_label   = _col(df, "component label")
    c_change  = _col(df, "change")
    c_details = _col(df, "additional details")
    c_feature = _col(df, "related feature")
    c_enable  = _col(df, "enablement")
    c_status  = _col(df, "delivered status")

    entries = []
    for _, row in df.iterrows():
        change = _get(row, c_change)
        status = _get(row, c_status)
        if not change or status == "Not Applicable":
            continue

        parent   = _get(row, c_parent).lower()
        comp     = _get(row, c_name).lower()
        ctype    = _get(row, c_type)
        label    = _get(row, c_label)
        details  = _get(row, c_details)
        feature  = _get(row, c_feature)
        enable   = _get(row, c_enable)
        needs_cfg = "requires" in enable.lower()

        comp_apis = _apis_from_string(comp) | (_apis_from_string(parent) if parent else set())

        entries.append({
            "parent":     parent,
            "component":  comp,
            "comp_apis":  comp_apis,
            "label":      label,
            "ctype":      ctype,
            "change":     change,
            "needs_cfg":  needs_cfg,
            "enablement": enable,
            "feature":    feature,
            "details":    details,
            "status":     status,
        })
    return entries


# ── Config report parser ──────────────────────────────────────────────────────

def _parse_config(sheets: dict) -> dict:
    """
    Returns:
      all_apis      — every API name found anywhere in the config
      object_apis   — API names from an 'Objects' or 'Object' sheet
      field_apis    — API names from 'Fields' or 'Object Fields' sheet
      layout_apis   — API names from 'Page Layouts' or 'Layouts' sheet
      integration_apis — API names from 'Integrations' sheet
    """
    result = {
        "all_apis":         set(),
        "object_apis":      set(),
        "field_apis":       set(),
        "layout_apis":      set(),
        "integration_apis": set(),
    }

    for name, df in sheets.items():
        apis = _apis_from_df(df)
        result["all_apis"].update(apis)
        nl = name.lower()
        if "object" in nl and "field" not in nl:
            result["object_apis"].update(apis)
        if "field" in nl:
            result["field_apis"].update(apis)
        if "layout" in nl:
            result["layout_apis"].update(apis)
        if "integrat" in nl or "connection" in nl or "loader" in nl:
            result["integration_apis"].update(apis)

    return result


# ── Cross-analysis ────────────────────────────────────────────────────────────

def _in_config(entry: dict, cfg: dict) -> bool:
    return bool(entry["comp_apis"] & cfg["all_apis"])


def _is_integration(entry: dict, cfg: dict) -> bool:
    # 1. Component API names overlap with config's Integrations sheet
    if bool(entry["comp_apis"] & cfg["integration_apis"]):
        return True
    # 2. Type column explicitly names an integration component type
    ctype = entry["ctype"].lower().replace(" ", "").replace("_", "").replace(".", "")
    return any(kw in ctype for kw in _INTEGRATION_CTYPES)


def _is_config_change(entry: dict) -> bool:
    ctype = entry["ctype"].lower().replace(" ", "").replace("_", "").replace(".", "")
    return ctype in {t.replace(" ", "").replace("_", "").replace(".", "") for t in _CONFIG_CHANGE_TYPES}


# ── Table builder ─────────────────────────────────────────────────────────────

def _table(rows: list[dict], cols: list[tuple]) -> str:
    if not rows:
        return "_No items found._"
    header = "| " + " | ".join(c[0] for c in cols) + " |"
    sep    = "| " + " | ".join(":---" for _ in cols) + " |"
    lines  = [header, sep]
    for r in rows:
        cells = []
        for _, key in cols:
            val = r.get(key, "")
            cells.append(f"`{val}`" if key in ("component", "parent") else str(val or "—"))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ── Main report ───────────────────────────────────────────────────────────────

def generate_impact_report(release_sheets: dict, config_sheets: dict) -> str:
    """
    Both release_sheets and config_sheets must be provided.
    Returns structured 5-section impact analysis.
    """
    entries = _parse_release(release_sheets)
    cfg     = _parse_config(config_sheets)

    if not entries:
        return (
            "Could not find a changes sheet in the release document.\n\n"
            "Expected a sheet named **'…Updates'** (e.g. *26R1 Updates*) with columns: "
            "`Parent Object or Picklist`, `Component Name`, `Change`, `Enablement`."
        )

    if not cfg["all_apis"]:
        return (
            "Could not extract any Vault API names from the Configuration Report.\n\n"
            "Ensure the file contains Vault object/field names such as `submission__v` or `application__v`."
        )

    # ── Classify each entry ───────────────────────────────────────────────────
    high         = []   # Updated, object/field level, in config
    medium       = []   # New, requires config, related to config objects
    integration  = []   # Anything hitting integration layer
    risk         = []   # Deleted + in config
    config_chg   = []   # Layout/picklist/field config changes on in-config objects

    for e in entries:
        in_cfg   = _in_config(e, cfg)
        is_intg  = _is_integration(e, cfg)
        is_cfg_t = _is_config_change(e)

        if e["change"] == "Delete" and in_cfg:
            risk.append(e)
            continue

        if is_intg and in_cfg:
            integration.append(e)
            continue

        # ── Only classify if there is actual overlap with config ──────────────
        if not in_cfg and not is_intg:
            continue   # no overlap → skip entirely

        if e["change"] == "Update" and in_cfg:
            if is_cfg_t:
                config_chg.append(e)
            else:
                high.append(e)
            continue

        if e["change"] == "Create" and in_cfg and is_cfg_t:
            config_chg.append(e)
            continue

        if e["change"] == "Create" and e["needs_cfg"] and in_cfg:
            medium.append(e)
            continue

    total_impacted = len(high) + len(medium) + len(integration) + len(risk) + len(config_chg)

    if total_impacted == 0:
        return (
            "## Release Impact Analysis\n\n"
            "No impact identified based on current configuration.\n\n"
            "The release document changes do not overlap with any objects, fields, "
            "layouts or integrations found in your Configuration Report."
        )

    lines = []
    lines.append("## Veeva RIM Release Impact Analysis\n")
    lines.append(
        f"Cross-referenced **{len(entries)} release changes** against your configuration. "
        f"Found **{total_impacted} impacted items**.\n"
    )
    lines.append(
        f"| High Impact | Medium Impact | Integration | Risk/Deprecated | Config Changes |\n"
        f"| :---: | :---: | :---: | :---: | :---: |\n"
        f"| {len(high)} | {len(medium)} | {len(integration)} | {len(risk)} | {len(config_chg)} |\n"
    )

    # ── 1. High Impact Objects ────────────────────────────────────────────────
    lines.append("---\n")
    lines.append(f"### 1. High Impact Objects ({len(high)})\n")
    if high:
        lines.append(
            "Updated objects/fields present in your configuration — "
            "**validate before upgrading**.\n"
        )
        lines.append(_table(high[:25], [
            ("Component", "component"),
            ("Type",      "ctype"),
            ("Change",    "change"),
            ("Enablement","enablement"),
            ("Feature",   "feature"),
        ]))
        if len(high) > 25:
            lines.append(f"\n_… and {len(high)-25} more._")
    else:
        lines.append("_No high-impact objects identified._")

    # ── 2. Medium Impact Objects ──────────────────────────────────────────────
    lines.append("\n---\n")
    lines.append(f"### 2. Medium Impact Objects ({len(medium)})\n")
    if medium:
        lines.append(
            "New components requiring additional configuration, related to objects "
            "already in your Vault.\n"
        )
        lines.append(_table(medium[:20], [
            ("Component", "component"),
            ("Type",      "ctype"),
            ("Enablement","enablement"),
            ("Feature",   "feature"),
        ]))
        if len(medium) > 20:
            lines.append(f"\n_… and {len(medium)-20} more._")
    else:
        lines.append("_No medium-impact objects identified._")

    # ── 3. Integration Impact ─────────────────────────────────────────────────
    lines.append("\n---\n")
    lines.append(f"### 3. Integration Impact ({len(integration)})\n")
    if integration:
        lines.append(
            "These changes affect objects or fields used in your integrations "
            "(loaders, connections, APIs, ETL). "
            "**Review with your integration team before upgrade.**\n"
        )
        lines.append(_table(integration[:20], [
            ("Component", "component"),
            ("Parent",    "parent"),
            ("Type",      "ctype"),
            ("Change",    "change"),
            ("Feature",   "feature"),
        ]))
    else:
        lines.append("_No integration-related impact identified._")

    # ── 4. Deprecated / Risk Items ────────────────────────────────────────────
    lines.append("\n---\n")
    lines.append(f"### 4. Deprecated / Risk Items ({len(risk)})\n")
    if risk:
        lines.append(
            "These components are **being deleted** in this release but "
            "**exist in your configuration** — immediate action required.\n"
        )
        lines.append(_table(risk, [
            ("Component", "component"),
            ("Parent",    "parent"),
            ("Type",      "ctype"),
            ("Details",   "details"),
        ]))
    else:
        lines.append("_No deprecated or deleted items found in your configuration._")

    # ── 5. Configuration Changes Required ────────────────────────────────────
    lines.append("\n---\n")
    lines.append(f"### 5. Configuration Changes Required ({len(config_chg)})\n")
    if config_chg:
        lines.append(
            "Page layout, picklist, field, or permission set changes that affect "
            "objects in your configuration — **manual configuration updates needed**.\n"
        )
        lines.append(_table(config_chg[:25], [
            ("Component", "component"),
            ("Parent",    "parent"),
            ("Type",      "ctype"),
            ("Change",    "change"),
            ("Enablement","enablement"),
        ]))
        if len(config_chg) > 25:
            lines.append(f"\n_… and {len(config_chg)-25} more._")
    else:
        lines.append("_No configuration changes required._")

    # ── Recommended Actions ───────────────────────────────────────────────────
    lines.append("\n---\n")
    lines.append("### Recommended Actions\n")
    actions = []
    if risk:
        actions.append(
            f"1. **Immediate** — {len(risk)} deleted component(s) found in your config. "
            "Remove or migrate these before upgrade."
        )
    if high:
        actions.append(
            f"2. **Pre-upgrade testing** — Validate {len(high)} updated object(s)/field(s) "
            "in a sandbox environment."
        )
    if integration:
        actions.append(
            f"3. **Integration review** — Coordinate with your integration team on "
            f"{len(integration)} change(s) affecting loaders/connections/APIs."
        )
    if config_chg:
        actions.append(
            f"4. **Configuration updates** — Apply {len(config_chg)} layout/picklist/field "
            "changes in your Vault configuration."
        )
    if medium:
        actions.append(
            f"5. **Optional adoption** — {len(medium)} new feature(s) require setup if you "
            "want to use them."
        )
    lines.extend(actions)

    return "\n".join(lines)
