"""scripts/ci_pin_only.py decides whether CI may skip the long steps for a Play-Nice pin bump.

The yes behind it covers "a change that only bumps a version line", so the judge reads the diff
itself, as git's own bytes, and it reads WHERE the change sits as well as what each line says: one
hunk under ``source:``, the revision line replaced where it stands, at most the re-pin job's one
comment directly above. It also reads the manifest the PR started from, because a line that reads
``revision: <sha>`` inside a block of text or under a second key prints the very diff a bump
prints. Every doubt must give only=false (everything runs).

The judge and the tables below are shared with the estate's review lane (agent-platform,
bin/mission_second_review.py and tests/test_second_review_super_speed.py): keep them the same. The
comment's words are written by the estate's re-pin job (agent-platform, bin/contract-repin). They
are copied here, so if that job ever changes its words the skip simply stops (CI runs everything)
until this file and the script follow.
"""

import ast
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ci_pin_only.py"
WORKFLOWS = ROOT / ".github" / "workflows"

# -- the tables: the same ones the review lane's tests use ------------------------------------------------------------
PIN = ".project/contracts/adoption.yaml"
OLD_SHA, NEW_SHA, THIRD_SHA = "a" * 40, "b" * 40, "c" * 40
UPSTREAM = "  repository: rylee-bee-labs/play-nice-contracts\n"
OLD_NOTE = "  # 2026-11-01: auto re-pin, fast-forward from 4fa9afe (1 commit(s); 0 file(s) under contracts/ changed)\n"
REV_OLD, REV_NEW = f"  revision: {OLD_SHA}\n", f"  revision: {NEW_SHA}\n"
PIN_BASE = (
    f"schema: play-nice/adoption-v1\nsource:\n{UPSTREAM}"
    f"{OLD_NOTE}{REV_OLD}freshness:\n  policy: require-current\nalways:\n  - secrets-and-data\n")


# What the re-pin job writes: one new dated comment above the revision line, and the revision line itself. The job
# lives in agent-platform (bin/contract-repin: repin_note, repin_text), so its words are copied here by hand.
def note_for(old, indent="  ", commits=1, files=0):
    """The one comment the re-pin job writes above the revision line it replaces."""
    return (
        f"{indent}# 2026-11-02: auto re-pin, fast-forward from {old[:7]} "
        f"({commits} commit(s); {files} file(s) under contracts/ changed)\n"
    )


def tool_bump(base: str, new: str = "b" * 40) -> str:
    """`base` with its pin moved to `new`, the way the re-pin job writes it."""
    (indent, old), = re.findall(r"^( +)revision: ([0-9a-f]{40})$", base, flags=re.M)
    return base.replace(f"{indent}revision: {old}\n", note_for(old, indent) + f"{indent}revision: {new}\n")


NEW_NOTE = note_for(OLD_SHA)
PIN_BUMP = tool_bump(PIN_BASE)
DROPPED = PIN_BASE.replace("  - secrets-and-data\n", "")    # the same manifest with a contract taken off its list

