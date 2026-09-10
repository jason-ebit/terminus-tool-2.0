"""Which layer each rule belongs to, how results combine, and who may change them.

Three assessment layers, never averaged together:

    static    deterministic evaluation of objective properties. A required
              static failure is a confirmed policy failure.
    rubric    semantic judgement, usually by the model. It can flag work for a
              human; it can never establish or deny policy compliance.
    advisory  reviewer guidance and manual checks. Display only.

Everything here is pure data and pure functions so it can be tested without a
server, a model or a terminal-bench clone.
"""

from __future__ import annotations

import re
import time
from typing import Any

from policy_diff_data import POLICY_DIFF

PROFILE_T3, PROFILE_T4 = "t3", "t4"

# Only parsed fields and exact file checks belong in the T3 static gate.
# Legacy keyword scans can misread pip requirements and shell flags, so they
# remain rubric findings for a reviewer to assess.
T3_STATIC_RULES = frozenset({
    "top-level-artifacts-configured",       # task.toml, parsed
    "task-toml-required-metadata-present",  # task.toml, parsed
    "agent-timeout-range",                  # task.toml, parsed
    "verifier-isolation",                   # task.toml, parsed
    "network-mode-intentional",             # task.toml, parsed (recommended)
    "open-category",                        # task.toml, parsed
    "taxonomy-alignment",                   # task.toml, parsed
    "docker-base-images-digest-pinned",     # Dockerfile FROM lines, parsed
    "dependencies-declared",                # declaration lines, parsed
    "tests-dockerfile-present",             # exact path
    "docker-environment-present",           # exact path
})

LAYERS = ("static", "rubric", "advisory")
REQUIRED_SEVERITIES = {"required", "blocking"}


def rule_layer(profile: str, item: dict[str, Any]) -> str:
    source = item.get("source")
    if profile == PROFILE_T4:
        if source == "harbor-static-check":
            return "static"
        if source == "harbor-rubric":
            return "rubric"
        # Legacy T3 checks carried into T4 have no T4 source, so under the
        # authority hierarchy they are labelled inferences and cannot block.
        return "advisory"
    if item.get("review_mode") == "manual":
        return "advisory"
    if item.get("id") in T3_STATIC_RULES:
        return "static"
    return "rubric"


def static_outcome(status: str) -> str:
    """Static results are pass / fail / unknown / not_applicable, nothing else."""
    return {"satisfied": "pass", "not_applicable": "not_applicable",
            "missing": "fail", "partial": "fail"}.get(status, "unknown")


def rubric_outcome(status: str) -> str:
    """A rubric verdict of "missing" is a semantic concern, never a confirmed failure."""
    return {"missing": "concern"}.get(status, status if status in
                                      {"satisfied", "partial", "concern", "unknown",
                                       "not_applicable"} else "unknown")


def is_required(item: dict[str, Any]) -> bool:
    return str(item.get("severity") or "").lower() in REQUIRED_SEVERITIES


# ----------------------------------------------------------------- legacy labels

def _t4_targets(row: dict[str, str]) -> list[str]:
    return [x.strip() for x in row.get("t4_rule", "").split(",") if x.strip()]


def legacy_labels(profile: str, item_id: str) -> list[dict[str, str]]:
    """Cross-version lineage for one rule, taken only from the verified diff.

    Under T4 a rule shows the T3 rule(s) it descends from; under T3 a rule shows
    what became of it in T4. A rule with no diff entry gets no label, so the
    labels are never decorative.
    """
    if profile == PROFILE_T4:
        return [{"version": "T3", "rule": t3, "relation": row["relation"],
                 "sources": row.get("source_ids", "")}
                for t3, row in POLICY_DIFF.items() if item_id in _t4_targets(row)]
    row = POLICY_DIFF.get(item_id)
    if not row:
        return []
    targets = _t4_targets(row)
    if not targets:
        return [{"version": "T4", "rule": "", "relation": row["relation"],
                 "sources": row.get("source_ids", "")}]
    return [{"version": "T4", "rule": t, "relation": row["relation"],
             "sources": row.get("source_ids", "")} for t in targets]


# ----------------------------------------------------------------- overall state

STATE_LABELS = {
    "policy_pass": "Policy pass",
    "policy_fail": "Policy fail",
    "review_required": "Review required",
    "profile_unverified": "Profile unverified",
}


