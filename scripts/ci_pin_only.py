#!/usr/bin/env python3
"""Is this pull request only a Play-Nice pin bump? Prints ``only=true`` or ``only=false``.

CI runs this before the long steps. ``true`` lets a job skip them; the job itself still runs and
reports, because it is a required check. The contract-freshness job is separate and still runs.

It is true only when ALL of these hold (anything else, any error, any doubt is false, so CI runs
everything):

* the event is ``pull_request`` (EVENT_NAME), and the checkout is a merge commit (HEAD^1 = base,
  HEAD^2 = the PR head);
* the diff HEAD^1..HEAD touches one file, .project/contracts/adoption.yaml, in one hunk;
* in that hunk one ``revision:`` line is replaced where it stands: the same line number, the same
  indentation, a different 40-hex sha;
* that line is the pin of the manifest the PR started from (HEAD^1): a plain file with one
  ``source:`` block at the top level, one ``revision`` key in the whole file, and nothing above the
  pin that could turn it into text or into another key's value (``pin_line``);
* at most one line is added with it, directly above: the comment the re-pin job writes, in its
  exact words (``# YYYY-MM-DD: auto re-pin, fast-forward from <old pin> (N commit(s); N file(s)
  under contracts/ changed)``, each N one to six digits, or ``?`` for the commits), with a real
  date and naming the pin it replaces;
* the whole diff is plain printable ASCII.

Both are read as git's own bytes, and the judge looks at WHERE the change sits as well as what each
line says. A revision-shaped line that moved to another key or another indentation changes what the
file means; a comment with other words in it (or a character a YAML reader takes as a line end) can
carry anything; and a line that reads ``revision: <sha>`` inside a block of text, under a second
``source:`` key or beside a second ``revision`` key prints the very diff a bump prints. All of them
run everything.

The judge is strict about the manifest on purpose, so a few honest shapes run everything too: a
blank line between ``source:`` and the pin, a list or a block above ``source:``, DOS line ends, a
pin that is the file's last line with no newline after it, a character outside ASCII above the
pin, a comment after the pin's sha (the re-pin job's own shape before 2026-10-18).

What a skip does not prove. The judge does not check that the rest of the manifest is valid YAML.
On a pull request the contract-freshness job only warns, so a well-formed sha that is not a real,
current Play-Nice commit passes this judge and is caught on main after it lands, not before. The
judge takes HEAD^1 as the base and HEAD as GitHub's test merge, as GitHub's pull_request checkout
makes them; it checks that HEAD^2 exists, not that it is the PR's head.

The same two functions judge the estate's review lane (agent-platform,
bin/mission_second_review.py: ``pin_line`` and ``pin_bump_only``). Keep them the same code; a
script compared them part by part on 2026-11-12, and each repo's own tests hold its own copy.

With GITHUB_OUTPUT set, the line is also appended there. When the answer is true a second line is
printed, a GitHub notice, so the skipped run says on its own page why it was short.
"""

import os
import re
import subprocess
import sys
from datetime import datetime

