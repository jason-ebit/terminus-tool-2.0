# Expert review — T4 practice tasks and checker

Reviewed on 10 September 2026. Scope: the local `terminus-3-tool-` and `terminus-3-tool-enhanced` folders, the handoff found in the enhanced folder, the running website, and Terminal-Bench clone `v4.0.0-22-g83c7a617` (`83c7a6172d629c6575b785ab12c8db787bb2e323`). The supplied Desktop handoff path did not exist. These are observations of this source snapshot, not certification against an unpublished company T4 policy.

The checker provides useful mechanical evidence, but its semantic passes need human verification. No functional checker changes were applied during this review.

## Final task results

| Task | Oracle | NOP | Static gate | Reference score | Rubric |
|---|---:|---:|---:|---:|---|
| discount-boundary | 1.0 | 0.0 | 22/22 | 96 | 33 satisfied; 0 partial; 2 concern; 0 unknown |
| stable-dedup | 1.0 | 0.0 | 22/22 | 95 | 32 satisfied; 0 partial; 3 concern; 0 unknown |
| merge-intervals | 1.0 | 0.0 | 22/22 | 97 | 32 satisfied; 1 partial; 1 concern; 1 unknown |

All three final model assessments say **Review required**, with the T4 profile still **preview**. Each made six successful model calls. Full JSON/TXT reports are in `final-reviews/`; the final discount task also has a website screenshot and a separate website export.

The tasks are intentionally small: discount threshold/rounding/validation, stable deduplication, and merging intervals. The reference implementations passed the 14 Python test functions. Twelve deliberately wrong implementations were rejected by those same tests. Harbor independently confirmed oracle 1 and NOP 0 for every final task, with CTRF reports. These are suitable practice fixtures; they do not meet the benchmark's demanding difficulty, novelty, human-authorship or adversarial-verifier expectations.

The initial website ZIPs are preserved under `reviewed-v1-zips/`. Their scores were 100, 92 and 96. Before final validation, unnecessary schema/phase-network settings were removed to follow the local template and the subcategory changed from Systems to Algorithms. Function code and tests did not change. Original screenshots are evidence of that first revision, not screenshots of the final ZIP hashes. This was not a controlled model-repeatability experiment.

## Findings and proposed fixes