# What `git diff -U0` prints for the two real bumps of PIN_BASE (its pin is line 5). Every odd shape below is one change
# away from one of them, so each is turned down by the one rule it is named for.
DIFF_HEAD = f"diff --git a/{PIN} b/{PIN}\nindex 1111111..2222222 100644\n--- a/{PIN}\n+++ b/{PIN}\n"
OK = DIFF_HEAD + f"@@ -5 +5,2 @@ source:\n-{REV_OLD}+{NEW_NOTE}+{REV_NEW}"
OK_BARE = DIFF_HEAD + f"@@ -5 +5 @@ source:\n-{REV_OLD}+{REV_NEW}"
NOTE, LIVE_KEY = NEW_NOTE[:-1], "  repository: someone-else/contracts\n"
GOOD_DIFFS = {
    "the tool's bump": OK,
    "the revision line alone": OK_BARE,
    "a commit count the tool could not read":    # the job's own word for it when GitHub gave no number
        OK.replace(NEW_NOTE, note_for(OLD_SHA, commits="?")),
    "counts of several digits": OK.replace("(1 commit(s); 0 file(s)", "(12 commit(s); 345 file(s)"),
    "counts of six digits": OK.replace("(1 commit(s); 0 file(s)", "(123456 commit(s); 654321 file(s)"),
    "an executable manifest": OK.replace("100644", "100755"),
    "full-length blob names": OK.replace("1111111..2222222", "1" * 40 + ".." + "2" * 64),
}
ODD_DIFFS = {
    # the whole diff
    "nothing changed": "",
    "only the file header": DIFF_HEAD,
    "no final newline in the diff": OK[:-1],
    "a 41st character where the last newline should be": OK[:-1] + "c",
    "no newline at the end of the file": OK + "\\ No newline at end of file\n",
    "no newline at the end of the file, on the bare bump": OK_BARE + "\\ No newline at end of file\n",
    "a blank first line": "\n" + OK,
    "a blank last line": OK + "\n",
    "a second hunk": OK + f"@@ -9 +10 @@ source:\n-{REV_OLD}+{REV_NEW}",
    "a second file": OK + "diff --git a/README.md b/README.md\nindex 1111111..2222222 100644\n",
    "the bump twice": OK + OK,
    "carriage returns": OK.replace("\n", "\r\n"),
    "a carriage return on the new line only": OK[:-1] + "\r\n",
    "a NUL on the new line": OK[:-1] + "\x00\n",
    # the four header lines
    "a mode change": f"diff --git a/{PIN} b/{PIN}\nold mode 100644\nnew mode 100755\n",
    "a mode change with the bump": OK.replace("index ", "old mode 100644\nnew mode 100755\nindex "),
    "a symlink": OK.replace("100644", "120000"),
    "no index line": OK.replace("index 1111111..2222222 100644\n", ""),
    "an index line with no mode": OK.replace("2222222 100644", "2222222"),
    "words after the index mode": OK.replace("100644\n", "100644 and more\n"),
    "another file on the diff line": OK.replace(f"diff --git a/{PIN} b/{PIN}", f"diff --git a/{PIN} b/README.md"),
    "another file on the old-name line": OK.replace(f"--- a/{PIN}", "--- a/README.md"),
    "another file on the new-name line": OK.replace(f"+++ b/{PIN}", "+++ b/README.md"),
    "a new file": OK.replace(f"--- a/{PIN}", "--- /dev/null"),
    # the hunk header
    "a hunk header that is not one": OK.replace("@@ -5 +5,2 @@ source:", "@@ garbage"),
    "the line moved down": OK.replace("+5,2", "+6,2"),
    "another line of the file": OK.replace("-5 +5,2", "-4 +4,2"),
    "under another key": OK.replace("@@ source:", "@@ freshness:"),
    "under no key": OK.replace(" @@ source:", " @@"),
    "words after the key": OK.replace("@@ source:", "@@ source: and more"),
    "more lines than the header says": OK.replace("+5,2", "+5,3"),
    "fewer lines than the header says": OK_BARE.replace("+5 @@", "+5,2 @@"),
    "two lines taken out": DIFF_HEAD + f"@@ -4,2 +4 @@ source:\n-{OLD_NOTE}-{REV_OLD}+{REV_NEW}",
    "a line count with too many digits": OK.replace("+5,2", "+5," + "2" * 5000),
    "a line number with a leading zero": OK.replace("-5 +5,2", "-05 +05,2"),
    "a zero count": OK.replace("+5,2", "+5,0"),
    "a count of one written out, which git never prints": OK_BARE.replace("+5 @@", "+5,1 @@"),
    # which lines came and went
    "only an added line": OK.replace(f"-{REV_OLD}", ""),
    "only a removed line": DIFF_HEAD + f"@@ -5 +4,0 @@ source:\n-{REV_OLD}",
    "the first line is not a removal": OK.replace(f"-{REV_OLD}", f" {REV_OLD}"),
    "the last line is not an addition": OK.replace(f"+{REV_NEW}", f" {REV_NEW}"),
    "the note is a removal": OK.replace(f"+{NEW_NOTE}", f"-{NEW_NOTE}"),
    "the note is an unchanged line": OK.replace(f"+{NEW_NOTE}", f" {NEW_NOTE}"),
    "the note after the revision": DIFF_HEAD + f"@@ -5 +5,2 @@ source:\n-{REV_OLD}+{REV_NEW}+{NEW_NOTE}",
    "the note removed, not added": DIFF_HEAD + f"@@ -5,2 +5 @@ source:\n-{NEW_NOTE}-{REV_OLD}+{REV_NEW}",
    "two notes": DIFF_HEAD + f"@@ -5 +5,3 @@ source:\n-{REV_OLD}+{NEW_NOTE}+{NEW_NOTE}+{REV_NEW}",
    "a live key after the note": DIFF_HEAD + f"@@ -5 +5,3 @@ source:\n-{REV_OLD}+{NEW_NOTE}+{LIVE_KEY}+{REV_NEW}",
    "a blank line after the note": DIFF_HEAD + f"@@ -5 +5,3 @@ source:\n-{REV_OLD}+{NEW_NOTE}+\n+{REV_NEW}",
    "a blank line in the note's place": DIFF_HEAD + f"@@ -5 +5,2 @@ source:\n-{REV_OLD}+\n+{REV_NEW}",
    "a live key in the note's place": DIFF_HEAD + f"@@ -5 +5,2 @@ source:\n-{REV_OLD}+{LIVE_KEY}+{REV_NEW}",
    # the new revision line
    "not a sha": OK.replace(f"+{REV_NEW}", "+  revision: not-a-sha\n"),
    "a short sha": OK.replace(NEW_SHA, NEW_SHA[:39]),
    "a long sha": OK.replace(NEW_SHA, NEW_SHA + "b"),
    "an upper-case sha": OK.replace(NEW_SHA, NEW_SHA.upper()),
    "the same sha": OK.replace(NEW_SHA, OLD_SHA),
    "words after the new sha": OK[:-1] + " # and more\n",
    "a quoted sha": OK.replace(f"revision: {NEW_SHA}", f'revision: "{NEW_SHA}"'),
    "the new line indented deeper": OK.replace(f"+{REV_NEW}", f"+  {REV_NEW}"),
    "the new line not indented": OK.replace(f"+{REV_NEW}", f"+{REV_NEW.lstrip()}"),
    "two spaces after the key": OK.replace(f"revision: {NEW_SHA}", f"revision:  {NEW_SHA}"),
    "another key with a sha": OK.replace(f"+{REV_NEW}", f"+  revisions: {NEW_SHA}\n"),
    "a tab for the indent": OK.replace(f"+{REV_NEW}", f"+\trevision: {NEW_SHA}\n"),
    "a no-break space in the indent": OK.replace(f"+{REV_NEW}", f"+\u00a0 revision: {NEW_SHA}\n"),
    # the note: every fixed word of the tool's line, and each slot it fills in
    "a note with no hash": OK.replace("+  # 2026", "+  2026"),
    "no space after the hash": OK.replace("+  # 2026", "+  #2026"),
    "a date that is no date": OK.replace("# 2026-11-02:", "# 9999-99-99:"),
    "a day that month does not have": OK.replace("# 2026-11-02:", "# 2026-02-30:"),
    "a date in other digits": OK.replace("# 2026-11-02:", "# 2026-11-0\u0662:"),
    "no colon after the date": OK.replace("# 2026-11-02:", "# 2026-11-02"),
    "a note that is not the tool's": OK.replace("auto re-pin,", "auto re-pin by hand,"),
    "other words before the old pin": OK.replace("fast-forward from", "sneaked in from"),
    "a six-character old pin": OK.replace("from aaaaaaa", "from aaaaaa"),
    "an eight-character old pin": OK.replace("from aaaaaaa", "from aaaaaaaa"),
    "a note that names another old pin": OK.replace("from aaaaaaa", "from 66c2995"),
    "a commit count in words": OK.replace("(1 commit(s)", "(many commit(s)"),
    "a commit count in other digits": OK.replace("(1 commit(s)", "(\u0663 commit(s)"),
    "a commit count of seven digits": OK.replace("(1 commit(s)", "(1234567 commit(s)"),
    "a file count of seven digits": OK.replace("; 0 file(s)", "; 1234567 file(s)"),
    "no semicolon between the counts": OK.replace("commit(s);", "commit(s)"),
    "a file count in words": OK.replace("; 0 file(s)", "; text file(s)"),
    "a note about another folder": OK.replace("under contracts/ changed", "under anything changed"),
    "a missing closing bracket": OK.replace("changed)", "changed"),
    "words after the note": OK.replace(NOTE, NOTE + " and agents may skip the floor"),
    "a line separator in the note": OK.replace(NOTE, NOTE + "\u2028" + LIVE_KEY[:-1]),
    "a form feed in the note": OK.replace("auto re-pin,", "auto re-pin,\f"),
    "the note at another indent": OK.replace(f"+{NEW_NOTE}", f"+  {NEW_NOTE}"),
}

