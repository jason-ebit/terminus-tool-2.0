# T3 to T4 policy diff

Generated 2026-09-10T08:38:15.373163+00:00.
T3 rules: 49 · T4 rules: 61

Relation counts: merged 3, modified 9, removed 3, replaced 19, split 5, unchanged 4, unclear 6

## T3 rules and their fate

| T3 rule | Relation | T4 rule | T3 behaviour | T4 behaviour | Sources |
|---|---|---|---|---|---|
| `open-category` | unchanged | `check-task-fields` | Category is one of seven open categories. | Identical seven domains, plus a required non-empty subcategory. | t4-taxonomy,t4-review-automation |
| `no-milestone-task` | unclear | — | Task is not a milestone task. | No milestone concept found in T4 sources. | — |
| `no-gpu-requirement` | removed | `check-gpu-types` | Task must not require a GPU. | Up to one GPU permitted; gpu_types validated against canonical Modal strings. | t4-task-template,t4-review-automation |
| `no-canary-strings` | replaced | `check-canary` | Canary strings forbidden in every component. | Canary string REQUIRED in instruction.md, task.toml, environment/Dockerfile and every text file under solution/ and tests/. | t4-review-automation,t4-task-template |
| `verifier-isolation` | merged | `check-separate-verifier` | environment_mode = "separate". | Five mechanical conditions: environment_mode, top-level artifacts, tests/Dockerfile, COPY into /tests, RUN mkdir -p for artifact parents. | t4-review-automation |
| `top-level-artifacts-configured` | merged | `check-separate-verifier` | artifacts declared at the top level of task.toml. | Same requirement, now one of five conditions in check-separate-verifier. | t4-review-automation |
| `task-toml-required-metadata-present` | modified | `check-task-fields` | difficulty, solution_explanation, verification_explanation, relevant_experience required as [metadata] fields. | author_name, author_email, category, subcategory, tags, expert_time_estimate_hours required in task.toml; the four explanations are required README '##' sections. 'difficulty' is not a valid T4 field. | t4-review-automation,t4-implementation-rubric |
| `agent-timeout-range` | modified | `check-task-timeout` | agent.timeout_sec between 1800 and 18000. | Capped at 28800; no floor. All 66 merged tasks use the flat 8h value. | t4-review-automation,t4-task-template |
| `network-mode-intentional` | modified | `check-allow-internet,check-no-allow-internet-true` | network_mode set to public or no-network intentionally. | Open internet assumed; allow_internet must be omitted entirely, not set either way. | t4-review-automation |
| `terminus-3-project-target` | replaced | `check-task-package-name` | Submission targets the Terminus-3-Prod project. | [task] name = "terminal-bench/<folder>". | t4-review-automation |
| `starter-template-replaced` | modified | `check-task-fields,rubric-category-and-tags` | Starter-template placeholders such as REPLACE removed. | Template defaults (empty category, tags, expert_time_estimate_hours = 0) are rejected as unfilled. | t4-review-automation,t4-implementation-rubric |
| `required-task-files-present` | modified | `check-separate-verifier,check-task-fields` | Required task files and directories present. | Same scaffold plus a required README with four named sections. | t4-review-automation |
| `tests-dockerfile-present` | merged | `check-separate-verifier` | tests/Dockerfile included. | Same, as a separate-verifier condition. | t4-review-automation |
| `test-sh-entrypoint-canonical` | split | `check-test-sh-sanity,rubric-binary-reward,rubric-ctrf-reporting` | tests/test.sh follows canonical entrypoint behaviour. | uv isolation mechanically; binary 0/1 reward and CTRF reporting in the rubric. | t4-review-automation,t4-implementation-rubric |
| `instruction-file-clear` | replaced | `rubric-instruction-concision` | Instructions state goal, constraints and deliverable. | Human-written, concise, absolute paths, no fluff; plus check-task-absolute-path and check-instruction-suffix mechanically. | t4-implementation-rubric,t4-review-automation |
| `domain-grounded-task` | split | `rubric-difficult,rubric-interesting` | Domain-grounded and targets a difficult coding-agent workflow. | Split into difficult (needs professional expertise) and interesting (real-world value). The bar is explicitly higher. | t4-implementation-rubric |
| `not-trivial-or-pure-formatting` | replaced | `rubric-essential-difficulty` | Not a trivial formatting or boilerplate edit. | Difficulty must stem from logical reasoning, not formatting minutiae. | t4-implementation-rubric |
| `difficulty-tier-evidence` | replaced | `rubric-difficulty-explanation-quality` | Evidence for the expected difficulty tier; metadata.difficulty field. | No self-declared tier. A README Difficulty explanation section plus expert_time_estimate_hours; difficulty judged by reviewers and /run pass rates. | t4-implementation-rubric,t4-review-automation |
| `taxonomy-alignment` | modified | `check-task-fields` | Category, subcategory and tags align with the taxonomy. | subcategory is mandatory and validated; taxonomy published in TAXONOMY.md. | t4-taxonomy |
| `oracle-solution-present` | replaced | `rubric-solvable` | An oracle or reference solution is included. | A working solution that passes all tests, validated by the oracle run. | t4-implementation-rubric |
| `oracle-solution-correct` | replaced | `rubric-solution-quality` | Oracle represents a correct solution. | Solution demonstrates actual computation, not hardcoded answers. | t4-implementation-rubric |
| `semantic-verifier-present` | replaced | `rubric-functional-verification` | Verifier checks semantics rather than appearance. | Tests verify actual behaviour through execution, not source-code keywords. | t4-implementation-rubric |
| `rejects-wrong-solution` | unclear | — | Verifier rejects a deliberately wrong solution. | Covered by /cheat adversarial trials and the nop validation run, both of which execute code. No static equivalent. | t4-review-automation |
| `no-agent-writable-ground-truth` | replaced | `rubric-anti-cheat-robustness` | Ground truth not read from agent-writable paths. | Tests resist adversarial agent behaviour; also probed by /cheat trials. | t4-implementation-rubric |
| `no-proxy-only-checks` | replaced | `rubric-functional-verification` | Verifier does not rely only on proxy checks. | Same intent, folded into functional_verification. | t4-implementation-rubric |
| `no-unrebuilt-binary-grading` | replaced | `rubric-anti-cheat-robustness` | Verifier does not grade a stale binary. | Folded into anti_cheat_robustness. | t4-implementation-rubric |
| `tolerance-and-tie-breaks-tested` | modified | `rubric-verification-explanation-quality` | Verifier covers tolerances and tie-breaks when relevant. | Any inequality-based check must have its bounds justified in the README verification explanation. | t4-implementation-rubric |
| `deterministic-tests` | replaced | `rubric-deterministic-reproducible` | Tests deterministic, no flaky timing or external state. | Consistent across runs with pinned dependencies and no live-service dependency. | t4-implementation-rubric |
| `local-validation-documented` | replaced | — | Local validation or CI feedback documented. | Superseded by automated Docker build, oracle and nop validation on every push, which execute code and are outside this checker's scope. | t4-review-automation |
| `docker-environment-present` | unchanged | `check-separate-verifier` | Docker/environment setup included. | environment/Dockerfile required; tests/Dockerfile additionally required. | t4-review-automation |
| `dockerfile-best-practices` | split | `check-dockerfile-sanity,rubric-environment-hygiene` | Dockerfile follows documented requirements. | Mechanical apt rules in check-dockerfile-sanity; image cleanliness in environment_hygiene (agent image must not carry tests/solution or test-only deps). | t4-review-automation,t4-implementation-rubric |
| `docker-base-images-digest-pinned` | removed | — | Dockerfile FROM images must be digest-pinned. | No such rule. Package pinning is enforced instead. | t4-review-automation |
| `docker-package-installs-pinned` | split | `check-pip-pinning,check-pytest-version` | Python package installs pin exact versions. | check-pip-pinning requires == everywhere; check-pytest-version additionally pins pytest and pytest-json-ctrf to repo-wide canonical versions. | t4-review-automation |
| `no-platform-pinning` | unchanged | `check-dockerfile-platform` | No FROM --platform. | Same. | t4-review-automation |
| `no-bare-nproc` | unchanged | `check-nproc` | No bare nproc. | Same; nproc --all permitted. | t4-review-automation |
| `no-privileged-docker-ops` | unclear | — | Task does not require privileged Docker or unsafe container flags. | No explicit T4 rule names privileged container flags. task_security covers exploitation of the agent or host in general terms only. | — |
| `dependencies-declared` | modified | `check-pip-pinning,check-verifier-tooling-baked` | Runtime and test dependencies declared in the ZIP. | Declaration plus exact == pinning, and verifier tooling baked into the image rather than installed at trial time. | t4-review-automation |
| `no-hidden-instructions-or-ai-scaffolding` | replaced | `rubric-anti-cheat-robustness` | No hidden instructions or AI-framework scaffolding in environment files. | The answer must not be reachable by trivial inspection. | t4-implementation-rubric |
| `no-hidden-external-dependency` | split | `check-trial-network-fetch,rubric-deterministic-reproducible` | No hidden local files, private services or undeclared external resources. | Trial-time fetches mechanically blocked; live-service dependence judged in the rubric. | t4-review-automation,t4-implementation-rubric |
| `submission-zip-clean` | replaced | `rubric-no-extraneous-files` | ZIP excludes caches, build artefacts and secrets. | Task directory contains only files needed to build, run, solve or verify. | t4-implementation-rubric |
| `no-direct-reviewer-contact` | unclear | — | Materials do not instruct contributors to contact reviewers directly. | No counterpart found. T4 actively directs authors to Discord and maintainers. | t4-contributing |
| `reviewer-checklist-ready` | replaced | `rubric-reviewable` | Task is ready for reviewer checklist inspection. | Non-specialist reviewers can verify correctness, or sufficient explanation is given. | t4-implementation-rubric |
| `rubric-or-evaluation-notes-present` | replaced | `rubric-verification-explanation-quality` | Rubric or evaluation notes present for nuanced judgement. | README Verification explanation describes how tests establish correctness. | t4-implementation-rubric,t4-review-automation |
| `faq-troubleshooting-considered` | unclear | — | Known FAQ/troubleshooting issues addressed. | No counterpart found. | — |
| `kernel-cpu-simulated-or-compile-only` | removed | — | Kernel tasks CPU-simulated or compile-only. | GPUs permitted (max 1, H100), so the constraint no longer follows. | t4-task-template |
| `multi-container-metadata` | modified | `check-compose-host-binds` | Multi-container tasks tagged under metadata. | No tagging requirement found; compose is constrained to named volumes instead. | t4-review-automation |
| `performance-threshold-not-too-tight` | replaced | `rubric-verification-explanation-quality` | Performance thresholds not too tight relative to the oracle. | Numeric bounds must be justified and calibrated in the verification explanation. | t4-implementation-rubric |
| `reward-file-zero-on-failure` | replaced | `rubric-binary-reward` | Failed runs write 0 to the reward file. | Exactly 0 or 1 on every reachable path; no partial credit. | t4-implementation-rubric |
| `env-vars-have-defaults` | unclear | — | Environment variables in test.sh have compatible defaults. | No verified T4 counterpart found. | — |

