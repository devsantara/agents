#!/usr/bin/env python3
"""Print the names a dependency-upgrade run should use.

Read-only: inspects the repository, creates nothing.

  run_paths.py                       # date, next free run folder, next free branch
  run_paths.py @types/react lodash   # also the <dep> filename for each package

Options:
  --repo PATH    repository to inspect (default: current directory)
  --date DATE    override today's date (YYYY-MM-DD), mainly for testing
"""
import argparse
import datetime
import json
import os
import subprocess
import sys


def git(repo, *args):
    out = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return out.returncode, out.stdout.strip()


def next_free(base, taken):
    """base, base-2, base-3, ... : the first one for which taken() is false."""
    if not taken(base):
        return base
    n = 2
    while taken(f"{base}-{n}"):
        n += 1
    return f"{base}-{n}"


def dep_filename(name):
    return name.replace("/", "__") + ".md"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deps", nargs="*")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--date")
    args = ap.parse_args()

    code, root = git(args.repo, "rev-parse", "--show-toplevel")
    if code != 0:
        sys.exit("not inside a git repository")

    date = args.date or datetime.date.today().isoformat()
    docs_root = os.path.join(root, "docs", "dependency-upgrade")

    _, branches = git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes")
    existing = set()
    for ref in branches.splitlines():
        existing.add(ref)
        # origin/chore/upgrade-... also blocks the local name
        if "/" in ref:
            existing.add(ref.split("/", 1)[1])

    run_name = next_free(date, lambda n: os.path.exists(os.path.join(docs_root, n)))
    branch = next_free(f"chore/upgrade-{date}", lambda n: n in existing)
    _, current = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    _, dirty = git(root, "status", "--porcelain")

    result = {
        "date": date,
        "git_root": root,
        "current_branch": current,
        "working_tree_clean": dirty == "",
        "run_dir": os.path.join("docs", "dependency-upgrade", run_name),
        "run_dir_is_suffixed": run_name != date,
        "branch": branch,
        "branch_is_suffixed": branch != f"chore/upgrade-{date}",
        "dep_files": {d: dep_filename(d) for d in args.deps},
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