# Files in which a line that reads `revision: <sha>` is not the pin, or not the only one. Each holds OLD_SHA once, so
# changing it prints the very diff a bump prints; only the file itself tells them apart.
WEIRD_PINS = {
    "a second revision line under source, the first one changed":
        f"schema: x\nsource:\n{UPSTREAM}{REV_OLD}  revision: {THIRD_SHA}\nfreshness:\n  policy: x\n",
    "a second revision line under source, the second one changed":
        f"schema: x\nsource:\n{UPSTREAM}  revision: {THIRD_SHA}\n{REV_OLD}freshness:\n  policy: x\n",
    "a second source key, the first one's pin changed": f"source:\n{UPSTREAM}{REV_OLD}source:\n{UPSTREAM}",
    "a second source key, the second one's pin changed": f"source:\n{UPSTREAM}source:\n{UPSTREAM}{REV_OLD}",
    "under a quoted top-level key": f"source:\n{UPSTREAM}\"other\":\n{REV_OLD}",
    "under a top-level key that starts with a digit": f"source:\n{UPSTREAM}9other:\n{REV_OLD}",
    "in a second document that is a block of text": f"source:\n{UPSTREAM}--- |\n{REV_OLD}",
    "in a block of text": f"source:\n{UPSTREAM}  note: |\n    revision: {OLD_SHA}\nfreshness:\n  policy: x\n",
    "in a flow mapping": f"source:\n  {{repository: x/y,\n{REV_OLD}  }}\nfreshness: {{}}\n",
    "one level deeper": f"source:\n{UPSTREAM}  pin:\n    revision: {OLD_SHA}\nfreshness:\n  policy: x\n",
    "under a list item's map": f"source:\n{UPSTREAM}  items:\n  - name: x\n    revision: {OLD_SHA}\n",
    "inside a quoted value that began above source": f"notes: \"foo\nsource:\n{REV_OLD}  # bar\"\n",
    "under an anchor that is merged elsewhere":
        f"source:\n{UPSTREAM}  tmpl: &b\n    revision: {OLD_SHA}\n  child:\n    <<: *b\nfreshness:\n  policy: x\n",
    "at the top level, right under an empty source": f"source:\nrevision: {OLD_SHA}\n",
}
# One change away from PIN_BASE each. The judge gives no pin line for any of them, so no diff of them is a bump.
ODD_BASES = {
    "an empty file": "",
    "no revision line": PIN_BASE.replace(REV_OLD, ""),
    "two revision lines": PIN_BASE.replace(REV_OLD, REV_OLD + f"  revision: {THIRD_SHA}\n"),
    "a second revision under another key": PIN_BASE + f"other:\n  revision: {THIRD_SHA}\n",
    "a second revision in a block of text": PIN_BASE + f"notes: |\n  revision: {THIRD_SHA}\n",
    "a second revision key in quotes": PIN_BASE + f"other:\n  \"revision\": {THIRD_SHA}\n",
    "a second revision key with no value": PIN_BASE + "other:\n  revision:\n",
    "a comment after the pin's value (the tool's October shape)":
        PIN_BASE.replace(REV_OLD, f"  revision: {OLD_SHA}  # 2026-10-01: re-pinned\n"),
    "an anchor on the pin's value": PIN_BASE.replace(REV_OLD, f"  revision: &r {OLD_SHA}\n"),
    "the pin under another key after source": PIN_BASE.replace(REV_OLD, "").replace("freshness:\n", "freshness:\n" + REV_OLD),
    "the pin above source": f"other:\n{REV_OLD}" + PIN_BASE.replace(REV_OLD, ""),
    "the pin in a list item": PIN_BASE.replace(REV_OLD, f"  - revision: {OLD_SHA}\n"),
    "the pin as an explicit key": PIN_BASE.replace(REV_OLD, f"  ? revision\n  : {OLD_SHA}\n"),
    "a folded block before the pin": PIN_BASE.replace(REV_OLD, "  note: >-\n    folded\n" + REV_OLD),
    "a block of text opening right above the pin": PIN_BASE.replace(REV_OLD, "  note: |\n" + REV_OLD),
    "a key with no value before the pin": PIN_BASE.replace(REV_OLD, "  note:\n" + REV_OLD),
    "a quoted value before the pin": PIN_BASE.replace(UPSTREAM, "  repository: \"x\"\n"),
    "a blank line before the pin": PIN_BASE.replace(REV_OLD, "\n" + REV_OLD),
    "a key after the pin inside source": PIN_BASE.replace(REV_OLD, REV_OLD + "  extra: x\n"),
    "a continued value under the pin": PIN_BASE.replace(REV_OLD, REV_OLD + "    and more\n"),
    "a letter of another script before the pin": PIN_BASE.replace("schema:", "# café\nschema:"),
    "a letter of another script inside source": PIN_BASE.replace(OLD_NOTE, "  # café\n" + OLD_NOTE),
    "carriage returns throughout": PIN_BASE.replace("\n", "\r\n"),
    "a lone carriage return after the pin's block": PIN_BASE + "# a\rb: c\n",
    "a tab after the pin's block": PIN_BASE + "# a\tb\n",
    "a line separator after the pin's block": PIN_BASE + "# a\u2028b: c\n",
    "a next-line character after the pin's block": PIN_BASE + "# a\u0085b: c\n",
    "a delete character after the pin's block": PIN_BASE + "# a\x7fb\n",
    "bytes that are not UTF-8": PIN_BASE.encode() + b"\xff\n",
    "an anchor on source": PIN_BASE.replace("source:\n", "source: &s\n"),
    "a comment on the source line": PIN_BASE.replace("source:\n", "source: # the pin\n"),
    "a value on the source line": PIN_BASE.replace("source:\n", "source: x\n"),
    "source in quotes": PIN_BASE.replace("source:\n", "\"source\":\n"),
    "a second source key": PIN_BASE + "source:\n  x: y\n",
    "a document marker": "---\n" + PIN_BASE,
    "a directive": "%YAML 1.2\n" + PIN_BASE,
    "a list item above source": "- x\n" + PIN_BASE,
    "a block of text above source": "notes: |\n  words\n" + PIN_BASE,
    "a key with no value above source": "notes:\n" + PIN_BASE,
    "an indented line above source": "  # words\n" + PIN_BASE,
    "a line inside source one space deeper than the pin": PIN_BASE.replace(UPSTREAM, " " + UPSTREAM),
    "a line inside source one space shallower than the pin": PIN_BASE.replace(UPSTREAM, UPSTREAM[1:]),
    "a comment inside source deeper than the pin": PIN_BASE.replace(OLD_NOTE, "  " + OLD_NOTE),
}
# Plain manifests: the judge finds the pin, and the tool's bump of each one is skipped.
GOOD_BASES = {
    "the usual shape": PIN_BASE,
    "a four-space indent": f"schema: play-nice/adoption-v1\nsource:\n  {UPSTREAM}    revision: {OLD_SHA}\nalways:\n  - x\n",
    "a one-space indent": f"source:\n{UPSTREAM[1:]} revision: {OLD_SHA}\nalways:\n  - x\n",
    "a comment after a value before the pin": PIN_BASE.replace(UPSTREAM, UPSTREAM[:-1] + "  # upstream\n"),
    "blank lines and comments after the pin": PIN_BASE.replace(REV_OLD, REV_OLD + "\n  # a comment\n\n"),
    "another script after the pin's block, and no final newline": PIN_BASE + "# café, notes",
}


