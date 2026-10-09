# Go modules

## Contents

- [Detect](#detect)
- [Where code runs](#where-code-runs)
- [Outdated](#outdated)
- [Registry metadata (no execution)](#registry-metadata-no-execution)
- [Package diff](#package-diff)
- [Vulnerability scan](#vulnerability-scan)
- [Upgrade](#upgrade)
- [`go.mod` and `go.sum`](#gomod-and-gosum)
- [Pins](#pins)
- [Cooldown](#cooldown)
- [Coupled groups](#coupled-groups)

## Detect

`go.mod` at the module root; `go.work` for a multi-module workspace (each module has its own `go.mod` and is upgraded on its own). Read the `go` directive, the `toolchain` line if present, `GOPROXY` / `GOPRIVATE` / `GONOSUMDB` from `go env`, a `vendor/` directory, and Renovate or Dependabot config.

## Where code runs

Go has no install scripts. `go get`, `go mod download`, and `go mod tidy` fetch and verify source; they do not execute it. That makes the install step itself low risk, and moves the gate to the first time the new code is compiled into something that runs:

- **`go test`, `go run`, and running a built binary** execute dependency code, including every `init()` function in every imported package.
- **`go generate`** runs whatever commands the `//go:generate` comments name. It is never run implicitly. Do not run it on dependency code, and check whether the project's own generate directives invoke a tool that is being upgraded.
- **cgo** compiles C code with the system compiler at build time; `#cgo` directives can pass flags to it.
- **`go run <module>@<version>` and `go install <module>@<version>`** download and execute or install a tool. Third-party code execution; audit first.
- **Tool dependencies** (the `tool` directive in `go.mod`, or a `tools.go` file) are run by `go tool` and by the project's scripts.

So: audit, then `go get`, then build and test.

## Outdated

```bash
go list -m -u -json all        # every module with an available Update
go list -m -u -f '{{if and .Update (not .Indirect)}}{{.Path}} {{.Version}} -> {{.Update.Version}}{{end}}' all
go list -m -versions <module>  # every known version
go list -m -u -retracted all   # include retraction notices
```

Direct dependencies are the `require` lines without `// indirect`. `.Update` shows the latest version **within the same major**: Go treats `v2+` as a different module path (`example.com/mod/v2`). To see whether a newer major exists, query it directly: `go list -m -versions example.com/mod/v2` (then `/v3`, and so on). A major upgrade is an import-path change across the codebase and is always a required code change.

## Registry metadata (no execution)

```bash
python3 <skill>/scripts/list_versions.py --ecosystem go <module> <current> <target> --cooldown-days 7
curl -s https://proxy.golang.org/<module>/@v/list            # versions (uppercase letters are escaped as !lowercase)
curl -s https://proxy.golang.org/<module>/@v/<version>.info  # publish time
curl -s https://proxy.golang.org/<module>/@v/<version>.mod   # that version's go.mod: its requirements and go directive
```

Compare the `.mod` files of the current and target versions for new requirements, a raised `go` directive, and `retract` directives.

There is no maintainer list or publisher account for a Go module: identity is the repository behind the module path. The checks that replace "publisher change" are: did the repository move or change owner, is it archived, and does the checksum database agree. Integrity is enforced by `go.sum` and the checksum database (`sum.golang.org`). Never set `GOSUMDB=off`, `GONOSUMDB`, or `GOINSECURE` to get past a verification failure; a checksum mismatch is a BLOCK.

Pseudo-versions (`v0.0.0-20250101120000-abcdef123456`) pin a commit, not a release. There is no changelog entry for them; use the commit compare and mark it lower confidence.

## Package diff

```bash
old=$(go mod download -json <module>@<current> | sed -n 's/.*"Dir": "\(.*\)",*/\1/p')
new=$(go mod download -json <module>@<target>  | sed -n 's/.*"Dir": "\(.*\)",*/\1/p')
diff -ru "$old" "$new"
```

`go mod download` places verified source in the module cache without compiling it. The module cache is outside the repository. Look especially at: new `init()` functions, new `//go:generate` and `#cgo` directives, `unsafe`, `os/exec`, `net` and `net/http` use in packages that had none, `//go:linkname`, embedded binary blobs (`//go:embed`), and new assembly files.

## Vulnerability scan

- `govulncheck ./...` if it is installed. It reports only vulnerabilities in functions the project actually calls, which is exactly the "does this affect us" question. It is a tool download if missing (`go run golang.org/x/vuln/cmd/govulncheck@latest`): official, but still ask before fetching it.
- OSV (see `security-audit.md`) with ecosystem `Go` for the exact target version.

## Upgrade

```bash
go get <module>@<exact version>
go mod tidy
go build ./... && go vet ./... && go test ./...
```

- Name the exact audited version. `go get -u` and `@latest` resolve at run time and also move transitive requirements.
- `go get` may raise the `go` directive or add a `toolchain` line if the new version requires a newer Go. That is a runtime requirement change: flag it at the checkpoint before applying, because it changes what every developer and CI job needs installed.
- Go uses minimal version selection: upgrading one module can raise the minimum version of modules it shares with others. The `go.mod` diff shows every requirement that moved; each is part of this upgrade and belongs in the lockfile-diff review.
- If the project vendors, run `go mod vendor` after the bump and commit the `vendor/` changes in the same commit.
- Major upgrade (`/v2` → `/v3`): `go get <module>/v3@<ver>`, rewrite import paths in every file that imports it, remove the old requirement with `go mod tidy`.

## `go.mod` and `go.sum`

- Both are written by the `go` command. Do not edit `go.sum` at all. Edit `go.mod` only through `go get` / `go mod edit` / `go mod tidy`.
- Review after every bump: new `require` lines (especially new indirect modules), requirements that moved without being asked, changes to `go` / `toolchain`, and that `go mod verify` passes.

## Pins

Under rule 8 these are pins. A plain `require` at a specific version is not; that is how every Go dependency is declared.

| Mechanism | Meaning |
| :-- | :-- |
| `replace` | Substitutes a module with another version, a fork, or a local path |
| `exclude` | Forbids a specific version |
| `// indirect` requirement held above what the graph needs | A transitive version raised by hand, usually for a vulnerability |
| Renovate / Dependabot ignore rules | In their config files |

`go.mod` allows comments; read the lines around the directive. Otherwise:

```bash
git log -S'<module>' --format='%h %ad %an%n  %s%n%b' --date=short -- go.mod
```

A `replace` pointing at a fork exists because upstream lacked a fix. Check whether the upstream target version now contains it (the fork's extra commits against the upstream changelog). If it does, drop the directive with `go mod edit -dropreplace=<module>` and run `go mod tidy`. A `replace` to a local path is a development setup, not an upgrade candidate; report it and leave it.

## Cooldown

Go has no native minimum-release-age setting. Enforce it by choosing the target explicitly from the version list with publish times.

## Coupled groups

- Modules from one repository released together (`go.opentelemetry.io/otel` and its `sdk`, `trace`, `metric`, exporters; `google.golang.org/grpc` with `google.golang.org/protobuf` and generated code; `k8s.io/api`, `k8s.io/apimachinery`, `k8s.io/client-go`, which must share a minor; `github.com/aws/aws-sdk-go-v2` and its service modules).
- A code generator and its runtime library (`protoc-gen-go` with `protobuf`, `sqlc`, `ent`, `gqlgen`): upgrading one usually means regenerating, which is a required change.

Confirm from the target version's `.mod` file what it requires.
