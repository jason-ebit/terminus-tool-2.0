# T3 assessment corrections

This is a separate runnable copy of the user's locally installed terminus-3-tool-.
The original installation and reviewed benchmark ZIPs were not modified.

## Policy compatibility

The entire source_supported_checklist() seed was compared with the original and
is unchanged: criteria, IDs, severities, categories, conditional applicability,
review modes, timeout range, digest rule and required metadata are preserved.
These changes are compatible with that existing T3 policy implementation. They
are not certification that every hardcoded rule matches the current official
Terminus 3 submission specification. Exact source/version citations per rule
still require a separate policy audit; no citations or policy exceptions were invented.

## Changes

- Full stored text is available for structural checks. Model excerpts remain
  limited to 5,000 characters per file and 60,000 total and this is disclosed.
- Parse TOML structurally: read agent.timeout_sec, enforce the original
  1800â€“18000 range, identify top-level artifacts, inspect the metadata table,
  and distinguish invalid or multiple configs from a confirmed missing field.
- README explanations do not replace T3-required TOML fields.
- Recognize dependency declarations in Dockerfiles, conda/mamba commands and
  solution uv commands. Report declaration presence separately from successful
  builds, completeness and version locking. Standard-library-only tasks are not
  automatically labelled defective for lacking a manifest.
- Check real digest syntax, internal build-stage references and scratch images;
  unresolved ARG image expressions require review rather than an invented verdict.
- Scope variable checks to verifier shell scripts. Exclude Dockerfile PATH and
  shell status $?. Unresolved variables remain unknown; detecting a default
  alone does not establish that it is semantically compatible.
- Neither prose nor assertions prove that negative runs occurred. Wrong-solution
  rejection remains unknown until a reviewer validates execution evidence.
- For corrected objective checks, structured evidence overrides LLM verdicts.
- Disable unsupported semantic conclusions in fallback mode (for example,
  solution filename presence no longer proves oracle correctness).
- Disclose model versus fallback mode, model excerpt limits, unresolved items
  and required findings. Keep the existing conservative score arithmetic but
  label the score provisional, not approval. Unknown still contributes zero;
  this patch does not inflate scores by excluding uncertainty.
- Retain the canonical T3 criteria when receiving a client/saved checklist.
- Reject archives exceeding review limits instead of silently treating an
  incompletely read text file as absent evidence.

## Run on Ubuntu or macOS

Use Python 3.11 or later (tomllib is required). With uv:

```sh
cd terminus-3-tool-reviewed
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt
python terminus_checklist_site.py
```

Stop any previous checker using port 8765 before starting this copy. Open
http://127.0.0.1:8765. Ollama and the selected model are still needed for LLM
review; without them the UI now explicitly identifies deterministic fallback.
No Docker or uploaded task code is executed by the checker.

The old website assets remain otherwise unchanged. Checklist refresh still
uses the original source-fetching mechanism; it cannot independently update
the fixed policy criteria. If old saved custom criteria existed, this copy
starts from the canonical seed rather than copying that local state.

## Verification

```sh
python -m unittest -v test_assessment.py
```

16 offline regressions passed. Coverage includes late-file TOML fields, nested
artifacts, correct timeout section, invalid configuration, README field-location
mismatches, dependency formats, digest enforcement, variable scope, fallback
disclosure, and preventing LLM override of structured findings.

Both supplied ZIPs also passed integration assertions for the corrected checks.
ASSESSMENT-EXAMPLES.json contains their offline fallback reports. These are
review reports, not Harbor execution results. Live Ollama and browser interaction
were not tested. No fresh T3 policy certification or scientific task execution
was performed.

## Remaining limitations

This is a targeted assessment patch, not a complete semantic analyzer. Existing
uncorrected heuristic rules, notably package-version pinning and shell entrypoint
analysis, still need manual interpretation. Shell scanning is conservative and
does not fully parse quoting, heredocs, sourced scripts or control flow. Dependency
recognition proves declarations exist, not that every import is satisfied. Digest
syntax does not prove registry availability. LLM semantic findings remain advisory.
Negative-run evidence is not automatically authenticated. The score is not a
submission acceptance decision, even at 100/100.


## On-demand TXT exports (t3-assessment-1.1)