def sha_line(base) -> tuple[int, str]:
    """(1-based line number, the line) of the one line of `base` that holds OLD_SHA; the usual pin when none does."""
    text = base.decode("utf-8", "replace") if isinstance(base, bytes) else base
    return next(((i, x) for i, x in enumerate(text.split("\n"), 1) if OLD_SHA in x), (5, REV_OLD[:-1]))


def bare_bump_of(base) -> str:
    """The diff git prints when the one line of `base` that holds OLD_SHA gets NEW_SHA in its place."""
    at, line = sha_line(base)
    return DIFF_HEAD + f"@@ -{at} +{at} @@ source:\n-{line}\n+{line.replace(OLD_SHA, NEW_SHA)}\n"


# -- helpers ----------------------------------------------------------------------------------------------------------
def load():
    spec = importlib.util.spec_from_file_location("ci_pin_only", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git(cwd, *args):
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, env=env).stdout


def put(repo, rel, value):
    """Write one file as bytes, so a carriage return reaches the commit the way it was written."""
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else value.encode("utf-8"))


def make_pr(tmp_path, edits, *, merge=True, base=PIN_BASE, also=None, gitlink=None):
    """A repo whose HEAD is a merge of a PR branch (the `edits` mapping path -> new text or bytes) into main.

    `base` is the manifest on main. `also` is more files on main. `gitlink` is a pair of commit
    names: main records a submodule `sub` at the first, and the PR branch records it at the second.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "core.autocrlf", "false")
    files = {"README.md": "hello\n", PIN: base, **(also or {})}
    for rel, value in files.items():
        put(repo, rel, value)
    git(repo, "add", "-A")
    if gitlink:
        (repo / "sub").mkdir()
        git(repo, "update-index", "--add", "--cacheinfo", f"160000,{gitlink[0]},sub")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "checkout", "-q", "-b", "pr")
    for rel, value in edits.items():
        put(repo, rel, value)
    git(repo, "add", "-A")
    if gitlink:
        git(repo, "update-index", "--cacheinfo", f"160000,{gitlink[1]},sub")
    git(repo, "commit", "-q", "-m", "pr")
    git(repo, "checkout", "-q", "main")
    if merge:
        git(repo, "merge", "-q", "--no-ff", "-m", "merge", "pr")
    else:
        git(repo, "merge", "-q", "--ff-only", "pr")
    if gitlink:  # the two commits really record what the test asked for
        assert [git(repo, "rev-parse", f"{rev}:sub").decode().strip() for rev in ("HEAD^1", "HEAD")] == list(gitlink)
    return repo


def run(repo, event="pull_request"):
    env = {**os.environ, "EVENT_NAME": event}
    env.pop("GITHUB_OUTPUT", None)
    res = subprocess.run([sys.executable, str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    answer, *rest = res.stdout.splitlines()
    # a skipped run says why on its own page, and a full run says nothing extra
    assert rest == ([load().NOTICE] if answer == "only=true" else []), res.stdout
    return answer


def changed_files(repo):
    """What a plain `git diff` lists for the PR, under whatever this repo's own settings say."""
    return git(repo, "diff", "--name-only", "HEAD^1", "HEAD").decode().split()


