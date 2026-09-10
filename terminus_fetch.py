#!/usr/bin/env python3
"""Fetch Terminus EC Training documentation pages.

The GitHub Pages app is a single-page application, so deep links such as
`/portal/docs/getting-started/quick-start` return GitHub's 404 HTML when fetched
directly. The app itself loads markdown from `/docs/{slug}.md`; this tool follows
that same path and optionally discovers the current docs index from the JS bundle.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://snorkel-ai.github.io/Terminus-EC-Training-stateful/"
DEFAULT_DOC_SLUG = "getting-started/welcome"
DEFAULT_SUMMARY_MODEL = "qwen2.5:3b"
DOCS_ROUTE_MARKER = "/portal/docs/"
PORTAL_ROUTE_SLUGS = {
    "/portal/category-status": "reference/category-status",
    "/portal/changelog": "reference/changelog",
}
USER_AGENT = "terminus-fetch/1.0"
OLLAMA_REPAINT_PATTERN = re.compile(r"[^\n]*\x1b\[[0-9]+D\x1b\[K")
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "script":
            return
        attr_map = dict(attrs)
        src = attr_map.get("src")
        if src:
            self.scripts.append(src)


def fetch_text(url: str) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            content_type = response.headers.get("content-type", "")
            return response.read().decode(charset, errors="replace"), content_type
    except HTTPError as exc:
        raise SystemExit(f"Fetch failed: {url} returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise SystemExit(f"Fetch failed: {url}: {exc.reason}") from exc


def discover_bundle_url(base_url: str) -> str:
    html, _ = fetch_text(base_url)
    parser = AssetParser()
    parser.feed(html)
    candidates = [src for src in parser.scripts if "/assets/index-" in src and src.endswith(".js")]
    if not candidates:
        raise SystemExit("Could not find the Terminus app bundle in the site HTML.")
    return urljoin(base_url, candidates[-1])


def extract_docs_index(bundle: str) -> list[dict[str, str]]:
    """Pull the docs index out of the portal's minified SPA bundle.

    The original pattern hardcoded `const d8={sections:[...]},lx=`. `d8` and
    `lx` are Vite-minified symbols that are regenerated on every rebuild, so a
    routine portal redeploy silently reduced this to zero docs while the
    refresh still reported success. Match the shape of the data instead of
    whatever the bundler happened to name it.
    """
    match = re.search(
        r"=\{sections:\[(?P<sections>.*?)\]\}(?=\s*,\s*[A-Za-z_$])", bundle, re.S
    )
    if not match:
        return []

    docs: list[dict[str, str]] = []
    section_blocks = re.finditer(
        r'\{title:"(?P<section>[^"]+)",items:\[(?P<items>.*?)\]\}',
        match.group("sections"),
    )
    for section_match in section_blocks:
        section = section_match.group("section")
        item_blocks = re.finditer(
            r'\{slug:"(?P<slug>[^"]+)",title:"(?P<title>[^"]+)"\}',
            section_match.group("items"),
        )
        for item_match in item_blocks:
            docs.append(
                {
                    "section": section,
                    "slug": item_match.group("slug"),
                    "title": item_match.group("title"),
                }
            )
    return docs


def slug_from_input(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme and parsed.netloc:
        path = parsed.path.rstrip("/")
        if path.endswith("/portal/docs"):
            slug = DEFAULT_DOC_SLUG
        else:
            route_slug = next(
                (
                    route_slug
                    for route_path, route_slug in PORTAL_ROUTE_SLUGS.items()
                    if path.endswith(route_path)
                ),
                None,
            )
            if route_slug:
                slug = route_slug
            else:
                marker_index = parsed.path.find(DOCS_ROUTE_MARKER)
                if marker_index == -1:
                    raise SystemExit(
                        f"URL is not a known Terminus docs route: {value}"
                    )
                slug = parsed.path[marker_index + len(DOCS_ROUTE_MARKER) :]
    else:
        slug = value

    slug = slug.strip("/")
    if slug.endswith(".md"):
        slug = slug[:-3]
    if not slug:
        raise SystemExit("A non-empty docs slug or docs URL is required.")
    if ".." in slug or slug.startswith("/"):
        raise SystemExit(f"Unsafe docs slug: {slug!r}")
    return slug


def markdown_url(base_url: str, slug: str) -> str:
    return urljoin(base_url, f"docs/{slug}.md")


def markdown_to_text(markdown: str) -> str:
    text = re.sub(r"```.*?```", lambda m: m.group(0).strip("`"), markdown, flags=re.S)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s{0,3}[-*+]\s+", "- ", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def summary_prompt(markdown: str, title: str | None, slug: str) -> str:
    heading = title or slug
    return f"""Summarize this Terminus EC Training documentation page.

