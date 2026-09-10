"""Terminal-Bench 4.0 policy, read from a terminal-bench clone rather than reimplemented.

The benchmark ships its own mechanical rules as executable scripts in
`scripts/checks/` and its judgement-call rules as a rubric in
`docs/prompts/task-implementation.toml`. Reimplementing either in Python
guarantees drift on the next release, which is exactly how the previous T3
checker ended up scoring submissions against rules the benchmark had moved on
from. This module discovers both from the clone and runs the real scripts, so a
policy update arrives via `git pull` instead of a code change.

The check scripts only grep and parse task files. They do not execute uploaded
task code, and neither does this module.

Requires bash. On the Windows side of a WSL setup, discovery still works
(the checklist can be built) but `run_checks` reports itself unavailable.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

CHECK_TIMEOUT_SEC = 120
STATIC_CATEGORY = "Harbor Static Checks"
RUBRIC_CATEGORY = "Implementation Rubric"


def repo_root(explicit: str | None = None) -> Path | None:
    """Locate a terminal-bench clone: explicit path, T4_REPO, or a sibling dir."""
    candidates = [explicit, os.environ.get("T4_REPO")]
    here = Path(__file__).resolve().parent
    candidates += [str(here.parent / "terminal-bench"), str(here / "terminal-bench")]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if (path / "scripts" / "checks").is_dir() and (path / "docs" / "prompts").is_dir():
            return path
    return None


def repo_version(repo: Path) -> dict[str, str]:
    """Record exactly which policy revision produced a review."""
    info = {"path": str(repo), "describe": "unknown", "sha": "unknown", "committed_at": ""}
    for key, args in (("describe", ["describe", "--tags", "--always"]), ("sha", ["rev-parse", "HEAD"]),
                      ("committed_at", ["log", "-1", "--format=%cI"])):
        try:
            out = subprocess.run(
                ["git", "-C", str(repo), *args],
                capture_output=True, text=True, timeout=15, check=False,
            )
            if out.returncode == 0:
                info[key] = out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return info


def _script_summary(path: Path) -> str:
    """First prose line of a check script's header comment block."""
    lines = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines()[:40]:
        line = raw.strip()
        if line.startswith("#!") or line.startswith("# shellcheck"):
            continue
        if line.startswith("#"):
            text = line.lstrip("#").strip()
            if text:
                lines.append(text)
        elif lines:
            break
    return " ".join(lines)[:400]


