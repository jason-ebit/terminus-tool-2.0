# Handoff brief: Terminus task checker, legacy to tb-review-2.5

For the reviewer writing the manager-facing changelog. Detail lives in
`ASSESSMENT-CHANGES.md`; this is the short version.

## Context in two lines

- There are two live programmes with **opposite rules**. Snorkel EC "Terminus 3"
  (training data): canary strings forbidden, agent timeout 1800 to 18000 s.
  Terminal-Bench 4.0 (public benchmark): canary required, timeout up to 28800 s.
  A task that passes one can fail the other. The tool now asks which one you mean.
- Repos: legacy = `terminus-3-tool-` (the original, "Hung's tool"). Current =
  `terminus-3-tool-enhanced`, now at `tb-review-2.5`. Nothing has been pushed,
  merged or published.

## What was wrong

**Legacy tool**
- Scored well (82/100 on `foodstuff-beta-activity`) partly because it rarely
  found problems, not because tasks were compliant. Some of its rules were wrong
  for the programme it claimed to check.
- One blended percentage mixed hard facts with model opinion, so nobody could
  tell what moved the number.
- Its markdown cleaner deleted every underscore, so policy keys reached
  reviewers as `environmentmode` instead of `environment_mode`.

**Enhanced tool before this work**
- Scored lower (50/100 on the same task) with the same model. Main causes: the
  model was not actually being consulted on the review path, "unknown" counted
  as failure, and the portal refresh broke when the site's minified code changed.
- Could not tell the two programmes apart. With a Terminal-Bench clone on disk
  it silently switched to Terminus 4 rules.
- Under Terminus 3 it could never report a hard fail, even for a clear
  violation such as a 28800 s timeout.
- No protection against hostile ZIPs, non-atomic saves, and noisy crashes when
  the browser disconnected.
- The page was a 16,000 px wall of text, and the category and policy panels
  rendered empty.

## What changed (changelog style)

| Version | Change |
|---|---|
| 1.1 to 1.2 | Model really consulted; unknown no longer counts as failure; TXT export. |
| 2.0 | Terminus 4 mode reads policy from the benchmark's own repo (22 check scripts + 35-item rubric) instead of hardcoding it. |
| 2.1 | Two explicit profiles, T3 and T4, stamped on every report. Portal refresh fixed. |
| 2.2 | Findings split by how they were established (deterministic vs model). |
| 2.3 | Usable review page: filters, collapsed rows, panels follow the profile. |
| 2.4 | Provenance: baseline capture, source manifest (10 sources, 0 gaps), full T3 to T4 rule diff (all 49 T3 rules have a recorded fate). |
| 2.5 | Owner decisions, resilience, new page. Below. |

**2.5 in brief**
- **Profiles:** T3 is the default. T4 only when chosen, labelled "preview"
  (never "verified" without owner sign-off). If T4 is unavailable it refuses
  rather than quietly using T3. T4 also refuses if any policy source is missing.
- **Verdicts:** three layers never averaged. Static (deterministic) can fail a
  task. Rubric (model) can only flag for review. Advisory is display only.
  States: Policy pass, Policy fail, Review required, Profile unverified.
- **Human overrides:** a reviewer can resolve an "unknown" with name, evidence
  and reason. The original result stays on record and appears in the report.
- **Score:** the old blended figure is kept, shown first for reference, labelled
  "legacy experimental score" with its formula and a disclaimer. It decides
  nothing.
- **Model:** unchanged, `qwen2.5:3b`. Every report records model, digest,
  duration, fallback reason, prompt version and policy hashes.
- **Cross-version labels:** each rule shows its T3/T4 counterpart and relation
  (unchanged, modified, replaced, removed...), taken from the verified diff.
  Tests check them against real behaviour on two purpose-built fixtures.
- **Safety:** ZIP limits based on measurements of all 70 real benchmark tasks,
  with 2x or more headroom. Path, symlink, zip-bomb and encrypted-entry checks.
  Nothing uploaded is executed. Atomic saves, a corrupt checklist is
  quarantined, and browser disconnects log one line instead of a traceback.
- **Page:** drag-and-drop ZIP with automatic review and a done/failed state.
  Linked source cards, changelog and policy tables. Status shown like the legacy
  tool (✅ / 🚫). Split counts beside the score. Changing profile clears stale
  results without re-running.
- **Fixes found along the way:** underscore-stripping bug; T4 descriptions now
  come from the benchmark's docs instead of script comments ("Exit on error");
  the static file server's path check hardened.

## Evidence

- Same five real tasks, before vs after: **no change in any per-rule result**
  under either profile. Only the overall state moved: T3 now correctly says
  Policy fail where parsed evidence proves a violation.
- Worked example, `foodstuff-beta-activity` (a merged T4 task):
  T3 = Policy fail (timeout 28800 over the cap, unpinned base images, missing
  T3 metadata). T4 = 22/22 static pass, Review required (4 model concerns).
  This is the opposite-rules problem, now visible instead of hidden.
- Tests: Windows 177 OK (8 skipped, they need bash for T4). Ubuntu 183 OK
  (full run by the second reviewer). JS: 8/8. Migration fixtures: 4/4.

## Limitations and documentation gaps

- **Terminus 4 has no update board or changelog page.** Policy is read from a
  local git clone (`harbor-framework/terminal-bench`). "Updates" are
  policy-affecting commits. The tool is only as current as the last `git pull`.
- **Terminus 3 portal** is a JavaScript app. The tool reads its markdown route.
  Changelog entries have no anchors, so links open the page, not the entry.
- **T4 is "preview"** until an owner approves it. Open policy questions are
  listed in `source-gap-report.md`.
- **Model rubric results are opinions** from a 3B model. They flag for review
  and are never treated as proof either way.
- **Not compared with the official `harbor check`**: that needs the owner's
  Anthropic API key and should be run by the owner.
- **Windows alone cannot run T4** (the benchmark checks are bash scripts). Run
  under WSL, Linux or macOS.
- The T3 "update" button regenerates the saved checklist through the model; it
  was not re-exercised in the browser this round.

## Decisions still needing the owner

1. Approve T4 moving from preview to verified.
2. Confirm which 11 T3 rules count as deterministic (static) blockers.
3. Keep the legacy score shown first on the page (the report puts the state first).
4. New blocking T4 rules, and T3 blockers dropped for T4, as listed in the diff.
5. Whether to try a larger model later (default stays 3B for now).

## Where things are

- Code: `C:\Users\acer\Documents\GitHub\terminus-3-tool-enhanced`
- Full notes: `ASSESSMENT-CHANGES.md` (2.5 section has migration table and rollback)
- Rule diff: `t3-to-t4-policy-diff.md`, gaps: `source-gap-report.md`
- Rollback: full 2.4 copy at `..\terminus-3-tool-enhanced.bak-2.4`
- Run (WSL): `T4_REPO=/mnt/c/Users/acer/Documents/GitHub/terminal-bench python3 terminus_checklist_site.py`

## Suggested next steps

1. Owner runs `harbor check` on one task and compares with the rubric layer.
2. Owner decisions above.
3. Build the 2 to 3 new T4 tasks that were requested earlier (not started; topics needed).