After reviewing a ZIP, use **Copy report** or **Download TXT**. Downloads are
named `<original-zip-stem>-review-<UTC timestamp>.txt`. Reports contain every
checklist item with unresolved findings first, evidence/recommendations,
assessment source, status counts, score explanation, model/fallback details,
elapsed review time, checker version, checklist hash and original ZIP hash.
No review history is automatically written to disk. A report is kept in page
memory until copied/downloaded or replaced; selecting another ZIP clears the
export controls. The existing saved checklist behavior is unchanged.

Extract this updated ZIP and start its Python server instead of the previous
copy. Restart the server and reload the browser page after updating. No extra
Python packages are required by reporting.py. 18 Python regressions passed,
including report completeness, filename safety, hashes, fallback disclosure
and unchanged score calculation; JavaScript syntax was checked.


## Review-path corrections (t3-assessment-1.2)

The 49-item seed is unchanged: `source_supported_checklist()` still compares
byte-identical to the original installation, and `.terminus_checklist.json`
still hashes to `6d00bb3e...`. Criteria, IDs, severities, categories,
`applies_when` conditions, review modes, the 1800-18000 timeout range and the
digest rule are untouched. Nothing below edits a T3 rule; the changes are to
how a verdict is reached and reported.

### The LLM was never actually consulted

`run_ollama` shelled out to `ollama run` without setting `num_ctx`. Ollama's
server default is 4096 tokens. A review prompt carrying the checklist plus file
excerpts measures about 11,850 tokens for a small task, so Ollama truncated it
from the front: the model never received the schema or the criteria, answered
the trailing file excerpts in prose, and `json_from_model_output` raised
`JSONDecodeError`. Both this copy and the original installation silently fell
back to the deterministic keyword pass on every review. The original reported
no mode, so this was invisible there.

`run_ollama` now calls the `/api/generate` HTTP endpoint with `format: "json"`
(constrained decoding), `temperature: 0`, and `num_ctx` sized to the prompt and
capped by `T3_OLLAMA_MAX_CTX` (default 32768). `OLLAMA_HOST` is honoured. A
generation stopped by the context limit raises rather than returning a partial
review. Uploaded task code is still never executed.

### Unknown no longer reads as failure

The score weights were left at `unknown = missing = 0.0`, so every honest
`unknown` this patch introduced was scored as noncompliance. `score` keeps the
original arithmetic unchanged for continuity. Added alongside it:
`compliance_score` over resolved items only, and `coverage`, the share of
scored items that reached a verdict. The UI and the TXT report lead with
compliance and coverage together, because high compliance at low coverage
means little was established.

### Verdict precedence

- A structured check that returns `unknown` no longer erases a resolved verdict,
  and no check may overwrite an `applies_when` exclusion. Conditional items
  stayed `not_applicable` in the original and were being converted to `unknown`,
  which moved them from outside the denominator to a zero inside it.
- `OBJECTIVE_ITEMS`: criteria decided by file inventory or a literal term scan
  over complete file text now outrank a model verdict, exactly as the structural
  `task.toml` checks already did. qwen2.5:3b inverts negatively-phrased criteria
  (`no-milestone-task` marked missing, with evidence stating no milestone
  framing was found) and reports files absent that appear in the inventory it
  was handed.
- A model `missing` on a criterion in `SEMANTIC_ITEMS` is downgraded to
  `unknown`. A model verdict is admissible as evidence of compliance, not as
  proof of noncompliance on a semantic or execution property. The item still
  appears in `required_findings`.

### Term matching

Absence scans read stored file content instead of the 600-character preview,
so their negative evidence now covers the whole file. Bare substring matching
over complete files produced false positives that the truncated preview had
been hiding: `gpus = 0` read as a GPU requirement, `.replace(` as an unreplaced
REPLACE placeholder, `os.environ` as a committed `.env`. `term_present` adds
word boundaries, and matches case-sensitively when the term is capitalised,
because the capitals are the placeholder signal. The term lists are unchanged.

With that in place, `deterministic-tests`, `no-agent-writable-ground-truth` and
`no-unrebuilt-binary-grading` were removed from the fallback blanket and return
to evidence-based verdicts; `SEMANTIC_ITEMS` goes from 18 to 14.
`no-hidden-external-dependency` stays listed because its terms (`private`,
`secret`, `token`) are ordinary English and cannot carry a verdict either way.

