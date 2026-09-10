# T4 gate and rubric coverage

Baseline columns refer to the final ZIPs. Mutations use the live server API with an intentionally unavailable model; all remain separate from the three practice deliverables. Human notes do not overwrite tool findings.

## Static gates — all 22

| Rule | Final baselines | Observed negative example | Review limit |
|---|---|---|---|
| check-allow-internet | Pass / pass / pass | allow-internet-false | Legacy allow_internet key check, not complete phase-network validation. |
| check-canary | Pass / pass / pass | missing-canary | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-compose-host-binds | Pass / pass / pass | compose-host-bind | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-dockerfile-platform | Pass / pass / pass | platform-pin | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-dockerfile-references | Pass / pass / pass | copy-solution | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-dockerfile-sanity | Pass / pass / pass | apt-pin | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-gpu-types | Pass / pass / pass | invalid-gpu | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-instruction-suffix | Pass / pass / pass | wrong-suffix, timeout-too-high | Runs after automatic LF normalization in this wrapper. |
| check-no-allow-internet-true | Pass / pass / pass | allow-internet-true | Combined with the false-value check, requires omission of the old key. |
| check-nproc | Pass / pass / pass | bare-nproc | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-pip-pinning | Pass / pass / pass | unpinned-pip | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-pytest-version | Pass / pass / pass | wrong-pytest | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-separate-verifier | Pass / pass / pass | shared-verifier | Empty artifacts list allowed; sufficiency still needs review/run. |
| check-task-absolute-path | Pass / pass / pass | relative-path | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-task-fields | Pass / pass / pass | missing-readme-sections | Presence/headings do not establish truthful authorship or quality. |
| check-task-package-name | Pass / pass / pass | wrong-package-name | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-task-slug | Pass / pass / pass | long-slug | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-task-timeout | Pass / pass / pass | timeout-too-high | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-test-file-references | Pass / pass / pass | hidden-output-quoted | Unquoted hyphenated redirection missed; quoted control fails. |
| check-test-sh-sanity | Pass / pass / pass | shared-verifier | Separate verifier short-circuits this dependency-isolation check; it is not a reward-correctness test. |
| check-trial-network-fetch | Pass / pass / pass | trial-network | Passed observed positive and negative controls; broader syntax coverage not proven. |
| check-verifier-tooling-baked | Pass / pass / pass | trial-pytest-install | Passed observed positive and negative controls; broader syntax coverage not proven. |

## Rubric — all 35

D = discount; S = stable deduplication; M = merge intervals. These are model statuses, followed by an independent human assessment.