# -- the script, on a real git checkout -------------------------------------------------------------------------------
def test_the_re_pin_jobs_bump_is_pin_only(tmp_path):
    assert PIN_BUMP == PIN_BASE.replace(REV_OLD, NEW_NOTE + REV_NEW)
    assert "auto re-pin, fast-forward from aaaaaaa (1 commit(s); 0 file(s) under contracts/ changed)" in NEW_NOTE
    assert run(make_pr(tmp_path, {PIN: PIN_BUMP})) == "only=true"


def test_the_notice_is_one_github_notice_line():
    notice = load().NOTICE
    assert notice.startswith("::notice title=") and "\n" not in notice and "pin" in notice


def test_the_revision_line_alone_is_pin_only(tmp_path):
    assert run(make_pr(tmp_path, {PIN: PIN_BASE.replace(OLD_SHA, NEW_SHA)})) == "only=true"


@pytest.mark.parametrize("case", sorted(GOOD_BASES))
def test_the_re_pin_jobs_bump_of_any_plain_manifest_is_pin_only(tmp_path, case):
    base = GOOD_BASES[case]
    assert run(make_pr(tmp_path, {PIN: tool_bump(base)}, base=base)) == "only=true"


def test_a_bump_of_this_repos_own_manifest_is_pin_only(tmp_path):
    """The judge must fit the file it is for: the real manifest, with its many notes above and below the pin."""
    real = (ROOT / PIN).read_bytes().decode("utf-8")
    found = re.findall(r"^( +)revision: ([0-9a-f]{40})$", real, flags=re.M)
    assert len(found) == 1, "the manifest has one pin"
    indent, old = found[0]
    new = NEW_SHA if old != NEW_SHA else OLD_SHA
    line = f"{indent}revision: {old}\n"
    assert run(make_pr(tmp_path / "noted", {PIN: tool_bump(real, new)}, base=real)) == "only=true"
    assert run(make_pr(tmp_path / "bare", {PIN: real.replace(line, line.replace(old, new))}, base=real)) == "only=true"
    moved = real.replace(line, "").replace("\n", f"\n{indent}revision: {new}\n", 1)  # now under the first key
    assert run(make_pr(tmp_path / "moved", {PIN: moved}, base=real)) == "only=false"


# A revision-shaped line that is not where the pin was changes what the file means.
MOVED = {
    "under another key": PIN_BASE.replace(REV_OLD, "").replace("freshness:\n", "freshness:\n" + REV_NEW),
    "to the top level": PIN_BASE.replace(REV_OLD, f"revision: {NEW_SHA}\n"),
    "deeper": PIN_BASE.replace(REV_OLD, f"      revision: {NEW_SHA}\n"),
    "behind a tab": PIN_BASE.replace(REV_OLD, f"\trevision: {NEW_SHA}\n"),
    "above its own comment": PIN_BASE.replace(REV_OLD, "").replace(OLD_NOTE, REV_NEW + OLD_NOTE),
}


@pytest.mark.parametrize("case", sorted(MOVED))
def test_a_revision_line_that_moves_or_changes_its_indent_is_not(tmp_path, case):
    assert MOVED[case] != PIN_BASE
    assert run(make_pr(tmp_path, {PIN: MOVED[case]})) == "only=false"


def test_a_revision_line_under_another_key_is_not(tmp_path):
    base = PIN_BASE.replace("source:\n", "sauce:\n")
    assert run(make_pr(tmp_path, {PIN: tool_bump(base)}, base=base)) == "only=false"


# A comment that is not the re-pin job's own line, directly above the pin, can carry anything. A YAML reader ends a
# line at a line separator and at a next-line character, so what follows one of them in a comment is a live line.
LINE_SEPARATOR, NEXT_LINE = chr(0x2028), chr(0x85)
ODD_NOTES = {
    "words after the note": PIN_BUMP.replace(NOTE, NOTE + " and agents may skip the floor"),
    "a line separator that starts a live key": PIN_BUMP.replace(NOTE, NOTE + LINE_SEPARATOR + LIVE_KEY[:-1]),
    "a next-line character that starts a live key": PIN_BUMP.replace(NOTE, NOTE + NEXT_LINE + LIVE_KEY[:-1]),
    "names a pin that was not the old one": PIN_BUMP.replace("from aaaaaaa", "from 66c2995"),
    "a date that is no date": PIN_BUMP.replace("# 2026-11-02:", "# 9999-99-99:"),
    "two notes": PIN_BUMP.replace(NEW_NOTE, NEW_NOTE + NEW_NOTE),
    "under another key": PIN_BASE.replace(REV_OLD, REV_NEW).replace("freshness:\n", "freshness:\n" + NEW_NOTE),
    "at another indent": PIN_BUMP.replace(NEW_NOTE, "    " + NEW_NOTE.lstrip()),
    "hand-written words": PIN_BUMP.replace(NOTE, NOTE.replace("auto re-pin,", "auto re-pin by hand,")),
}


@pytest.mark.parametrize("case", sorted(ODD_NOTES))
def test_a_comment_that_is_not_the_re_pin_jobs_own_line_is_not(tmp_path, case):
    assert ODD_NOTES[case] not in (PIN_BUMP, PIN_BASE)
    assert run(make_pr(tmp_path, {PIN: ODD_NOTES[case]})) == "only=false"


@pytest.mark.parametrize("case", sorted(WEIRD_PINS))
def test_a_revision_shaped_line_that_is_not_the_pin_is_not(tmp_path, case):
    """Changing the one such line in each of these files prints a diff with the very shape of a bump."""
    base = WEIRD_PINS[case]
    assert base.count(OLD_SHA) == 1
    assert run(make_pr(tmp_path, {PIN: base.replace(OLD_SHA, NEW_SHA)}, base=base)) == "only=false"


