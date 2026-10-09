#!/usr/bin/env python3
"""Create a fixture repository for one eval run.

  setup_fixture.py <fixture> <dest> --registry http://127.0.0.1:47873/r/<run-id>/
  setup_fixture.py session-service <dest> --registry ... --variant override

Copies repos/<fixture> to <dest>, points it at the mock registry, installs the
*old* versions named in package.json (scripts disabled) so the lockfile starts
out of date, and commits. The mock registry (registry.py) must be running.

Variants:
  override   session-service only. Adds an npm `overrides` pin on fxt-lru in a
             second, back-dated commit whose message explains why.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
IDENT = {"GIT_AUTHOR_NAME": "Dana Reyes", "GIT_AUTHOR_EMAIL": "dana@example.com",
         "GIT_COMMITTER_NAME": "Dana Reyes", "GIT_COMMITTER_EMAIL": "dana@example.com"}
NPM = ["npm", "install", "--ignore-scripts", "--no-audit", "--no-fund", "--loglevel=error"]

OVERRIDE_MESSAGE = """fix: pin fxt-lru to 1.0.3

fxt-lru 1.0.4 leaks memory: every set() appends the key to an internal
history array that is never trimmed, and the session service runs out of
memory after a few days in production (fxt-lru issue #12).

fxt-cache pulls fxt-lru in through ^1.0.0, so we get 1.0.4 on a fresh
install. Pin the last good version with an override until upstream ships
a fix.
"""


def run(cmd, cwd, env=None):
    proc = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"{' '.join(cmd)} failed in {cwd}:\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout


def read_manifest(dest):
    with open(os.path.join(dest, "package.json")) as fh:
        return json.load(fh)


def write_manifest(dest, doc):
    with open(os.path.join(dest, "package.json"), "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


def commit(dest, message, date=None):
    env = dict(IDENT)
    if date:
        env.update({"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
    run(["git", "add", "-A"], dest)
    run(["git", "commit", "-q", "-m", message], dest, env)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fixture")
    ap.add_argument("dest")
    ap.add_argument("--registry", required=True)
    ap.add_argument("--variant", choices=["override"])
    args = ap.parse_args()

    src = os.path.join(HERE, "repos", args.fixture)
    dest = os.path.abspath(args.dest)
    if not os.path.isdir(src):
        sys.exit(f"unknown fixture: {args.fixture}")
    if os.path.exists(dest):
        sys.exit(f"{dest} already exists")
    shutil.copytree(src, dest)
    with open(os.path.join(dest, ".npmrc"), "w") as fh:
        # "scope=" clears any user-level default scope; with one set, npm routes
        # unscoped lookups to that scope's registry instead of this one.
        fh.write(f"registry={args.registry.rstrip('/')}/\nscope=\n")

    # Install the exact old versions first, then restore the ranges: npm keeps a
    # locked version that still satisfies its range, so the lockfile stays old.
    wanted = read_manifest(dest)
    exact = json.loads(json.dumps(wanted))
    exact["dependencies"] = {k: v.lstrip("^~") for k, v in wanted["dependencies"].items()}
    if args.variant == "override":
        exact["overrides"] = {"fxt-lru": "1.0.4"}
    write_manifest(dest, exact)
    run(NPM, dest)
    write_manifest(dest, wanted)
    run(NPM, dest)

    run(["git", "init", "-q", "-b", "main"], dest)
    if args.variant == "override":
        commit(dest, "chore: initial import of session-service", "2025-03-20T09:00:00+00:00")
        pinned = read_manifest(dest)
        pinned["overrides"] = {"fxt-lru": "1.0.3"}
        write_manifest(dest, pinned)
        run(NPM, dest)
        commit(dest, OVERRIDE_MESSAGE, "2025-04-02T14:30:00+00:00")
    else:
        commit(dest, f"chore: initial import of {args.fixture}")

    lock = json.load(open(os.path.join(dest, "package-lock.json")))
    resolved = {k.split("node_modules/")[-1]: v["version"] for k, v in lock["packages"].items() if k}
    print(json.dumps({"repo": dest, "fixture": args.fixture, "variant": args.variant, "installed": resolved}, indent=2))


if __name__ == "__main__":
    main()
