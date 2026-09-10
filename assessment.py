"""Evidence checks for the existing T3 policy. Never executes uploaded files.

Python 3.11+ is required for structural TOML parsing. This module changes
assessment, not the seed checklist's criteria, severities or limits.
"""
import re
import tomllib
from pathlib import PurePosixPath


def result(key, status, evidence, recommendation):
    return dict(id=key, status=status, evidence=evidence, recommendation=recommendation)


def files(inventory):
    return [(f['path'], f.get('content', f.get('preview', ''))) for f in inventory['files']]


def config(inventory):
    matches = [(p, t) for p, t in files(inventory) if PurePosixPath(p).name == 'task.toml']
    if len(matches) != 1:
        return None, f'Expected one task.toml; found {len(matches)}. Review one task ZIP at a time.'
    p, text = matches[0]
    try:
        return tomllib.loads(text), p
    except tomllib.TOMLDecodeError as exc:
        return None, f'{p}: invalid TOML: {exc}'


def structured_checks(inventory):
    checks = {}
    def put(key, status, evidence, recommendation):
        checks[key] = result(key, status, evidence, recommendation)
    cfg, source = config(inventory)
    keys = ['top-level-artifacts-configured', 'task-toml-required-metadata-present',
            'agent-timeout-range', 'verifier-isolation', 'network-mode-intentional',
            'open-category', 'taxonomy-alignment']
    if cfg is None:
        for key in keys:
            put(key, 'unknown', source, 'Inspect `task.toml`; resolve missing, invalid or ambiguous configuration before assessing this rule.')
        return checks
    def section(name):
        value = cfg.get(name, {})
        return value if isinstance(value, dict) else {}
    artifacts = cfg.get('artifacts')
    valid = isinstance(artifacts, list) and bool(artifacts) and all(isinstance(p, str) and p.strip() for p in artifacts)
    put(keys[0], 'satisfied' if valid else 'missing',
        f'{source}: top-level artifacts = {artifacts!r}; nested keys do not satisfy this requirement.',
        'Verify listed paths cover verifier inputs.' if valid else 'Declare a nonempty top-level `artifacts` array in `task.toml`.')
    meta = section('metadata')
    required = ['category', 'subcategory', 'tags', 'difficulty', 'expert_time_estimate_hours',
                'solution_explanation', 'verification_explanation', 'relevant_experience']
    missing = [k for k in required if k not in meta or meta[k] is None or meta[k] == '' or meta[k] == []]
    put(keys[1], 'partial' if missing else 'satisfied',
        f'{source}: missing/empty T3 metadata fields: {missing}. README prose does not replace required TOML fields.',
        'Complete the required `[metadata]` fields in `task.toml`.' if missing else 'Review metadata content for accuracy; field presence alone does not validate explanations.')
    timeout = section('agent').get('timeout_sec')
    valid = type(timeout) in (int, float) and 1800 <= timeout <= 18000
    put(keys[2], 'satisfied' if valid else 'missing', f'{source}: agent.timeout_sec = {timeout!r}; T3 range is 1800–18000 seconds.',
        'No change needed to `task.toml` agent timeout.' if valid else 'Set `[agent].timeout_sec` within the T3 range and revalidate task feasibility; do not substitute verifier/build timeouts.')
    mode = section('verifier').get('environment_mode')
    put(keys[3], 'satisfied' if mode == 'separate' else 'missing', f'{source}: verifier.environment_mode = {mode!r}.',
        'No change needed to verifier isolation.' if mode == 'separate' else 'Set `[verifier].environment_mode = "separate"` in `task.toml`.')
    network = section('environment').get('network_mode')
    put(keys[4], 'satisfied' if network in ('public', 'no-network') else 'unknown',
        f'{source}: environment.network_mode = {network!r}.', 'Review intended networking in `task.toml` against T3 policy.')
    category = meta.get('category')
    valid = category in ['Science', 'Software', 'ML', 'Operations', 'Security', 'Hardware', 'Media']
    for key in keys[5:]:
        put(key, 'satisfied' if valid else 'missing', f'{source}: metadata.category = {category!r}; checked against the unchanged T3 category list.',
            'Review subcategory/tags manually; this check establishes category membership only.' if valid else 'Use a T3-supported category in `task.toml`.')
    return checks


def dependency_check(inventory):
    key = 'dependencies-declared'
    evidence = []
    manifests = {'requirements.txt', 'pyproject.toml', 'package.json', 'package-lock.json',
                 'uv.lock', 'poetry.lock', 'environment.yml', 'environment.yaml', 'conda-lock.yml'}
    command = re.compile(r'\b(?:pip3?\s+install|uv\s+(?:pip\s+install|run\b)|(?:mamba|micromamba|conda)\s+(?:install|create)|apt-get\s+install|npm\s+(?:ci|install))\b')
    for path, text in files(inventory):
        name = PurePosixPath(path).name
        if name in manifests and text.strip():
            evidence.append(f'{path}: dependency manifest present')
        if name.lower().startswith('dockerfile') or name.endswith('.sh'):
            for number, line in enumerate(text.splitlines(), 1):
                if not line.lstrip().startswith('#') and command.search(line):
                    evidence.append(f'{path}:{number}: {line.strip()}')
    return result(key, 'satisfied' if evidence else 'unknown',
                  '; '.join(evidence) if evidence else 'No recognized dependency declarations found; a standard-library-only task may need none.',
                  'Review declaration completeness, version locks and clean-build logs; presence does not prove a runnable environment.')


