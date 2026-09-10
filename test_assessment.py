"""Offline regressions: python -m unittest -v test_assessment.py"""
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
import zipfile
from unittest.mock import patch

import assessment as a
import harbor_policy as hp
import terminus_checklist_site as site


def inventory(mapping):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        for p, text in mapping.items():
            z.writestr('task/' + p, text)
    return b.getvalue(), site.zip_inventory(b.getvalue())


def force_t3():
    """Pin the legacy T3 path: T4 mode activates whenever a terminal-bench clone is found."""
    return patch.object(site.harbor_policy, 'repo_root', lambda *a, **k: None)


class AssessmentTests(unittest.TestCase):
    def test_report_complete_named_and_score_preserved(self):
        import hashlib
        raw, inv = inventory({'environment/Dockerfile': 'FROM python:3.12'})
        checklist = site.source_supported_checklist()
        with patch.object(site, 'run_ollama', return_value='{"results":[]}'):
            with force_t3():
                reviewed = site.review_zip(raw, checklist, 'example-model', '../foodstuff-beta-activity.zip')
        expected = site.normalize_review({'results': []}, checklist, inv)
        self.assertEqual(reviewed['score'], expected['score'])
        self.assertEqual(reviewed['report_metadata']['zip_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertTrue(reviewed['report_filename'].startswith('foodstuff-beta-activity-review-'))
        self.assertNotIn('/', reviewed['report_filename'])
        for item in checklist['items']:
            self.assertEqual(reviewed['report_text'].count('ID: ' + item['id'] + '\n'), 1)
        self.assertEqual(sum(reviewed['status_counts'].values()), len(checklist['items']))
        self.assertIn('Assessment source: structured/static check', reviewed['report_text'])
        self.assertIn('example-model', reviewed['report_text'])

    def test_report_discloses_fallback(self):
        raw, _ = inventory({'README.md': 'example'})
        with patch.object(site, 'run_ollama', side_effect=TimeoutError()):
            with force_t3():
                reviewed = site.review_zip(raw, site.source_supported_checklist(), 'slow-model', 'example.zip')
        self.assertIn('fallback_reason: TimeoutError', reviewed['report_text'])
        self.assertIn('assessment_mode: deterministic-fallback', reviewed['report_text'])
        self.assertIn('llm_succeeded: False', reviewed['report_text'])

    def test_timeout_sec_and_correct_section(self):
        _, inv = inventory({'task.toml': '[agent]\ntimeout_sec=28800\n[verifier]\ntimeout_sec=1800'})
        self.assertEqual(a.structured_checks(inv)['agent-timeout-range']['status'], 'missing')

    def test_complete_toml_not_preview(self):
        _, inv = inventory({'task.toml': '# filler\n' * 800 + '[agent]\ntimeout_sec=1800'})
        self.assertEqual(a.structured_checks(inv)['agent-timeout-range']['status'], 'satisfied')
        self.assertTrue(inv['model_excerpts_limited'])

    def test_nested_artifacts_are_not_top_level(self):
        _, inv = inventory({'task.toml': '[metadata]\nartifacts=["/app/out"]'})
        self.assertEqual(a.structured_checks(inv)['top-level-artifacts-configured']['status'], 'missing')

    def test_invalid_toml_unknown(self):
        _, inv = inventory({'task.toml': 'broken=['})
        self.assertEqual(a.structured_checks(inv)['agent-timeout-range']['status'], 'unknown')

    def test_category_not_taken_from_readme(self):
        _, inv = inventory({'task.toml': '[metadata]\ncategory="Unsupported"', 'README.md': 'Science'})
        self.assertEqual(a.structured_checks(inv)['open-category']['status'], 'missing')

    def test_readme_does_not_waive_t3_metadata(self):
        _, inv = inventory({'task.toml': '[metadata]\ncategory="Science"', 'README.md': 'solution_explanation verification_explanation relevant_experience'})
        self.assertEqual(a.structured_checks(inv)['task-toml-required-metadata-present']['status'], 'partial')

    def test_env_scope(self):
        _, inv = inventory({'environment/Dockerfile': 'ENV PATH="/bin:$PATH"', 'tests/test.sh': 'pytest\nif [ $? -eq 0 ]; then echo 1; fi'})
        self.assertEqual(a.env_check(inv)['status'], 'not_applicable')

    def test_one_default_does_not_cover_all_variables(self):
        _, inv = inventory({'tests/test.sh': 'echo "${FIRST:-yes}" "$SECOND"'})
        self.assertEqual(a.env_check(inv)['status'], 'unknown')
        self.assertIn('SECOND', a.env_check(inv)['evidence'])

    def test_dependencies_in_conda_dockerfile(self):
        _, inv = inventory({'environment/Dockerfile': 'FROM image\nRUN mamba install -y scipy'})
        self.assertEqual(a.dependency_check(inv)['status'], 'satisfied')

    def test_solver_uv_dependencies(self):
        _, inv = inventory({'solution/solve.sh': 'uv run --with pandas==2.2.3 python solve.py'})
        self.assertEqual(a.dependency_check(inv)['status'], 'satisfied')

    def test_missing_declarations_unknown_not_invented_failure(self):
        _, inv = inventory({'environment/app.py': 'print("hello")'})
        self.assertEqual(a.dependency_check(inv)['status'], 'unknown')

    def test_digest_remains_required(self):
        _, inv = inventory({'environment/Dockerfile': 'FROM python:3.12-slim'})
        self.assertEqual(a.digest_check(inv)['status'], 'missing')

    def test_digest_and_internal_stage(self):
        _, inv = inventory({'environment/Dockerfile': 'FROM python@sha256:' + 'a'*64 + ' AS base\nFROM base\n'})
        self.assertEqual(a.digest_check(inv)['status'], 'satisfied')

    def test_negative_run_not_proven_by_prose(self):
        _, inv = inventory({'README.md': 'negative test should fail; oracle correct'})
        self.assertEqual(a.assessments(inv)['rejects-wrong-solution']['status'], 'unknown')

    def test_llm_cannot_override_structured_evidence(self):
        raw, _ = inventory({'task.toml': '[agent]\ntimeout_sec=28800', 'environment/Dockerfile': 'FROM python:3.12'})
        with patch.object(site, 'run_ollama', return_value='{"results":[{"id":"agent-timeout-range","status":"satisfied"}]}'):
            with force_t3():
                reviewed = site.review_zip(raw, site.source_supported_checklist(), 'fake')
        results = {r['id']: r for r in reviewed['results']}
        self.assertEqual(results['agent-timeout-range']['status'], 'missing')
        self.assertEqual(reviewed['review_mode'], 'llm-assisted')

    def test_fallback_visible_and_semantics_unknown(self):
        raw, _ = inventory({'solution/solve.sh': 'echo yes', 'tests/test.sh': 'echo 1'})
        with patch.object(site, 'run_ollama', side_effect=RuntimeError('offline')):
            with force_t3():
                reviewed = site.review_zip(raw, site.source_supported_checklist(), 'fake')
        results = {r['id']: r for r in reviewed['results']}
        self.assertEqual(reviewed['review_mode'], 'deterministic-fallback')
        self.assertEqual(results['oracle-solution-correct']['status'], 'unknown')
        self.assertEqual(results['semantic-verifier-present']['status'], 'unknown')
        self.assertTrue(reviewed['required_findings'])


class OllamaTransportTests(unittest.TestCase):
    """The prompt must not be silently truncated by Ollama's 4096-token default."""

    def test_num_ctx_covers_a_full_review_prompt(self):
        # A real T3 review prompt for a small task runs to roughly 12k tokens.
        prompt = 'x' * 48_000
        ctx = site.required_context_tokens(prompt)
        self.assertGreater(ctx, len(prompt) // 4, 'num_ctx must exceed the prompt token estimate')
        self.assertLessEqual(ctx, site.OLLAMA_MAX_CTX)

    def test_num_ctx_has_a_floor_and_a_ceiling(self):
        self.assertEqual(site.required_context_tokens('hi'), 8192)
        self.assertEqual(site.required_context_tokens('x' * 10_000_000), site.OLLAMA_MAX_CTX)

    def test_request_asks_for_json_and_sets_context(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"response": "{}"}'

        def fake_urlopen(request, timeout=None):
            captured.update(json.loads(request.data.decode('utf-8')))
            return FakeResponse()

        with patch.object(site.urllib.request, 'urlopen', fake_urlopen):
            site.run_ollama('a prompt', 'example-model')
        self.assertEqual(captured['format'], 'json')
        self.assertFalse(captured['stream'])
        self.assertIn('num_ctx', captured['options'])

    def test_truncated_generation_is_an_error_not_a_silent_partial(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"response": "partial", "done_reason": "length"}'

        with patch.object(site.urllib.request, 'urlopen', lambda *a, **k: FakeResponse()):
            with self.assertRaises(RuntimeError):
                site.run_ollama('p', 'm')


class TermMatchingTests(unittest.TestCase):
    """Full-file scanning must not fire on longer identifiers."""

    def test_declaring_zero_gpus_is_not_a_gpu_requirement(self):
        self.assertFalse(site.term_present('gpu', 'cpus = 2\ngpus = 0\n'))
        self.assertTrue(site.term_present('gpu', 'requires a gpu at runtime'))

    def test_python_str_replace_is_not_a_REPLACE_placeholder(self):
        self.assertFalse(site.term_present('REPLACE', 'value.replace(",", ".")'))
        self.assertTrue(site.term_present('REPLACE', 'author = "REPLACE"'))

    def test_os_environ_is_not_a_committed_dotenv(self):
        self.assertFalse(site.term_present('.env', 'os.environ.get("APP_ROOT")'))
        self.assertTrue(site.term_present('.env', 'task/.env'))

    def test_absence_scan_reads_stored_content_not_the_600_char_preview(self):
        filler = '# padding\n' * 200
        _, inv = inventory({'tests/test_it.py': filler + 'time.sleep(5)\n'})
        result = site.check_absent_term(
            inv, 'deterministic-tests', ('time.sleep',), 'clean', 'fix it')
        self.assertEqual(result['status'], 'partial')


class VerdictPrecedenceTests(unittest.TestCase):
    def test_structured_unknown_does_not_erase_a_resolved_verdict(self):
        _, inv = inventory({'instruction.md': 'do the thing'})
        checklist = site.source_supported_checklist()
        llm = {'results': [{'id': 'network-mode-intentional', 'status': 'satisfied',
                            'evidence': 'network_mode = "no-network"',
                            'recommendation': 'none', 'assessment_source': 'LLM'}]}
        out = site.normalize_review(llm, checklist, inv)
        got = next(r for r in out['results'] if r['id'] == 'network-mode-intentional')
        # 2.5: network-mode-intentional is a static rule. With no task.toml its
        # parsed result is unknown, and a model may not turn that into a pass.
        self.assertEqual(got['status'], 'unknown')

    def test_structured_unknown_still_yields_to_evidence_on_non_static_rules(self):
        _, inv = inventory({'instruction.md': 'do the thing'})
        checklist = site.source_supported_checklist()
        llm = {'results': [{'id': 'rejects-wrong-solution', 'status': 'satisfied',
                            'evidence': 'x', 'recommendation': 'none', 'assessment_source': 'LLM'}]}
        out = site.normalize_review(llm, checklist, inv)
        got = next(r for r in out['results'] if r['id'] == 'rejects-wrong-solution')
        self.assertEqual(got['status'], 'satisfied')  # rubric-layer rule, old behaviour kept

    def test_applies_when_exclusion_survives_the_fallback_blanket(self):
        _, inv = inventory({'instruction.md': 'plain task'})
        checklist = site.source_supported_checklist()
        base = {'results': [{'id': 'reward-file-zero-on-failure', 'status': 'not_applicable',
                             'evidence': 'no reward file', 'recommendation': 'none'}]}
        out = site.normalize_review(base, checklist, inv)
        got = next(r for r in out['results'] if r['id'] == 'reward-file-zero-on-failure')
        self.assertEqual(got['status'], 'not_applicable')

    def test_objective_file_facts_outrank_a_hallucinating_model(self):
        raw, _ = inventory({'tests/Dockerfile': 'FROM python:3.12', 'instruction.md': 'go'})
        checklist = site.source_supported_checklist()
        bogus = json.dumps({'summary': '', 'results': [
            {'id': 'tests-dockerfile-present', 'status': 'missing',
             'evidence': 'The ZIP does not contain a tests/Dockerfile file.',
             'recommendation': 'add one'}]})
        with patch.object(site, 'run_ollama', return_value=bogus):
            with force_t3():
                out = site.review_zip(raw, checklist, 'm', 'task.zip')
        got = next(r for r in out['results'] if r['id'] == 'tests-dockerfile-present')
        self.assertEqual(out['review_mode'], 'llm-assisted')
        self.assertEqual(got['status'], 'satisfied')

    def test_model_cannot_assert_semantic_noncompliance(self):
        raw, _ = inventory({'instruction.md': 'a real domain task'})
        checklist = site.source_supported_checklist()
        bogus = json.dumps({'summary': '', 'results': [
            {'id': 'domain-grounded-task', 'status': 'missing',
             'evidence': 'not domain grounded', 'recommendation': 'fix'}]})
        with patch.object(site, 'run_ollama', return_value=bogus):
            with force_t3():
                out = site.review_zip(raw, checklist, 'm', 'task.zip')
        got = next(r for r in out['results'] if r['id'] == 'domain-grounded-task')
        # 2.5: a model "missing" is a semantic concern for a human: neither a
        # confirmed failure nor "unknown" (which means insufficient evidence).
        self.assertEqual(got['status'], 'concern')
        self.assertIn('domain-grounded-task', out['assessment']['rubric_flags'])
        self.assertNotIn('domain-grounded-task', out['assessment']['confirmed_failures'])


class ScoringTests(unittest.TestCase):
    def test_unknown_lowers_coverage_not_compliance(self):
        _, inv = inventory({'instruction.md': 'go'})
        checklist = site.source_supported_checklist()
        out = site.normalize_review({'results': []}, checklist, inv)
        scored = [r for r in out['results']
                  if r['status'] != 'not_applicable' and r['review_mode'] != 'manual']
        resolved = [r for r in scored if r['status'] != 'unknown']
        self.assertEqual(out['applicable_count'], len(scored))
        self.assertEqual(out['resolved_count'], len(resolved))
        self.assertEqual(out['coverage'], round(len(resolved) / len(scored) * 100))

    def test_legacy_score_arithmetic_is_unchanged(self):
        _, inv = inventory({'instruction.md': 'go'})
        checklist = site.source_supported_checklist()
        out = site.normalize_review({'results': []}, checklist, inv)
        weights = {'satisfied': 1.0, 'partial': 0.5, 'missing': 0.0, 'unknown': 0.0}
        scored = [r for r in out['results']
                  if r['status'] != 'not_applicable' and r['review_mode'] != 'manual']
        self.assertEqual(out['score'],
                         round(sum(weights[r['status']] for r in scored) / len(scored) * 100))


class RobustnessTests(unittest.TestCase):
    def test_oversized_text_file_does_not_abort_the_review(self):
        raw, inv = inventory({'instruction.md': 'go', 'logs/run.txt': 'x' * (2 * 1024 * 1024 + 10)})
        entry = next(f for f in inv['files'] if f['path'].endswith('run.txt'))
        self.assertIn('read_error', entry)
        self.assertTrue(any(f['path'].endswith('instruction.md') for f in inv['files']))


class PolicyIntegrityTests(unittest.TestCase):
    def test_seed_checklist_matches_the_original_t3_contract(self):
        items = site.source_supported_checklist()['items']
        self.assertEqual(len(items), 49)
        self.assertEqual(sum(1 for i in items if i.get('review_mode', 'auto') == 'manual'), 11)

    def test_objective_and_semantic_sets_are_disjoint_and_real(self):
        ids = {i['id'] for i in site.source_supported_checklist()['items']}
        self.assertTrue(a.OBJECTIVE_ITEMS <= ids)
        self.assertTrue(a.SEMANTIC_ITEMS <= ids)
        self.assertEqual(a.OBJECTIVE_ITEMS & a.SEMANTIC_ITEMS, set())


class HarborPolicyTests(unittest.TestCase):
    """Policy is read from the terminal-bench clone, never hardcoded here."""

    @classmethod
    def setUpClass(cls):
        cls.repo = hp.repo_root()
        if cls.repo is None:
            raise unittest.SkipTest('no terminal-bench clone found; set T4_REPO')

    def test_checklist_is_discovered_not_hardcoded(self):
        checks = hp.discover_checks(self.repo)
        rubric = hp.discover_rubric(self.repo)
        self.assertGreaterEqual(len(checks), 20)
        self.assertGreaterEqual(len(rubric), 30)
        # Every static item must name a real script on disk.
        for item in checks:
            self.assertTrue(Path(item['script']).is_file(), item['id'])

    def test_policy_revision_is_recorded(self):
        checklist = hp.build_checklist(self.repo)
        self.assertNotEqual(checklist['policy']['sha'], 'unknown')
        self.assertIn('terminal-bench', checklist['policy']['name'])

    def test_checklist_ids_are_unique(self):
        ids = [i['id'] for i in hp.build_checklist(self.repo)['items']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_retired_t3_rules_are_gone(self):
        """These were wrong for T4 and must not come back."""
        ids = {i['id'] for i in hp.build_checklist(self.repo)['items']}
        for retired in ('agent-timeout-range', 'docker-base-images-digest-pinned',
                        'terminus-3-project-target', 'no-canary-strings',
                        'no-gpu-requirement'):
            self.assertNotIn(retired, ids, f'{retired} is not a T4 rule')

    def test_canary_polarity_is_inverted_for_t4(self):
        """T3 treated the canary as contamination; T4 requires it."""
        ids = {i['id'] for i in hp.build_checklist(self.repo)['items']}
        self.assertIn('check-canary', ids)

    def test_static_checks_explain_themselves_from_the_automation_doc(self):
        """Script header comments ("Exit on error") are not an explanation."""
        by_id = {i['id']: i for i in hp.discover_checks(self.repo)}
        self.assertIn('training data contamination', by_id['check-canary']['why_it_matters'])
        self.assertIn('environment_mode', by_id['check-separate-verifier']['why_it_matters'])
        for item in by_id.values():
            self.assertNotIn('Exit on error', item['why_it_matters'], item['id'])
            self.assertNotIn('`', item['why_it_matters'], item['id'])


class T4ExtractionTests(unittest.TestCase):
    def test_finds_the_task_root_inside_a_wrapper_directory(self):
        raw, _ = inventory({'task.toml': 'x = 1', 'tests/test.sh': 'echo hi'})
        with tempfile.TemporaryDirectory() as tmp:
            found = site.extract_task_dir(raw, Path(tmp))
        self.assertEqual(found.name, 'task')

    def test_rejects_a_zip_with_no_task_toml(self):
        raw, _ = inventory({'README.md': 'nothing here'})
        with tempfile.TemporaryDirectory() as tmp:
            # A clear validation error (HTTP 400), not a server fault.
            with self.assertRaises(site.ArchiveRejected):
                site.extract_task_dir(raw, Path(tmp))

    def test_refuses_path_traversal(self):
        b = io.BytesIO()
        with zipfile.ZipFile(b, 'w') as z:
            z.writestr('../escape/task.toml', 'x = 1')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(site.ArchiveRejected):
                site.extract_task_dir(b.getvalue(), Path(tmp))


class T4CheckExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = hp.repo_root()
        if cls.repo is None or not hp.bash_available():
            raise unittest.SkipTest('needs a terminal-bench clone and bash')

    def test_a_merged_benchmark_task_passes_its_own_checks(self):
        sample = next(p for p in sorted((self.repo / 'tasks').iterdir())
                      if (p / 'task.toml').is_file())
        with tempfile.TemporaryDirectory() as tmp:
            results = hp.run_checks(self.repo, sample, Path(tmp))
        failed = [k for k, v in results.items()
                  if v['status'] != 'satisfied' and k != 'submission-line-endings']
        self.assertEqual(failed, [], f'{sample.name} failed its own benchmark checks')

    def test_crlf_is_normalised_and_reported_not_silently_failed(self):
        """A Windows checkout fails 65 of 66 merged tasks on byte-exact checks."""
        sample = next(p for p in sorted((self.repo / 'tasks').iterdir())
                      if (p / 'task.toml').is_file())
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / 'crlf' / sample.name
            staged.parent.mkdir(parents=True)
            shutil.copytree(sample, staged)
            for f in staged.rglob('*'):
                if f.is_file() and f.suffix in {'.md', '.toml', '.sh', '.py'}:
                    # Normalise first: a Windows checkout is already CRLF, and a
                    # blind \n -> \r\n would produce \r\r\n.
                    body = f.read_bytes().replace(b'\r\n', b'\n')
                    f.write_bytes(body.replace(b'\n', b'\r\n'))
            results = hp.run_checks(self.repo, staged, Path(tmp) / 'ws')
        self.assertEqual(results['check-instruction-suffix']['status'], 'satisfied')
        self.assertEqual(results['submission-line-endings']['status'], 'partial')


class T4ReviewTests(unittest.TestCase):
    # 2.5: T4 is never selected automatically, so every call names it.
    @classmethod
    def setUpClass(cls):
        cls.repo = hp.repo_root()
        if cls.repo is None or not hp.bash_available():
            raise unittest.SkipTest('needs a terminal-bench clone and bash')

    def _minimal_zip(self):
        return inventory({
            'task.toml': 'version = "1.0"\n[metadata]\ncategory = "software-engineering"\n',
            'instruction.md': 'Fix the typo.\n',
            'tests/test.sh': '#!/bin/bash\necho 1 > /logs/verifier/reward.txt\n',
        })[0]

    def test_static_checks_outrank_the_model(self):
        raw = self._minimal_zip()
        bogus = json.dumps({'summary': '', 'results': [
            {'id': 'check-canary', 'status': 'satisfied',
             'evidence': 'looks fine to me', 'recommendation': 'none'}]})
        with patch.object(site, 'run_ollama', return_value=bogus):
            out = site.review_zip(raw, {}, 'm', 'fix-typo.zip', profile='t4')
        got = next(r for r in out['results'] if r['id'] == 'check-canary')
        self.assertEqual(got['status'], 'missing')
        self.assertEqual(got['assessment_source'], 'harbor static check')

    def test_model_cannot_assert_rubric_noncompliance(self):
        raw = self._minimal_zip()
        bogus = json.dumps({'summary': '', 'results': [
            {'id': 'rubric-difficult', 'status': 'missing',
             'evidence': 'too easy', 'recommendation': 'harden'}]})
        with patch.object(site, 'run_ollama', return_value=bogus):
            out = site.review_zip(raw, {}, 'm', 'fix-typo.zip', profile='t4')
        got = next(r for r in out['results'] if r['id'] == 'rubric-difficult')
        # 2.5: a semantic concern for a human, never a confirmed failure.
        self.assertEqual(got['status'], 'concern')
        self.assertIn('rubric-difficult', out['assessment']['rubric_flags'])
        self.assertNotIn('rubric-difficult', out['assessment']['confirmed_failures'])

    def test_review_survives_ollama_being_down(self):
        raw = self._minimal_zip()
        with patch.object(site, 'run_ollama', side_effect=RuntimeError('no ollama')):
            out = site.review_zip(raw, {}, 'm', 'fix-typo.zip', profile='t4')
        self.assertEqual(out['review_mode'], 'static-only')
        self.assertEqual(out['fallback_reason'], 'RuntimeError')
        # Static policy still produced verdicts without the model.
        static = [r for r in out['results'] if r['assessment_source'] == 'harbor static check']
        self.assertGreaterEqual(len(static), 20)

    def test_report_records_the_policy_revision(self):
        raw = self._minimal_zip()
        with patch.object(site, 'run_ollama', side_effect=RuntimeError('down')):
            out = site.review_zip(raw, {}, 'm', 'fix-typo.zip', profile='t4')
        self.assertIn('Terminal-Bench 4.0', out['policy_profile'])
        self.assertNotEqual(out['policy_version']['sha'], 'unknown')
        self.assertIn('Terminal-Bench 4.0', out['report_text'])


class PolicyProfileTests(unittest.TestCase):
    """Two live programmes with opposite rules. Neither may silently win."""

    def test_explicit_profile_beats_autodetection(self):
        self.assertEqual(site.requested_profile('t3'), site.PROFILE_T3)
        self.assertEqual(site.requested_profile('t4'), site.PROFILE_T4)
        self.assertEqual(site.requested_profile('ec'), site.PROFILE_T3)
        self.assertEqual(site.requested_profile('harbor'), site.PROFILE_T4)

    def test_env_var_selects_the_profile(self):
        with patch.dict(os.environ, {'T3_PROFILE': 't3'}):
            self.assertEqual(site.requested_profile(), site.PROFILE_T3)
        with patch.dict(os.environ, {'T3_PROFILE': 't4'}):
            self.assertEqual(site.requested_profile(), site.PROFILE_T4)

    def test_auto_falls_back_to_ec_when_no_clone(self):
        with patch.dict(os.environ, {'T3_PROFILE': 'auto'}), \
             patch.object(site.harbor_policy, 'repo_root', lambda *a, **k: None):
            self.assertEqual(site.requested_profile(), site.PROFILE_T3)

    def test_t4_request_without_a_clone_is_refused_not_downgraded(self):
        """Silently scoring a benchmark task against EC rules is the failure to avoid."""
        raw, _ = inventory({'task.toml': 'x = 1'})
        with patch.object(site.harbor_policy, 'repo_root', lambda *a, **k: None):
            with self.assertRaises(RuntimeError) as ctx:
                site.review_zip(raw, {}, 'm', 'task.zip', profile='t4')
        self.assertIn('unavailable', str(ctx.exception))

    def test_ec_profile_still_scores_against_the_unchanged_t3_seed(self):
        raw, _ = inventory({'instruction.md': 'go'})
        with patch.object(site, 'run_ollama', side_effect=RuntimeError('down')):
            out = site.review_zip(raw, site.source_supported_checklist(), 'm', 't.zip', profile='t3')
        self.assertEqual(out['profile'], site.PROFILE_T3)
        self.assertEqual(len(out['results']), 49)
        self.assertIn('canary forbidden', out['policy_profile'])

    def test_report_names_the_profile_and_warns_they_differ(self):
        raw, _ = inventory({'instruction.md': 'go'})
        with patch.object(site, 'run_ollama', side_effect=RuntimeError('down')):
            out = site.review_zip(raw, site.source_supported_checklist(), 'm', 't.zip', profile='t3')
        self.assertIn('Policy profile:    T3', out['report_text'])
        self.assertIn('profile_actual: t3', out['report_text'])
        self.assertIn('not interchangeable', out['report_text'])

    def test_the_two_profiles_disagree_about_the_canary(self):
        """If these ever agree, one of them has been corrupted."""
        t3_ids = {i['id'] for i in site.source_supported_checklist()['items']}
        self.assertIn('no-canary-strings', t3_ids)
        repo = hp.repo_root()
        if repo is None:
            self.skipTest('no terminal-bench clone')
        t4_ids = {i['id'] for i in hp.build_checklist(repo)['items']}
        self.assertIn('check-canary', t4_ids)
        self.assertNotIn('no-canary-strings', t4_ids)

    def test_checklist_endpoint_serves_the_requested_profile(self):
        ec = site.checklist_response(profile='t3')
        self.assertEqual(ec['profile'], site.PROFILE_T3)
        self.assertEqual(len(ec['checklist']['items']), 49)
        if hp.repo_root() is not None and hp.checks_runnable():
            tb = site.checklist_response(profile='t4')
            self.assertEqual(tb['profile'], site.PROFILE_T4)
            self.assertIn('policy', tb['checklist'])


class PortalRefreshTests(unittest.TestCase):
    """The docs index must survive the portal being rebuilt."""

    def test_extractor_does_not_depend_on_minified_symbol_names(self):
        import terminus_fetch as tf
        body = ('{slug:"a/b",title:"T"}')
        for symbol in ('d8', 'f5', 'zZ9'):
            bundle = f'const {symbol}={{sections:[{{title:"S",items:[{body}]}}]}},nextVar=1'
            docs = tf.extract_docs_index(bundle)
            self.assertEqual(len(docs), 1, f'failed for minified symbol {symbol}')
            self.assertEqual(docs[0]['slug'], 'a/b')

    def test_extractor_returns_empty_on_an_unrelated_bundle(self):
        import terminus_fetch as tf
        self.assertEqual(tf.extract_docs_index('var x = 1;'), [])

    def test_markdown_cleaning_keeps_identifier_underscores(self):
        clean = site.clean_markdown_inline
        self.assertEqual(clean('Required: `environment_mode = "separate"`'),
                         'Required: environment_mode = "separate"')
        self.assertEqual(clean('check verifier_interpreter_permissions now'),
                         'check verifier_interpreter_permissions now')
        self.assertEqual(clean('**Bold** and _emphasis_ and ***both***'), 'Bold and emphasis and both')
        self.assertEqual(clean('see [Writing Tests](/docs/x) and __init__'), 'see Writing Tests and init')
        self.assertEqual(clean('`__init__` stays'), '__init__ stays')


class ProfilePanelTests(unittest.TestCase):
    """Sources, updates and category data must follow the chosen programme."""

    def test_panel_titles_follow_the_profile(self):
        self.assertEqual(site.profile_panels(site.PROFILE_T3)['updates_title'], 'Terminus-3 updates')
        self.assertEqual(site.profile_panels(site.PROFILE_T4)['updates_title'], 'Terminus-4 updates')

    def test_t3_sources_are_the_portal_paths(self):
        paths = [s['path'] for s in site.profile_panels(site.PROFILE_T3)['sources']]
        self.assertIn('/portal/docs', paths)
        self.assertIn('/portal/changelog', paths)

    def test_t4_sources_are_the_benchmark_documents(self):
        if hp.repo_root() is None:
            self.skipTest('no terminal-bench clone')
        sources = site.profile_panels(site.PROFILE_T4)['sources']
        paths = [s['path'] for s in sources]
        self.assertIn('docs/prompts/task-implementation.toml', paths)
        self.assertIn('scripts/checks', paths)
        self.assertTrue(all(s['state'] == 'ok' for s in sources), sources)

    def test_missing_source_is_reported_as_tba_not_hidden(self):
        with patch.object(site.harbor_policy, 'repo_root', lambda *a, **k: None):
            sources = site.profile_panels(site.PROFILE_T4)['sources']
        self.assertEqual([s['state'] for s in sources], ['TBA'])

    def test_t4_changelog_has_dates_and_detail(self):
        if hp.repo_root() is None:
            self.skipTest('no terminal-bench clone')
        payload = site.changelog_payload(4, profile='t4')
        self.assertEqual(payload['profile'], site.PROFILE_T4)
        self.assertTrue(payload['entries'], 'expected dated policy commits')
        for entry in payload['entries']:
            self.assertRegex(entry['date'], r'^\d{4}-\d{2}-\d{2}$')
            self.assertTrue(entry['change'].strip())

    def test_t4_changelog_says_tba_when_unreadable(self):
        with patch.object(site.harbor_policy, 'repo_root', lambda *a, **k: None):
            payload = site.changelog_payload(4, profile='t4')
        self.assertEqual(payload['entries'], [])
        self.assertIn('TBA', payload['note'])

    def test_t4_category_status_is_taxonomy_plus_live_policy(self):
        if hp.repo_root() is None:
            self.skipTest('no terminal-bench clone')
        tables = site.category_status_payload(profile='t4')['tables']
        titles = ' '.join(t['title'] for t in tables)
        self.assertIn('categories', titles.lower())
        self.assertIn('Policies & settings', titles)
        policy = next(t for t in tables if t['title'].startswith('Policies'))
        # Rows must be dicts keyed by header: the UI renders row[header], so a
        # list-of-lists renders every cell blank. That was a live bug.
        for table in tables:
            for row in table['rows']:
                self.assertIsInstance(row, dict, table['title'])
                self.assertEqual(set(row) - {'_links'}, set(table['headers']))
                self.assertTrue(all(str(row[h]).strip() for h in table['headers']), row)
        values = {r['Policy']: r['Status'] for r in policy['rows']}
        # Read from the check scripts, so it cannot drift from what is enforced.
        self.assertIn('28800', values['Agent timeout'])
        self.assertIn('Required', values['Canary string'])

    def test_the_two_profiles_disagree_in_the_policy_panel(self):
        """T3 forbids the canary, T4 requires it. The panels must say so."""
        if hp.repo_root() is None:
            self.skipTest('no terminal-bench clone')
        t4 = site.category_status_payload(profile='t4')['tables']
        policy = next(t for t in t4 if t['title'].startswith('Policies'))
        canary = next(r for r in policy['rows'] if r['Policy'] == 'Canary string')
        self.assertIn('Required', canary['Status'])
        t3_ids = {i['id'] for i in site.source_supported_checklist()['items']}
        self.assertIn('no-canary-strings', t3_ids)

    def test_checklist_response_carries_panels_for_both_profiles(self):
        for profile in ('t3', 't4'):
            if profile == 't4' and site.profile_unavailable_reason('t4'):
                continue
            payload = site.checklist_response(profile=profile)
            self.assertIn('panels', payload)
            self.assertIn('updates_title', payload['panels'])
            self.assertIn('profiles', payload)




class PolicyProvenanceTests(unittest.TestCase):
    """Milestones 0-2: no blocking T4 rule may exist without verified source support."""

    @classmethod
    def setUpClass(cls):
        import policy_provenance
        cls.pp = policy_provenance
        cls.repo = hp.repo_root()

    def test_baseline_captures_the_frozen_t3_contract(self):
        base = self.pp.baseline_t3()
        self.assertEqual(base['item_count'], 49)
        self.assertEqual(base['review_mode_counts']['manual'], 11)
        self.assertTrue(base['checklist_sha256'])
        self.assertTrue(base['known_defects'])

    def test_every_blocking_t4_rule_has_a_verified_source(self):
        if self.repo is None:
            self.skipTest('no terminal-bench clone')
        self.assertEqual(self.pp.unsourced_blocking_rules(self.repo), [])

    def test_manifest_hashes_the_normative_sources(self):
        if self.repo is None:
            self.skipTest('no terminal-bench clone')
        manifest = {e['source_id']: e for e in self.pp.source_manifest(self.repo)}
        for key in ('t4-implementation-rubric', 't4-static-checks', 't4-task-template'):
            self.assertEqual(manifest[key]['status'], 'verified', key)
            self.assertTrue(manifest[key]['content_sha256'], key)
            self.assertEqual(manifest[key]['authority'], 'normative')

    def test_manifest_reports_a_missing_source_rather_than_omitting_it(self):
        manifest = {e['source_id']: e for e in self.pp.source_manifest(None)}
        self.assertEqual(manifest['t4-task-template']['status'], 'unavailable')
        self.assertIsNone(manifest['t4-task-template']['content_sha256'])

    def test_every_t3_rule_has_a_recorded_fate(self):
        diff = self.pp.policy_diff(self.repo)
        self.assertEqual(len(diff['rules']), 49)
        allowed = {'unchanged', 'modified', 'replaced', 'removed', 'split', 'merged', 'unclear'}
        for row in diff['rules']:
            self.assertIn(row['relation'], allowed, row['t3_rule'])

    def test_a_mapped_rule_cites_its_source(self):
        diff = self.pp.policy_diff(self.repo)
        for row in diff['rules']:
            if row['relation'] in {'unchanged', 'modified', 'replaced', 'split', 'merged'}:
                self.assertTrue(row['source_ids'], f"{row['t3_rule']} has no source")

    def test_the_canary_inversion_is_recorded_as_replaced(self):
        rules = {r['t3_rule']: r for r in self.pp.policy_diff(self.repo)['rules']}
        canary = rules['no-canary-strings']
        self.assertEqual(canary['relation'], 'replaced')
        self.assertEqual(canary['t4_rule'], 'check-canary')
        self.assertIn('forbidden', canary['t3'].lower())
        self.assertIn('required', canary['t4'].lower())

    def test_unclear_rules_carry_a_reason_and_no_t4_rule(self):
        for row in self.pp.policy_diff(self.repo)['rules']:
            if row['relation'] == 'unclear':
                self.assertFalse(row['t4_rule'], row['t3_rule'])
                self.assertTrue(row['note'], row['t3_rule'])


class DecisionTableTests(unittest.TestCase):
    """The owner's decision table for unknowns, applied through policy_model."""

    import policy_model as pm

    def items(self, *specs):
        return [{'id': rid, 'severity': sev, 'source': src} for rid, sev, src in specs]

    def state(self, items, results, status='stable', fallback=None, profile='t4'):
        return self.pm.assess(profile, status, items,
                              [{'id': k, 'status': v} for k, v in results.items()], fallback)

    def test_required_static_fail_is_policy_fail(self):
        a = self.state(self.items(('c', 'required', 'harbor-static-check')), {'c': 'missing'})
        self.assertEqual(a['overall_state'], 'policy_fail')
        self.assertEqual(a['confirmed_failures'], ['c'])

    def test_required_static_unknown_is_review_required_not_failure(self):
        a = self.state(self.items(('c', 'required', 'harbor-static-check')), {'c': 'unknown'})
        self.assertEqual(a['overall_state'], 'review_required')
        self.assertEqual(a['required_unknowns'], ['c'])
        self.assertEqual(a['confirmed_failures'], [])

    def test_recommended_static_unknown_or_fail_never_blocks(self):
        items = self.items(('r', 'recommended', 'harbor-static-check'))
        for status in ('unknown', 'missing'):
            a = self.state(items, {'r': status}, status='verified')
            self.assertEqual(a['overall_state'], 'policy_pass', status)
            self.assertEqual(a['recommended_unresolved'], ['r'])

    def test_required_rubric_unknown_flags_for_review_but_never_fails(self):
        a = self.state(self.items(('k', 'required', 'harbor-rubric')), {'k': 'unknown'})
        self.assertEqual(a['overall_state'], 'review_required')
        self.assertEqual(a['confirmed_failures'], [])

    def test_rubric_concern_cannot_cause_policy_fail(self):
        a = self.state(self.items(('k', 'required', 'harbor-rubric')), {'k': 'missing'})
        self.assertEqual(a['rubric']['concern'], 1)
        self.assertEqual(a['overall_state'], 'review_required')

    def test_advisory_unknown_is_display_only(self):
        a = self.state(self.items(('x', 'required', 'legacy-t3')), {'x': 'unknown'},
                       status='verified')
        self.assertEqual(a['overall_state'], 'policy_pass')
        self.assertEqual(a['advisory_findings'], ['x'])

    def test_rubric_cannot_cancel_a_static_failure(self):
        items = self.items(('c', 'required', 'harbor-static-check'),
                           *[(f'k{i}', 'required', 'harbor-rubric') for i in range(30)])
        results = {'c': 'missing', **{f'k{i}': 'satisfied' for i in range(30)}}
        self.assertEqual(self.state(items, results)['overall_state'], 'policy_fail')

    def test_fallback_forces_review_required(self):
        a = self.state(self.items(('c', 'required', 'harbor-static-check')), {'c': 'satisfied'},
                       status='verified', fallback='RuntimeError')
        self.assertEqual(a['overall_state'], 'review_required')

    def test_clean_result_under_a_preview_profile_is_profile_unverified(self):
        a = self.state(self.items(('c', 'required', 'harbor-static-check')), {'c': 'satisfied'},
                       status='preview')
        self.assertEqual(a['overall_state'], 'profile_unverified')

    def test_clean_result_under_the_stable_profile_is_policy_pass(self):
        items = [{'id': 'agent-timeout-range', 'severity': 'required', 'review_mode': 'auto'}]
        a = self.state(items, {'agent-timeout-range': 'satisfied'}, profile='t3')
        self.assertEqual(a['overall_state'], 'policy_pass')

    def test_legacy_score_excludes_advisory_and_unknown(self):
        items = self.items(('c', 'required', 'harbor-static-check'), ('k', 'required', 'harbor-rubric'),
                           ('x', 'required', 'legacy-t3'))
        score = self.pm.legacy_score(items, [{'id': 'c', 'status': 'satisfied'},
                                             {'id': 'k', 'status': 'unknown'},
                                             {'id': 'x', 'status': 'missing'}], 't4')
        self.assertEqual(score['value'], 100)  # only c counts
        self.assertEqual(score['counted'], 1)
        self.assertIn('not a policy decision', score['disclaimer'])

    def test_t3_layers_follow_evaluator_precision(self):
        seed = {i['id']: i for i in site.source_supported_checklist()['items']}
        layer = lambda rid: self.pm.rule_layer('t3', seed[rid])
        self.assertEqual(layer('agent-timeout-range'), 'static')       # parsed TOML
        self.assertEqual(layer('tests-dockerfile-present'), 'static')  # exact path
        self.assertEqual(layer('docker-package-installs-pinned'), 'rubric')  # loose text scan
        self.assertEqual(layer('terminus-3-project-target'), 'advisory')     # manual
        counts = {}
        for item in seed.values():
            counts[self.pm.rule_layer('t3', item)] = counts.get(self.pm.rule_layer('t3', item), 0) + 1
        self.assertEqual(counts, {'static': 11, 'rubric': 27, 'advisory': 11})

    def test_echoed_guidance_is_flagged_as_low_confidence(self):
        import reporting
        guidance = ('Verifiers should report per-test results in CTRF Common Test Report Format '
                    'at /logs/verifier/ctrf.json not just a bare reward number. The reward says '
                    'whether the trial passed the CTRF report says which checks failed.')
        item = {'id': 'rubric-ctrf-reporting', 'source': 'harbor-rubric', 'severity': 'required',
                'guidance': guidance}
        echo = {'id': 'rubric-ctrf-reporting', 'status': 'satisfied',
                'evidence': 'Verifiers should report per-test results in CTRF Common Test Report '
                            'Format at /logs/verifier/ctrf.json not just a bare reward number'}
        real = {**echo, 'evidence': 'tests/test.sh runs pytest without --ctrf so no report is written'}
        for result, expected in ((echo, ['rubric-ctrf-reporting']), (real, [])):
            review = {'profile': 't4', 'profile_status': 'preview', 'results': [dict(result)]}
            reporting.summarise(review, {'items': [item]})
            self.assertEqual(review['assessment']['echoed_guidance'], expected)

if __name__ == '__main__':
    unittest.main()