Page: {heading}

Write a concise, useful summary for a developer. Include:
- The main purpose of the page
- Key setup steps or requirements
- Important warnings or gotchas
- Recommended next actions

Keep it clear and practical.

Documentation content:
{markdown}
"""


def summarize_with_ollama(
    markdown: str,
    *,
    model: str,
    title: str | None,
    slug: str,
    timeout: int,
) -> str:
    if shutil.which("ollama") is None:
        raise SystemExit("Ollama is not installed or is not available on PATH.")

    prompt = summary_prompt(markdown, title, slug)
    try:
        result = subprocess.run(
            ["ollama", "run", model, "--nowordwrap"],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SystemExit(f"Ollama summary timed out after {timeout} seconds.") from exc

    if result.returncode != 0:
        stderr = result.stderr.strip()
        hint = f": {stderr}" if stderr else ""
        raise SystemExit(f"Ollama failed while running model {model!r}{hint}")

    summary = OLLAMA_REPAINT_PATTERN.sub("", result.stdout)
    summary = ANSI_ESCAPE_PATTERN.sub("", summary)
    summary = summary.replace("\r", "")
    return summary.strip() + "\n"


def build_payload(
    base_url: str,
    slug: str,
    markdown: str,
    docs: list[dict[str, str]],
) -> dict[str, Any]:
    metadata = next((doc for doc in docs if doc["slug"] == slug), {})
    return {
        "source_url": f"{base_url.rstrip('/')}/portal/docs/{slug}",
        "markdown_url": markdown_url(base_url, slug),
        "slug": slug,
        "title": metadata.get("title"),
        "section": metadata.get("section"),
        "content": markdown,
    }


def write_output(content: str, output_path: str | None) -> None:
    if output_path:
        Path(output_path).write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch markdown content from the Terminus EC Training docs site."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=DEFAULT_DOC_SLUG,
        help=f"Docs slug or full /portal/docs/... URL. Defaults to {DEFAULT_DOC_SLUG}.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Training site base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "text", "json", "summary"),
        default="markdown",
        help="Output format. Default: markdown.",
    )
    parser.add_argument(
        "--summary-model",
        default=DEFAULT_SUMMARY_MODEL,
        help=f"Ollama model to use when --format summary is selected. Default: {DEFAULT_SUMMARY_MODEL}",
    )
    parser.add_argument(
        "--summary-timeout",
        type=int,
        default=300,
        help="Seconds to wait for Ollama summary generation. Default: 300.",
    )
    parser.add_argument("-o", "--output", help="Write output to this file.")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List docs discovered from the current app bundle instead of fetching content.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/") + "/"
    bundle_url = discover_bundle_url(base_url)
    bundle, _ = fetch_text(bundle_url)
    docs = extract_docs_index(bundle)

    if args.list:
        write_output(json.dumps(docs, indent=2) + "\n", args.output)
        return 0

    slug = slug_from_input(args.target)
    content, content_type = fetch_text(markdown_url(base_url, slug))
    if "text/html" in content_type.lower():
        raise SystemExit(f"Expected markdown but received HTML for slug: {slug}")

    metadata = next((doc for doc in docs if doc["slug"] == slug), {})

    if args.format == "json":
        output = json.dumps(build_payload(base_url, slug, content, docs), indent=2) + "\n"
    elif args.format == "summary":
        output = summarize_with_ollama(
            content,
            model=args.summary_model,
            title=metadata.get("title"),
            slug=slug,
            timeout=args.summary_timeout,
        )
    elif args.format == "text":
        output = markdown_to_text(content)
    else:
        output = content

    write_output(output, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
