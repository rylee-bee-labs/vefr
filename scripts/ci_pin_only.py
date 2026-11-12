#!/usr/bin/env python3
"""Is this pull request only a Play-Nice pin bump? Prints ``only=true`` or ``only=false``.

CI runs this before the long steps. ``true`` lets a job skip them; the job itself still runs and
reports, because it is a required check. The contract-freshness job is separate and still runs.

It is true only when ALL of these hold (anything else, any error, any doubt is false, so CI runs
everything):

* the event is ``pull_request`` (EVENT_NAME), and the checkout is a merge commit (HEAD^1 = base,
  HEAD^2 = the PR head);
* the diff HEAD^1..HEAD touches one file, .project/contracts/adoption.yaml;
* every changed line in it is one of: the ``revision:`` line (one removed, one added, a 40-hex
  sha), or an added ``# YYYY-MM-DD: auto re-pin ...`` comment, the two things the re-pin job writes.

With GITHUB_OUTPUT set, the line is also appended there.
"""

import os
import re
import subprocess
import sys

PIN_FILE = ".project/contracts/adoption.yaml"
REVISION_RE = re.compile(r"^\s*revision: [0-9a-f]{40}$")
COMMENT_RE = re.compile(r"^\s*# \d{4}-\d{2}-\d{2}: auto re-pin\b.*$")
HEADER_PREFIXES = ("index ", "--- ", "+++ ")


def is_pin_only(diff: str) -> bool:
    """Judge the output of ``git diff --no-renames --no-ext-diff -U0 HEAD^1 HEAD``."""
    files = []
    in_hunk = False
    removed_rev = added_rev = changed = 0
    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            files.append(line)
            in_hunk = False
        elif line.startswith("@@"):
            in_hunk = True
        elif not in_hunk:
            if line and not line.startswith(HEADER_PREFIXES):
                return False  # mode change, binary file, rename, new or deleted file: not just text edits
        elif line.startswith("-") and REVISION_RE.match(line[1:]):
            removed_rev += 1
            changed += 1
        elif line.startswith("+") and REVISION_RE.match(line[1:]):
            added_rev += 1
            changed += 1
        elif line.startswith("+") and COMMENT_RE.match(line[1:]):
            changed += 1
        elif line:
            return False  # any other changed line, a removed comment, or a "\ No newline" marker
    return (
        files == [f"diff --git a/{PIN_FILE} b/{PIN_FILE}"]
        and (removed_rev, added_rev) == (1, 1)
        and changed > 0
    )


def pin_only(event_name: str) -> bool:
    if event_name != "pull_request":
        return False
    try:
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "HEAD^2"], check=True, capture_output=True
        )
        out = subprocess.run(
            ["git", "diff", "--no-renames", "--no-ext-diff", "--no-color", "-U0", "HEAD^1", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return is_pin_only(out)
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return False


def main() -> int:
    only = pin_only(os.environ.get("EVENT_NAME", ""))
    line = f"only={'true' if only else 'false'}"
    print(line)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
