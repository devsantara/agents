#!/usr/bin/env python3
"""List every released version in (current, target] with publish dates.

Read-only: queries registry metadata, installs and executes nothing.

  list_versions.py --ecosystem npm   <pkg>    <current> <target|latest>
  list_versions.py --ecosystem pypi  <pkg>    <current> <target|latest>
  list_versions.py --ecosystem go    <module> <current> <target|latest>
  list_versions.py --ecosystem cargo <crate>  <current> <target|latest>

Options:
  --cooldown-days N       flag versions younger than N days (default 7)
  --include-prerelease    keep pre-release versions
  --registry URL          override the registry / proxy base URL
  --json                  machine-readable output

For npm, the registry comes from the project's npm config (run this from the
project directory so .npmrc and scoped registries apply). If the registry needs
auth, the script falls back to `npm view`, which uses npm's own credentials.
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = "dependency-upgrade-list-versions"
PRE_RE = re.compile(r"(?:^|[-._]?)(a|b|c|rc|alpha|beta|pre|preview|dev|next|canary|nightly|snapshot)[-._]?\d*", re.I)


def http_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def vkey(version):
    """Sortable key. Good for semver and for the common shapes of PEP 440."""
    v = version.strip().lstrip("vV")
    v = v.split("+", 1)[0]  # build metadata / +incompatible
    m = re.match(r"(\d+(?:\.\d+)*)(.*)$", v)
    if not m:
        return ((0,), -1, (version,))
    release = tuple(int(x) for x in m.group(1).split("."))
    release = release + (0,) * (3 - len(release))
    rest = m.group(2)
    post = re.match(r"[-._]?post[-._]?(\d*)$", rest, re.I)
    if not rest:
        return (release, 1, ())
    if post:
        return (release, 2, (int(post.group(1) or 0),))
    parts = tuple((0, int(p)) if p.isdigit() else (1, p.lower()) for p in re.split(r"[-._]", rest) if p)
    return (release, 0, parts)


def is_prerelease(version):
    return vkey(version)[1] == 0


def parse_time(text):
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        t = datetime.datetime.fromisoformat(text)
    except ValueError:
        t = datetime.datetime.fromisoformat(re.sub(r"\.\d+", "", text))
    return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)


# ---- ecosystems: each returns (rows, latest) with rows = [{version, published, flags}] ----

def npm_config(key):
    try:
        out = subprocess.run(["npm", "config", "get", key], capture_output=True, text=True, timeout=30)
        val = out.stdout.strip()
        return None if val in ("", "undefined", "null") else val
    except (OSError, subprocess.SubprocessError):
        return None


def from_npm(pkg, registry):
    if not registry and pkg.startswith("@"):
        registry = npm_config(pkg.split("/", 1)[0] + ":registry")
    registry = (registry or npm_config("registry") or "https://registry.npmjs.org/").rstrip("/")
    try:
        doc = http_json(f"{registry}/{urllib.parse.quote(pkg, safe='@')}")
        times = doc.get("time", {})
        rows = [{"version": v, "published": times.get(v), "flags": ["deprecated"] if meta.get("deprecated") else []}
                for v, meta in doc.get("versions", {}).items()]
        return rows, doc.get("dist-tags", {}).get("latest")
    except (urllib.error.URLError, ValueError, OSError):
        pass  # private registry or auth: let npm do the request
    out = subprocess.run(["npm", "view", pkg, "time", "dist-tags", "--json"], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"npm view failed: {out.stderr.strip() or out.stdout.strip()}")
    doc = json.loads(out.stdout)
    times = doc.get("time", {})
    rows = [{"version": v, "published": t, "flags": []} for v, t in times.items() if v not in ("created", "modified")]
    print("note: read through `npm view`; per-version deprecation flags are not available this way", file=sys.stderr)
    return rows, doc.get("dist-tags", {}).get("latest")


def from_pypi(pkg, registry):
    base = (registry or "https://pypi.org").rstrip("/")
    doc = http_json(f"{base}/pypi/{pkg}/json")
    rows = []
    for v, files in doc.get("releases", {}).items():
        if not files:
            continue
        times = [f.get("upload_time_iso_8601") or f.get("upload_time") for f in files]
        flags = []
        if all(f.get("yanked") for f in files):
            flags.append("yanked")
        if not any(f.get("packagetype") == "bdist_wheel" for f in files):
            flags.append("sdist-only")
        rows.append({"version": v, "published": min(t for t in times if t), "flags": flags})
    return rows, doc.get("info", {}).get("version")


def from_go(module, registry):
    base = (registry or "https://proxy.golang.org").rstrip("/")
    escaped = re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), module)
    versions = [v for v in http_text(f"{base}/{escaped}/@v/list").split() if v]
    return [{"version": v, "published": None, "flags": [], "_info": f"{base}/{escaped}/@v/{v}.info"} for v in versions], None


def from_cargo(crate, registry):
    base = (registry or "https://crates.io").rstrip("/")
    doc = http_json(f"{base}/api/v1/crates/{crate}")
    rows = [{"version": v["num"], "published": v.get("created_at"), "flags": ["yanked"] if v.get("yanked") else []}
            for v in doc.get("versions", [])]
    return rows, doc.get("crate", {}).get("max_stable_version")


SOURCES = {"npm": from_npm, "pypi": from_pypi, "go": from_go, "cargo": from_cargo}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ecosystem", required=True, choices=sorted(SOURCES))
    ap.add_argument("package")
    ap.add_argument("current")
    ap.add_argument("target", help="a version, or 'latest'")
    ap.add_argument("--cooldown-days", type=float, default=7)
    ap.add_argument("--include-prerelease", action="store_true")
    ap.add_argument("--registry")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    try:
        rows, latest = SOURCES[args.ecosystem](args.package, args.registry)
    except urllib.error.HTTPError as e:
        sys.exit(f"registry returned {e.code} for {args.package}")
    except urllib.error.URLError as e:
        sys.exit(f"could not reach the registry: {e.reason}")

    keep_pre = args.include_prerelease or (args.target != "latest" and is_prerelease(args.target))
    stable = [r for r in rows if keep_pre or not is_prerelease(r["version"])]
    if not stable:
        sys.exit("no versions found")
    newest = max(stable, key=lambda r: vkey(r["version"]))["version"]
    target = args.target
    if target == "latest":
        target = latest if latest and (keep_pre or not is_prerelease(latest)) else newest

    lo, hi = vkey(args.current), vkey(target)
    in_range = sorted((r for r in stable if lo < vkey(r["version"]) <= hi), key=lambda r: vkey(r["version"]))

    now = datetime.datetime.now(datetime.timezone.utc)
    for r in in_range:
        if r.get("_info"):  # Go: one request per version, only for the range
            try:
                r["published"] = json.loads(http_text(r.pop("_info"))).get("Time")
            except (urllib.error.URLError, ValueError):
                r.pop("_info", None)
        t = parse_time(r["published"])
        r["age_days"] = round((now - t).total_seconds() / 86400, 1) if t else None
        r["published"] = t.strftime("%Y-%m-%d") if t else None
        if r["age_days"] is not None and r["age_days"] < args.cooldown_days:
            r["flags"].append("cooldown")
            r["clears_cooldown_on"] = (t + datetime.timedelta(days=args.cooldown_days)).strftime("%Y-%m-%d")
        if is_prerelease(r["version"]):
            r["flags"].append("prerelease")

    blocking = {"cooldown", "yanked", "deprecated"}
    eligible = [r["version"] for r in in_range if not blocking & set(r["flags"]) and r["age_days"] is not None]
    result = {
        "ecosystem": args.ecosystem,
        "package": args.package,
        "current": args.current,
        "target": target,
        "registry_latest": latest,
        "newest_version_overall": newest,
        "cooldown_days": args.cooldown_days,
        "count": len(in_range),
        "newest_eligible": eligible[-1] if eligible else None,
        "versions": in_range,
    }
    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"{args.package} ({args.ecosystem}): {len(in_range)} version(s) in ({args.current}, {target}]")
    if latest and latest != newest:
        print(f"note: registry 'latest' is {latest} but the newest version is {newest}")
    print(f"{'version':<24}{'published':<14}{'age (days)':<12}flags")
    for r in in_range:
        age = "?" if r["age_days"] is None else r["age_days"]
        print(f"{r['version']:<24}{r['published'] or '?':<14}{age!s:<12}{', '.join(r['flags'])}")
    print()
    if not in_range:
        print("Nothing in range. Check that the current version exists and is older than the target.")
    elif result["newest_eligible"] == target:
        print(f"Newest eligible version: {target} (the target passes the {args.cooldown_days:g}-day cooldown).")
    elif result["newest_eligible"]:
        held = [r for r in in_range if vkey(r["version"]) > vkey(result["newest_eligible"])]
        print(f"Newest eligible version: {result['newest_eligible']}. Held back: " + "; ".join(
            f"{r['version']} ({', '.join(r['flags'])}" + (f", clears {r['clears_cooldown_on']}" if r.get("clears_cooldown_on") else "") + ")"
            for r in held))
    else:
        print("No eligible version in range (all are inside the cooldown, yanked, deprecated, or undated).")


if __name__ == "__main__":
    main()