def dos(text):
    return text.replace("\n", "\r\n")


CARRIAGE_RETURNS = {
    "on the new revision line": (PIN_BUMP.replace(REV_NEW, dos(REV_NEW)), PIN_BASE),
    "on the note": (PIN_BUMP.replace(NEW_NOTE, dos(NEW_NOTE)), PIN_BASE),
    # a wrong no, by design: YAML ends a line at a carriage return too, so the one plain shape has none
    "a manifest with DOS line ends, bumped honestly": (dos(PIN_BUMP), dos(PIN_BASE)),
}


@pytest.mark.parametrize("case", sorted(CARRIAGE_RETURNS))
def test_a_carriage_return_reaches_the_judge_and_is_not(tmp_path, case):
    """git is read as bytes. Read as text, a DOS line end turns into a plain one on the way in, and each of these
    reads as a clean bump."""
    text, base = CARRIAGE_RETURNS[case]
    repo = make_pr(tmp_path, {PIN: text}, base=base)
    assert git(repo, "cat-file", "blob", f"HEAD:{PIN}").count(b"\r\n") >= 1, "the carriage return must be committed"
    assert run(repo) == "only=false"


GITMODULES = '[submodule "sub"]\n  path = sub\n  url = ./sub\n  ignore = all\n'


def test_a_submodule_that_moves_with_the_pin_is_not_however_git_is_told_to_hide_it(tmp_path):
    """A repo's own .gitmodules (ignore = all) or its settings (diff.ignoreSubmodules) take a submodule's new commit
    out of what `git diff` prints, and a submodule's commit is code. The judge asks git to ignore none of them."""
    moved, hidden = (THIRD_SHA, NEW_SHA), {".gitmodules": GITMODULES}
    assert run(make_pr(tmp_path / "plain", {PIN: PIN_BUMP}, gitlink=moved)) == "only=false"
    by_file = make_pr(tmp_path / "file", {PIN: PIN_BUMP}, gitlink=moved, also=hidden)
    assert changed_files(by_file) == [PIN], "the file must really hide it"
    assert run(by_file) == "only=false"
    by_setting = make_pr(tmp_path / "setting", {PIN: PIN_BUMP}, gitlink=moved)
    git(by_setting, "config", "diff.ignoreSubmodules", "all")
    assert changed_files(by_setting) == [PIN], "the setting must really hide it"
    assert run(by_setting) == "only=false"
    # a submodule that did not move is no part of the change
    still = make_pr(tmp_path / "still", {PIN: PIN_BUMP}, gitlink=(THIRD_SHA, THIRD_SHA), also=hidden)
    assert run(still) == "only=true"


def tool(tmp_path, name, body):
    """An executable shell script outside the repo."""
    path = tmp_path / name
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return str(path)


def convert_with(repo, command):
    """Tell this repo's git to show every .yaml file through `command`, the way a textconv setting does."""
    (repo / ".git" / "info").mkdir(exist_ok=True)
    (repo / ".git" / "info" / "attributes").write_text("*.yaml diff=shown\n", encoding="utf-8")
    git(repo, "config", "diff.shown.textconv", command)


def colour(repo, tmp_path):
    git(repo, "config", "color.ui", "always")
    git(repo, "config", "color.diff", "always")


def no_prefixes(repo, tmp_path):
    git(repo, "config", "diff.noprefix", "true")


def a_diff_program_that_prints_nothing(repo, tmp_path):
    git(repo, "config", "diff.external", tool(tmp_path, "quiet-diff", "exit 0\n"))


def a_converter_that_shouts(repo, tmp_path):
    convert_with(repo, tool(tmp_path, "shout", 'tr a-z A-Z < "$1"\n'))


SETTINGS = (colour, no_prefixes, a_diff_program_that_prints_nothing, a_converter_that_shouts)


@pytest.mark.parametrize("setting", SETTINGS, ids=[s.__name__ for s in SETTINGS])
def test_a_git_setting_does_not_change_what_the_judge_is_handed(tmp_path, setting):
    """Each of these settings changes what a plain `git diff` prints for the very same bump. The options the script
    asks git with (DIFF) switch each one off, so the judge still gets the diff itself."""
    repo = make_pr(tmp_path, {PIN: PIN_BUMP})
    plain = git(repo, "diff", "-U0", "HEAD^1", "HEAD")
    setting(repo, tmp_path)
    assert git(repo, "diff", "-U0", "HEAD^1", "HEAD") != plain, "the setting must really change what git prints"
    assert run(repo) == "only=true"


def test_a_git_setting_cannot_hide_a_second_change_behind_the_bump(tmp_path):
    """The other way round is the one that matters: a text converter or an outside diff program can print a bump and
    nothing else for a change that also takes a contract off the list."""
    more = PIN_BUMP.replace("  - secrets-and-data\n", "")
    assert more != PIN_BUMP
    bump = git(make_pr(tmp_path / "bump", {PIN: PIN_BUMP}), "diff", "-U0", "HEAD^1", "HEAD")
    converted = make_pr(tmp_path / "converted", {PIN: more})
    convert_with(converted, tool(tmp_path, "no-lists", 'grep -v "^  - " "$1"\n'))
    shown = git(converted, "diff", "-U0", "HEAD^1", "HEAD")
    assert shown.split(b"\n")[4:] == bump.split(b"\n")[4:], "the converter must really leave only the bump to see"
    assert run(converted) == "only=false"
    forged = make_pr(tmp_path / "forged", {PIN: more})
    (tmp_path / "bump.diff").write_bytes(bump)
    git(forged, "config", "diff.external", tool(tmp_path, "forge", f'cat "{tmp_path}/bump.diff"\n'))
    assert git(forged, "diff", "-U0", "HEAD^1", "HEAD") == bump, "the outside program must really print the bump"
    assert run(forged) == "only=false"


