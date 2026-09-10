"""Run both migration fixtures through both profiles and print the outcome.

    python fixtures/run_migration_fixtures.py

Needs bash, python3 and a terminal-bench clone for the T4 half (WSL, Linux or
macOS). The model is stubbed: these fixtures test static policy, not the rubric.
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import terminus_checklist_site as site  # noqa: E402

HERE = Path(__file__).resolve().parent / "migration"


def package(name: str) -> bytes:
    root = HERE / name
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                archive.write(path, f"{name}/{path.relative_to(root).as_posix()}")
    return buf.getvalue()


def review(name: str, profile: str) -> dict:
    with patch.object(site, "run_ollama", side_effect=RuntimeError("fixture: model stubbed")):
        return site.review_zip(package(name), site.source_supported_checklist(), "stub",
                               f"{name}.zip", profile=profile)


def fixtures() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(HERE.glob("*.fixture.json"))]


if __name__ == "__main__":
    for meta in fixtures():
        name = meta["fixture"]
        for profile in ("t3", "t4"):
            if profile == "t4" and site.t4_status()[0] == "unavailable":
                print(f"{name:15} t4: skipped ({site.t4_status()[1]})")
                continue
            out = review(name, profile)
            statuses = {r["id"]: r["status"] for r in out["results"]}
            expected = meta["expected"][profile]
            ok = (out["assessment"]["confirmed_failures"] == expected["confirmed_failures"] and
                  all(statuses.get(k) == v for k, v in expected["rule_outcomes"].items()))
            print(f"{name:15} {profile}: {'OK ' if ok else 'BAD'} state={out['overall_state']:18} "
                  f"static={out['assessment']['static']} "
                  f"confirmed={out['assessment']['confirmed_failures']} "
                  + " ".join(f"{k}={statuses.get(k)}" for k in expected["rule_outcomes"]))
