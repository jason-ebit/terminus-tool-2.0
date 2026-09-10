# Start here: T3/T4 task checker

This started as the Terminus 3 checker and now reviews tasks under either programme. T3 (Snorkel EC) is the default. T4 (Terminal-Bench 4.0) is marked preview. The two have opposite rules in places, so a task can pass one and fail the other.

- `practice-tasks/`: three small T4 tasks. They pass Harbor's oracle run, fail the NOP run, and clear every T4 static check.
- `t3-to-t4-policy-diff.md`: what happened to each T3 rule in T4.
- `ASSESSMENT-CHANGES.md`: change notes by version. The tb-review-2.5 section is the latest.
- `docs/review/`: the second review, the open issues, and the wdm-design finding.

Run the site on WSL, Linux or macOS with a terminal-bench clone (T4 runs its bash check scripts):

```bash
T4_REPO=/path/to/terminal-bench python3 terminus_checklist_site.py
```

Open `http://127.0.0.1:8765` and pick the profile before dropping in a task ZIP. Ollama with `qwen2.5:3b` is needed for the rubric part; without it you still get the static checks.

# Terminus Docs Fetcher

Small CLI for fetching documentation from the Snorkel Terminus EC Training site.

The site is a single-page app, so deep links like:

```text
https://snorkel-ai.github.io/Terminus-EC-Training-stateful/portal/docs/getting-started/quick-start
```

return GitHub Pages 404 HTML when fetched directly. The app loads the actual docs
from markdown files under `/docs/{slug}.md`; `terminus_fetch.py` follows that same
route.

## Usage

```bash
python3 terminus_fetch.py
python3 terminus_fetch.py https://snorkel-ai.github.io/Terminus-EC-Training-stateful/portal/docs
python3 terminus_fetch.py https://snorkel-ai.github.io/Terminus-EC-Training-stateful/portal/docs/getting-started/quick-start
python3 terminus_fetch.py getting-started/quick-start --format text
python3 terminus_fetch.py getting-started/quick-start --format json -o quick-start.json
python3 terminus_fetch.py getting-started/quick-start --format summary
python3 terminus_fetch.py getting-started/quick-start --format summary --summary-model qwen2.5:3b
python3 terminus_fetch.py --list
```

The default target is `getting-started/welcome`, which is the page loaded by
`/portal/docs` in the app.

## Summaries with Ollama

`--format summary` sends the fetched markdown content to a local Ollama model and
prints the generated summary. The default model is `qwen2.5:3b`.

Make sure Ollama is running and the model is available:

```bash
ollama pull qwen2.5:3b
python3 terminus_fetch.py getting-started/quick-start --format summary
```

## Local Checklist Website

Run the local checklist and ZIP review website:

```bash
python3 terminus_checklist_site.py
```

Then open:

```text
http://127.0.0.1:8765
```

The site fetches these Terminus sources:

```text
https://snorkel-ai.github.io/Terminus-EC-Training-stateful/portal/docs
https://snorkel-ai.github.io/Terminus-EC-Training-stateful/portal/category-status
```

It uses local Ollama, defaulting to `qwen2.5:3b`, to build a source-grounded
checklist and review an uploaded Terminus task ZIP against that checklist.