## New in T4

| T4 rule | Requirement | Sources |
|---|---|---|
| `check-instruction-suffix` | instruction.md must end with the exact timeout/anti-cheat sentence naming [agent].timeout_sec | t4-review-automation |
| `check-task-slug` | Task folder name at most 3 hyphen-separated tokens | t4-review-automation |
| `check-dockerfile-references` | Agent image must not COPY tests/ or solution/ | t4-review-automation |
| `check-test-file-references` | Expected output files documented in instruction.md | t4-review-automation |
| `check-task-absolute-path` | Instructions use absolute paths | t4-review-automation |
| `rubric-do-not-modify-enforced` | Stated do-not-modify constraints are actually enforced | t4-implementation-rubric |
| `rubric-verifier-execution-isolation` | Agent code runs unprivileged; reward channel out of reach | t4-implementation-rubric |
| `rubric-artifact-efficiency` | Artifacts carry only agent-produced content | t4-implementation-rubric |
| `rubric-task-toml-schema` | task.toml carries only valid fields | t4-implementation-rubric |

## Unresolved questions

- Does T4 require negative-run evidence at review time, or only via /cheat trials?
- Are the four README explanation sections mandatory for every task, or only when the metadata fields are absent?
- Is `schema_version` required, or is its absence tolerated?
- Do any T3-only rules with no T4 counterpart still apply to T4 submissions?