### Other

- A text file over 2 MiB raised `ValueError` inside a `try` whose only handler
  was `except RuntimeError`, aborting the entire review with a 500. The guard
  now records a per-file `read_error` and the review continues.
- `deterministic_results()` split out of `deterministic_review()` so the
  objective override does not re-enter `normalize_review`.
- Fixed double-encoded UTF-8 in the `web/app.js` checklist counter.

### Verification

`python -m unittest -q test_assessment.py` - 35 offline regressions, run on
Windows and in Ubuntu WSL. The 18 original regressions are unmodified and still
pass. The 17 added cover context sizing, the JSON request shape, truncated
generations, each documented term-matching false positive, full-content
scanning, structured-unknown precedence, `applies_when` survival, objective
override of a hallucinating model, semantic `missing` downgrade, coverage
arithmetic, unchanged legacy score arithmetic, the oversized-file guard, and
seed integrity (49 items, 11 manual).

Measured on `foodstuff-beta-activity` from terminal-bench
(`1c35bfc1f4024eff0a7eb26a12f64e0da4e289e0df34d13b0e4a2cef457056f3`) with
qwen2.5:3b on Ollama 0.33.3:

| | mode | result |
|---|---|---|
| original installation | fallback (undisclosed) | 82/100 |
| this copy, 1.1 | fallback | 50/100 |
| this copy, 1.2, Ollama down | fallback | 85 compliance / 68% coverage |
| this copy, 1.2, Ollama up | llm-assisted | 88 compliance / 63% coverage |

Findings that survive every path, all genuine and all missed or unresolved by
the original: `agent.timeout_sec = 28800` against the 1800-18000 range; four
absent required `[metadata]` fields; `python:3.12-slim` unpinned in both
Dockerfiles; a `harbor-canary` GUID in `task.toml`.

### Model choice

qwen2.5:3b is too small to be a T3 reviewer. With the transport fixed it still
inverted negatively-phrased criteria and claimed `instruction.md` was absent.
The precedence rules above contain that damage rather than repair it: 28 of 49
items now come from structured or objective checks. Use a larger local model
for the semantic criteria, and read `assessment_source` on every finding before
acting on it. A review remains a review, not a submission decision.


## Terminal-Bench 4.0 mode (tb-review-2.0)

### Why the policy is no longer written here

T4.0 is the `harbor-framework/terminal-bench` repo at `v4.0.0`. The Snorkel
Terminus EC portal that the original checker fetched describes T3 only, so it
is no longer consulted for review policy.

The benchmark ships its own rules in executable form: 22 `check-*.sh` scripts in
`scripts/checks/` (what CI runs on every push) and a 35-criterion implementation
rubric in `docs/prompts/task-implementation.toml`. `harbor_policy.py` discovers
both from a local clone and runs the scripts. A benchmark release updates the
policy through `git pull`; nothing in this repo needs editing. The scripts only
grep and parse task files, so uploaded task code is still never executed.

Point the checker at a clone with `T4_REPO=/path/to/terminal-bench`, or keep the
clone beside this directory. `T4_PORT` moves the server off 8765. The startup
banner states which policy is active. Running the checks needs bash and python3
on a POSIX system, so use WSL, Linux or macOS; on Windows the checker falls back
to the legacy T3 checklist and says so.

### T3 rules that were wrong for T4

Verified against the v4.0.0 checkout and its 66 merged tasks:

- **Agent timeout 1800-18000.** Retired. T4.0 gives every task a flat 8-hour
  timeout; all 66 merged tasks set `agent.timeout_sec = 28800.0`, and
  `check-task-timeout` enforces only that ceiling. The old rule flagged
  canonical compliance as a violation.
- **`no-canary-strings`.** Inverted, and this was the dangerous one. T4 requires
  `harbor-canary GUID 26b5c67b-...` in `instruction.md`, `task.toml`,
  `environment/Dockerfile` and every text file under `solution/` and `tests/`.
  The T3 rule scored the canary's *presence* as contamination, so it penalised
  compliant tasks and green-lit non-compliant ones. Now `check-canary`.
