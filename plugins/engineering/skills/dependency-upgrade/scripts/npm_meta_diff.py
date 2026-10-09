#!/usr/bin/env python3
"""Compare registry metadata of two versions of an npm package.

Read-only: uses `npm view`, which reads the registry with the project's npm
config and executes nothing. Run it from the project directory.

  npm_meta_diff.py <pkg> <old> <new>
  npm_meta_diff.py <pkg> <old> <new> --json

Covers the metadata half of the audit: lifecycle scripts, dependencies,
maintainers, publisher, license, repository, engines, bin, provenance,
deprecation, and package size. It does not read the package contents; use
`npm diff` for that.
"""
import argparse
import json
import subprocess
import sys

LIFECYCLE = ("preinstall", "install", "postinstall", "prepare", "prepublish", "preuninstall", "uninstall", "postuninstall")
DEP_FIELDS = ("dependencies", "optionalDependencies", "peerDependencies", "bundleDependencies")


def view(pkg, version):
    out = subprocess.run(["npm", "view", f"{pkg}@{version}", "--json"], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"npm view {pkg}@{version} failed: {out.stderr.strip() or out.stdout.strip()}")
    doc = json.loads(out.stdout)
    if isinstance(doc, list):  # a range matched several versions
        doc = doc[-1]
    return doc


def people(value):
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    names = []
    for p in items:
        names.append(p.get("name") or p.get("email") or str(p) if isinstance(p, dict) else str(p).split(" <")[0])
    return sorted(set(names))


def repo_url(doc):
    r = doc.get("repository")
    return (r.get("url") if isinstance(r, dict) else r) or None


def dict_diff(old, new):
    old, new = old or {}, new or {}
    if isinstance(old, list):
        old = {k: "*" for k in old}
    if isinstance(new, list):
        new = {k: "*" for k in new}
    return {
        "added": {k: new[k] for k in sorted(new) if k not in old},
        "removed": {k: old[k] for k in sorted(old) if k not in new},
        "changed": {k: [old[k], new[k]] for k in sorted(new) if k in old and old[k] != new[k]},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package")
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    a, b = view(args.package, args.old), view(args.package, args.new)

    def scripts(doc):
        s = doc.get("scripts") or {}
        found = {k: s[k] for k in LIFECYCLE if k in s}
        if doc.get("gypfile"):
            found.setdefault("install", "(implicit) node-gyp rebuild")
        return found

    def prov(doc):
        dist = doc.get("dist") or {}
        return {"attestations": bool(dist.get("attestations")), "signatures": bool(dist.get("signatures"))}

    report = {
        "package": args.package,
        "old": a.get("version"),
        "new": b.get("version"),
        "install_scripts": dict_diff(scripts(a), scripts(b)),
        "install_scripts_new_version": scripts(b),
        "dependencies": {f: dict_diff(a.get(f), b.get(f)) for f in DEP_FIELDS},
        "maintainers": {"old": people(a.get("maintainers")), "new": people(b.get("maintainers"))},
        "published_by": {"old": people(a.get("_npmUser")), "new": people(b.get("_npmUser"))},
        "license": [a.get("license"), b.get("license")],
        "repository": [repo_url(a), repo_url(b)],
        "engines": dict_diff(a.get("engines"), b.get("engines")),
        "bin": dict_diff(a.get("bin") if isinstance(a.get("bin"), dict) else {}, b.get("bin") if isinstance(b.get("bin"), dict) else {}),
        "provenance": {"old": prov(a), "new": prov(b)},
        "deprecated": [a.get("deprecated"), b.get("deprecated")],
        "unpacked_size": [(a.get("dist") or {}).get("unpackedSize"), (b.get("dist") or {}).get("unpackedSize")],
        "file_count": [(a.get("dist") or {}).get("fileCount"), (b.get("dist") or {}).get("fileCount")],
    }

    flags = []
    s = report["install_scripts"]
    if s["added"]:
        flags.append("install-time scripts ADDED: " + ", ".join(s["added"]))
    if s["changed"]:
        flags.append("install-time scripts CHANGED: " + ", ".join(s["changed"]))
    for field, d in report["dependencies"].items():
        if d["added"]:
            flags.append(f"new {field}: " + ", ".join(f"{k}@{v}" for k, v in d["added"].items()))
    m = report["maintainers"]
    if set(m["new"]) - set(m["old"]):
        flags.append("maintainers added: " + ", ".join(sorted(set(m["new"]) - set(m["old"]))))
    if set(m["old"]) - set(m["new"]):
        flags.append("maintainers removed: " + ", ".join(sorted(set(m["old"]) - set(m["new"]))))
    p = report["published_by"]
    if p["old"] != p["new"]:
        flags.append(f"publishing account changed: {p['old'] or 'unknown'} -> {p['new'] or 'unknown'}")
    for key in ("attestations", "signatures"):
        if report["provenance"]["old"][key] and not report["provenance"]["new"][key]:
            flags.append(f"{key} present on {report['old']} and MISSING on {report['new']}")
    if report["license"][0] != report["license"][1]:
        flags.append(f"license changed: {report['license'][0]} -> {report['license'][1]}")
    if report["repository"][0] != report["repository"][1]:
        flags.append(f"repository changed: {report['repository'][0]} -> {report['repository'][1]}")
    if report["deprecated"][1]:
        flags.append(f"target version is deprecated: {report['deprecated'][1]}")
    if report["engines"]["added"] or report["engines"]["changed"]:
        flags.append("engines changed: " + json.dumps({**report["engines"]["added"], **{k: v[1] for k, v in report["engines"]["changed"].items()}}))
    if report["bin"]["added"]:
        flags.append("new bin entries: " + ", ".join(report["bin"]["added"]))
    report["flags"] = flags

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"{args.package}: {report['old']} -> {report['new']} (registry metadata)\n")
    print("Flags:" if flags else "Flags: none. Metadata is unchanged in every field that matters for the audit.")
    for f in flags:
        print(f"  - {f}")
    print("\nInstall-time scripts in the new version:")
    if report["install_scripts_new_version"]:
        for k, v in report["install_scripts_new_version"].items():
            mark = "NEW" if k in s["added"] else "CHANGED" if k in s["changed"] else "unchanged"
            print(f"  {k} [{mark}]: {v}")
    else:
        print("  none")
    print(f"\nMaintainers: {', '.join(m['old']) or 'unknown'} -> {', '.join(m['new']) or 'unknown'}")
    print(f"Published by: {', '.join(p['old']) or 'unknown'} -> {', '.join(p['new']) or 'unknown'}")
    print(f"Provenance: attestations {report['provenance']['old']['attestations']} -> {report['provenance']['new']['attestations']}, "
          f"signatures {report['provenance']['old']['signatures']} -> {report['provenance']['new']['signatures']}")
    print(f"License: {report['license'][0]} -> {report['license'][1]}")
    print(f"Unpacked size: {report['unpacked_size'][0]} -> {report['unpacked_size'][1]} bytes; files {report['file_count'][0]} -> {report['file_count'][1]}")
    print("\nThis covers metadata only. Read the package contents with `npm diff`.")


if __name__ == "__main__":
    main()
