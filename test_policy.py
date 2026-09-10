"""Owner decisions 1-4, legacy lineage labels, human overrides and report provenance.

    python -m unittest -v test_policy.py
"""

import io
import json
import os
import unittest
import zipfile
from unittest.mock import patch

import harbor_policy as hp
import policy_diff_data as diff
import policy_model as pm
import reporting
import terminus_checklist_site as site

REPO = hp.repo_root()


def zip_of(mapping):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for name, text in mapping.items():
            z.writestr("task/" + name, text)
    return b.getvalue()


def t3_review(raw=None, llm=None):
    raw = raw or zip_of({"instruction.md": "go", "task.toml": "[agent]\ntimeout_sec = 3600\n"})
    target = {"return_value": llm} if llm else {"side_effect": RuntimeError("stub")}
    with patch.object(site, "run_ollama", **target):
        return site.review_zip(raw, site.source_supported_checklist(), "qwen2.5:3b", "t.zip", profile="t3")


# ----------------------------------------------------------------- Decision 1

class ProfileSelectionTests(unittest.TestCase):

    def test_t3_is_the_default_even_with_a_clone_present(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("T3_PROFILE", None)
            self.assertEqual(site.requested_profile(), "t3")
            self.assertEqual(site.requested_profile(None), "t3")

    def test_clone_presence_never_selects_t4(self):
        with patch.object(site.harbor_policy, "repo_root", lambda *a, **k: REPO), \
             patch.object(site.harbor_policy, "checks_runnable", lambda: True):
            os.environ.pop("T3_PROFILE", None)
            self.assertEqual(site.requested_profile(), "t3")
            self.assertEqual(site.requested_profile("auto"), "t3")

    def test_t4_is_used_only_when_named(self):
        self.assertEqual(site.requested_profile("t4"), "t4")
        with patch.dict(os.environ, {"T3_PROFILE": "t4"}):
            self.assertEqual(site.requested_profile(), "t4")

    def test_t4_is_never_reported_verified(self):
        state, reason = site.t4_status()
        self.assertIn(state, ("preview", "unavailable"))
        self.assertTrue(reason)

    def test_t4_is_unavailable_without_a_clone_and_says_why(self):
        with patch.object(site.harbor_policy, "repo_root", lambda *a, **k: None):
            state, reason = site.t4_status()
        self.assertEqual(state, "unavailable")
        self.assertIn("clone", reason.lower())

    def test_incomplete_source_manifest_stops_t4_activation(self):
        if REPO is None:
            self.skipTest("no terminal-bench clone")
        partial = [dict(s) for s in hp.source_paths(REPO)]
        partial[2]["state"] = "TBA"  # docs/TAXONOMY.md gone from the clone
        with patch.object(site.harbor_policy, "repo_root", lambda *a, **k: REPO), \
             patch.object(site.harbor_policy, "checks_runnable", lambda: True), \
             patch.object(site.harbor_policy, "source_paths", lambda repo: partial):
            state, reason = site.t4_status()
        self.assertEqual(state, "unavailable")
        self.assertIn("docs/TAXONOMY.md", reason)

    def test_unavailable_t4_disables_assessment_rather_than_downgrading(self):
        with patch.object(site.harbor_policy, "repo_root", lambda *a, **k: None):
            with self.assertRaises(RuntimeError) as ctx:
                site.review_zip(zip_of({"task.toml": "x=1"}), {}, "m", "t.zip", profile="t4")
        self.assertIn("unavailable", str(ctx.exception))

    def test_checklist_response_reports_every_profile_state(self):
        payload = site.checklist_response(profile="t3")
        self.assertEqual(payload["profile"], "t3")
        self.assertEqual(payload["profile_states"]["t3"]["status"], "stable")
        self.assertIn(payload["profile_states"]["t4"]["status"], ("preview", "unavailable"))

    def test_review_records_requested_and_actual_profile(self):
        out = t3_review()
        self.assertEqual(out["profile"], "t3")
        self.assertIn("profile_requested", out)
        self.assertIn("profile_actual: t3", out["report_text"])
        self.assertIn("profile_status: stable", out["report_text"])


# ----------------------------------------------------------------- Decision 2

class UnknownAndOverrideTests(unittest.TestCase):

    def base(self):
        # Every file-presence rule is satisfied; only task.toml is absent, so the
        # TOML-parsed static rules are unknown rather than failed.
        digest = "@sha256:" + "a" * 64
        dockerfile = f"FROM python:3.12{digest}\n"
        return t3_review(zip_of({"instruction.md": "go",
                                 "environment/Dockerfile": dockerfile,
                                 "tests/Dockerfile": dockerfile}))

    def test_required_static_unknown_is_review_required_not_failure(self):
        out = self.base()
        a = out["assessment"]
        self.assertIn("agent-timeout-range", a["required_unknowns"])
        self.assertNotIn("agent-timeout-range", a["confirmed_failures"])
        self.assertEqual(out["overall_state"], "review_required")

    def override(self, **kw):
        record = {"id": "agent-timeout-range", "determination": "pass", "reviewer": "J. Reviewer",
                  "evidence": "task.toml supplied separately shows timeout_sec = 3600",
                  "reason": "file omitted from the upload"}
        record.update(kw)
        return record

    def test_a_human_can_resolve_an_unknown_and_it_is_recorded(self):
        out = self.base()
        checklist = {"items": site.source_supported_checklist()["items"]}
        again = reporting.rerender_with_overrides(out, checklist, [self.override()])
        got = next(r for r in again["results"] if r["id"] == "agent-timeout-range")
        self.assertEqual(got["status"], "satisfied")
        self.assertTrue(got["assessment_source"].startswith("human override"))
        record = again["human_overrides"][0]
        for field in ("reviewer", "original_result", "final_determination", "evidence",
                      "timestamp", "reason"):
            self.assertTrue(record[field], field)
        self.assertEqual(record["original_result"], "unknown")
        self.assertIn("HUMAN OVERRIDES", again["report_text"])
        self.assertNotIn("agent-timeout-range", again["assessment"]["required_unknowns"])

    def test_only_unknown_results_can_be_overridden(self):
        out = t3_review(zip_of({"task.toml": "[agent]\ntimeout_sec = 99999\n"}))
        checklist = {"items": site.source_supported_checklist()["items"]}
        with self.assertRaises(ValueError):  # it is a confirmed failure, not unknown
            reporting.rerender_with_overrides(out, checklist, [self.override()])

    def test_every_override_field_is_required(self):
        out = self.base()
        checklist = {"items": site.source_supported_checklist()["items"]}
        for missing in ("reviewer", "evidence", "reason"):
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                reporting.rerender_with_overrides(out, checklist, [self.override(**{missing: ""})])

    def test_static_overrides_only_accept_pass_or_fail(self):
        out = self.base()
        checklist = {"items": site.source_supported_checklist()["items"]}
        with self.assertRaises(ValueError):
            reporting.rerender_with_overrides(out, checklist, [self.override(determination="satisfied")])

    def test_rerender_never_mutates_the_original_review(self):
        out = self.base()
        before = json.dumps(out["results"], sort_keys=True)
        checklist = {"items": site.source_supported_checklist()["items"]}
        again = reporting.rerender_with_overrides(out, checklist, [self.override()])
        self.assertEqual(json.dumps(out["results"], sort_keys=True), before)
        self.assertNotEqual(again["report_filename"], out["report_filename"])

    def test_a_model_cannot_turn_a_required_static_unknown_into_a_pass(self):
        llm = json.dumps({"results": [{"id": "agent-timeout-range", "status": "satisfied",
                                       "evidence": "looks fine", "recommendation": "none"}]})
        out = t3_review(zip_of({"instruction.md": "go"}), llm=llm)
        got = next(r for r in out["results"] if r["id"] == "agent-timeout-range")
        self.assertEqual(got["status"], "unknown")

    def test_report_endpoint_applies_overrides_and_rejects_bad_ones(self):
        from test_resilience import make_handler, response_of
        out = self.base()
        checklist = {"items": site.source_supported_checklist()["items"]}
        for overrides, expected in (([self.override()], 200),
                                    ([self.override(reviewer="")], 400)):
            body = json.dumps({"review": out, "checklist": checklist, "overrides": overrides}).encode()
            h = make_handler("POST", "/api/report", body=body,
                             headers={"Content-Length": str(len(body)),
                                      "Content-Type": "application/json"})
            h.do_POST()
            status, payload = response_of(h)
            self.assertEqual(status, expected)
            if expected == 200:
                self.assertEqual(len(payload["human_overrides"]), 1)


# ----------------------------------------------------------------- Decision 3

class ScoringPresentationTests(unittest.TestCase):

    def test_advisory_findings_never_enter_the_legacy_score(self):
        out = t3_review()
        advisory = {r["id"] for r in out["results"] if r["layer"] == "advisory"}
        self.assertTrue(advisory)
        self.assertEqual(out["legacy_score"]["counted"],
                         sum(1 for r in out["results"] if r["layer"] != "advisory"
                             and r["status"] in ("satisfied", "partial", "missing", "concern")))

    def test_legacy_score_is_labelled_and_documented(self):
        text = t3_review()["report_text"]
        self.assertIn("Legacy experimental score:", text)
        self.assertIn("This figure is not a policy decision and is retained for comparison only.", text)
        self.assertIn("Formula:", text)

    def test_unknown_is_reported_separately_from_failure(self):
        text = t3_review(zip_of({"instruction.md": "go"}))["report_text"]
        self.assertIn("Required unknowns (need evidence):", text)
        self.assertIn("Confirmed failures (required static):", text)
        self.assertIn("never a confirmed failure", text)

    def test_the_legacy_score_does_not_decide_the_state(self):
        # a high legacy score with one required static failure is still policy_fail
        out = t3_review(zip_of({"task.toml": "[agent]\ntimeout_sec = 99999\n"}))
        self.assertEqual(out["overall_state"], "policy_fail")
        self.assertIn("agent-timeout-range", out["assessment"]["confirmed_failures"])


# ----------------------------------------------------------------- Decision 4

class ModelProvenanceTests(unittest.TestCase):

    def test_fallback_report_records_model_and_reason(self):
        out = t3_review()
        text = out["report_text"]
        for field in ("model_requested: qwen2.5:3b", "model_tag: 3b", "prompt_version: t3-review/",
                      "prompt_template_sha256:", "policy_sha256:", "source_manifest_sha256:",
                      "assessment_mode: deterministic-fallback", "fallback_reason: RuntimeError",
                      "duration_sec:"):
            self.assertIn(field, text)
        self.assertEqual(out["model_digest"], "not called")

    def test_actual_model_is_taken_from_the_ollama_response(self):
        class FakeResponse:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return self.body

        def fake_urlopen(request, timeout=None):
            if hasattr(request, "full_url") and request.full_url.endswith("/api/generate"):
                return FakeResponse(json.dumps({"model": "qwen2.5:3b", "response": '{"results": []}',
                                                "eval_count": 7}).encode())
            return FakeResponse(json.dumps({"models": [{"name": "qwen2.5:3b",
                                                        "digest": "abc123"}]}).encode())
        with patch.object(site.urllib.request, "urlopen", fake_urlopen):
            raw = zip_of({"instruction.md": "go"})
            out = site.review_zip(raw, site.source_supported_checklist(), "qwen2.5:3b", "t.zip",
                                  profile="t3")
        self.assertEqual(out["model_actual"], "qwen2.5:3b")
        self.assertEqual(out["model_digest"], "abc123")
        self.assertEqual(out["review_mode"], "llm-assisted")

    def test_default_model_is_unchanged(self):
        html = (site.WEB_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("qwen2.5:3b", html)
        self.assertNotIn("qwen2.5:7b", html)


# ----------------------------------------------------------------- Legacy labels

class LegacyLabelTests(unittest.TestCase):
    """Cross-version labels must be measured lineage, never decoration."""

    T3_IDS = {i["id"] for i in site.source_supported_checklist()["items"]}

    def test_every_t3_rule_has_a_recorded_fate(self):
        for rid in self.T3_IDS:
            labels = pm.legacy_labels("t3", rid)
            self.assertTrue(labels, rid)
            self.assertIn(labels[0]["relation"],
                          {"unchanged", "modified", "replaced", "removed", "split", "merged", "unclear"})

    def test_t4_labels_point_back_through_the_diff(self):
        if REPO is None:
            self.skipTest("no terminal-bench clone")
        t4_ids = {i["id"] for i in hp.build_checklist(REPO)["items"]}
        for rid in t4_ids:
            for label in pm.legacy_labels("t4", rid):
                self.assertIn(label["rule"], self.T3_IDS, rid)
                self.assertIn(rid, diff.POLICY_DIFF[label["rule"]]["t4_rule"], rid)

    def test_t3_labels_point_at_real_t4_rules(self):
        if REPO is None:
            self.skipTest("no terminal-bench clone")
        t4_ids = {i["id"] for i in hp.build_checklist(REPO)["items"]}
        for rid in self.T3_IDS:
            for label in pm.legacy_labels("t3", rid):
                if label["rule"]:
                    self.assertIn(label["rule"], t4_ids, rid)

    def test_mapped_labels_carry_their_sources(self):
        for rid in self.T3_IDS:
            for label in pm.legacy_labels("t3", rid):
                if label["relation"] in {"unchanged", "modified", "replaced", "split", "merged"}:
                    self.assertTrue(label["sources"], rid)

    def test_canary_lineage_is_the_verified_inversion(self):
        self.assertEqual(pm.legacy_labels("t4", "check-canary"),
                         [{"version": "T3", "rule": "no-canary-strings", "relation": "replaced",
                           "sources": "t4-review-automation,t4-task-template"}])

    def test_new_t4_rules_carry_no_invented_ancestry(self):
        for rid, _, _ in diff.NEW_T4_RULES:
            self.assertEqual(pm.legacy_labels("t4", rid), [], rid)

    def test_a_rule_is_never_both_new_and_a_descendant(self):
        # This caught eight contradictions in the diff data while it was being built.
        targets = {t.strip() for row in diff.POLICY_DIFF.values()
                   for t in row["t4_rule"].split(",") if t.strip()}
        self.assertEqual([rid for rid, _, _ in diff.NEW_T4_RULES if rid in targets], [])

    def test_removed_t3_rule_shows_no_t4_counterpart(self):
        label = pm.legacy_labels("t3", "docker-base-images-digest-pinned")
        self.assertEqual(label[0]["relation"], "removed")
        self.assertEqual(label[0]["rule"], "")

    def test_labels_reach_the_checklist_and_the_report(self):
        items = site.checklist_response(profile="t3")["checklist"]["items"]
        self.assertTrue(all("lineage" in i and "layer" in i for i in items))
        text = t3_review()["report_text"]
        self.assertIn("Lineage: T4 check-canary (replaced)", text)


if __name__ == "__main__":
    unittest.main()