| Priority | Finding and evidence | Proposed change — not applied |
|---|---|---|
| High | **Unsupported positive rubric verdicts.** The first discount review marked all 35 rubric criteria satisfied despite a few-line exercise. The final report claims `setpriv --reuid nobody --regid nogroup --clear-groups --no-new-privs in solve.sh`; no task file contains that command. The verifier imports agent code directly into pytest. The model also calls the trivial repair agentic and novel. | Require concrete, verifiable file evidence before accepting a positive claim. Reject fabricated locations/quotes into unknown; use calibrated examples for difficulty/agentic judgments. A larger model is an experiment, not a substitute for validation. Never fix a difficulty concern merely by adding prose claiming expertise. |
| High | **Model response validation is incomplete.** `t4_rubric_verdicts` accepts one empty-evidence verdict out of 35 without recording a failed batch. An ID of `[]` raises an uncaught TypeError outside the batch exception handler. Duplicate IDs overwrite earlier values. | Validate ID type, membership, uniqueness, status and evidence per batch; record missing IDs and parse errors; retain good batches and mark the affected criteria unknown. Report requested/returned/usable/resolved counts separately. |
| High | **Detected weak evidence still counts as a pass.** `reporting.summarise` computes `echoed_guidance` after the decision and leaves those items satisfied. The probe yields score 100, no rubric flags and profile_unverified even when the evidence is the guidance copied back. The website has no corresponding low-confidence badge. | Surface the flag in the UI and route unsupported echoes to human review. Keep T4 preview; do not let approving the profile accidentally promote these results to acceptance. Decide how unresolved evidence should affect the comparison denominator explicitly. |
| Medium | **Evidence can describe different inputs.** T4 extraction selects the first shallow `task.toml`, while rubric inventory includes all roots. A two-task ZIP selected `a` but gave the model both `a` and `b`. Separately, an unread 2 MiB+ text file produces a read error while `model_excerpts_limited` remains false. Eighteen of 35 rubric guidance texts are cut to 1,200 characters without a policy-truncation flag. | Require one unambiguous task root and use it for both checks and model context. Include skipped files, reasons and policy truncation in provenance. Preserve every operative rule or explicitly mark incomplete assessment; do not silently omit the tail of policy guidance. |
| Medium | **Runner failures can become task violations.** A simulated exit 127 / `python3: command not found` is marked missing with a “blocks CI” recommendation. Timeouts and launch errors already become unknown, but failures inside a launched script do not. | Preflight required tooling and distinguish check violations from execution failures using a defined result protocol or conservative error classification. Do not turn every nonzero exit into unknown: real policy failures must still block. |
| Medium | **Uploaded bytes are normalized before static checks.** The CRLF instruction probe passes the suffix gate after conversion and only gets an advisory. This is disclosed, but it is not a check of the exact uploaded artifact. | Report raw-artifact and normalized-copy results separately, or run strict checks on the original. Keep checkout convenience separate from submission evidence. Do not assume Git normalization will happen for every ZIP workflow. |
| Medium | **Archive/request boundaries have remaining gaps.** File/directory prefix conflicts are accepted; colon-containing names are accepted despite Windows extraction concerns. Negative Content-Length reaches `read(-1)` in both report and review handlers. There is no request-body deadline or bounded review queue. | Reject ambiguous archive layouts before writing; define portable filename handling. Require bounded nonnegative body lengths, limit read time and concurrent work, and cap the whole review budget. The length probe used a fake reader, not a live denial-of-service test. |
| Medium | **Source and compatibility labels are stronger than the evidence.** Manifest “verified” primarily means locally available/hashable. T3's runtime source hash hashes URLs, not fetched document contents. T4 links point at mutable main. The local rubric calls README optional and refers to metadata explanations, while current contributing/static requirements require README sections. Some recommendations point at checker scripts rather than task files. | Distinguish captured, source-verified and owner-approved. Hash actual source snapshots, use commit links and record dirty state. Surface source conflicts using an explicit authority order. Keep recommendations attached to real submitted paths. Preserve the frozen T3 contract until a reviewed policy change is approved. |
| Medium | **Inherited check coverage is limited.** An actual test reading `/app/secret-output.csv` and an unquoted solution redirection to that file pass `check-test-file-references`; quoting the redirection causes the expected failure. An always-reward-1 verifier passes all static gates. An empty artifacts list is accepted even when this task needs app.py transferred. | Record these as scope/coverage limitations. Propose the filename detection fix upstream or as a clearly labelled supplementary diagnostic. Use semantic review and execution for verifier behavior and artifact sufficiency; do not rewrite the official gates or create practice-task exemptions. |

The structured-output concern is a false positive for these function repair tasks: input/output types and behavior are specified, and no JSON/CSV/API artifact is required. The model's instruction to add a schema is not justified by absence of such an artifact. Conversely, difficulty and unsafe execution of submitted Python are legitimate concerns. Passing the oracle does not settle those concerns.

## What held up in testing

- All 22 T4 gates passed for each final ZIP. Across 27 small live API mutation cases, every static rule also had at least one observed failure case. These requests deliberately named a nonexistent model to test fallback; they did not change the site's default model or execute archive contents.
- Missing canaries, platform pins, missing artifacts key, wrong suffix, prohibited allow_internet values, package/version errors, invalid names, missing README sections, excessive timeout, bare nproc, solution leakage, apt pinning, invalid GPU types, host binds, relative paths and trial-time installs/fetches were detected.
- Model-unavailable cases retained their static results and reported static-only / review_required or policy_fail. Required static failures were not canceled by rubric results. T4 remained preview; unknown did not become a confirmed failure.
- Existing tests cover archive traversal, symlinks, duplicate/case collisions, encrypted entries, compression ratios/size limits, atomic-write failures, corrupt-state quarantine, client disconnects, policy selection, overrides and migration fixtures. The full Ubuntu suite passed 183 tests. The Windows snapshot suite ran 177 tests: 168 passed and 9 were skipped, after a documented temporary-directory ACL adaptation; 8 UI guard tests passed. This is regression evidence, not an exhaustive concurrency or security audit.
- The website's upload/review flow, profile selection, attention filter, copy control and TXT downloads were exercised. Downloaded reports retain ZIP names, hashes, profile, model and findings. The initial “100%, Profile unverified” screenshot demonstrates the approval safeguard holding despite an overconfident rubric.