- **`docker-base-images-digest-pinned`.** Retired. No T4 check requires it and
  only 8 of 69 merged tasks digest-pin, so the rule failed 88% of the benchmark.
  Pinning is enforced for packages instead (`check-pip-pinning`,
  `check-pytest-version`).
- **`terminus-3-project-target`.** Retired. "Terminus-3-Prod" does not exist in
  T4. The real requirement is `[task] name = "terminal-bench/<folder>"`
  (`check-task-package-name`).
- **`no-gpu-requirement`.** Retired. T4 permits `gpus` up to 1 and validates
  `gpu_types` against canonical Modal strings (`check-gpu-types`).
- **Explanations as `[metadata]` fields.** The four explanations are README
  sections (`## Difficulty explanation`, `## Solution explanation`,
  `## Verification explanation`, `## Relevant experience`); 66 of 70 tasks use
  README, 6 use TOML. `check-task-fields` enforces the README form.

Four T3 rules with no T4 counterpart were kept as `legacy-t3` items:
privileged-Docker flags, hidden instructions/AI scaffolding, agent-writable
ground truth, and a new line-endings check (below). Everything else the T3 seed
covered is now enforced by a shipped script.

### Verdict, not just a score

Static checks are CI gates, not points. A task failing one cannot merge however
well it scores elsewhere, so a review now leads with `VERDICT: BLOCKED` and the
list of failing checks. Compliance and coverage stay, below the verdict, for the
rubric criteria where a percentage means something.

### Rubric batching

35 criteria in one prompt made qwen2.5:3b abandon the schema and answer with a
single object keyed by the task name, leaving every rubric criterion unresolved.
Criteria now go out in batches of 6 (`T4_RUBRIC_BATCH`), out-of-batch and
invented ids are discarded, and a failed batch costs only its own criteria. On
`fix-typo` this took rubric resolution from 0/35 to 35/35 and coverage from 43%
to 95%. Model verdicts of `missing` on a rubric criterion are still downgraded
to `unknown`: a small local model is evidence of compliance, never proof of
violation.

### Line endings

`check-instruction-suffix` compares the closing sentence byte-exactly. A Windows
checkout makes it fail 65 of 66 already-merged tasks purely on CRLF. Task files
are normalised to LF for the check run and the CRLF is reported as its own
finding, rather than emitting a screenful of false failures or hiding a problem
that will fail real CI.

### Verification

`python3 -m unittest -q test_assessment.py` — 49 tests, all passing under WSL
with a clone present; 43 pass and 2 skip on Windows, where the checks cannot
run. The 18 original regressions and the 17 added in 1.2 are unchanged; legacy
tests now pin the T3 path explicitly, since T4 activates whenever a clone is
found. New coverage: policy discovery matches real scripts on disk, the policy
revision is recorded, retired T3 rules cannot return, a merged benchmark task
passes its own checks, CRLF is normalised and reported, ZIP extraction finds the
task root and refuses path traversal, static checks outrank the model, the model
cannot assert rubric noncompliance, and a review survives Ollama being down.

Measured on `fix-typo.zip`
(`a5a8968f0056c4a8374fee08d0db58db2986abe856667059ce258e12bb34e8be`) against
`v4.0.0-22-g83c7a617` with qwen2.5:3b:

```
VERDICT: BLOCKED — 6 static checks fail
  check-canary, check-instruction-suffix, check-separate-verifier,
  check-task-fields, check-task-package-name, check-test-sh-sanity
llm-assisted | 95% coverage | 35/35 rubric criteria resolved
```

Identical to running the benchmark's own scripts by hand.

### Still true

The checker never executes uploaded task code, never runs Docker, and never
performs the execution checks (`/validate`, `/run`, `/cheat`, `/fortify`) that
gate a real PR. It is a pre-flight mirror of the static half of CI plus an
advisory rubric pass. A clean verdict is not a merge decision.

The directory and module names still say "terminus 3". They are unchanged to
avoid breaking existing paths and bookmarks.


## Two programmes, two profiles (tb-review-2.1)

### Correction to the 2.0 notes

The 2.0 section above called several T3 rules "wrong", naming the canary rule
"inverted and dangerous" and the 1800-18000 agent timeout a false positive.
That was wrong, and the error mattered.

The Snorkel EC portal is live. It was rebuilt on 2026-09-07 and serves 43 docs.
It states, verbatim:

> Tasks must not include canary strings in **any** component - instruction,
> environment, solution, tests, or metadata. Canary strings exist to keep
> benchmark data out of training corpora; this is a training dataset, so they
> are excluded.

> Set `[agent].timeout_sec` to a **minimum of 1800 seconds (30 minutes)**, with
> a ceiling of 18000 seconds (5 hours).

So the original checker encoded its programme's rules correctly. These are two
different programmes whose rules are deliberately opposite:

| | Snorkel EC Terminus 3 | Terminal-Bench 4.0 |
|---|---|---|
| Purpose | training dataset | public benchmark |
| Canary strings | forbidden | required in 5 locations |
| Agent timeout | 1800-18000 | flat 28800 |
| Policy source | EC portal markdown | terminal-bench clone |

A task compliant with one is non-compliant with the other. Replacing T3 with T4
was therefore the wrong call, and 2.1 restores both as selectable profiles.

What remains true of the original checker: the `num_ctx` transport bug (the
model was never consulted), `unknown` scoring identically to `missing`, and the
docs-index extractor below. Those three are real and are fixed.

### The checklist refresh was broken by a minified symbol

`extract_docs_index` matched `const d8={sections:[...]},lx=`. `d8` and `lx` are
Vite-minified symbols regenerated on every portal build. The portal was rebuilt,
the pattern stopped matching, and the refresh returned zero docs while still
reporting success. The pattern now matches the shape of the data rather than the
bundler's naming, and recovers all 43 docs. Two regressions pin this: the
extractor must work across different minified symbol names, and must still
return empty on an unrelated bundle.

### Profiles

`T3_PROFILE` selects the programme: `t3`, `t4`, or `auto` (default; picks t4
when a usable clone is present, otherwise t3). The UI exposes both as links and
`/api/checklist?profile=` serves either. Every report names the active profile
and states that the two are not interchangeable.

Requesting `t4` without a usable clone now raises instead of silently falling
back to the EC ruleset. Scoring a benchmark task against training-dataset rules
is the exact confusion this release exists to prevent, and it must fail loudly.

The EC seed remains byte-identical to the original installation: 49 items,
`source_supported_checklist()` unchanged, `.terminus_checklist.json` still
`6d00bb3e...`.

### Verification

59 tests, green under WSL with a clone present. New coverage: explicit profile
beats autodetection, `T3_PROFILE` selects, auto falls back to EC without a
clone, a `t4` request without a clone is refused rather than downgraded, the EC
profile still scores against the unchanged 49-item seed, the report names the
profile and warns they differ, the two profiles provably disagree about the
canary, the endpoint serves either, and the docs extractor survives a rebuild.

### Known gap: harbor check

`harbor` 0.22.0 is installed but `harbor check` could not be run for comparison.
It provisions the task's Docker environment and runs a real trial, so it needs
both a running Docker daemon and agent credentials. Neither was available. The
rubric layer therefore remains unbenchmarked against the official checker.


## Findings split by evidence type (tb-review-2.2)

### Why

A single blended percentage inherits the reliability of its weakest input. The
`wdm-design` run reported 97/100 built from 23 reproducible static verdicts and
35 model opinions averaged together, and the reader could not tell which half
moved the number. On that same run the model marked a *merged benchmark task* as
possibly not `difficult` and not `interesting`, six criteria carried a status
contradicting their own evidence, and three restated the rubric guidance as if
it were a finding.

The findings themselves are useful. The aggregate over them was not.

### Buckets

Every result is now classified by how it was established, and the buckets are
never averaged:

- **Static gate** - the benchmark's own check scripts. Reproducible, byte-exact,
  identical to CI. This is the only bucket that blocks.
- **Verified** - our deterministic checks: parsed `task.toml` facts, file
  inventory, literal term scans, legacy scans.
- **Advisory** - model verdicts and unestablished placeholders. Labelled
  "opinion or unestablished, not a measurement" and presented as a reading list.

The report and the score card lead with the buckets. The old blended figures are
kept below them for continuity with earlier reports, explicitly marked as such.

### Echoed-guidance detector

