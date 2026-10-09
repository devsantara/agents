# Cargo

## Contents

- [Detect](#detect)
- [Where code runs](#where-code-runs)
- [Outdated](#outdated)
- [Registry metadata (no execution)](#registry-metadata-no-execution)
- [Package diff](#package-diff)
- [Vulnerability scan](#vulnerability-scan)
- [Upgrade](#upgrade)
- [`Cargo.lock`](#cargolock)
- [Pins](#pins)
- [Cooldown](#cooldown)
- [Coupled groups](#coupled-groups)

## Detect

`Cargo.toml` and `Cargo.lock`; a `[workspace]` table for multi-crate repositories (with `[workspace.dependencies]` as the shared version table); `rust-version` (MSRV) and `rust-toolchain.toml`; `.cargo/config.toml` for alternate registries and source replacement; `deny.toml` (cargo-deny) and `supply-chain/` (cargo-vet) if the project uses them; Renovate or Dependabot config.

## Where code runs

Cargo has no install scripts and no switch that disables build-time execution. The gate is therefore: **audit before the first build**.

- **`build.rs`** is compiled and run on the host for any crate that has one, during `cargo build`, `cargo check`, `cargo test`, `cargo clippy`, `cargo doc`, and `cargo run`. It can do anything the user can.
- **Procedural macros** are compiled and run inside the compiler for every crate that uses them, during the same commands.
- **Editor tooling** (rust-analyzer) runs build scripts and proc macros in the background as soon as the manifest changes. It cannot be controlled from here; this is one more reason the audit happens before the manifest is touched.
- **`cargo install <crate>`** builds and installs a binary. Third-party code execution; audit first.

These do **not** execute dependency code: `cargo update`, `cargo fetch`, `cargo metadata`, `cargo tree`, `cargo generate-lockfile`, `cargo add`, `cargo remove`, `cargo info`, `cargo search`.

So Phase 5 has two distinct steps: change the manifest and lockfile (safe), then build (runs the audited code).

## Outdated

```bash
cargo update --dry-run                 # what would move within the declared requirements
cargo tree --depth 1                   # direct dependencies and their resolved versions
cargo info <crate>                     # latest version, rust-version, features
```

`cargo outdated` and `cargo upgrade` (cargo-edit) are third-party plugins. Use them if the project already has them; do not install them for this run without asking.

`cargo update --dry-run` only shows semver-compatible moves. To find newer incompatible versions (a new major, or a new minor for `0.x` crates, which Cargo treats as breaking), compare each direct dependency's resolved version with the newest version from crates.io:

```bash
python3 <skill>/scripts/list_versions.py --ecosystem cargo <crate> <current> latest --cooldown-days 7
```

## Registry metadata (no execution)

```bash
curl -s -H 'User-Agent: dependency-upgrade-audit' https://crates.io/api/v1/crates/<crate>
curl -s -H 'User-Agent: dependency-upgrade-audit' https://crates.io/api/v1/crates/<crate>/<version>
curl -s -H 'User-Agent: dependency-upgrade-audit' https://crates.io/api/v1/crates/<crate>/<version>/dependencies
curl -s -H 'User-Agent: dependency-upgrade-audit' https://crates.io/api/v1/crates/<crate>/owners
```

crates.io requires a User-Agent header. Per version it gives `created_at`, `yanked`, `license`, `rust_version`, and `published_by`. Compare `published_by` and the owner list between versions for the publisher check. A yanked target is not a valid target.

## Package diff

Download the `.crate` archives (plain gzip tarballs) outside the repository:

```bash
tmp=$(mktemp -d)
for v in <current> <target>; do
  curl -sL -o "$tmp/$v.crate" "https://static.crates.io/crates/<crate>/<crate>-$v.crate"
  mkdir "$tmp/$v" && tar -xzf "$tmp/$v.crate" -C "$tmp/$v" --strip-components=1
done
diff -ru "$tmp/<current>" "$tmp/<target>"
```

If the project uses cargo-vet, `cargo vet diff <crate> <current> <target>` does the same and records the review.

Read in full, every time: `build.rs` (or whatever `build = "..."` names in `Cargo.toml`), and the entry point of any proc-macro crate. A crate that gains a `build.rs`, becomes a proc-macro, or adds a `links` key in the target version is a REVIEW item. Also look at: new `unsafe` blocks, `std::process::Command`, `std::net`, `std::env::var` in build scripts, `include_bytes!` of opaque blobs, and new dependencies with build scripts of their own.

The published `.crate` contains a `.cargo_vcs_info.json` with the commit it was packaged from; use it to compare the archive against the repository at that commit when something looks off.

## Vulnerability scan

- `cargo audit` (RustSec) or `cargo deny check advisories` if the project already has them. Both are third-party plugins: do not install for this run without asking.
- OSV (see `security-audit.md`) with ecosystem `crates.io` for the exact target version. OSV includes RustSec advisories.

## Upgrade

Semver-compatible bump (the declared requirement already allows the target):

```bash
cargo update -p <crate> --precise <exact version>
```

Incompatible bump, or to raise the declared requirement:

```bash
cargo add <crate>@<exact version>          # rewrites the requirement in Cargo.toml, keeps features
cargo update -p <crate> --precise <exact version>
```

Then, and only after the audit has passed for this exact version:

```bash
cargo check --all-targets && cargo clippy --all-targets && cargo test
```

- Name the exact audited version. A bare `cargo update` re-resolves everything.
- `cargo add` writes a caret requirement by default (`"1.2.3"`). If the manifest used a different operator (`=1.2.3`, `~1.2`), keep it: `cargo add <crate>@=1.2.4`.
- In a workspace with `[workspace.dependencies]`, change the version there, once.
- If the target's `rust-version` is above the project's MSRV or toolchain, that is a runtime requirement change: flag it at the checkpoint; do not raise the project's toolchain silently.
- Features can change between versions (a default feature removed, a feature renamed). Compare the `[features]` tables in the two `Cargo.toml` files from the package diff; a silently dropped default feature is a classic silent behavior change.

## `Cargo.lock`

- Written by Cargo, never by hand.
- Review after every bump: new packages (each one that has a build script or is a proc-macro gets its script read), a second major of a crate that used to be unified, `source` lines pointing anywhere other than the expected registry, checksum changes on an unchanged version.
- Libraries sometimes do not commit `Cargo.lock`. Then there is no lockfile diff; record the before/after of `cargo tree` instead and say so in the baseline.

## Pins

Under rule 8 these are pins. A version requirement in `[dependencies]`, including an exact `=1.2.3`, is a style and stays upgradable; keep its operator.

| Mechanism | Meaning |
| :-- | :-- |
| `[patch.crates-io]` / `[patch.<registry>]` | Substitutes a crate with a fork, git revision, or local path |
| `[replace]` | The older form of the same thing |
| A git or path dependency standing in for a published crate | A fork in use until upstream releases a fix |
| A transitive crate added to `[dependencies]` only to hold its version | Look for a comment |
| cargo-deny `skip` / `ban` entries, cargo-vet exemptions | Policy records with reasons attached |
| Renovate / Dependabot ignore rules | In their config files |

`Cargo.toml` allows comments; read the lines around the entry. Otherwise:

```bash
git log -S'<crate>' --format='%h %ad %an%n  %s%n%b' --date=short -- Cargo.toml
```

A `[patch]` to a fork exists because upstream lacked something. Check whether the upstream target version contains it. If it does, remove the patch entry, run `cargo update -p <crate>`, and confirm in `Cargo.lock` that the crate now comes from the registry.

## Cooldown

Cargo has no native minimum-release-age setting. Enforce it by choosing the target explicitly from the version list with publish times and using `--precise`.

## Coupled groups

- Crates released in lockstep from one workspace (`tokio` + `tokio-util` + `tokio-stream` compatibility, `serde` + `serde_derive`, `tonic` + `prost` + `tonic-build` + `prost-build`, `axum` + `tower-http` + `hyper` majors, `sqlx` + `sqlx-macros`, `wasm-bindgen` + its CLI, `tracing-*`, `opentelemetry-*`, `bevy_*`).
- A derive or macro crate with its runtime crate.
- Crates that appear in each other's public API: if the project passes a type from crate A to crate B, both must agree on A's major.

Confirm from the target version's dependency list.
