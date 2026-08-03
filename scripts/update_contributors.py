#!/usr/bin/env python3
"""Regenerate the README contributors stats table (avatars, profiles, LOC).

Fills the block between:
  <!-- CONTRIBUTORS-STATS:START -->
  <!-- CONTRIBUTORS-STATS:END -->

Uses the GitHub Contributors API for logins/avatars, git numstat for lines
of code, and .all-contributorsrc for contribution-type badges.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
ALL_CONTRIBUTORS_PATH = REPO_ROOT / ".all-contributorsrc"
OWNER = "protocorn"
REPO = "clippy-vision"
AVATAR_SIZE = 64

START = "<!-- CONTRIBUTORS-STATS:START -->"
END = "<!-- CONTRIBUTORS-STATS:END -->"

# all-contributors emoji keys we surface in the table
TYPE_EMOJI = {
    "code": "💻",
    "doc": "📖",
    "design": "🎨",
    "ideas": "🤔",
    "bug": "🐛",
    "maintenance": "🚧",
    "review": "👀",
    "test": "⚠️",
    "infra": "🚇",
    "translation": "🌍",
    "example": "💡",
    "question": "💬",
    "tutorial": "✅",
    "blog": "📝",
    "audio": "🔊",
    "video": "📹",
    "tool": "🔧",
    "fundingFinding": "🔍",
    "financial": "💵",
    "projectManagement": "📆",
    "security": "🛡️",
    "data": "🔣",
    "userTesting": "📓",
    "eventOrganizing": "📋",
}


def github_request(url: str) -> object:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "clippy-vision-contributors",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_contributors() -> list[dict]:
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contributors?per_page=100&anon=false"
    data = github_request(url)
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected contributors response: {data!r}")
    return [c for c in data if c.get("type") == "User" and c.get("login")]


def fetch_commit_login_map() -> dict[str, str]:
    """Map commit author email / name -> GitHub login via recent commits."""
    mapping: dict[str, str] = {}
    page = 1
    while page <= 10:
        url = (
            f"https://api.github.com/repos/{OWNER}/{REPO}/commits"
            f"?per_page=100&page={page}"
        )
        try:
            batch = github_request(url)
        except urllib.error.HTTPError:
            break
        if not isinstance(batch, list) or not batch:
            break
        for commit in batch:
            author = commit.get("author") or {}
            login = author.get("login")
            if not login:
                continue
            info = (commit.get("commit") or {}).get("author") or {}
            email = (info.get("email") or "").strip().lower()
            name = (info.get("name") or "").strip().lower()
            if email:
                mapping[email] = login
            if name:
                mapping[f"name:{name}"] = login
        if len(batch) < 100:
            break
        page += 1
    return mapping


def parse_noreply_login(email: str) -> str | None:
    # 123456+login@users.noreply.github.com or login@users.noreply.github.com
    m = re.match(
        r"^(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com$",
        email,
        re.I,
    )
    return m.group(1) if m else None


def compute_loc_by_login(login_map: dict[str, str]) -> dict[str, dict[str, int]]:
    """Return login -> {commits, added, deleted} from git history."""
    result = subprocess.run(
        ["git", "log", "--format=%aN|%aE", "--numstat", "--no-merges"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
        errors="replace",
    )

    stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"commits": 0, "added": 0, "deleted": 0}
    )
    current_login: str | None = None

    for raw in result.stdout.splitlines():
        line = raw.rstrip("\n")
        if "|" in line and "\t" not in line:
            name, _, email = line.partition("|")
            name_l = name.strip().lower()
            email_l = email.strip().lower()
            login = (
                login_map.get(email_l)
                or login_map.get(f"name:{name_l}")
                or parse_noreply_login(email_l)
                or name.strip()
            )
            current_login = login
            stats[current_login]["commits"] += 1
            continue

        if current_login and "\t" in line:
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            try:
                added = 0 if parts[0] == "-" else int(parts[0])
                deleted = 0 if parts[1] == "-" else int(parts[1])
            except ValueError:
                continue
            stats[current_login]["added"] += added
            stats[current_login]["deleted"] += deleted

    return stats


def load_contribution_types() -> dict[str, list[str]]:
    if not ALL_CONTRIBUTORS_PATH.exists():
        return {}
    data = json.loads(ALL_CONTRIBUTORS_PATH.read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for person in data.get("contributors") or []:
        login = person.get("login")
        if login:
            out[login] = list(person.get("contributions") or [])
    return out


def format_int(n: int) -> str:
    return f"{n:,}"


def types_cell(types: list[str]) -> str:
    if not types:
        return "💻"
    parts = []
    for t in types:
        emoji = TYPE_EMOJI.get(t, "✨")
        parts.append(f'{emoji}&nbsp;<sub>{t}</sub>')
    return "<br/>".join(parts)


def build_table(
    contributors: list[dict],
    loc: dict[str, dict[str, int]],
    types: dict[str, list[str]],
) -> str:
    lines = [
        "",
        "| | Contributor | Types | Commits | Lines added | Lines removed |",
        "| :---: | :--- | :--- | ---: | ---: | ---: |",
    ]

    # Prefer GitHub API order (most commits first); attach LOC when available.
    seen: set[str] = set()
    rows: list[tuple[str, dict, dict[str, int]]] = []

    for c in contributors:
        login = c["login"]
        seen.add(login.lower())
        s = loc.get(login) or loc.get(login.lower()) or {
            "commits": int(c.get("contributions") or 0),
            "added": 0,
            "deleted": 0,
        }
        # If API commits exist but git mapping missed LOC under different key
        if s["added"] == 0 and s["deleted"] == 0:
            for key, val in loc.items():
                if key.lower() == login.lower():
                    s = val
                    break
        rows.append((login, c, s))

    # Include anyone with LOC but missing from API (unlikely)
    for key, s in loc.items():
        if key.lower() in seen:
            continue
        if s["added"] == 0 and s["deleted"] == 0 and s["commits"] == 0:
            continue
        # skip raw author names that aren't github logins when API list is present
        if contributors and key.lower() not in {c["login"].lower() for c in contributors}:
            # only add if it looks like a github login already in types
            if key not in types:
                continue
        rows.append(
            (
                key,
                {
                    "login": key,
                    "html_url": f"https://github.com/{key}",
                    "avatar_url": f"https://github.com/{key}.png",
                },
                s,
            )
        )

    rows.sort(key=lambda r: (-r[2]["added"], -r[2]["commits"], r[0].lower()))

    for login, c, s in rows:
        avatar = c.get("avatar_url") or f"https://github.com/{login}.png"
        profile = c.get("html_url") or f"https://github.com/{login}"
        avatar_md = (
            f'<a href="{profile}">'
            f'<img src="{avatar}" width="{AVATAR_SIZE}" height="{AVATAR_SIZE}" '
            f'alt="{login}"/></a>'
        )
        name_md = f'<a href="{profile}"><b>@{login}</b></a>'
        lines.append(
            "| "
            f"{avatar_md} | {name_md} | {types_cell(types.get(login, ['code']))} | "
            f"{format_int(s['commits'])} | +{format_int(s['added'])} | "
            f"−{format_int(s['deleted'])} |"
        )

    lines.append("")
    lines.append(
        "<sub>Stats are regenerated automatically from git history by "
        "<code>scripts/update_contributors.py</code>.</sub>"
    )
    lines.append("")
    return "\n".join(lines)


def replace_section(readme: str, table: str) -> str:
    pattern = re.compile(
        re.escape(START) + r".*?" + re.escape(END),
        re.DOTALL,
    )
    replacement = f"{START}\n{table}{END}"
    if not pattern.search(readme):
        raise SystemExit(
            f"Could not find {START} ... {END} markers in README.md"
        )
    return pattern.sub(replacement, readme)


def main() -> int:
    try:
        contributors = fetch_contributors()
    except Exception as exc:  # noqa: BLE001 — surface clear CI error
        print(f"Failed to fetch GitHub contributors: {exc}", file=sys.stderr)
        return 1

    login_map = fetch_commit_login_map()
    loc = compute_loc_by_login(login_map)
    types = load_contribution_types()
    table = build_table(contributors, loc, types)

    readme = README_PATH.read_text(encoding="utf-8")
    updated = replace_section(readme, table)
    if updated == readme:
        print("README contributors section already up to date.")
        return 0

    README_PATH.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Updated {README_PATH.relative_to(REPO_ROOT)} with {len(contributors)} contributors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