A small model asked to judge 35 criteria often restates the guidance it was
given and marks the item satisfied. That reads like a verdict and is worth
nothing. Advisory findings whose evidence or recommendation is a substring of
the criterion's own guidance are flagged LOW CONFIDENCE. On `wdm-design` this
caught `rubric-ctrf-reporting` and `rubric-binary-reward`, the two items
identified by hand as prompt echo.

### Gate contamination fixed

`submission-line-endings` is ours, severity recommended, and CI never sees CRLF
because git normalises on commit. It was labelled `harbor static check`, landed
in the gate bucket, and flipped a merged task to FAIL. Classification now
prefers the checklist item's declared `source` over the free-text label, and the
finding is labelled `legacy scan`. A regression pins it: our own recommended
check cannot fail the benchmark gate.

### Verification

60 tests on Windows (2 skipped), 66 under WSL with a clone. New coverage: gate
and advisory counted separately, a failing advisory item does not fail the gate,
echoed guidance is flagged, a real finding is not flagged as echo, the EC
profile also separates verified from advisory, our recommended check cannot fail
the gate, and the report leads with the buckets before any blended figure.


## Reviewer-facing UI (tb-review-2.3)

### The checklist had become unusable

Findings were rendering correctly the whole time: checkboxes, status classes and
pills all worked. The problem was scale. 61 items, each printing its full
`why_it_matters` (up to 600 characters of rubric guidance, or a check script's
entire header comment) produced a **16,526-pixel page** with the checklist alone
occupying 15,341 of it. A reviewer could not find the flags because reaching
them meant scrolling past fifteen thousand pixels of prose.

Rebuilt around what a reviewer actually does:

- **Collapsed by default.** Each item is a `<details>` showing criterion, kind
  and status on one line. Failing gate items auto-expand; everything else opens
  on click. Guidance is truncated inside the body rather than printed in full.
- **Ordered by urgency.** Failing gate, then advisory, then passing. The
  blocking findings are met before the wall of green.
- **Filtered.** Needs attention (default), Failing gate, Advisory, Passed, All,
  plus an expand/collapse toggle and a running tally.
- **Kind is visible per row.** A `GATE` / `ADVISORY` / `CHECK` tag and a coloured
  left border carry the 2.2 bucket split down to the item, so the distinction
  between a reproducible gate and a model opinion survives at the point of use.

Measured on a 61-item review: page height 16,526px to 4,430px, and 22 items in
view instead of 61. "All" with everything collapsed is 7,566px.

This answers the "revert then improve" question as: nothing needed reverting.
The per-item flags were never lost, they were buried.

### Panels follow the chosen programme

Sources, the updates title and the category tables were hardcoded to Terminus 3.
They now switch with the profile:

|  | Terminus 3 | Terminus 4 |
|---|---|---|
| Title | Terminus-3 updates | Terminus-4 updates |
| Sources | `/portal/docs`, `/portal/category-status`, `/portal/changelog` | the benchmark's seven policy documents |
| Updates | portal changelog | dated policy-affecting commits from the clone |
| Categories | portal tables | `docs/TAXONOMY.md`, 31 subcategories across 7 domains |
| Policy | portal tables | ten settings read live from the check scripts |

The T4 policy table reads its values out of the scripts themselves
(`MAX_TIMEOUT_SEC`, `CANONICAL_PYTEST`, `REQUIRED_FIELDS`, `VALID_CATEGORIES`,
`MAX_TOKENS`) rather than restating them, so the panel cannot drift from what is
actually enforced. It carries the policy revision and the commit dates for
provenance.

A source the profile cannot reach is shown as **TBA** rather than omitted, so
"nothing published yet" is distinguishable from "we forgot to wire it up".

### Profile selector

Links became buttons. The active programme is filled green on white text, the
inactive one inverted (white on green, green border). An unavailable profile is
disabled with the reason shown rather than silently absent.

### Model field

Fixed at `qwen2.5:3b` and no longer editable: an `<output>` element styled green
on white. `HTMLOutputElement.value` still returns the model string, so the
review request is unchanged. Revisit when a larger model is adopted.

### Verification

69 tests on Windows (2 skipped), 75 under WSL with a clone. New coverage: panel
titles follow the profile, T3 sources are the portal paths, T4 sources are the
benchmark documents, a missing source reports TBA rather than hiding, the T4
changelog carries real dates and detail, an unreadable changelog says TBA, the
T4 category panel is taxonomy plus live policy read from the scripts, the two
profiles provably disagree in the policy panel about the canary, and
`checklist_response` carries panels for both profiles.