NOT_ONLY = {
    "another line of the same file": {PIN: PIN_BUMP.replace("  - secrets-and-data\n", "")},
    "another comment in the same file": {PIN: PIN_BUMP.replace("source:\n", "source:\n  # a note anyone could write\n")},
    "another key in the same file": {PIN: PIN_BUMP.replace("schema:", "schema2:")},
    "a second file": {PIN: PIN_BUMP, "README.md": "changed\n"},
    "another file alone": {"README.md": "changed\n"},
}


@pytest.mark.parametrize("case", sorted(NOT_ONLY))
def test_a_bump_with_anything_else_is_not(tmp_path, case):
    assert NOT_ONLY[case].get(PIN) != PIN_BUMP or len(NOT_ONLY[case]) > 1
    assert run(make_pr(tmp_path, NOT_ONLY[case])) == "only=false"


def test_a_push_event_is_not(tmp_path):
    assert run(make_pr(tmp_path, {PIN: PIN_BUMP}), event="push") == "only=false"
    assert run(make_pr(tmp_path / "x", {PIN: PIN_BUMP}), event="") == "only=false"
    assert run(make_pr(tmp_path / "y", {PIN: PIN_BUMP}), event="pull_request_target") == "only=false"


def test_a_checkout_that_is_not_a_merge_commit_is_not(tmp_path):
    assert run(make_pr(tmp_path, {PIN: PIN_BUMP}, merge=False)) == "only=false"


def test_a_broken_git_call_is_not(tmp_path):
    empty = tmp_path / "not-a-repo"
    empty.mkdir()
    env = {**os.environ, "EVENT_NAME": "pull_request", "GIT_CEILING_DIRECTORIES": str(tmp_path)}
    env.pop("GITHUB_OUTPUT", None)
    for path in (env["PATH"], str(tmp_path / "no-git-here")):
        env["PATH"] = path
        res = subprocess.run([sys.executable, str(SCRIPT)], cwd=empty, env=env, capture_output=True, text=True)
        assert res.returncode == 0, res.stderr  # the step itself must not fail the job
        assert res.stdout.strip() == "only=false"


def test_any_error_at_all_is_not(monkeypatch):
    mod = load()

    def boom(*args, **kwargs):
        raise RuntimeError("something nobody planned for")

    monkeypatch.setattr(mod.subprocess, "run", boom)
    assert mod.pin_only("pull_request") is False


@pytest.mark.parametrize("first", ["rev-parse", "diff", "cat-file"])
def test_a_git_call_that_fails_is_never_a_skip(tmp_path, monkeypatch, first):
    mod, repo = load(), make_pr(tmp_path, {PIN: PIN_BUMP})
    monkeypatch.chdir(repo)
    assert mod.pin_only("pull_request") is True
    real = mod.git_bytes

    def broken(*args):
        if args[0] == first:
            raise subprocess.CalledProcessError(128, ["git", *args])
        return real(*args)

    monkeypatch.setattr(mod, "git_bytes", broken)
    assert mod.pin_only("pull_request") is False


def test_writes_github_output(tmp_path):
    repo = make_pr(tmp_path, {PIN: PIN_BUMP})
    out = tmp_path / "gh_out"
    env = {**os.environ, "EVENT_NAME": "pull_request", "GITHUB_OUTPUT": str(out)}
    subprocess.run([sys.executable, str(SCRIPT)], cwd=repo, env=env, check=True, capture_output=True)
    assert out.read_text() == "only=true\n"


@pytest.mark.parametrize(
    "text, shape",
    [(PIN_BUMP, OK), (PIN_BASE.replace(OLD_SHA, NEW_SHA), OK_BARE)],
    ids=["the job's bump", "the revision line alone"],
)
def test_the_judge_is_handed_gits_own_bytes_the_diff_and_the_file_before_it(tmp_path, monkeypatch, text, shape):
    """OK and OK_BARE, which every table above starts from, are what git really prints for the two bumps of PIN_BASE
    (the blob names aside), and the file handed over is the manifest the PR started from, byte for byte."""
    mod, repo, seen = load(), make_pr(tmp_path, {PIN: text}), []
    judge = mod.is_pin_only
    monkeypatch.setattr(mod, "is_pin_only", lambda diff, base: seen.append((diff, base)) or judge(diff, base))
    monkeypatch.chdir(repo)
    assert mod.pin_only("pull_request") is True
    ((diff, base),) = seen
    assert re.sub(rb"index [0-9a-f]+\.\.[0-9a-f]+ ", b"index 1111111..2222222 ", diff) == shape.encode()
    assert base == PIN_BASE.encode()


# -- the two judges, on the bytes alone -------------------------------------------------------------------------------
@pytest.mark.parametrize("case", sorted(GOOD_DIFFS))
def test_the_diff_judge_passes_the_real_shapes(case):
    assert load().is_pin_only(GOOD_DIFFS[case].encode(), PIN_BASE.encode()) is True


@pytest.mark.parametrize("case", sorted(ODD_DIFFS))
def test_the_diff_judge_passes_no_odd_shape(case):
    assert ODD_DIFFS[case] not in GOOD_DIFFS.values()
    assert load().is_pin_only(ODD_DIFFS[case].encode("utf-8"), PIN_BASE.encode()) is False


def test_the_diff_judge_checks_the_line_against_the_file_it_came_from():
    judge = load().is_pin_only
    one_down = ("# a comment\n" + PIN_BASE).encode()  # the same manifest with its pin on line 6
    assert judge(OK.encode(), one_down) is False, "the diff says line 5 and the pin is on line 6"
    assert judge(OK.replace("-5 +5,2", "-6 +6,2").encode(), one_down) is True
    another = PIN_BASE.replace(OLD_SHA, THIRD_SHA).encode()
    assert judge(OK.encode(), another) is False, "the line that goes out is not the file's pin"