def digest_check(inventory):
    key = 'docker-base-images-digest-pinned'
    missing, unresolved, found = [], [], []
    for path, text in files(inventory):
        if not PurePosixPath(path).name.lower().startswith('dockerfile'):
            continue
        stages = set()
        for number, line in enumerate(text.splitlines(), 1):
            match = re.match(r'\s*FROM\s+(?:--\S+\s+)*(\S+)(?:\s+AS\s+(\S+))?', line, re.I)
            if not match:
                continue
            image, alias = match.groups()
            location = f'{path}:{number}: {image}'
            found.append(location)
            if '$' in image:
                unresolved.append(location)
            elif image.lower() != 'scratch' and image.lower() not in stages and not re.search(r'@sha256:[0-9a-fA-F]{64}$', image):
                missing.append(location)
            if alias:
                stages.add(alias.lower())
    status = 'missing' if missing else 'unknown' if unresolved or not found else 'satisfied'
    return result(key, status, '; '.join(missing or unresolved or found) or 'No FROM instructions available.',
                  'Pin external base images to verified digests; ARG-based references need manual resolution. A syntactically valid digest still requires registry/build verification.')


def env_check(inventory):
    
    key = 'env-vars-have-defaults'
    scripts = [(p,t) for p,t in files(inventory) if '/tests/' in '/' + p and p.endswith('.sh')]
    if not scripts:
        return result(key, 'unknown', 'No verifier shell script available.', 'Inspect the verifier entrypoint before assessing environment defaults.')
    uses, unresolved = [], []
    pattern = re.compile(r'\$\{([A-Z][A-Z0-9_]*)([^}]*)\}|\$([A-Z][A-Z0-9_]*)')
    for path, text in scripts:
        for number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith('#'):
                continue
            for match in pattern.finditer(line):
                name = match[1] or match[3]
                suffix = match[2] or ''
                location = f'{path}:{number}: {match[0]}'
                uses.append(location)
                if not (suffix.startswith(':-') or suffix.startswith(':=')) or not suffix[2:]:
                    unresolved.append(location)
    if not uses:
        return result(key, 'not_applicable', 'No uppercase configuration-variable expansions in verifier shell scripts; $? is shell status and Dockerfile PATH is outside this check.', 'No environment-default edit is required for these verifier scripts.')
    return result(key, 'unknown' if unresolved else 'partial', '; '.join(unresolved or uses),
                  'Inspect each variable assignment, inherited value, quoting and execution path; confirm compatible defaults. Static scanning cannot establish shell data flow or semantic compatibility.')


# Fallback verdicts the legacy keyword heuristic cannot support: filename
# presence claimed as semantics, or quality judged from keyword presence.
# Absence scans (no-agent-writable-ground-truth, no-unrebuilt-binary-grading,
# deterministic-tests) are
# deliberately NOT listed: they now scan complete stored file text rather than a
# 600-character preview with boundary-aware matching, so their negative
# evidence stands on its own and the original T3 coverage is preserved.
# no-hidden-external-dependency stays listed: its terms ('private', 'secret',
# 'token') are ordinary English and cannot carry a verdict either way.
SEMANTIC_ITEMS = {
    'oracle-solution-correct', 'semantic-verifier-present', 'rejects-wrong-solution',
    'domain-grounded-task', 'not-trivial-or-pure-formatting', 'difficulty-tier-evidence',
    'no-proxy-only-checks', 'instruction-file-clear', 'reviewer-checklist-ready',
    'dockerfile-best-practices', 'no-hidden-external-dependency',
    'tolerance-and-tie-breaks-tested', 'performance-threshold-not-too-tight',
    'reward-file-zero-on-failure', 'env-vars-have-defaults',
}


# Items decided by file inventory or by a literal term scan over complete file
# text. These are facts about the archive, not judgements about it, so the
# deterministic result outranks a model verdict exactly as the structural
# task.toml checks do. Small local models routinely invert negatively-phrased
# criteria ("no-milestone-task" -> missing, with evidence stating no milestone
# framing was found) and report files absent that are listed in the inventory
# they were given; this set makes those verdicts unreachable.
# no-hidden-external-dependency is deliberately excluded: its terms are ordinary
# English words and its scan cannot carry a verdict either way.
OBJECTIVE_ITEMS = frozenset({
    'required-task-files-present', 'tests-dockerfile-present',
    'oracle-solution-present', 'docker-environment-present',
    'no-milestone-task', 'no-gpu-requirement', 'no-canary-strings',
    'starter-template-replaced', 'no-agent-writable-ground-truth',
    'no-unrebuilt-binary-grading', 'deterministic-tests',
    'no-platform-pinning', 'no-bare-nproc', 'no-privileged-docker-ops',
    'submission-zip-clean', 'no-direct-reviewer-contact',
    'no-hidden-instructions-or-ai-scaffolding',
})


def assessments(inventory, fallback=False):
    checks = structured_checks(inventory)
    for fn in (dependency_check, digest_check, env_check):
        r = fn(inventory)
        checks[r['id']] = r
    # No static or LLM verdict can establish that a negative run actually happened.
    checks['rejects-wrong-solution'] = result('rejects-wrong-solution', 'unknown',
        'This reviewer did not execute the verifier. File names, assertions and prose cannot establish a negative-run outcome.',
        'Inspect recorded negative-run evidence against verifier version and artifact hashes, or run deliberate incorrect and shortcut artifacts in an isolated validation environment. Do not mark missing solely because evidence was not recognized.')
    if fallback:
        for key in SEMANTIC_ITEMS - checks.keys():
            checks[key] = result(key, 'unknown',
                'Deterministic fallback cannot establish this semantic or execution property.',
                'Manually review task evidence and validation logs; keyword presence is not proof of compliance.')
    return checks
