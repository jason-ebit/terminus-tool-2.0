"""Milestone E: policy-migration fixtures and cross-profile isolation.

    python -m unittest -v test_migration.py

The T4 half needs bash, python3 and a terminal-bench clone (WSL, Linux or macOS)
and is skipped, not faked, elsewhere.
"""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "fixtures"))

import harbor_policy as hp  # noqa: E402
import run_migration_fixtures as rf  # noqa: E402
import terminus_checklist_site as site  # noqa: E402

T4_READY = site.t4_status()[0] != "unavailable"
FIXTURES = {m["fixture"]: m for m in rf.fixtures()}
T3_IDS = {i["id"] for i in site.source_supported_checklist()["items"]}


class FixtureMetadataTests(unittest.TestCase):

    def test_both_migration_directions_exist(self):
        directions = {m["direction"] for m in FIXTURES.values()}
        self.assertIn("passes T3 static gate, fails T4 static gate", directions)
        self.assertIn("fails T3 static gate, passes T4 static gate", directions)

    def test_every_fixture_rule_is_sourced_on_both_sides(self):
        for name, meta in FIXTURES.items():
            for key, rule in meta["rules"].items():
                with self.subTest(fixture=name, rule=key):
                    self.assertIn(rule["t3_rule"], T3_IDS)
                    self.assertTrue(rule["t3_excerpt"] and rule["t4_excerpt"])
                    self.assertIn(rule["t3_source"].split(",")[0], meta["sources"])
                    self.assertIn(rule["t4_source"].split(",")[0], meta["sources"])
            for source in meta["sources"].values():
                self.assertRegex(source["sha256_at_capture"], r"^[0-9a-f]{64}$")

    def test_fixture_rules_are_recorded_differences_in_the_policy_diff(self):
        import policy_diff_data as diff
        for meta in FIXTURES.values():
            for rule in meta["rules"].values():
                row = diff.POLICY_DIFF[rule["t3_rule"]]
                self.assertIn(rule["t4_rule"], row["t4_rule"])
                self.assertNotEqual(row["relation"], "unchanged")

    def test_fixture_files_are_lf_only(self):
        for path in (HERE / "fixtures" / "migration").rglob("*"):
            if path.is_file():
                self.assertNotIn(b"\r\n", path.read_bytes(), path.name)


class T3MigrationTests(unittest.TestCase):
    """T3 runs anywhere."""

    def test_expected_t3_outcome_for_each_fixture(self):
        for name, meta in FIXTURES.items():
            with self.subTest(fixture=name):
                out = rf.review(name, "t3")
                expected = meta["expected"]["t3"]
                statuses = {r["id"]: r["status"] for r in out["results"]}
                self.assertEqual(out["assessment"]["confirmed_failures"], expected["confirmed_failures"])
                for rule, status in expected["rule_outcomes"].items():
                    self.assertEqual(statuses[rule], status, rule)

    def test_new_t4_rules_are_never_applied_under_t3(self):
        for name in FIXTURES:
            ids = {r["id"] for r in rf.review(name, "t3")["results"]}
            self.assertEqual(ids, T3_IDS)
            repo = hp.repo_root()
            if repo is not None:
                # By identity, not prefix: T3 has its own "rubric-or-evaluation-notes-present".
                t4_only = {i["id"] for i in hp.build_checklist(repo)["items"]} - T3_IDS
                self.assertFalse(ids & t4_only)

    def test_same_task_and_profile_give_the_same_static_result(self):
        for name in FIXTURES:
            first, second = rf.review(name, "t3"), rf.review(name, "t3")
            static = lambda o: {r["id"]: r["status"] for r in o["results"] if r["layer"] == "static"}
            self.assertEqual(static(first), static(second))

    def test_profile_is_recorded_in_the_exported_report(self):
        out = rf.review("t4-marker-gap", "t3")
        self.assertIn("profile_actual: t3", out["report_text"])


