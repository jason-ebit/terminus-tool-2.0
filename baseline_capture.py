"""Milestone A: capture reproducible fixture outputs before behaviour changes.

The model is replaced with a deterministic stub so the captured static results are
reproducible run to run; the LLM layer is characterised separately. Run before and
after a change, then diff the two JSON files: any unexplained T3 difference is a
regression.

    python baseline_capture.py before.json
    python baseline_capture.py after.json
    python baseline_capture.py --diff before.json after.json
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import terminus_checklist_site as site

GITHUB = Path(__file__).resolve().parent.parent
FIXTURES = {
    "foodstuff-beta-activity": GITHUB / "terminal-bench" / "tasks" / "foodstuff-beta-activity.zip",
    "battleship-t2": GITHUB / "Snorkel Passed TB 2.0 - 340" / "Snorkel Passed TB 2.0 - 340" / "battleship.zip",
    "fix-typo": GITHUB.parent / "Codex" / "2026-09-08" / "referenced-chatgpt-conversation-this-is-an" / "outputs" / "fix-typo.zip",
    "fix-typo-t4": GITHUB.parent / "Codex" / "2026-09-08" / "referenced-chatgpt-conversation-this-is-an" / "outputs" / "fix-typo-t4.zip",
}


def zip_directory(path: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(path.rglob("*")):
            if item.is_file():
                archive.write(item, f"{path.name}/{item.relative_to(path).as_posix()}")
    return buf.getvalue()


def load_fixtures() -> dict[str, bytes]:
    out = {name: p.read_bytes() for name, p in FIXTURES.items() if p.is_file()}
    merged = GITHUB / "terminal-bench" / "tasks" / "wdm-design"
    if merged.is_dir():
        out["wdm-design-merged"] = zip_directory(merged)
    return out


def summarise(review: dict) -> dict:
    return {
        "profile": review.get("profile"),
        "review_mode": review.get("review_mode"),
        "overall_state": review.get("overall_state"),
        "statuses": {r["id"]: r["status"] for r in review.get("results", [])},
        "sources": {r["id"]: r.get("assessment_source") for r in review.get("results", [])},
    }


def capture() -> dict:
    results: dict = {}
    fixtures = load_fixtures()
    for name, raw in sorted(fixtures.items()):
        results[name] = {}
        for profile in ("t3", "t4"):
            if profile == "t4" and site.profile_unavailable_reason("t4"):
                results[name][profile] = {"skipped": site.profile_unavailable_reason("t4")}
                continue
            with patch.object(site, "run_ollama", side_effect=RuntimeError("baseline: model stubbed")):
                try:
                    review = site.review_zip(raw, site.source_supported_checklist(), "stub",
                                             f"{name}.zip", profile=profile)
                    results[name][profile] = summarise(review)
                except Exception as exc:  # recorded, not hidden
                    results[name][profile] = {"error": f"{type(exc).__name__}: {exc}"}
    return results


def diff(before: dict, after: dict) -> list[str]:
    lines = []
    for name in sorted(set(before) | set(after)):
        for profile in ("t3", "t4"):
            a = before.get(name, {}).get(profile, {}).get("statuses", {})
            b = after.get(name, {}).get(profile, {}).get("statuses", {})
            for rule in sorted(set(a) | set(b)):
                if a.get(rule) != b.get(rule):
                    lines.append(f"{profile} {name}: {rule} {a.get(rule)} -> {b.get(rule)}")
    return lines


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--diff":
        changes = diff(json.load(open(sys.argv[2])), json.load(open(sys.argv[3])))
        print("\n".join(changes) if changes else "no static-result differences")
        raise SystemExit(1 if any(c.startswith("t3 ") for c in changes) else 0)
    target = sys.argv[1] if len(sys.argv) > 1 else "baseline-fixtures.json"
    data = capture()
    Path(target).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    for name, profiles in sorted(data.items()):
        for profile, res in profiles.items():
            if "statuses" in res:
                bad = sum(1 for s in res["statuses"].values() if s in ("missing", "partial"))
                print(f"{profile} {name:26} {res['overall_state']:16} {len(res['statuses']):3} items, {bad} missing/partial")
            else:
                print(f"{profile} {name:26} {next(iter(res.values()))[:70]}")