PIN_FILE = ".project/contracts/adoption.yaml"
INDEX_RE = re.compile(r"index [0-9a-f]{7,64}\.\.[0-9a-f]{7,64} 100(?:644|755)")
HUNK_RE = re.compile(r"@@ -([1-9][0-9]{0,8}) \+([1-9][0-9]{0,8})(,2)? @@ source:")  # git's only two shapes
REVISION_RE = re.compile(r"( +)revision: ([0-9a-f]{40})")
COMMENT_RE = re.compile(
    r"( +)# ([0-9]{4}-[0-9]{2}-[0-9]{2}): auto re-pin, fast-forward from ([0-9a-f]{7}) "
    r"\((?:[0-9]{1,6}|\?) commit\(s\); [0-9]{1,6} file\(s\) under contracts/ changed\)"
)
REVISION_KEY_RE = re.compile(r"""[ \t]*["']?revision["']?[ \t]*:""")  # any spelling of the key, at any indent
TOP_KEY_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*):(?: .*)?")  # a top-level line: a plain key
PLAIN_PAIR_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*: [A-Za-z0-9][A-Za-z0-9._/+-]*(?: +#.*)?")  # `key: plain-value`
# What git is asked for. The options switch off everything a git config could add to or take out of what it prints.
DIFF = (
    "diff",
    "--no-renames",
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--ignore-submodules=none",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "-U0",
    "HEAD^1",
    "HEAD",
)
NOTICE = (
    "::notice title=Play-Nice pin bump only::Only the pin's revision line changed, "
    "so the long steps of this job were skipped (scripts/ci_pin_only.py)."
)


def pin_line(base: bytes) -> tuple[int, str] | None:
    """(1-based line number, the line) of the pin in the manifest ``base``, or None when the file is not plain
    enough to say. Plain means: one ``source:`` alone on a top-level line, one ``revision`` key in the whole file
    and it sits under that ``source:``, every line above the pin a comment or a ``key: plain-value`` pair (so no
    block of text, quote, flow mapping, list, anchor or second document can have swallowed it), and nothing but
    comments after it until the next top-level key."""
    try:
        text = base.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if any(c != "\n" and (c < " " or c in "\x7f\x85\u2028\u2029") for c in text):
        return None  # a tab, a carriage return or another character a YAML reader may take as a line end
    lines = text.split("\n")
    sources = []
    for i, line in enumerate(lines):
        if line[:1] in ("", " ", "#"):
            continue
        key = TOP_KEY_RE.fullmatch(line)
        if not key:
            return None  # a document marker, a directive, a list item, a quoted key
        if key.group(1) == "source":
            sources.append(i)
    pins = [i for i, line in enumerate(lines) if REVISION_KEY_RE.match(line)]
    if len(sources) != 1 or len(pins) != 1 or lines[sources[0]] != "source:" or pins[0] < sources[0]:
        return None
    start, at = sources[0], pins[0]
    pin = REVISION_RE.fullmatch(lines[at])
    if not pin or not all(" " <= c <= "~" for line in lines[:at] for c in line):
        return None
    indent = pin.group(1)
    for line in lines[:start]:
        if line and not line.startswith("#") and not PLAIN_PAIR_RE.fullmatch(line):
            return None
    for line in lines[start + 1 : at]:
        rest = line[len(indent) :]
        if not line.startswith(indent) or not (rest.startswith("#") or PLAIN_PAIR_RE.fullmatch(rest)):
            return None
    for line in lines[at + 1 :]:
        if line[:1] not in ("", " ", "#"):
            break
        if line.strip(" ") and not line.lstrip(" ").startswith("#"):
            return None  # a key after the pin inside source:, or a value that carries on under it
    return at + 1, lines[at]


def is_pin_only(diff: bytes, base: bytes) -> bool:
    """Judge the bytes git prints for ``DIFF``, against the manifest as it was at HEAD^1.

    A pin bump has exactly one shape there: the four header lines of the one file, one hunk header
    that starts at the same line on both sides, the old revision line out, then the new one in, with
    at most the re-pin comment between them. And the line that goes out is the manifest's pin.
    """
    if not isinstance(diff, bytes) or not isinstance(base, bytes):
        return False
    try:
        text = diff.decode("ascii")
    except UnicodeDecodeError:
        return False
    if not text.endswith("\n") or not all(c == "\n" or " " <= c <= "~" for c in text):
        return False  # a tab, a carriage return, a NUL, or anything a YAML reader may read as a line end
    lines = text[:-1].split("\n")
    if len(lines) not in (7, 8) or lines[0] != f"diff --git a/{PIN_FILE} b/{PIN_FILE}":
        return False  # a second file or hunk, a mode change, a rename, a "\ No newline" marker
    if not INDEX_RE.fullmatch(lines[1]) or lines[2:4] != [f"--- a/{PIN_FILE}", f"+++ b/{PIN_FILE}"]:
        return False
    hunk, body = HUNK_RE.fullmatch(lines[4]), lines[5:]
    if not hunk or hunk.group(1) != hunk.group(2) or len(body) != (3 if hunk.group(3) else 2):
        return False  # the line moved, or it is not the one under source:
    if not body[0].startswith("-") or not all(line.startswith("+") for line in body[1:]):
        return False
    gone, came = REVISION_RE.fullmatch(body[0][1:]), REVISION_RE.fullmatch(body[-1][1:])
    if not gone or not came or gone.group(1) != came.group(1) or gone.group(2) == came.group(2):
        return False  # not a revision line, another indentation, or no bump at all
    if pin_line(base) != (int(hunk.group(1)), body[0][1:]):
        return False  # the line only looks like the pin: the file it came from says otherwise
    if len(body) == 2:
        return True
    comment = COMMENT_RE.fullmatch(body[1][1:])
    if not comment or comment.group(1) != gone.group(1) or comment.group(3) != gone.group(2)[:7]:
        return False  # other words, another indentation, or it names a pin that was not the old one
    try:
        datetime.strptime(comment.group(2), "%Y-%m-%d")
    except ValueError:
        return False
    return True


def git_bytes(*args: str) -> bytes:
    """What git prints, as bytes. Read as text, a carriage return would be gone before the judge saw it."""
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def pin_only(event_name: str) -> bool:
    if event_name != "pull_request":
        return False
    try:
        git_bytes("rev-parse", "-q", "--verify", "HEAD^2")
        return is_pin_only(git_bytes(*DIFF), git_bytes("cat-file", "blob", f"HEAD^1:{PIN_FILE}"))
    except Exception:  # any error at all is doubt, and doubt runs everything
        return False


def main() -> int:
    only = pin_only(os.environ.get("EVENT_NAME", ""))
    line = f"only={'true' if only else 'false'}"
    print(line)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    if only:
        print(NOTICE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
