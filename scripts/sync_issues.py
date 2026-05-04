#!/usr/bin/env python3
"""
Sync GitHub Issues to Jekyll _posts/
Run in GitHub Actions or locally for preview.

Environment variables:
  GITHUB_TOKEN          - GitHub token (optional for public repos)
  GITHUB_REPOSITORY     - "owner/repo" (default: ciceroxiao/hong525)
"""
import os
import re
import json
import urllib.request
from pathlib import Path
from datetime import datetime


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "ciceroxiao/hong525")
IGNORE_LABELS = {"bug", "duplicate", "question", "invalid", "no-blog"}


def api_request(url: str) -> list:
    """Make authenticated GitHub API request and return JSON."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")

    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def fetch_issues() -> list:
    """Fetch all issues (not PRs) from the repository."""
    owner, repo = GITHUB_REPOSITORY.split("/", 1)
    url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=all&per_page=100"
    data = api_request(url)
    # Filter out pull requests
    return [i for i in data if "pull_request" not in i]


def slugify(text: str) -> str:
    """Convert title to URL-friendly slug."""
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s]+", "-", text)
    return text[:50]


def escape_yaml_string(value: str) -> str:
    """Escape a string for YAML front matter."""
    return value.replace('"', '\\"')


def format_yaml_list(items: list) -> str:
    """Format a Python list as YAML inline list."""
    if not items:
        return "[]"
    quoted = []
    for item in items:
        # Quote items that contain YAML special characters
        if any(c in item for c in [":", "#", "{", "}", "[", "]", ",", "&", "*", "?", "|", "-", "<", ">", "=", "!", "%", "@", "`", "'", '"']):
            escaped = item.replace("\\", "\\\\").replace('"', '\\"')
            quoted.append(f'"{escaped}"')
        else:
            quoted.append(item)
    return "[" + ", ".join(quoted) + "]"


def generate_posts():
    posts_dir = Path("_posts")
    posts_dir.mkdir(exist_ok=True)

    # Remove existing posts to ensure clean sync
    for f in posts_dir.glob("*.md"):
        f.unlink()
        print(f"Removed old: {f.name}")

    issues = fetch_issues()
    if not issues:
        print("No issues found.")
        return

    generated = 0
    for issue in issues:
        labels = [l["name"] for l in issue.get("labels", [])]

        # Skip ignored labels
        if any(l.lower() in IGNORE_LABELS for l in labels):
            print(f"Skipped #{issue['number']} (ignored label)")
            continue

        number = issue["number"]
        title = issue.get("title", "Untitled")
        body = issue.get("body") or ""
        created_at = issue["created_at"]

        # Parse date
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d")
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S %z")

        slug = slugify(title)
        filename = f"{date_str}-{slug}-{number}.md"

        # Strip leading front matter from issue body if present
        # (some issues were copied from markdown files that already had front matter)
        clean_body = body
        if clean_body.strip().startswith("---"):
            parts = clean_body.split("---", 2)
            if len(parts) >= 3:
                clean_body = parts[2].lstrip("\n")

        # Build front matter
        front_matter_lines = [
            "---",
            "layout: post",
            f'title: "{escape_yaml_string(title)}"',
            f"date: {time_str}",
            f"issue_url: {issue['html_url']}",
            f"issue_number: {number}",
            f"categories: {format_yaml_list(labels)}",
            "---",
            "",
        ]

        filepath = posts_dir / filename
        filepath.write_text("\n".join(front_matter_lines) + clean_body, encoding="utf-8")
        print(f"Generated: {filename}")
        generated += 1

    print(f"\nDone. Generated {generated} posts.")


if __name__ == "__main__":
    generate_posts()