def assess(profile: str, profile_status: str, items: list[dict[str, Any]],
           results: list[dict[str, Any]], fallback_reason: str | None) -> dict[str, Any]:
    """Apply the owner's decision table to one set of results.

        required static fail     -> policy_fail
        required static unknown  -> review_required (no automatic approval)
        recommended static *     -> displayed, never blocks
        required rubric unknown  -> review_required (flag for a human)
        rubric concern / partial -> review_required
        advisory *               -> displayed only

    A rubric result can never cancel a static failure, and an advisory item can
    never create one. Under a profile that is not verified, a clean result is
    reported as profile_unverified rather than policy_pass.
    """
    by_id = {r["id"]: r for r in results}
    static = {"pass": 0, "fail": 0, "unknown": 0, "not_applicable": 0}
    rubric = {"satisfied": 0, "partial": 0, "concern": 0, "unknown": 0, "not_applicable": 0}
    advisory_findings: list[str] = []
    confirmed_failures: list[str] = []
    required_unknowns: list[str] = []
    recommended_unresolved: list[str] = []
    rubric_flags: list[str] = []
    layer_of: dict[str, str] = {}

    for item in items:
        rid = item["id"]
        result = by_id.get(rid, {"status": "unknown"})
        layer = rule_layer(profile, item)
        layer_of[rid] = layer
        status = result.get("status", "unknown")
        if layer == "static":
            outcome = static_outcome(status)
            static[outcome] += 1
            if is_required(item):
                if outcome == "fail":
                    confirmed_failures.append(rid)
                elif outcome == "unknown":
                    required_unknowns.append(rid)
            elif outcome in ("fail", "unknown"):
                recommended_unresolved.append(rid)
        elif layer == "rubric":
            outcome = rubric_outcome(status)
            rubric[outcome] += 1
            if outcome in ("concern", "partial") or (outcome == "unknown" and is_required(item)):
                rubric_flags.append(rid)
        else:
            if status not in ("satisfied", "not_applicable"):
                advisory_findings.append(rid)

    if confirmed_failures:
        state = "policy_fail"
    elif required_unknowns or rubric_flags or fallback_reason:
        state = "review_required"
    else:
        state = "policy_pass"
    if state == "policy_pass" and profile_status not in ("verified", "stable"):
        state = "profile_unverified"

    return {
        "overall_state": state,
        "overall_state_label": STATE_LABELS[state],
        "static": static,
        "rubric": rubric,
        "advisory": {"findings": len(advisory_findings),
                     "total": sum(1 for layer in layer_of.values() if layer == "advisory")},
        "confirmed_failures": confirmed_failures,
        "required_unknowns": required_unknowns,
        "recommended_unresolved": recommended_unresolved,
        "rubric_flags": rubric_flags,
        "advisory_findings": advisory_findings,
        "layer_of": layer_of,
    }


def legacy_score(items: list[dict[str, Any]], results: list[dict[str, Any]],
                 profile: str) -> dict[str, Any]:
    """The retained blended figure, clearly scoped and never used for decisions.

    Formula: over static and rubric items only (advisory excluded), ignoring
    not_applicable and unknown, satisfied = 1, partial = 0.5, and missing,
    concern or failed = 0. Reported as a percentage of resolved items.
    """
    by_id = {r["id"]: r for r in results}
    weights = {"satisfied": 1.0, "partial": 0.5, "missing": 0.0, "concern": 0.0}
    counted = []
    for item in items:
        if rule_layer(profile, item) == "advisory":
            continue
        status = by_id.get(item["id"], {}).get("status", "unknown")
        if status in weights:
            counted.append(weights[status])
    value = round(sum(counted) / len(counted) * 100) if counted else None
    return {
        "value": value,
        "counted": len(counted),
        "formula": "static + rubric items only; advisory excluded; unknown and not_applicable "
                   "excluded; satisfied = 1, partial = 0.5, missing/concern/fail = 0",
        "disclaimer": "This figure is not a policy decision and is retained for comparison only.",
    }


# ----------------------------------------------------------------- human overrides

_OVERRIDE_CHOICES = {"static": {"pass", "fail"}, "rubric": {"satisfied", "concern"},
                     "advisory": {"satisfied", "concern"}}
_STATIC_TO_STATUS = {"pass": "satisfied", "fail": "missing"}
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def _clean(value: Any, limit: int) -> str:
    return _CONTROL.sub("", str(value or "")).strip()[:limit]


def apply_overrides(profile: str, items: list[dict[str, Any]], results: list[dict[str, Any]],
                    overrides: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Let a named human resolve an `unknown` result, keeping the original on record.

    Only results that are currently unknown can be resolved, every field the
    owner asked for is required, and the original result is preserved on the
    finding. A model can never reach this path.
    """
    item_by_id = {i["id"]: i for i in items}
    out = [dict(r) for r in results]
    by_id = {r["id"]: r for r in out}
    applied: list[dict[str, Any]] = []
    for raw in overrides or []:
        rid = _clean(raw.get("id"), 200)
        item, result = item_by_id.get(rid), by_id.get(rid)
        if not item or not result:
            raise ValueError(f"Override names an unknown checklist item: {rid!r}")
        if result.get("status") != "unknown":
            raise ValueError(f"Only unknown results can be resolved by a reviewer; {rid} is "
                             f"{result.get('status')}.")
        layer = rule_layer(profile, item)
        determination = _clean(raw.get("determination"), 40).lower()
        if determination not in _OVERRIDE_CHOICES[layer]:
            raise ValueError(f"{rid}: determination must be one of "
                             f"{sorted(_OVERRIDE_CHOICES[layer])}.")
        reviewer = _clean(raw.get("reviewer"), 120)
        evidence = _clean(raw.get("evidence"), 2000)
        reason = _clean(raw.get("reason"), 500)
        if not (reviewer and evidence and reason):
            raise ValueError(f"{rid}: reviewer, evidence and reason are all required.")
        record = {
            "id": rid,
            "reviewer": reviewer,
            "original_result": result.get("status"),
            "original_source": result.get("assessment_source", "unspecified"),
            "final_determination": determination,
            "evidence": evidence,
            "reason": reason,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        result["status"] = _STATIC_TO_STATUS.get(determination, determination)
        result["assessment_source"] = f"human override ({reviewer})"
        result["evidence"] = f"{evidence} [overrode {record['original_result']}: {reason}]"
        result["override"] = record
        applied.append(record)
    return out, applied