| Rule | D / S / M | Human review |
|---|---|---|
| rubric-verifiable | satisfied / satisfied / satisfied | Basic functional checks are direct and deterministic; this is not a hardened adversarial verifier. |
| rubric-solvable | satisfied / satisfied / satisfied | Supported by successful Harbor oracle runs, including artifact transfer and verifier execution. |
| rubric-difficult | concern / concern / unknown | Concern: deliberately easy practice exercises, not expert benchmark tasks. |
| rubric-interesting | satisfied / satisfied / satisfied | Plausible everyday software repairs; modest scope does not establish benchmark value. |
| rubric-outcome-verified | satisfied / satisfied / satisfied | Supported: assertions check function results, exceptions and mutation behavior. |
| rubric-anti-cheat-robustness | satisfied / satisfied / satisfied | Concern: submitted Python is imported into the pytest process; no adversarial hardening demonstrated. |
| rubric-task-security | satisfied / satisfied / satisfied | Authored task files contain no observed malicious payload; this does not secure arbitrary future submissions. |
| rubric-functional-verification | satisfied / satisfied / satisfied | Supported for ordinary implementations by pytest execution and wrong-solution checks. |
| rubric-deterministic-reproducible | satisfied / satisfied / satisfied | Deterministic inputs and pinned test packages; successful local build, but a mutable image tag is not a reproducibility guarantee. |
| rubric-essential-difficulty | satisfied / satisfied / satisfied | Behavioral reasoning rather than formatting; the level of difficulty remains intentionally low. |
| rubric-test-instruction-alignment | satisfied / satisfied / satisfied | Stated threshold/order/merge/validation/mutation cases map to tests. No full input-space proof. |
| rubric-novel | satisfied / satisfied / satisfied | Not established: these are familiar introductory algorithms and repair patterns. |
| rubric-agentic | satisfied / concern / satisfied | Concern: each fix can be produced in one short model response; editing/running alone does not establish substantial agentic work. |
| rubric-reviewable | satisfied / satisfied / satisfied | Supported: compact functions and tests are easy to inspect. |
| rubric-instruction-concision | satisfied / satisfied / satisfied | Concise and clear, but AI-assisted authorship is disclosed; formal human-authorship conditions are not satisfied by that disclosure. |
| rubric-solution-quality | satisfied / satisfied / satisfied | Supported: reference code computes results rather than hardcoding fixture outputs. |
| rubric-separate-verifier-configured | satisfied / satisfied / satisfied | Supported for final fixtures by actual Harbor runs; empty-artifact mutation shows presence checks alone are insufficient. |
| rubric-environment-hygiene | satisfied / satisfied / satisfied | Agent image contains app.py only; test tools and expectations are in the verifier image. |
| rubric-structured-data-schema | concern / concern / concern | Model concern is unjustified: no external structured artifact is required; function input/output shape is specified. |
| rubric-typos | satisfied / satisfied / partial | No unintended path/command typo found; shipped function bugs are intentional. |
| rubric-difficulty-explanation-quality | satisfied / satisfied / satisfied | Honest practice explanation, not evidence of intrinsic expert difficulty. |
| rubric-solution-explanation-quality | satisfied / satisfied / satisfied | Concern for formal submission: README mostly points to solve.sh instead of explaining its strategy. |
| rubric-verification-explanation-quality | satisfied / satisfied / satisfied | Basic mechanism described; fuller formal review rationale and adversarial coverage are absent. |
| rubric-category-and-tags | satisfied / satisfied / satisfied | Final Software/Algorithms and Python/debugging tags fit the tasks. |
| rubric-task-name | satisfied / satisfied / satisfied | Names are specific, short and match the package namespace. |
| rubric-resource-configuration | satisfied / satisfied / satisfied | Small CPU/memory allocation ran successfully; no GPU needed. |
| rubric-task-readme | satisfied / satisfied / satisfied | Four required headings present. Upstream optional-README rubric text conflicts with the contributing/static requirements. |
| rubric-expert-time-estimate | satisfied / satisfied / satisfied | 15/30-minute practice estimates are plausible for reading and checking; not difficulty evidence. |
| rubric-task-toml-schema | satisfied / satisfied / satisfied | Final minimal configuration accepted by installed Harbor. Local rubric field list and current template disagree on networking; source reconciliation needed. |
| rubric-no-extraneous-files | satisfied / satisfied / satisfied | Final ZIPs contain only scaffold, runtime, reference, tests and README files. |
| rubric-artifact-efficiency | satisfied / satisfied / satisfied | Only the edited app.py is transferred. |
| rubric-verifier-execution-isolation | satisfied / satisfied / satisfied | Confirmed concern: direct import as verifier identity. Model invented a setpriv command that is absent. |
| rubric-ctrf-reporting | satisfied / satisfied / satisfied | CTRF files produced in actual oracle and successful NOP trials; no complete attack-resistance claim. |
| rubric-do-not-modify-enforced | satisfied / satisfied / satisfied | No protected-file constraint; input-list immutability is checked as functional behavior where required. |
| rubric-binary-reward | satisfied / satisfied / satisfied | Observed ordinary paths write 0 or 1. A binary value alone does not prove grading is correct. |

## Advisory — all 4

| Rule | Human review |
|---|---|
| submission-line-endings | Final ZIPs use LF. The CRLF mutation is disclosed but its normalized pass must not be confused with a raw-artifact pass. |
| no-privileged-docker-ops | No privileged Docker option observed. This does not mean submitted code executes with a safe verifier identity. |
| no-hidden-instructions-or-ai-scaffolding | No such files observed. A negative keyword scan cannot prove the absence of every hidden hint. |
| no-agent-writable-ground-truth | Expected values are baked into tests, but imported submitted Python executes alongside them. File placement alone does not prove runtime protection. |

## Test interpretation

All 22 static rule IDs appear in at least one actual-failure result across the probes. This demonstrates one negative control per rule, not exhaustive detection. The always-one verifier and empty-artifact mutations expose semantic gaps beyond those gates. The unquoted/quoted output-file pair isolates an inherited filename-detection limitation.

T3: all 49 original contracts were compared unchanged, and its existing regression/migration suite was exercised. This review did not create a new official interpretation for every T3 rule or replay every T3 rule through the browser. See source-and-task-inventory.json for the full T3 layer inventory.
