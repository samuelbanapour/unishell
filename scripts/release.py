#!/usr/bin/env python3
"""Cut a new UniShell release: bump the version, roll the changelog, tag.

Usage:
    scripts/release.py 0.2.0

What it does:
  1. Validates the working tree is clean and the new version is greater
     than the current one.
  2. Requires CHANGELOG.md to have real entries under [Unreleased] --
     refuses to release with an empty changelog.
  3. Updates the version in pyproject.toml and src/unishell/__init__.py.
  4. Renames [Unreleased] to [X.Y.Z] - YYYY-MM-DD in CHANGELOG.md, adds a
     fresh empty [Unreleased] section above it, and fixes the compare links.
  5. Commits the bump and creates an annotated git tag vX.Y.Z.

It does NOT push. Review the commit and tag, then:
    git push && git push --tags
which triggers the Azure Pipelines build and GitHub Release.
"""

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
INIT_PY = ROOT / "src" / "unishell" / "__init__.py"
CHANGELOG = ROOT / "CHANGELOG.md"
REPO_URL = "https://github.com/samuelbanapour/unishell"


def run(*cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=True, **kw)


def current_version():
    text = PYPROJECT.read_text()
    m = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    if not m:
        sys.exit("release: couldn't find version in pyproject.toml")
    return m.group(1)


def parse_version(v):
    parts = v.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        sys.exit(f"release: '{v}' is not a valid X.Y.Z version")
    return tuple(int(p) for p in parts)


def check_clean_tree():
    status = run("git", "status", "--porcelain").stdout
    if status.strip():
        sys.exit("release: working tree is not clean; commit or stash first:\n" + status)


def check_changelog_has_unreleased_entries():
    text = CHANGELOG.read_text()
    m = re.search(r"^## \[Unreleased\]\s*\n(.*?)(?=\n## \[|\Z)", text, re.MULTILINE | re.DOTALL)
    if not m or not m.group(1).strip():
        sys.exit(
            "release: CHANGELOG.md has no entries under [Unreleased].\n"
            "Add what changed before cutting a release."
        )


def bump_pyproject(new_version):
    text = PYPROJECT.read_text()
    text = re.sub(r'^version = "[^"]+"', f'version = "{new_version}"', text, count=1, flags=re.MULTILINE)
    PYPROJECT.write_text(text)


def bump_init(new_version):
    text = INIT_PY.read_text()
    text = re.sub(r'^__version__ = "[^"]+"', f'__version__ = "{new_version}"', text, count=1, flags=re.MULTILINE)
    INIT_PY.write_text(text)


def roll_changelog(new_version, old_version):
    today = date.today().isoformat()
    text = CHANGELOG.read_text()

    text = text.replace(
        "## [Unreleased]\n",
        f"## [Unreleased]\n\n## [{new_version}] - {today}\n",
        1,
    )

    text = re.sub(
        r"^\[Unreleased\]: .*$",
        f"[Unreleased]: {REPO_URL}/compare/v{new_version}...HEAD\n"
        f"[{new_version}]: {REPO_URL}/compare/v{old_version}...v{new_version}",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    CHANGELOG.write_text(text)


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} X.Y.Z")
    new_version = sys.argv[1]
    new_tuple = parse_version(new_version)

    old_version = current_version()
    if new_tuple <= parse_version(old_version):
        sys.exit(f"release: {new_version} is not greater than current version {old_version}")

    check_clean_tree()
    check_changelog_has_unreleased_entries()

    bump_pyproject(new_version)
    bump_init(new_version)
    roll_changelog(new_version, old_version)

    run("git", "add", "pyproject.toml", "src/unishell/__init__.py", "CHANGELOG.md")
    run(
        "git", "commit", "-m",
        f"Release v{new_version}\n\nCo-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>",
    )
    run("git", "tag", "-a", f"v{new_version}", "-m", f"UniShell v{new_version}")

    print(f"Bumped {old_version} -> {new_version}, committed, and tagged v{new_version}.")
    print("Review with `git show` / `git log -1`, then push with:")
    print("  git push && git push --tags")


if __name__ == "__main__":
    main()