Two initial probe expectations were corrected after reading the scripts: `artifacts=[]` is allowed structurally (unlike omitting the key), and allow_internet=false is caught by `check-allow-internet`, while true is caught by `check-no-allow-internet-true`. Those are not reported as checker regressions.

Initial NOP builds failed in Docker's credential helper and had no verifier reward. They were not counted as successful negative tests. Retrying with an isolated, empty Docker auth configuration for the public Python image produced real reward-0 trials. The user's Docker configuration was not edited; both failed attempts and successful retries remain in the logs.

## Legacy versus enhanced

The 49 T3 item IDs, criteria, severities, categories, review modes and applicability contracts match the legacy snapshot. Their evaluators and presentation changed. The enhanced tree adds 20 Python/JS source/fixture files and changes 5 legacy source/UI files; it deletes none of the inventoried legacy code files. The exact list and SHA-256 inventory are in `source-and-task-inventory.json`.

| Area | Legacy | Enhanced snapshot |
|---|---|---|
| Policy | One T3 checklist | Explicit T3 default; T4 preview from a local clone; 22 static + 35 rubric + 4 advisory T4 items |
| Assessment | Mixed keyword/model findings and a percentage | Structured checks, static precedence, distinct policy state, rubric concerns and advisory findings |
| Models | Sends checklist/excerpts; broad silent fallback; no explicit context sizing | JSON output, context sizing, batched T4 review, model/fallback metadata; validation gaps remain |
| Evidence | Short previews and weaker parsing | Full stored text for objective checks, TOML parsing, stage-aware digest handling, better dependency/default handling |
| Reporting/UI | Basic checklist and score | Filters, traceable findings, override records, on-request TXT downloads; reference score still prominent |
| Resilience | Less defensive ZIP/save/disconnect handling | Shared archive guard, atomic replacement/quarantine, disconnect handling, regression and migration fixtures |

T3 and T4 are distinct programs, not interchangeable versions of one submission policy. T3 forbids canaries and uses its 1800–18000-second range; T4 requires its canary and caps timeout at 28800 (the final fixtures use the repository's flat 8-hour convention). T3 digest enforcement is not imported into the T4 gate. T4 adds package namespace/slug/suffix checks, README sections, canonical pytest pins and verifier packaging checks. Shared intentions such as semantic verification remain, but are reorganized. Lack of a verified T4 counterpart is not evidence that a company policy was rescinded.

The claim that the legacy tool never supplied checklist/task data to the LLM is contradicted by `review_prompt` and `review_zip` in the legacy file (lines 1758 and 1798). Context truncation and silent fallback are plausible causes of poor summaries. Some handoff/generated notes claim every old review fell back, but this audit has no historical request logs to establish that. Do not repeat that absolute claim in a manager report.

## Changes made in this review

- Created the three practice tasks, ZIPs, direct wrong-solution checks, live review evidence and Harbor oracle/NOP logs.
- Shortened seven comment blocks across `policy_model.py`, `harbor_policy.py`, `terminus_checklist_site.py` and `web/review-guard.js`, removing 20 comment lines overall. Python ASTs match the originals; only comment text changed in JS. Original line endings were preserved. Patch, hashes and original files are under `comment-cleanup/`.
- No executable checker statements, scoring rules, default model, policy activation or legacy repository files were changed by this review. No manager report was sent or published.

## Suggested next pass

1. Fix response/evidence validation and the treatment of detected weak evidence. Add focused regression cases for the reproduced failures.
2. Fix root selection, incomplete-context reporting and runner/request boundaries. Keep original artifact hashes and all good static results.
3. Reconcile policy-source conflicts and stale setup documentation. Calibrate on a small set containing clear passes, clear violations, unknowns and these deliberately simple tasks.
4. Review the concrete diff and results before approving T4 activation, score placement or a model change. Keep rollback and T3 baseline comparison. Do not relax rules to make these examples score higher.

All 61 T4 items are covered in `gate-and-rubric-matrix.md`; raw reports and probes provide the detailed evidence. Full frontier-agent difficulty trials, adversarial reward-channel exploitation, exhaustive prompt-injection testing and load testing were not performed.
