# npm, pnpm, yarn, bun

Flags change between package manager versions. Check the installed version first (`npm --version`, `pnpm --version`, `yarn --version`) and confirm an unfamiliar flag with `<pm> help <command>` before relying on it.

## Contents

- [Detect](#detect)
- [Where code runs at install time](#where-code-runs-at-install-time)
- [Outdated](#outdated)
- [Registry metadata (no execution)](#registry-metadata-no-execution)
- [Package diff](#package-diff)
- [Vulnerability scan](#vulnerability-scan)
- [Install with scripts disabled](#install-with-scripts-disabled)
- [Packages that need a build step](#packages-that-need-a-build-step)
- [Lockfile](#lockfile)
- [Pins](#pins)
- [Native cooldown settings](#native-cooldown-settings)
- [Coupled groups](#coupled-groups)

## Detect

| Signal | Package manager |
| :-- | :-- |
| `package-lock.json` or `npm-shrinkwrap.json` | npm |
| `pnpm-lock.yaml`, `pnpm-workspace.yaml` | pnpm |
| `yarn.lock` with `.yarnrc.yml` or `.yarn/` | yarn berry (2+) |
| `yarn.lock` without those | yarn classic (1.x) |
| `bun.lock` or `bun.lockb` | bun |

The `packageManager` field in `package.json` names the exact tool and version; use that tool. Do not switch package managers or create a second lockfile.

Also read: `engines`, `.nvmrc` / `.node-version`, `workspaces` (or `pnpm-workspace.yaml`), `.npmrc` / `.yarnrc.yml` for registries and scoped registries, and `renovate.json` / `.github/renovate.json*` / `.github/dependabot.yml`.

## Where code runs at install time

- **Lifecycle scripts of dependencies:** `preinstall`, `install`, `postinstall`. A package with a `binding.gyp` and no `install` script gets an implicit `node-gyp rebuild`.
- **Git and directory dependencies:** `prepare` (and `prepack`) run when a dependency is installed from a git URL or local folder. Treat a dependency that moves from a registry version to a git URL as a red flag.
- **The project's own scripts:** `prepare`, `postinstall` in the root `package.json` run on a plain install. `--ignore-scripts` disables these too; run the ones the project needs (for example `husky`, code generation) deliberately afterwards.
- **`npx`, `pnpm dlx`, `yarn dlx`, `bunx`:** download and execute a package immediately. Always third-party code execution; audit first.
- **`bin` entries:** not run at install, but run when a script calls them. The first `npm test` after an upgrade executes the new versions of the test runner, bundler, and every plugin they load. That is why the audit precedes the install and not just the scripts.

## Outdated

```bash
npm outdated --json --long          # exit code 1 when anything is outdated; not an error
pnpm outdated --format json --long  # add -r for all workspaces
yarn outdated --json                # classic only
```

`--long` adds the dependency type (prod, dev, optional, peer). Only direct dependencies are listed by default, which is what Phase 1 wants.

Yarn berry has no built-in non-interactive `outdated`. Read the direct dependencies from each `package.json` and compare against `yarn npm info <pkg> --fields version,dist-tags --json`, or use `npm view <pkg> dist-tags.latest`.

Workspaces: `npm outdated --workspaces` (or `-w <name>`), `pnpm -r outdated` (or `--filter <name>`).

"Wanted" is the highest version inside the declared range; "latest" is the `latest` dist-tag. The target for this skill is the latest **safe** version, which may be either or neither.

## Registry metadata (no execution)

`npm view` reads the registry using the project's `.npmrc` (registries, scopes, auth) and executes nothing. It works regardless of which package manager the project uses.

```bash
npm view <pkg> time --json                                # publish time of every version
npm view <pkg>@<ver> scripts dependencies peerDependencies engines --json
npm view <pkg>@<ver> maintainers _npmUser license repository deprecated --json
npm view <pkg>@<ver> dist --json                          # tarball, integrity, signatures, attestations
```

Helpers:

```bash
python3 <skill>/scripts/list_versions.py --ecosystem npm <pkg> <current> <target> --cooldown-days 7
python3 <skill>/scripts/npm_meta_diff.py <pkg> <current> <target>
```

Provenance: `dist.attestations` is present when the version was published with provenance. `npm audit signatures` verifies registry signatures and attestations for what is already installed (run it after install, as a second check).

## Package diff

```bash
npm diff --diff=<pkg>@<current> --diff=<pkg>@<target>              # full diff
npm diff --diff=<pkg>@<current> --diff=<pkg>@<target> --diff-name-only
npm diff --diff=<pkg>@<current> --diff=<pkg>@<target> -- package.json 'lib/**'
```

`npm diff` downloads both tarballs and diffs them without installing or running anything. Start with `--diff-name-only`.

To inspect one version's files (for example to read a packaged `CHANGELOG.md` or an install script), download and unpack it outside the repository:

```bash
tmp=$(mktemp -d)
npm pack <pkg>@<ver> --pack-destination "$tmp" --ignore-scripts
tar -xzf "$tmp"/*.tgz -C "$tmp"     # contents land in "$tmp/package/"
```

Never unpack into the project, and never run anything from the unpacked directory.

## Vulnerability scan

```bash
npm audit --json                    # uses the lockfile; exit code non-zero when issues exist
pnpm audit --json
yarn npm audit --all --recursive --json   # berry
yarn audit --json                         # classic
```

These report on what the lockfile currently resolves, so they describe the *current* state before Phase 5 and the *final* state in Phase 6. For a target version that is not installed yet, query OSV directly (see `security-audit.md`).

## Install with scripts disabled

Always name the exact audited version. `npm update` and `<pkg>@latest` resolve at run time and can pick a version published after the audit.

| Package manager | Bump one dependency | Install from lockfile |
| :-- | :-- | :-- |
| npm | `npm install <pkg>@<ver> --ignore-scripts` (add `--save-exact` if the manifest uses exact versions, `-D` is not needed for an existing dev dependency) | `npm ci --ignore-scripts` |
| pnpm | `pnpm add <pkg>@<ver> --ignore-scripts` (in a workspace: `--filter <name>`, or `-w` for the root) | `pnpm install --frozen-lockfile --ignore-scripts` |
| yarn berry | `YARN_ENABLE_SCRIPTS=false yarn up <pkg>@<ver>` | `YARN_ENABLE_SCRIPTS=false yarn install --immutable` |
| yarn classic | `yarn upgrade <pkg>@<ver> --ignore-scripts` | `yarn install --frozen-lockfile --ignore-scripts` |
| bun | `bun add <pkg>@<ver> --ignore-scripts` | `bun install --frozen-lockfile --ignore-scripts` |

Notes:

- npm keeps the existing range prefix style only if you pass the range you want. `npm install <pkg>@<ver>` writes `^<ver>` by default (or exact with `save-exact=true`). After the bump, check `package.json` shows the same style the project used (`^`, `~`, or exact) and correct it through the package manager, for example `npm install <pkg>@~<ver>`.
- Recent npm versions hold dependency install scripts until they are approved (`npm install-scripts ls`, `npm install-scripts approve <pkg>`). Still pass `--ignore-scripts`: older npm runs everything by default, and the flag makes the intent explicit. Treat `approve` like pnpm's allowlist below: only after reading the script, and mention it at the checkpoint.
- pnpm 10 and later do not run dependency lifecycle scripts unless the package is listed in `onlyBuiltDependencies` (in `pnpm-workspace.yaml` or the `pnpm` field of `package.json`). That allowlist is the project's record of reviewed build scripts; add to it only after reading the script, and mention the addition at the checkpoint.
- bun does not run dependency lifecycle scripts unless the package is in `trustedDependencies`. Same treatment as pnpm's allowlist.
- yarn berry: `enableScripts: false` in `.yarnrc.yml` is the persistent form. Do not change the project's config file for this; use the environment variable.
- In a workspace, bump the dependency in every workspace package that declares it, in one commit, unless they deliberately differ.

## Packages that need a build step

Some packages are useless without their install script (native addons, packages that download a platform binary). After a no-scripts install they fail at run time with a missing-binary error.

1. Identify them: the package has `install` / `postinstall` or a `binding.gyp`, and verification fails without it.
2. Read the script and what it invokes. Downloading a binary from the project's own release host, with a checksum, is the common legitimate case.
3. If the script is new or changed in the target version, that is already a REVIEW item from Phase 2.
4. Run it for that package only: `npm rebuild <pkg>` (npm), `pnpm rebuild <pkg>` after adding it to `onlyBuiltDependencies` (pnpm), `yarn rebuild <pkg>` (berry).

Many such packages now ship prebuilt binaries as optional dependencies (`@esbuild/<platform>`, `@swc/core-<platform>`) and need no script at all.

## Lockfile

- Never edit by hand. If a lockfile change is needed without touching `node_modules`: `npm install --package-lock-only --ignore-scripts`, `pnpm install --lockfile-only`, `yarn install --mode=update-lockfile` (berry).
- Review the diff after every bump:
  - packages added that the audit did not predict,
  - a second copy of a package that used to be deduplicated,
  - any `resolved` URL pointing somewhere other than the project's configured registry,
  - `integrity` values changing for a version that did not change (should never happen),
  - unrelated packages moving. npm sometimes re-resolves neighbours within their ranges; if that happens, note which and why, or re-run with the lockfile restored and a narrower command.
- "Lockfile refresh" (re-resolving everything inside existing ranges) moves many transitive packages at once. Treat it as its own unit of work: diff the lockfile, list every package that moved, run the vulnerability scan and release-age check on the new versions, and commit it separately from any direct upgrade.

## Pins

Under rule 8 these are pins. Exact versions in `dependencies` are not.

| Mechanism | Where |
| :-- | :-- |
| `overrides` | `package.json` (npm) |
| `pnpm.overrides`, `pnpm.packageExtensions`, `pnpm.patchedDependencies` | `package.json` or `pnpm-workspace.yaml` |
| `resolutions` | `package.json` (yarn, also honoured by pnpm and bun) |
| `patches/` with `patch-package` or `pnpm patch` | a patch applies to one exact version; upgrading that package invalidates it |
| Renovate `ignoreDeps`, `packageRules` with `enabled: false` or `allowedVersions` | Renovate config |
| Dependabot `ignore` entries | `.github/dependabot.yml` |

`package.json` cannot hold comments, so the reason for an override is usually in git history:

```bash
git log -S'"<name>"' --format='%h %ad %an%n  %s%n%b' --date=short -- package.json
```

To test whether an override is still needed, check what the graph would resolve to without it: read the requiring package's dependency range at its target version (`npm view <parent>@<target> dependencies --json`) and find the newest version of the pinned package that satisfies it. `npm explain <name>` shows who requires the pinned package now.

Removing an override: delete the entry with `npm pkg delete overrides.<name>` (use bracket form for scoped names, `npm pkg delete 'overrides[@scope/name]'`), then run the install so the lockfile re-resolves, and confirm the resolved version in the lockfile diff. A patched dependency (`patches/`) being upgraded needs the patch re-evaluated against the new version: check whether upstream fixed what the patch does; if so remove the patch, if not it is a required change to regenerate it, and a REVIEW item if that is not straightforward.

## Native cooldown settings

Useful as a second guard; they do not replace choosing the target explicitly. Availability depends on the installed version, so confirm before relying on any of them.

- npm: `--before=<ISO date>` resolves as if no version newer than that date exists. Recent npm versions also have a `min-release-age` config (check `npm config ls -l | grep -i release`).
- pnpm: `minimumReleaseAge` (minutes) in `pnpm-workspace.yaml`, with `minimumReleaseAgeExclude` for exceptions.
- yarn berry: `npmMinimalAgeGate` in `.yarnrc.yml`.
- bun: `minimumReleaseAge` (seconds) in `bunfig.toml`.

If the project already sets one, use the larger of that value and the run's cooldown.

## Coupled groups

Move together, in one commit:

- `react`, `react-dom`, `react-is`, `@types/react`, `@types/react-dom`
- a framework and its first-party packages released in lockstep (`next` + `eslint-config-next`, `@angular/*`, `@nestjs/*`, `@storybook/*`, `@babel/*` majors, `@tanstack/*` of the same product, `vitest` + `@vitest/*`, `jest` + `babel-jest` + `@types/jest`, `typescript-eslint` packages)
- a package and its `@types/<pkg>` when the types track the package's major
- anything whose `peerDependencies` at the target version require a specific version of another direct dependency

Confirm coupling from `peerDependencies` and the release notes rather than assuming from the name.