def _documented_checks(repo: Path) -> dict[str, str]:
    """The prose under each `#### check-*` heading of the automation doc.

    The doc explains each check in prose; script header comments are often just
    "Exit on error", which told reviewers nothing.
    """
    doc = repo / "docs" / "TASK_REVIEW_AUTOMATION.md"
    if not doc.is_file():
        return {}
    text = doc.read_text(encoding="utf-8", errors="replace")
    found = {}
    # Up to the next heading, so numbered conditions under a lead-in are kept.
    for m in re.finditer(r"^#### (check-[\w-]+)[ \t]*\n(.+?)(?=^#|\Z)", text, re.M | re.S):
        prose = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", m.group(2)).replace("**", "").replace("`", "")
        found[m.group(1)] = " ".join(prose.split())
    return found


def discover_checks(repo: Path) -> list[dict[str, Any]]:
    """Every check-*.sh the clone ships, as checklist items."""
    items = []
    documented = _documented_checks(repo)
    for script in sorted((repo / "scripts" / "checks").glob("check-*.sh")):
        items.append(
            {
                "id": script.stem,
                "category": STATIC_CATEGORY,
                "criterion": script.stem.replace("check-", "").replace("-", " ").capitalize(),
                "why_it_matters": (documented.get(script.stem) or _script_summary(script)
                                   or "Enforced by benchmark CI on every push."),
                "how_to_check": f"Runs `{script.name}` from the terminal-bench clone against the task directory.",
                "applies_when": "All Terminal-Bench 4.0 task submissions.",
                "severity": "required",
                "review_mode": "auto",
                "source": "harbor-static-check",
                "script": str(script),
            }
        )
    return items


def discover_rubric(repo: Path) -> list[dict[str, Any]]:
    """The implementation rubric's criteria, as checklist items."""
    path = repo / "docs" / "prompts" / "task-implementation.toml"
    if not path.is_file():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    items = []
    for entry in data.get("criteria", []):
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        guidance = str(entry.get("guidance") or "").strip()
        items.append(
            {
                "id": f"rubric-{name.replace('_', '-')}",
                "category": RUBRIC_CATEGORY,
                "criterion": str(entry.get("description") or name),
                "why_it_matters": guidance[:600],
                "how_to_check": "Judgement call. Assessed against the benchmark's own rubric guidance.",
                "applies_when": "All Terminal-Bench 4.0 task submissions.",
                "severity": "required",
                "review_mode": "auto",
                "source": "harbor-rubric",
                "guidance": guidance,
            }
        )
    return items


# T3 rules with no T4 counterpart that still describe real submission hygiene.
# Everything else from the T3 seed is either superseded by a check script above
# or was wrong for T4 (the 1800-18000 agent timeout floor, FROM digest pinning,
# the Terminus-3-Prod project target, and treating the canary as contamination
# when T4 requires it).
LEGACY_ITEMS: list[dict[str, Any]] = [
    {
        "id": "submission-line-endings",
        "category": "Submission",
        "criterion": "Task text files use LF line endings",
        "why_it_matters": (
            "check-instruction-suffix matches the closing line byte-exactly, so a stray CR fails it "
            "even when the sentence is correct. Authoring on Windows without core.autocrlf or a "
            ".gitattributes rule is the usual cause."
        ),
        "how_to_check": "Look for CRLF in task.toml, instruction.md, README.md, Dockerfiles and scripts.",
        "applies_when": "All Terminal-Bench 4.0 task submissions.",
        "severity": "recommended",
        "review_mode": "auto",
        "source": "legacy-t3",
    },
    {
        "id": "no-privileged-docker-ops",
        "category": "Environment",
        "criterion": "Task does not require privileged Docker or unsafe container flags",
        "why_it_matters": "Privileged containers break sandbox isolation on shared runners.",
        "how_to_check": "Search task.toml, compose files, and scripts for --privileged, cap_add, or privileged: true.",
        "applies_when": "All Terminal-Bench 4.0 task submissions.",
        "severity": "required",
        "review_mode": "auto",
        "source": "legacy-t3",
    },
    {
        "id": "no-hidden-instructions-or-ai-scaffolding",
        "category": "Environment",
        "criterion": "Environment files contain no hidden instructions, solution hints, or AI-framework scaffolding",
        "why_it_matters": "Hidden prompts or scaffolding leak the answer and corrupt difficulty measurement.",
        "how_to_check": "Scan environment files for prompt text, solution hints, or agent-framework markers.",
        "applies_when": "All Terminal-Bench 4.0 task submissions.",
        "severity": "required",
        "review_mode": "auto",
        "source": "legacy-t3",
    },
    {
        "id": "no-agent-writable-ground-truth",
        "category": "Verifier",
        "criterion": "Ground truth is not read from paths the agent can modify",
        "why_it_matters": "Ground truth inside agent-writable paths is trivially overwritten for a forged pass.",
        "how_to_check": "Confirm expected values live in the verifier image or a declared artifact, not agent-writable output paths.",
        "applies_when": "All Terminal-Bench 4.0 task submissions.",
        "severity": "required",
        "review_mode": "auto",
        "source": "legacy-t3",
    },
]


def build_checklist(repo: Path) -> dict[str, Any]:
    items = discover_checks(repo) + discover_rubric(repo) + LEGACY_ITEMS
    version = repo_version(repo)
    return {
        "title": f"Terminal-Bench 4.0 Task Checklist ({version['describe']})",
        "policy": {"name": "terminal-bench", **version},
        "items": items,
    }


def checks_runnable() -> bool:
    """The shipped checks need a POSIX shell plus python3.

    On Windows, bash resolves to msys and `python3` hits the Microsoft Store
    alias, so the scripts fail for environmental reasons rather than policy
    ones. Run the checker under WSL, Linux or macOS, as the project README
    already instructs.
    """
    if sys.platform.startswith("win"):
        return False
    return shutil.which("bash") is not None and shutil.which("python3") is not None


# Retained name for callers that only ask whether a shell exists.
bash_available = checks_runnable


def _strip_crlf(root: Path) -> None:
    """A Windows checkout gives the scripts CRLF endings, which bash rejects."""
    for script in root.rglob("*.sh"):
        data = script.read_bytes()
        if b"\r\n" in data:
            script.write_bytes(data.replace(b"\r\n", b"\n"))


TEXT_SUFFIXES = {
    "", ".cfg", ".conf", ".csv", ".dockerfile", ".ini", ".js", ".json", ".jsonl",
    ".md", ".py", ".sh", ".toml", ".txt", ".yaml", ".yml",
}


def _normalise_line_endings(root: Path) -> list[str]:
    """Convert CRLF task files to LF, returning the paths that needed it."""
    changed = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\r\n" in data:
            path.write_bytes(data.replace(b"\r\n", b"\n"))
            changed.append(path.relative_to(root).as_posix())
    return changed


def run_checks(repo: Path, task_dir: Path, workspace: Path) -> dict[str, dict[str, Any]]:
    """Run every shipped check against one extracted task directory.

    Mirrors CI: a workspace holding `scripts/` from the clone and the task at
    `tasks/<name>/`, with each script invoked on that path.
    """
    if not bash_available():
        raise RuntimeError(
            "Running the Terminal-Bench check scripts needs bash and python3 on a POSIX "
            "system. Start this checker under WSL, Linux or macOS."
        )
    workspace.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo / "scripts", workspace / "scripts", dirs_exist_ok=True)
    _strip_crlf(workspace / "scripts")
    tasks_dir = workspace / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    target = tasks_dir / task_dir.name
    if not target.exists():
        shutil.copytree(task_dir, target)
    relative = f"tasks/{task_dir.name}"

    # Run checks on an LF copy; disclose any CRLF conversion separately.
    crlf_files = _normalise_line_endings(target)

    results: dict[str, dict[str, Any]] = {}
    for script in sorted((workspace / "scripts" / "checks").glob("check-*.sh")):
        try:
            proc = subprocess.run(
                ["bash", f"scripts/checks/{script.name}", relative],
                cwd=str(workspace), capture_output=True, text=True,
                timeout=CHECK_TIMEOUT_SEC, check=False,
            )
            output = (proc.stdout + proc.stderr).strip()
            passed = proc.returncode == 0
        except subprocess.TimeoutExpired:
            output, passed = f"{script.name} exceeded {CHECK_TIMEOUT_SEC}s.", None
        except OSError as exc:
            output, passed = f"{script.name} could not run: {exc}", None

        detail = "\n".join(
            line for line in output.splitlines()
            if line.strip() and not line.startswith("Checking ")
        )[:1500]
        if passed is None:
            status, evidence = "unknown", detail or "Check did not complete."
        elif passed:
            status = "satisfied"
            evidence = detail or f"{script.name} passed."
        else:
            status = "missing"
            evidence = detail or f"{script.name} failed."
        results[script.stem] = {
            "id": script.stem,
            "status": status,
            "evidence": evidence,
            "recommendation": (
                "No change needed for this check."
                if status == "satisfied"
                else f"Resolve the failure reported by `{script.name}`; it blocks CI on every push."
            ),
            "assessment_source": "harbor static check",
        }

    results["submission-line-endings"] = {
        "id": "submission-line-endings",
        "status": "partial" if crlf_files else "satisfied",
        "evidence": (
            "CRLF line endings in: " + ", ".join(crlf_files[:12])
            + (f" (+{len(crlf_files) - 12} more)" if len(crlf_files) > 12 else "")
            + ". Normalised to LF before running the checks, so the results above reflect LF content."
            if crlf_files else "All task text files use LF line endings."
        ),
        "recommendation": (
            "Convert the task files to LF before submitting; check-instruction-suffix compares bytes "
            "and a trailing CR fails it. Set core.autocrlf=input or add a .gitattributes rule."
            if crlf_files else "No change needed."
        ),
        # Ours, not one of the benchmark's gating checks: CI never sees CRLF
        # because git normalises on commit. Mislabelling it as a gate would make
        # a compliant task read as BLOCKED.
        "assessment_source": "legacy scan",
    }
    return results


# --- Panel data for the Terminal-Bench 4.0 profile ------------------------------
#
# Build T4 panels from commit history, TAXONOMY.md and check constants.


def _shell_constant(path: Path, name: str) -> str | None:
    """Read `NAME=value` out of a check script."""
    if not path.is_file():
        return None
    match = re.search(rf'^[ \t]*{re.escape(name)}=(["\']?)(.*?)\1\s*(?:#.*)?$',
                      path.read_text(encoding="utf-8", errors="replace"), re.M)
    return match.group(2).strip() if match else None


def _shell_array(path: Path, name: str) -> list[str]:
    """Read `NAME=( "a" "b" )` out of a check script."""
    if not path.is_file():
        return []
    match = re.search(rf'^[ \t]*{re.escape(name)}=\((.*?)\)',
                      path.read_text(encoding="utf-8", errors="replace"), re.M | re.S)
    return re.findall(r'"([^"]+)"', match.group(1)) if match else []


GITHUB_REPO = "https://github.com/harbor-framework/terminal-bench"


def blob_url(rel: str) -> str:
    return f"{GITHUB_REPO}/blob/main/{rel}"


@lru_cache(maxsize=256)
def last_changed(repo_str: str, rel: str) -> tuple[str, str]:
    """(date, sha) of the last commit touching `rel`, or ("", "") if unknown."""
    try:
        out = subprocess.run(
            ["git", "-C", repo_str, "log", "-1", "--date=short", "--pretty=%ad%x1f%H", "--", rel],
            capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return "", ""
    line = out.stdout.strip()
    if out.returncode != 0 or "\x1f" not in line:
        return "", ""
    date, sha = line.split("\x1f", 1)
    return date, sha


def changelog_entries(repo: Path, limit: int = 5) -> list[dict[str, str]]:
    """Dated policy-affecting commits. The benchmark publishes no changelog doc."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", f"-{max(1, min(limit, 20))}",
             "--date=short", "--pretty=%ad%x1f%s%x1f%H", "--", "docs", "scripts/checks"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    entries = []
    for line in out.stdout.strip().splitlines():
        parts = line.split("\x1f")
        if len(parts) < 3:
            continue
        date, subject, sha = parts[0], parts[1], parts[2]
        kind = "Policy" if "check" in subject.lower() or "rubric" in subject.lower() else "Docs"
        entries.append({"date": date, "type": kind, "change": subject,
                        "url": f"{GITHUB_REPO}/commit/{sha}", "sha": sha[:12]})
    return entries


def taxonomy_tables(repo: Path) -> list[dict[str, Any]]:
    """Categories and policy for T4, in the same Name | Status | date shape as the T3 portal.

    Status is measured, not asserted: a category is Open because check-task-fields
    accepts it, and a policy row is marked enforced only when the script that
    enforces it exists in this clone. Dates come from git history of the
    governing file, so "Updated" means when that source last changed.
    """
    tables: list[dict[str, Any]] = []
    taxonomy = repo / "docs" / "TAXONOMY.md"
    checks = repo / "scripts" / "checks"
    repo_str = str(repo)
    valid = _shell_array(checks / "check-task-fields.sh", "VALID_CATEGORIES")

    subs: dict[str, list[str]] = {}
    if taxonomy.is_file():
        current = None
        for raw in taxonomy.read_text(encoding="utf-8", errors="replace").splitlines():
            heading = re.match(r"^#{2,3}\s+(.+?)\s*$", raw)
            if heading and heading.group(1).strip() in valid:
                current = heading.group(1).strip()
                subs.setdefault(current, [])
                continue
            sub = re.match(r"^\s*[-*]\s+\*\*(.+?)\*\*\s*[—–-]\s*(.+)$", raw)
            if sub and current:
                subs[current].append(sub.group(1).strip())
    tax_date, tax_sha = last_changed(repo_str, "docs/TAXONOMY.md")
    headers = ["Category", "Status", "Subcategories", "Updated"]
    rows = []
    for category in valid:
        rows.append({
            "Category": category,
            "Status": "\u2705 Open",
            "Subcategories": ", ".join(subs.get(category, [])) or "open list",
            "Updated": tax_date or "unknown",
            "_links": {"Category": f"{blob_url('docs/TAXONOMY.md')}#{category.lower()}"},
        })
    if rows:
        tables.append({"title": f"Categories ({len(rows)} open domains)", "headers": headers,
                       "rows": rows, "url": blob_url("docs/TAXONOMY.md")})

    version = repo_version(repo)
    max_timeout = _shell_constant(checks / "check-task-timeout.sh", "MAX_TIMEOUT_SEC") or "unknown"
    pytest_pin = _shell_constant(checks / "check-pytest-version.sh", "CANONICAL_PYTEST") or "unknown"
    ctrf_pin = _shell_constant(checks / "check-pytest-version.sh", "CANONICAL_CTRF") or "unknown"
    required = _shell_array(checks / "check-task-fields.sh", "REQUIRED_FIELDS")
    sections = _shell_array(checks / "check-task-fields.sh", "REQUIRED_README_SECTIONS")
    slug_tokens = _shell_constant(checks / "check-task-slug.sh", "MAX_TOKENS") or "unknown"

    policy = [
        ("Canary string", "required", "Required in instruction.md, task.toml, environment/Dockerfile "
         "and every text file under solution/ and tests/", "check-canary"),
        ("Agent timeout", "required", f"Up to {max_timeout}s; every merged task uses the flat 8h value",
         "check-task-timeout"),
        ("Verifier mode", "required", 'environment_mode = "separate", top-level artifacts, tests/Dockerfile '
         "with COPY into /tests and RUN mkdir -p for artifact parents", "check-separate-verifier"),
        ("task.toml fields", "required", ", ".join(required) or "unknown", "check-task-fields"),
        ("README sections", "required", ", ".join(f"## {x}" for x in sections) or "unknown",
         "check-task-fields"),
        ("Package pins", "required", f"pytest=={pytest_pin}, pytest-json-ctrf=={ctrf_pin}; every pip/uv "
         "install pinned with ==", "check-pytest-version"),
        ("Task slug", "required", f"At most {slug_tokens} hyphen-separated tokens; "
         '[task] name = "terminal-bench/<folder>"', "check-task-slug"),
        ("Internet access", "forbidden", "allow_internet must be omitted; setting it either way fails",
         "check-no-allow-internet-true"),
        ("Platform pinning", "forbidden", "FROM --platform is rejected in any Dockerfile",
         "check-dockerfile-platform"),
        ("Bare nproc", "forbidden", "Use [environment].cpus or a fixed value; nproc --all is allowed",
         "check-nproc"),
    ]
    headers = ["Policy", "Status", "Enforced by", "Updated"]
    rows = []
    for name, kind, detail, script in policy:
        rel = f"scripts/checks/{script}.sh"
        present = (repo / rel).is_file()
        date, _ = last_changed(repo_str, rel) if present else ("", "")
        mark = "\u2705" if kind == "required" else "\U0001F6AB"
        rows.append({
            "Policy": name,
            "Status": f"{mark} {detail}" if present else f"TBA: {script} not found in this clone",
            "Enforced by": script if present else "TBA",
            "Updated": date or "unknown",
            "_links": {"Enforced by": blob_url(rel)} if present else {},
        })
    rows.append({"Policy": "Policy revision", "Status": f"\u2139\ufe0f {version['describe']}",
                 "Enforced by": version["sha"][:12], "Updated": last_changed(repo_str, ".")[0] or "unknown",
                 "_links": {"Enforced by": f"{GITHUB_REPO}/commit/{version['sha']}"}})
    tables.append({"title": f"Policies & settings (read live from {version['describe']})",
                   "headers": headers, "rows": rows, "url": blob_url("docs/TASK_REVIEW_AUTOMATION.md")})
    return tables


def source_paths(repo: Path) -> list[dict[str, str]]:
    """Which policy documents back this profile, and whether they are actually there."""
    wanted = [
        ("docs/task-template.toml", "Task template"),
        ("docs/prompts/task-implementation.toml", "Implementation rubric"),
        ("docs/TAXONOMY.md", "Taxonomy"),
        ("docs/REVIEWING.md", "Reviewing guide"),
        ("docs/TASK_REVIEW_AUTOMATION.md", "Review automation"),
        ("CONTRIBUTING.md", "Contributing guide"),
        ("scripts/checks", "Static check scripts"),
    ]
    out = []
    for rel, label in wanted:
        target = repo / rel
        out.append({
            "path": rel, "label": label,
            "state": "ok" if target.exists() else "TBA",
            "url": (f"{GITHUB_REPO}/tree/main/{rel}" if target.is_dir() else blob_url(rel)),
        })
    return out


def demo() -> None:
    """Self-check: discover policy and, if bash is present, review a real task."""
    import tempfile

    repo = repo_root()
    assert repo is not None, "no terminal-bench clone found; set T4_REPO"
    checks = discover_checks(repo)
    rubric = discover_rubric(repo)
    assert len(checks) >= 20, f"expected the shipped check scripts, found {len(checks)}"
    assert len(rubric) >= 30, f"expected the implementation rubric, found {len(rubric)}"
    checklist = build_checklist(repo)
    ids = [item["id"] for item in checklist["items"]]
    assert len(ids) == len(set(ids)), "duplicate checklist ids"
    assert checklist["policy"]["sha"] != "unknown", "policy revision must be recorded"
    print(f"policy {checklist['policy']['describe']}: "
          f"{len(checks)} checks + {len(rubric)} rubric + {len(LEGACY_ITEMS)} legacy "
          f"= {len(ids)} items")

    sample = next((p for p in sorted((repo / "tasks").iterdir()) if (p / "task.toml").is_file()), None)
    if sample is None or not checks_runnable():
        print("POSIX shell/python3 or tasks/ unavailable; skipped execution check")
        return
    with tempfile.TemporaryDirectory() as tmp:
        results = run_checks(repo, sample, Path(tmp))
    assert len(results) == len(checks) + 1, "every check plus the line-ending finding"
    failed = [k for k, v in results.items()
              if v["status"] != "satisfied" and k != "submission-line-endings"]
    # A task merged into the benchmark passes the benchmark's own checks.
    assert not failed, f"merged task {sample.name} unexpectedly failed: {failed}"
    print(f"ran {len(results)} checks against merged task '{sample.name}': all satisfied")


if __name__ == "__main__":
    demo()