Browser-verified on both profiles: T4 shows 61 items with the benchmark sources
and `v4.0.0-22-g83c7a617` policy; T3 shows 49 items with the portal sources and
live portal changelog.


## Owner decisions, resilience and the review page (tb-review-2.5)

2.4 added the provenance artefacts (`baseline-t3.json`, `source-manifest.json`,
`source-gap-report.md`, `policy-diff.json`, `t3-to-t4-policy-diff.md`) produced
by `policy_provenance.py`. 2.5 applies the four owner decisions on top of that.

### Decisions applied

1. **Profile.** T3 is the default. T4 is used only when named (`?profile=t4`,
   `T3_PROFILE=t4`); a clone on disk makes T4 available, never selected. T4
   reports `preview` or `unavailable`, never `verified`. An unavailable T4
   refuses to assess instead of quietly scoring against T3, and T4 is
   unavailable if any of the seven manifest sources is missing from the clone.
2. **Unknowns.** Three layers, never averaged. *Static* (T4: the 22 check
   scripts; T3: the 11 rules whose evaluator reads parsed structure or an exact
   path) decides: any required fail is `policy_fail`. *Rubric* (model-assisted)
   can raise `review_required` but can neither establish nor deny compliance.
   *Advisory* is display only. A clean result under a non-stable profile is
   `profile_unverified`. A reviewer may resolve an `unknown` only, with name,
   evidence and reason; the original result and source stay on the record.
3. **Scores.** The page leads with the legacy blended figure because it was
   asked for as a reference, labelled "legacy experimental score" with its
   disclaimer and formula, and the overall state sits beside it as the decision.
   The TXT report puts the state first. Static, rubric and advisory counts are
   always shown separately. Advisory items are in no score.
4. **Model.** Default stays `qwen2.5:3b`. Each report records requested and
   actual model, tag, Ollama digest, call count, duration, success or fallback
   with the reason, prompt version and template hash, and the policy and source
   manifest hashes.

### Intentional behaviour changes (migration notes)

| Area | 2.4 | 2.5 | Why |
|---|---|---|---|
| T3 overall state | could never reach `policy_fail` | a parsed static failure gives `policy_fail` | a task with `timeout_sec = 28800` under T3 is a violation, not a question |
| Default profile | a clone on disk selected T4 | T3 unless T4 is named | decision 1 |
| Rubric "missing" | labelled missing | labelled `concern` | a model opinion is not a measured absence; legacy arithmetic unchanged (weight 0) |
| Hostile archive | exception, HTTP 500 | `ArchiveRejected`, HTTP 400 with the reason | it is the client's input that is wrong |
| Checklist save | direct overwrite | temp file, fsync, atomic replace; unreadable file quarantined | a failed write can no longer leave a half-written checklist |
| Portal text | every `_` deleted | emphasis removed, identifiers kept | reviewers saw `environmentmode` for `environment_mode`; the checklist-generation outline had the same damage |
| T4 static "Why" | first comment in the script (`Exit on error`) | the check's section in `docs/TASK_REVIEW_AUTOMATION.md` | description only; the T4 policy hash changes, no status does |
| T4 "updated" time | refresh stamped the current time | clone HEAD commit time, labelled "source updated" | re-reading the clone is not a policy change |
| Static files | string-prefix containment, directories accepted | `is_relative_to` the web root, files only | `/../web2/...` passed the old prefix test |
| `policy_provenance.py` | always rewrote the baseline | keeps `baseline-t3.json` unless `--rebaseline` | the baseline is evidence of the pre-change state |

Per-rule statuses did not move. `baseline_capture.py` over five real packages
(foodstuff-beta-activity, battleship-t2, fix-typo, fix-typo-t4,
wdm-design-merged), model stubbed: **no static-result differences** against the
2.4 capture under either profile. Every T3 state change (all five went from
`review_required` to `policy_fail`) traces to parsed evidence such as
`agent.timeout_sec = 28800.0` against the 18000 cap, or an unpinned `FROM` with
file and line.

### Resilience