def test_the_diff_judge_takes_bytes_and_only_bytes():
    judge, diff, base = load().is_pin_only, OK.encode(), PIN_BASE.encode()
    assert judge(diff, base) is True
    assert judge(OK, base) is False
    assert judge(diff, PIN_BASE) is False
    assert judge(diff.replace(b"auto re-pin", b"auto\xa0re-pin"), base) is False, "a byte that is no ASCII"


@pytest.mark.parametrize("case", sorted(GOOD_BASES))
def test_the_pin_is_found_in_a_plain_manifest(case):
    mod, base = load(), GOOD_BASES[case]
    assert mod.pin_line(base.encode("utf-8")) == sha_line(base)
    assert mod.is_pin_only(bare_bump_of(base).encode(), base.encode("utf-8")) is True


NOT_PLAIN = {**ODD_BASES, **WEIRD_PINS}


@pytest.mark.parametrize("case", sorted(NOT_PLAIN))
def test_the_pin_is_found_in_no_other_file(case):
    assert len(NOT_PLAIN) == len(ODD_BASES) + len(WEIRD_PINS)
    mod, base = load(), NOT_PLAIN[case]
    raw = base if isinstance(base, bytes) else base.encode("utf-8")
    assert mod.pin_line(raw) is None
    assert mod.is_pin_only(bare_bump_of(base).encode("utf-8"), raw) is False


def test_a_line_that_only_looks_like_the_pin_is_told_apart_by_the_file_alone():
    """The diff of each such file is a bump's diff to the letter: over a plain manifest with the pin on that line it
    IS a bump. So it is the reading of the file, and nothing in the diff, that turns these down."""
    judge, told = load().is_pin_only, 0
    for name, base in WEIRD_PINS.items():
        diff, (at, line) = bare_bump_of(base).encode(), sha_line(base)
        indent = line[: len(line) - len(line.lstrip(" "))]
        assert judge(diff, base.encode()) is False, name
        if indent:  # a revision line at the top level is no pin in any file: the diff itself is turned down
            plain = "source:\n" + f"{indent}key: value\n" * (at - 2) + line + "\n"
            assert judge(diff, plain.encode()) is True, name
            told += 1
    assert told == len(WEIRD_PINS) - 1


# -- the workflows. The test group has no YAML reader, so the steps are read as text. --------------------------------
GUARD = "        if: steps.pin.outputs.only != 'true'"
# (workflow, job, the steps after the pin step that a pin bump still runs)
PIN_JOBS = (("ci.yml", "gate", ["- name: Public-surface guard"]), ("dev-guards.yml", "browser", []))


def unguarded_steps(text, job):
    """The steps after the pin step that would still run on a pin bump."""
    lines = text.split("\n")
    start = lines.index(f"  {job}:")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r" {0,2}[^\s#]", lines[i])), len(lines))
    steps = []
    for line in lines[start:end]:
        if line.startswith("      - "):
            steps.append([line])
        elif steps:
            steps[-1].append(line)
    pin = [i for i, step in enumerate(steps) if "        run: python3 scripts/ci_pin_only.py" in step]
    assert len(pin) == 1 and steps[pin[0]][0] == "      - id: pin", job
    after = steps[pin[0] + 1 :]
    assert len(after) >= 5, job  # the long steps are still there to be skipped
    return [step[0].strip() for step in after if GUARD not in step]


@pytest.mark.parametrize("name, job, still_runs", PIN_JOBS)
def test_a_pin_bump_skips_the_long_steps_and_nothing_else(name, job, still_runs):
    """The yes names the long tests. The public-surface guard is a privacy check and takes seconds, so it runs on a
    pin bump too; every other step after the pin step is skipped."""
    text = (WORKFLOWS / name).read_text()
    assert text.count("python3 scripts/ci_pin_only.py") == 1, name
    assert unguarded_steps(text, job) == still_runs


def test_the_public_surface_guard_runs_on_every_change():
    text = (WORKFLOWS / "ci.yml").read_text()
    step = "      - name: Public-surface guard\n        run: python3 scripts/check_public_surface.py\n"
    assert text.count(step) == 1, "the guard is one step with no condition on it"


@pytest.mark.parametrize("name", ["ci_pin_only.py", "check_public_surface.py"])
def test_what_a_pin_bump_still_runs_needs_nothing_installed(name):
    """Both run on the runner's own python3: one before uv, Python and the deps are set up, one when they never are."""
    tree = ast.parse((ROOT / "scripts" / name).read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0 and node.module, name
            found.add(node.module.split(".")[0])
    assert found and found <= sys.stdlib_module_names, sorted(found - sys.stdlib_module_names)


@pytest.mark.parametrize("name, job, still_runs", PIN_JOBS)
def test_the_pin_step_sees_githubs_test_merge_and_both_its_parents(name, job, still_runs):
    """The judge diffs HEAD^1 against HEAD and reads the manifest at HEAD^1. That is the PR against its base only on
    the checkout GitHub makes for a pull request by default (its test merge), fetched deep enough for both parents."""
    text = (WORKFLOWS / name).read_text()
    start = text.index(f"\n  {job}:\n")
    block = text[start : text.index("      - id: pin", start)]
    assert block.count("uses: actions/checkout@") == 1, name
    depth = re.findall(r"^          fetch-depth: (\d+)$", block, flags=re.M)
    assert len(depth) == 1 and (depth[0] == "0" or int(depth[0]) >= 2), name
    assert not re.search(r"^\s*(ref|repository):", block, flags=re.M), name


def test_the_step_check_names_a_step_that_lost_its_guard():
    text = (WORKFLOWS / "ci.yml").read_text()
    step = "      - name: Pytest (blocks CI)\n"
    for broken in (
        text.replace(step + GUARD + "\n", step),
        text.replace(step + GUARD + "\n", step + GUARD.replace("if:", "# if:") + "\n"),
        text.replace(step + GUARD + "\n", step + GUARD.replace("!=", "==") + "\n"),
    ):
        assert broken != text
        assert unguarded_steps(broken, "gate") == ["- name: Pytest (blocks CI)", "- name: Public-surface guard"]
