"""The verified T3-to-T4 policy mapping, as plain data.

Kept free of imports so both the checker (for legacy labels on checklist items)
and policy_provenance (for the Milestone 2 diff) can use one copy. Every mapped
row cites source IDs from the source manifest; rows without verified support
are marked "unclear" and never block.
"""

# Every T3 seed rule's fate under T4, with the evidence for the call. Anything
# not backed by a verified source is marked unclear and must not block.
POLICY_DIFF: dict[str, dict[str, str]] = {
    "no-canary-strings": {
        "relation": "replaced", "t4_rule": "check-canary",
        "t3": "Canary strings forbidden in every component.",
        "t4": "Canary string REQUIRED in instruction.md, task.toml, environment/Dockerfile "
              "and every text file under solution/ and tests/.",
        "source_ids": "t4-review-automation,t4-task-template",
        "note": "Direct inversion. T3 excludes canaries because it is a training dataset; "
                "T4 requires them because it is a public benchmark.",
    },
    "agent-timeout-range": {
        "relation": "modified", "t4_rule": "check-task-timeout",
        "t3": "agent.timeout_sec between 1800 and 18000.",
        "t4": "Capped at 28800; no floor. All 66 merged tasks use the flat 8h value.",
        "source_ids": "t4-review-automation,t4-task-template",
        "note": "T3 floor would fail every merged T4 task.",
    },
    "docker-base-images-digest-pinned": {
        "relation": "removed", "t4_rule": "",
        "t3": "Dockerfile FROM images must be digest-pinned.",
        "t4": "No such rule. Package pinning is enforced instead.",
        "source_ids": "t4-review-automation",
        "note": "Only 8 of 69 merged tasks digest-pin; no check script enforces it.",
    },
    "terminus-3-project-target": {
        "relation": "replaced", "t4_rule": "check-task-package-name",
        "t3": "Submission targets the Terminus-3-Prod project.",
        "t4": '[task] name = "terminal-bench/<folder>".',
        "source_ids": "t4-review-automation", "note": "",
    },
    "no-gpu-requirement": {
        "relation": "removed", "t4_rule": "check-gpu-types",
        "t3": "Task must not require a GPU.",
        "t4": "Up to one GPU permitted; gpu_types validated against canonical Modal strings.",
        "source_ids": "t4-task-template,t4-review-automation", "note": "",
    },
    "task-toml-required-metadata-present": {
        "relation": "modified", "t4_rule": "check-task-fields",
        "t3": "difficulty, solution_explanation, verification_explanation, relevant_experience "
              "required as [metadata] fields.",
        "t4": "author_name, author_email, category, subcategory, tags, "
              "expert_time_estimate_hours required in task.toml; the four explanations are "
              "required README '##' sections. 'difficulty' is not a valid T4 field.",
        "source_ids": "t4-review-automation,t4-implementation-rubric",
        "note": "66 of 70 merged tasks use README sections.",
    },
    "verifier-isolation": {
        "relation": "merged", "t4_rule": "check-separate-verifier",
        "t3": 'environment_mode = "separate".',
        "t4": "Five mechanical conditions: environment_mode, top-level artifacts, "
              "tests/Dockerfile, COPY into /tests, RUN mkdir -p for artifact parents.",
        "source_ids": "t4-review-automation", "note": "",
    },
    "top-level-artifacts-configured": {
        "relation": "merged", "t4_rule": "check-separate-verifier",
        "t3": "artifacts declared at the top level of task.toml.",
        "t4": "Same requirement, now one of five conditions in check-separate-verifier.",
        "source_ids": "t4-review-automation", "note": "",
    },
    "open-category": {
        "relation": "unchanged", "t4_rule": "check-task-fields",
        "t3": "Category is one of seven open categories.",
        "t4": "Identical seven domains, plus a required non-empty subcategory.",
        "source_ids": "t4-taxonomy,t4-review-automation", "note": "",
    },
    "taxonomy-alignment": {
        "relation": "modified", "t4_rule": "check-task-fields",
        "t3": "Category, subcategory and tags align with the taxonomy.",
        "t4": "subcategory is mandatory and validated; taxonomy published in TAXONOMY.md.",
        "source_ids": "t4-taxonomy", "note": "",
    },
    "no-bare-nproc": {"relation": "unchanged", "t4_rule": "check-nproc",
                      "t3": "No bare nproc.", "t4": "Same; nproc --all permitted.",
                      "source_ids": "t4-review-automation", "note": ""},
    "no-platform-pinning": {"relation": "unchanged", "t4_rule": "check-dockerfile-platform",
                            "t3": "No FROM --platform.", "t4": "Same.",
                            "source_ids": "t4-review-automation", "note": ""},
    "docker-package-installs-pinned": {
        "relation": "split", "t4_rule": "check-pip-pinning,check-pytest-version",
        "t3": "Python package installs pin exact versions.",
        "t4": "check-pip-pinning requires == everywhere; check-pytest-version additionally "
              "pins pytest and pytest-json-ctrf to repo-wide canonical versions.",
        "source_ids": "t4-review-automation", "note": ""},
    "tests-dockerfile-present": {"relation": "merged", "t4_rule": "check-separate-verifier",
                                 "t3": "tests/Dockerfile included.",
                                 "t4": "Same, as a separate-verifier condition.",
                                 "source_ids": "t4-review-automation", "note": ""},
    "instruction-file-clear": {
        "relation": "replaced", "t4_rule": "rubric-instruction-concision",
        "t3": "Instructions state goal, constraints and deliverable.",
        "t4": "Human-written, concise, absolute paths, no fluff; plus check-task-absolute-path "
              "and check-instruction-suffix mechanically.",
        "source_ids": "t4-implementation-rubric,t4-review-automation", "note": ""},
    "domain-grounded-task": {
        "relation": "split", "t4_rule": "rubric-difficult,rubric-interesting",
        "t3": "Domain-grounded and targets a difficult coding-agent workflow.",
        "t4": "Split into difficult (needs professional expertise) and interesting "
              "(real-world value). The bar is explicitly higher.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "not-trivial-or-pure-formatting": {
        "relation": "replaced", "t4_rule": "rubric-essential-difficulty",
        "t3": "Not a trivial formatting or boilerplate edit.",
        "t4": "Difficulty must stem from logical reasoning, not formatting minutiae.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "difficulty-tier-evidence": {
        "relation": "replaced", "t4_rule": "rubric-difficulty-explanation-quality",
        "t3": "Evidence for the expected difficulty tier; metadata.difficulty field.",
        "t4": "No self-declared tier. A README Difficulty explanation section plus "
              "expert_time_estimate_hours; difficulty judged by reviewers and /run pass rates.",
        "source_ids": "t4-implementation-rubric,t4-review-automation",
        "note": "metadata.difficulty is not a valid T4 field."},
    "oracle-solution-present": {
        "relation": "replaced", "t4_rule": "rubric-solvable",
        "t3": "An oracle or reference solution is included.",
        "t4": "A working solution that passes all tests, validated by the oracle run.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "oracle-solution-correct": {
        "relation": "replaced", "t4_rule": "rubric-solution-quality",
        "t3": "Oracle represents a correct solution.",
        "t4": "Solution demonstrates actual computation, not hardcoded answers.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "semantic-verifier-present": {
        "relation": "replaced", "t4_rule": "rubric-functional-verification",
        "t3": "Verifier checks semantics rather than appearance.",
        "t4": "Tests verify actual behaviour through execution, not source-code keywords.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "no-proxy-only-checks": {
        "relation": "replaced", "t4_rule": "rubric-functional-verification",
        "t3": "Verifier does not rely only on proxy checks.",
        "t4": "Same intent, folded into functional_verification.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "no-agent-writable-ground-truth": {
        "relation": "replaced", "t4_rule": "rubric-anti-cheat-robustness",
        "t3": "Ground truth not read from agent-writable paths.",
        "t4": "Tests resist adversarial agent behaviour; also probed by /cheat trials.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "no-unrebuilt-binary-grading": {
        "relation": "replaced", "t4_rule": "rubric-anti-cheat-robustness",
        "t3": "Verifier does not grade a stale binary.",
        "t4": "Folded into anti_cheat_robustness.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "deterministic-tests": {
        "relation": "replaced", "t4_rule": "rubric-deterministic-reproducible",
        "t3": "Tests deterministic, no flaky timing or external state.",
        "t4": "Consistent across runs with pinned dependencies and no live-service dependency.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "tolerance-and-tie-breaks-tested": {
        "relation": "modified", "t4_rule": "rubric-verification-explanation-quality",
        "t3": "Verifier covers tolerances and tie-breaks when relevant.",
        "t4": "Any inequality-based check must have its bounds justified in the README "
              "verification explanation.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "dockerfile-best-practices": {
        "relation": "split", "t4_rule": "check-dockerfile-sanity,rubric-environment-hygiene",
        "t3": "Dockerfile follows documented requirements.",
        "t4": "Mechanical apt rules in check-dockerfile-sanity; image cleanliness in "
              "environment_hygiene (agent image must not carry tests/solution or test-only deps).",
        "source_ids": "t4-review-automation,t4-implementation-rubric", "note": ""},
    "docker-environment-present": {
        "relation": "unchanged", "t4_rule": "check-separate-verifier",
        "t3": "Docker/environment setup included.",
        "t4": "environment/Dockerfile required; tests/Dockerfile additionally required.",
        "source_ids": "t4-review-automation", "note": ""},
    "required-task-files-present": {
        "relation": "modified", "t4_rule": "check-separate-verifier,check-task-fields",
        "t3": "Required task files and directories present.",
        "t4": "Same scaffold plus a required README with four named sections.",
        "source_ids": "t4-review-automation", "note": ""},
    "dependencies-declared": {
        "relation": "modified", "t4_rule": "check-pip-pinning,check-verifier-tooling-baked",
        "t3": "Runtime and test dependencies declared in the ZIP.",
        "t4": "Declaration plus exact == pinning, and verifier tooling baked into the image "
              "rather than installed at trial time.",
        "source_ids": "t4-review-automation", "note": ""},
    "no-hidden-external-dependency": {
        "relation": "split", "t4_rule": "check-trial-network-fetch,rubric-deterministic-reproducible",
        "t3": "No hidden local files, private services or undeclared external resources.",
        "t4": "Trial-time fetches mechanically blocked; live-service dependence judged in the rubric.",
        "source_ids": "t4-review-automation,t4-implementation-rubric", "note": ""},
    "submission-zip-clean": {
        "relation": "replaced", "t4_rule": "rubric-no-extraneous-files",
        "t3": "ZIP excludes caches, build artefacts and secrets.",
        "t4": "Task directory contains only files needed to build, run, solve or verify.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "no-hidden-instructions-or-ai-scaffolding": {
        "relation": "replaced", "t4_rule": "rubric-anti-cheat-robustness",
        "t3": "No hidden instructions or AI-framework scaffolding in environment files.",
        "t4": "The answer must not be reachable by trivial inspection.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "reviewer-checklist-ready": {
        "relation": "replaced", "t4_rule": "rubric-reviewable",
        "t3": "Task is ready for reviewer checklist inspection.",
        "t4": "Non-specialist reviewers can verify correctness, or sufficient explanation is given.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "rubric-or-evaluation-notes-present": {
        "relation": "replaced", "t4_rule": "rubric-verification-explanation-quality",
        "t3": "Rubric or evaluation notes present for nuanced judgement.",
        "t4": "README Verification explanation describes how tests establish correctness.",
        "source_ids": "t4-implementation-rubric,t4-review-automation", "note": ""},
    "test-sh-entrypoint-canonical": {
        "relation": "split", "t4_rule": "check-test-sh-sanity,rubric-binary-reward,rubric-ctrf-reporting",
        "t3": "tests/test.sh follows canonical entrypoint behaviour.",
        "t4": "uv isolation mechanically; binary 0/1 reward and CTRF reporting in the rubric.",
        "source_ids": "t4-review-automation,t4-implementation-rubric", "note": ""},
    "reward-file-zero-on-failure": {
        "relation": "replaced", "t4_rule": "rubric-binary-reward",
        "t3": "Failed runs write 0 to the reward file.",
        "t4": "Exactly 0 or 1 on every reachable path; no partial credit.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "performance-threshold-not-too-tight": {
        "relation": "replaced", "t4_rule": "rubric-verification-explanation-quality",
        "t3": "Performance thresholds not too tight relative to the oracle.",
        "t4": "Numeric bounds must be justified and calibrated in the verification explanation.",
        "source_ids": "t4-implementation-rubric", "note": ""},
    "network-mode-intentional": {
        "relation": "modified", "t4_rule": "check-allow-internet,check-no-allow-internet-true",
        "t3": "network_mode set to public or no-network intentionally.",
        "t4": "Open internet assumed; allow_internet must be omitted entirely, not set either way.",
        "source_ids": "t4-review-automation", "note": ""},
    "starter-template-replaced": {
        "relation": "modified", "t4_rule": "check-task-fields,rubric-category-and-tags",
        "t3": "Starter-template placeholders such as REPLACE removed.",
        "t4": "Template defaults (empty category, tags, expert_time_estimate_hours = 0) are "
              "rejected as unfilled.",
        "source_ids": "t4-review-automation,t4-implementation-rubric", "note": ""},
    "env-vars-have-defaults": {
        "relation": "unclear", "t4_rule": "",
        "t3": "Environment variables in test.sh have compatible defaults.",
        "t4": "No verified T4 counterpart found.",
        "source_ids": "",
        "note": "Retained as advisory only. Absence of a check script is not proof of removal."},
    "no-milestone-task": {
        "relation": "unclear", "t4_rule": "",
        "t3": "Task is not a milestone task.",
        "t4": "No milestone concept found in T4 sources.",
        "source_ids": "", "note": "Likely T3-programme specific. Not carried over."},
    "local-validation-documented": {
        "relation": "replaced", "t4_rule": "",
        "t3": "Local validation or CI feedback documented.",
        "t4": "Superseded by automated Docker build, oracle and nop validation on every push, "
              "which execute code and are outside this checker's scope.",
        "source_ids": "t4-review-automation", "note": ""},
    "kernel-cpu-simulated-or-compile-only": {
        "relation": "removed", "t4_rule": "",
        "t3": "Kernel tasks CPU-simulated or compile-only.",
        "t4": "GPUs permitted (max 1, H100), so the constraint no longer follows.",
        "source_ids": "t4-task-template", "note": ""},
    "multi-container-metadata": {
        "relation": "modified", "t4_rule": "check-compose-host-binds",
        "t3": "Multi-container tasks tagged under metadata.",
        "t4": "No tagging requirement found; compose is constrained to named volumes instead.",
        "source_ids": "t4-review-automation", "note": ""},
    "no-direct-reviewer-contact": {
        "relation": "unclear", "t4_rule": "",
        "t3": "Materials do not instruct contributors to contact reviewers directly.",
        "t4": "No counterpart found. T4 actively directs authors to Discord and maintainers.",
        "source_ids": "t4-contributing", "note": "Likely intentionally dropped."},
    "faq-troubleshooting-considered": {
        "relation": "unclear", "t4_rule": "",
        "t3": "Known FAQ/troubleshooting issues addressed.",
        "t4": "No counterpart found.",
        "source_ids": "", "note": "Recommended severity in T3; not carried over."},
    "no-privileged-docker-ops": {
        "relation": "unclear", "t4_rule": "",
        "t3": "Task does not require privileged Docker or unsafe container flags.",
        "t4": "No explicit T4 rule names privileged container flags. task_security covers "
              "exploitation of the agent or host in general terms only.",
        "source_ids": "",
        "note": "Kept as a non-blocking advisory scan in the T4 profile. The T4 criterion "
                "verifier_execution_isolation concerns running agent code unprivileged inside "
                "the verifier, which is a different control."},
    "rejects-wrong-solution": {
        "relation": "unclear", "t4_rule": "",
        "t3": "Verifier rejects a deliberately wrong solution.",
        "t4": "Covered by /cheat adversarial trials and the nop validation run, both of "
              "which execute code. No static equivalent.",
        "source_ids": "t4-review-automation",
        "note": "Not statically decidable. Stays advisory in both profiles.",
    },
}

# T4 rules with no T3 ancestor at all. A rule the diff records as a descendant
# of some T3 rule (split, merged, modified...) must not also appear here.
NEW_T4_RULES = [
    ("check-instruction-suffix", "instruction.md must end with the exact timeout/anti-cheat "
     "sentence naming [agent].timeout_sec", "t4-review-automation"),
    ("check-task-slug", "Task folder name at most 3 hyphen-separated tokens",
     "t4-review-automation"),
    ("check-dockerfile-references", "Agent image must not COPY tests/ or solution/",
     "t4-review-automation"),
    ("check-test-file-references", "Expected output files documented in instruction.md",
     "t4-review-automation"),
    ("check-task-absolute-path", "Instructions use absolute paths", "t4-review-automation"),
    ("rubric-do-not-modify-enforced", "Stated do-not-modify constraints are actually enforced",
     "t4-implementation-rubric"),
    ("rubric-verifier-execution-isolation", "Agent code runs unprivileged; reward channel "
     "out of reach", "t4-implementation-rubric"),
    ("rubric-artifact-efficiency", "Artifacts carry only agent-produced content",
     "t4-implementation-rubric"),
    ("rubric-task-toml-schema", "task.toml carries only valid fields",
     "t4-implementation-rubric"),
]