- **Browser disconnect.** `BrokenPipeError`, `ConnectionResetError` and
  `ConnectionAbortedError` during a response are logged as one line
  (`[client-disconnect] POST /api/review during response delivery; ...`) with
  no traceback. A saved checklist stays saved when its response is lost, and
  the log says so. Generation failure, save failure and "saved but not
  delivered" are reported distinctly.
- **Atomic writes.** Same-directory temp file, flush, fsync, `os.replace`,
  previous file mode kept, temp removed on any failure. An unreadable checklist
  is moved to `.terminus_checklist.corrupt-<timestamp>.json`, the seed is used,
  and the page shows a recovery notice while any quarantined file exists.
- **Archives.** Checked before anything is read or extracted, from the raw
  names (`orig_filename`, because `zipfile` truncates at NUL):

  | Limit | Value | Basis (70 merged tasks) |
  |---|---|---|
  | upload body | 256 MiB | largest task 124.1 MiB |
  | entries | 5,000 | most 403 |
  | total uncompressed | 512 MiB | largest 124.1 MiB |
  | one entry | 256 MiB | largest file 94.7 MiB |
  | ratio per entry | 100:1 above 16 MiB | worst real 310:1, on a 0.5 MiB file |
  | ratio whole archive | 50:1 above 64 MiB | catches a bomb split into small files |
  | inspection time | 30 s | |

  Also rejected: absolute paths, drive letters, `..` escapes, control
  characters, symlinks, duplicate and case-colliding names, encrypted entries
  and unsupported compression. Oversized text members are inventoried with a
  read error instead of being loaded. Nothing from the archive is executed.

### Migration fixtures

`fixtures/migration/` holds two synthetic tasks, each differing from a clean
task in exactly one field, with the governing source text and its SHA-256 in
`.fixture.json`:

| Fixture | Difference | T3 | T4 |
|---|---|---|---|
| `t4-marker-gap` | no canary, timeout 3600 | static 11/11 pass, `review_required` | fails only `check-canary`, `policy_fail` |
| `t3-timeout-gap` | canary present, timeout 28800 | fails only `agent-timeout-range`, `policy_fail` | static 22/22 pass, `review_required` |

### Review page

Rewritten against the same API. The profile switch clears results, the report
and overrides but keeps the uploaded ZIP in page memory and offers "Review
under Terminus N?" without re-running it. A response produced under a
different profile than requested is discarded (`web/review-guard.js`, tested
with `node --test`). The ZIP is dropped onto a single target and reviewed
automatically; the result shows the state, the three layer counts and the
legacy figure. Source cards, changelog entries and status tables link to the
portal page, commit, document or check script behind them. Policies moved under
Latest Changes. Checks are expanded by default and carry their layer and their
measured cross-version lineage (from the policy diff, never inferred from
names).

### Verification

- Windows: 177 tests, OK, 8 skipped (they need bash to run the T4 check scripts).
- Ubuntu/WSL with the clone: 183 tests OK (full run by the second reviewer on
  10 Sep, including the lineage measurement test).
- `node --test web/review-guard.test.js`: 8 of 8.
- `fixtures/run_migration_fixtures.py`: 4 of 4 expectations.
- Browser, both profiles, `foodstuff-beta-activity.zip` with `qwen2.5:3b`: T3
  `policy_fail` in 61 s (3 static failures), T4 `review_required` in 86 s
  (22/22 static, 4 rubric concerns). An override on a static unknown moved the
  counts and appeared in the TXT export under HUMAN OVERRIDES.

### Rollback

The complete 2.4 tree is at `..\terminus-3-tool-enhanced.bak-2.4`. To roll back,
stop the server, move this directory aside, and copy the backup into its place.
`.terminus_checklist.json` has the same schema in both versions, so a checklist
saved by either loads in the other. Quarantined `.terminus_checklist.corrupt-*`
files are safe to delete once inspected.

### Still open

- `harbor check` was not compared against the rubric layer; it needs the
  owner's Anthropic key and is run by the owner.
- T4 rubric results come from a 3B model and are review evidence only.
- The T3 update button regenerates the saved checklist through the model; it
  was not exercised in the browser this round so the saved checklist was left
  untouched.
- Portal changelog entries have no anchors, so each card opens the changelog
  page rather than the entry.