@unittest.skipUnless(T4_READY, "Terminus 4 needs bash, python3 and a terminal-bench clone")
class T4MigrationTests(unittest.TestCase):

    def test_expected_t4_outcome_for_each_fixture(self):
        for name, meta in FIXTURES.items():
            with self.subTest(fixture=name):
                out = rf.review(name, "t4")
                expected = meta["expected"]["t4"]
                statuses = {r["id"]: r["status"] for r in out["results"]}
                self.assertEqual(out["assessment"]["confirmed_failures"], expected["confirmed_failures"])
                for rule, status in expected["rule_outcomes"].items():
                    self.assertEqual(statuses[rule], status, rule)

    def test_each_fixture_isolates_exactly_its_verified_rule(self):
        """Everything else passes both static gates, so the difference has one cause."""
        for name, meta in FIXTURES.items():
            for profile in ("t3", "t4"):
                with self.subTest(fixture=name, profile=profile):
                    out = rf.review(name, profile)
                    self.assertEqual(out["assessment"]["static"]["fail"],
                                     len(meta["expected"][profile]["confirmed_failures"]))
                    self.assertEqual(out["assessment"]["static"]["unknown"], 0)

    def test_removed_t3_rules_are_never_applied_under_t4(self):
        for name in FIXTURES:
            ids = {r["id"] for r in rf.review(name, "t4")["results"]}
            self.assertFalse(ids & {"agent-timeout-range", "no-canary-strings",
                                    "docker-base-images-digest-pinned", "terminus-3-project-target"})

    def test_same_task_and_profile_give_the_same_static_result_under_t4(self):
        first, second = rf.review("t3-timeout-gap", "t4"), rf.review("t3-timeout-gap", "t4")
        static = lambda o: {r["id"]: r["status"] for r in o["results"] if r["layer"] == "static"}
        self.assertEqual(static(first), static(second))

    def test_lineage_labels_explain_the_measured_divergence(self):
        """A lineage label is a claim. On each fixture the rule pair whose outcome
        actually flips between profiles must label each other with the same
        non-"unchanged" relation, so the label is checked against behaviour."""
        for name, meta in FIXTURES.items():
            t3 = {r["id"]: r for r in rf.review(name, "t3")["results"]}
            t4 = {r["id"]: r for r in rf.review(name, "t4")["results"]}
            for rule in meta["rules"].values():
                with self.subTest(fixture=name, rule=rule["t3_rule"]):
                    old, new = t3[rule["t3_rule"]], t4[rule["t4_rule"]]
                    self.assertNotEqual(old["status"] == "satisfied", new["status"] == "satisfied",
                                        "fixture no longer shows the divergence it was built for")
                    old_to_new = [l for l in old["lineage"] if l["rule"] == rule["t4_rule"]]
                    new_to_old = [l for l in new["lineage"] if l["rule"] == rule["t3_rule"]]
                    self.assertEqual(len(old_to_new), 1)
                    self.assertEqual(len(new_to_old), 1)
                    self.assertEqual(old_to_new[0]["relation"], new_to_old[0]["relation"])
                    self.assertNotEqual(old_to_new[0]["relation"], "unchanged")

    def test_t4_report_records_preview_status_and_profile(self):
        out = rf.review("t4-marker-gap", "t4")
        self.assertIn("profile_actual: t4", out["report_text"])
        self.assertIn("profile_status: preview", out["report_text"])
        self.assertNotIn("profile_status: verified", out["report_text"])


class T3BaselineComparisonTests(unittest.TestCase):
    """Per-rule T3 results must match the pre-change capture exactly."""

    def test_t3_rule_results_match_the_2_4_baseline(self):
        before_path = HERE / "baseline-fixtures-before.json"
        if not before_path.is_file():
            self.skipTest("no baseline capture")
        import baseline_capture as bc
        before = json.loads(before_path.read_text(encoding="utf-8"))
        after = bc.capture()
        changes = [c for c in bc.diff(before, after) if c.startswith("t3 ")]
        self.assertEqual(changes, [], "\n".join(changes))


if __name__ == "__main__":
    unittest.main()
