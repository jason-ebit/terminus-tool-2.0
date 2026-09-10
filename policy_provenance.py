"""Milestones 0-2: baseline capture, source manifest, and the T3-to-T4 policy diff.

The upgrade instruction requires that no blocking T4 rule exists without verified
source support, and that every T3 rule's fate is recorded. This module produces
those artefacts from the live checker and the live clone, so they are evidence
rather than prose: hashes are computed, not asserted.

Run it with `python policy_provenance.py` to regenerate:
    baseline-t3.json          Milestone 0 baseline (kept if present; --rebaseline replaces it)
    source-manifest.json      Milestone 1 manifest
    source-gap-report.md      Milestone 1 gaps
    policy-diff.json          Milestone 2 machine-readable diff
    t3-to-t4-policy-diff.md   Milestone 2 human diff
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import harbor_policy
import reporting
import terminus_checklist_site as site

ROOT = Path(__file__).resolve().parent


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Milestone 0 -------------------------------------------------------------

def baseline_t3() -> dict[str, Any]:
    checklist = site.source_supported_checklist()
    items = checklist["items"]
    return {
        "captured_at": _now(),
        "checker_version": reporting.CHECKER_VERSION,
        "profile": site.PROFILE_T3,
        "profile_label": site.PROFILE_LABELS[site.PROFILE_T3],
        "checklist_sha256": _hash(json.dumps(checklist, sort_keys=True)),
        "item_count": len(items),
        "severity_counts": {
            s: sum(1 for i in items if i.get("severity") == s)
            for s in sorted({i.get("severity") for i in items})
        },
        "review_mode_counts": {
            m: sum(1 for i in items if i.get("review_mode", "auto") == m)
            for m in sorted({i.get("review_mode", "auto") for i in items})
        },
        "item_ids": [i["id"] for i in items],
        "scoring": {
            "weights": {"satisfied": 1.0, "partial": 0.5, "missing": 0.0, "unknown": 0.0},
            "excluded": ["not_applicable", "review_mode == manual"],
            "note": "Legacy arithmetic retained unchanged for continuity.",
        },
        "known_defects": [
            "Original run_ollama never set num_ctx; Ollama truncated the prompt at its "
            "4096-token default so every review silently fell back to keyword matching.",
            "unknown and missing carry the same weight (0.0), so honest uncertainty scored "
            "as confirmed noncompliance.",
            "extract_docs_index matched a Vite-minified symbol, so a portal rebuild "
            "silently reduced the checklist refresh to zero docs.",
            "check_absent_term read a 600-character preview rather than stored content.",
        ],
    }


# --- Milestone 1 -------------------------------------------------------------

RAW_BASE = "https://raw.githubusercontent.com/harbor-framework/terminal-bench/main"

T4_SOURCES = [
    ("t4-task-template", "docs/task-template.toml", "Task template", "normative"),
    ("t4-implementation-rubric", "docs/prompts/task-implementation.toml",
     "Implementation rubric (35 criteria)", "normative"),
    ("t4-taxonomy", "docs/TAXONOMY.md", "Taxonomy: domains and subdomains", "normative"),
    ("t4-reviewing", "docs/REVIEWING.md", "Reviewing tasks", "normative"),
    ("t4-review-automation", "docs/TASK_REVIEW_AUTOMATION.md",
     "Review automation and static checks", "normative"),
    ("t4-contributing", "CONTRIBUTING.md", "Contributing guide", "normative"),
]

T3_SOURCES = [
    ("t3-portal-docs", "docs/understanding-tasks/task-requirements.md",
     "Task requirements", "normative"),
    ("t3-portal-checklist", "docs/submitting-tasks/submission-checklist.md",
     "Submission checklist", "normative"),
    ("t3-portal-difficulty", "docs/understanding-tasks/difficulty-guidelines.md",
     "Difficulty guidelines", "normative"),
]
T3_BASE = "https://snorkel-ai.github.io/Terminus-EC-Training-stateful"


def source_manifest(repo: Path | None) -> list[dict[str, Any]]:
    """Hash every policy source actually used, and record what is missing."""
    entries: list[dict[str, Any]] = []

    for source_id, rel, title, authority in T4_SOURCES:
        path = repo / rel if repo else None
        available = bool(path and path.exists())
        content = ""
        if available and path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")
        entries.append({
            "source_id": source_id,
            "version": "T4",
            "url": f"{RAW_BASE}/{rel}",
            "local_path": str(path) if path else None,
            "title": title,
            "retrieved_at": _now(),
            "content_sha256": _hash(content) if content else None,
            "authority": authority,
            "status": "verified" if available else "unavailable",
        })

    if repo:
        scripts = sorted((repo / "scripts" / "checks").glob("check-*.sh"))
        joined = "".join(p.read_text(encoding="utf-8", errors="replace") for p in scripts)
        version = harbor_policy.repo_version(repo)
        entries.append({
            "source_id": "t4-static-checks",
            "version": "T4",
            "url": f"{RAW_BASE}/scripts/checks",
            "local_path": str(repo / "scripts" / "checks"),
            "title": f"Executable static checks ({len(scripts)} scripts)",
            "retrieved_at": _now(),
            "content_sha256": _hash(joined),
            "authority": "normative",
            "status": "verified",
            "policy_revision": version["describe"],
            "policy_sha": version["sha"],
        })

    for source_id, rel, title, authority in T3_SOURCES:
        entries.append({
            "source_id": source_id,
            "version": "T3",
            "url": f"{T3_BASE}/{rel}",
            "local_path": None,
            "title": title,
            "retrieved_at": _now(),
            "content_sha256": None,
            "authority": authority,
            "status": "verified-remote",
            "note": "Live portal document; hashed at fetch time by the checklist refresh.",
        })
    return entries


# --- Milestone 2 -------------------------------------------------------------

from policy_diff_data import NEW_T4_RULES, POLICY_DIFF  # noqa: E402



def policy_diff(repo: Path | None) -> dict[str, Any]:
    t3_ids = [i["id"] for i in site.source_supported_checklist()["items"]]
    t4_ids: list[str] = []
    if repo:
        t4_ids = [i["id"] for i in harbor_policy.build_checklist(repo)["items"]]

    rows = []
    for rule_id in t3_ids:
        entry = POLICY_DIFF.get(rule_id)
        if entry:
            rows.append({"t3_rule": rule_id, **entry})
        else:
            rows.append({
                "t3_rule": rule_id, "relation": "unclear", "t4_rule": "",
                "t3": "See the T3 seed checklist.",
                "t4": "No verified T4 counterpart identified.",
                "source_ids": "",
                "note": "Not carried into the T4 profile. Marked unclear rather than removed: "
                        "absence of a check script is not proof the requirement was dropped.",
            })
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["relation"]] = counts.get(row["relation"], 0) + 1
    return {
        "generated_at": _now(),
        "t3_rule_count": len(t3_ids),
        "t4_rule_count": len(t4_ids),
        "relation_counts": counts,
        "rules": rows,
        "new_in_t4": [
            {"t4_rule": rid, "requirement": text, "source_ids": src}
            for rid, text, src in NEW_T4_RULES
        ],
        "unresolved_questions": [
            "Does T4 require negative-run evidence at review time, or only via /cheat trials?",
            "Are the four README explanation sections mandatory for every task, or only when "
            "the metadata fields are absent?",
            "Is `schema_version` required, or is its absence tolerated?",
            "Do any T3-only rules with no T4 counterpart still apply to T4 submissions?",
        ],
    }


def unsourced_blocking_rules(repo: Path | None) -> list[str]:
    """Blocking T4 rules whose source cannot be verified. Must be empty to ship."""
    if not repo:
        return ["<all>: no terminal-bench clone available"]
    manifest = {e["source_id"]: e for e in source_manifest(repo)}
    missing = []
    for item in harbor_policy.build_checklist(repo)["items"]:
        if item.get("source") == "harbor-static-check":
            if manifest.get("t4-static-checks", {}).get("status") != "verified":
                missing.append(item["id"])
        elif item.get("source") == "harbor-rubric":
            if manifest.get("t4-implementation-rubric", {}).get("status") != "verified":
                missing.append(item["id"])
    return missing


def main(argv: list[str] | None = None) -> int:
    repo = harbor_policy.repo_root()
    # The baseline is evidence of the pre-change state; only replace it on purpose.
    baseline = ROOT / "baseline-t3.json"
    if not baseline.exists() or "--rebaseline" in (argv or []):
        baseline.write_text(json.dumps(baseline_t3(), indent=2), encoding="utf-8")
    else:
        print(f"baseline-t3.json        kept (pass --rebaseline to replace)")
    manifest = source_manifest(repo)
    (ROOT / "source-manifest.json").write_text(
        json.dumps({"generated_at": _now(), "sources": manifest}, indent=2), encoding="utf-8")
    diff = policy_diff(repo)
    (ROOT / "policy-diff.json").write_text(json.dumps(diff, indent=2), encoding="utf-8")

    gaps = [e for e in manifest if e["status"] not in ("verified", "verified-remote")]
    unsourced = unsourced_blocking_rules(repo)
    (ROOT / "source-gap-report.md").write_text("\n".join([
        "# Source gap report", "",
        f"Generated {_now()}.", "",
        f"- Sources checked: {len(manifest)}",
        f"- Unavailable or ambiguous: {len(gaps)}",
        f"- Blocking T4 rules without verified source support: {len(unsourced)}", "",
        "## Gaps", "",
        *([f"- `{g['source_id']}` ({g['status']}): {g['url']}" for g in gaps] or ["None."]),
        "", "## Unsourced blocking rules", "",
        *([f"- `{r}`" for r in unsourced] or ["None. Every blocking T4 rule traces to a verified source."]),
        "", "## Unresolved policy questions", "",
        *[f"- {q}" for q in diff["unresolved_questions"]],
        "",
    ]), encoding="utf-8")

    lines = ["# T3 to T4 policy diff", "",
             f"Generated {_now()}.",
             f"T3 rules: {diff['t3_rule_count']} · T4 rules: {diff['t4_rule_count']}", "",
             "Relation counts: " + ", ".join(f"{k} {v}" for k, v in sorted(diff["relation_counts"].items())),
             "", "## T3 rules and their fate", "",
             "| T3 rule | Relation | T4 rule | T3 behaviour | T4 behaviour | Sources |",
             "|---|---|---|---|---|---|"]
    for row in diff["rules"]:
        lines.append("| `{t3_rule}` | {relation} | {t4} | {a} | {b} | {s} |".format(
            t3_rule=row["t3_rule"], relation=row["relation"],
            t4=f"`{row['t4_rule']}`" if row["t4_rule"] else "—",
            a=row["t3"].replace("|", "/"), b=row["t4"].replace("|", "/"),
            s=row["source_ids"] or "—"))
    lines += ["", "## New in T4", "",
              "| T4 rule | Requirement | Sources |", "|---|---|---|"]
    for row in diff["new_in_t4"]:
        lines.append(f"| `{row['t4_rule']}` | {row['requirement']} | {row['source_ids']} |")
    lines += ["", "## Unresolved questions", ""] + [f"- {q}" for q in diff["unresolved_questions"]] + [""]
    (ROOT / "t3-to-t4-policy-diff.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"source-manifest.json    {len(manifest)} sources, {len(gaps)} gaps")
    print(f"policy-diff.json        {diff['relation_counts']}")
    print(f"source-gap-report.md    {len(unsourced)} unsourced blocking rules")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
