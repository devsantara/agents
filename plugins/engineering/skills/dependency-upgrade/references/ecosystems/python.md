# pip, uv, poetry

Flags change between tool versions. Check the installed version first and confirm an unfamiliar flag with `--help` before relying on it.

## Contents

- [Detect](#detect)
- [Where code runs at install time](#where-code-runs-at-install-time)
- [Outdated](#outdated)
- [Registry metadata (no execution)](#registry-metadata-no-execution)
- [Package diff](#package-diff)
- [Vulnerability scan](#vulnerability-scan)
- [Install without building](#install-without-building)
- [Lockfile](#lockfile)
- [Pins](#pins)
- [Native cooldown settings](#native-cooldown-settings)
- [Coupled groups](#coupled-groups)

## Detect

| Signal | Tool |
| :-- | :-- |
| `uv.lock`, `[tool.uv]` in `pyproject.toml` | uv |
| `poetry.lock`, `[tool.poetry]` | poetry |
| `requirements*.txt` with a matching `requirements*.in` | pip-tools (or `uv pip compile`) |
| `requirements*.txt` only | pip |
| `Pipfile.lock` | pipenv |
| `pdm.lock` | pdm |

Also read: `requires-python` / `python_requires`, `.python-version`, dependency groups and extras in `pyproject.toml`, index configuration (`pip.conf`, `[[tool.uv.index]]`, `[[tool.poetry.source]]`, `--index-url` lines in requirements files), and Renovate or Dependabot config.

Use the project's own virtual environment. Never install into the system interpreter.

## Where code runs at install time

- **sdist builds.** Installing from a source distribution runs the build backend: `setup.py` or any PEP 517 backend, with whatever build dependencies it declares. This is arbitrary code execution at install time, and it also happens when a tool only needs *metadata* from an sdist (resolving, `pip download`).
- **Wheels** run nothing at install. Prefer them: `--only-binary=:all:`.
- **`.pth` files and import-time code.** A wheel can ship a `.pth` file that executes on every interpreter start, and any module can run code at import. So the first `pytest` after an upgrade runs the new code. The audit has to precede the install, not just the build.
- **`uvx`, `uv tool run`, `pipx run`:** download and execute immediately. Always third-party code execution; audit first.
- **Direct URL and VCS dependencies** (`pkg @ git+https://...`) always build from source. A dependency that moves from an index version to a VCS URL is a red flag.

## Outdated

```bash
pip list --outdated --format=json            # everything in the environment, including transitives
uv pip list --outdated
uv tree --outdated --depth 1                 # direct dependencies of a uv project
poetry show --outdated --top-level
```

`pip list --outdated` does not distinguish direct from transitive. Intersect it with the names declared in `pyproject.toml` or the top-level requirements file (the `.in` file for pip-tools).

## Registry metadata (no execution)

The PyPI JSON API returns everything the audit needs and executes nothing.

```bash
curl -s https://pypi.org/pypi/<pkg>/json            # all releases, upload times, yanked flags, project_urls
curl -s https://pypi.org/pypi/<pkg>/<ver>/json      # one version: requires_dist, requires_python, license, files
python3 <skill>/scripts/list_versions.py --ecosystem pypi <pkg> <current> <target> --cooldown-days 7
```

Compare between the two versions: `info.requires_dist` (new dependencies), `info.requires_python`, `info.license` / `info.license_expression`, `info.project_urls` (repository change), `info.yanked`, and the file list in `urls` (did a version stop shipping wheels?).

PyPI does not expose the maintainer list or the uploading account in the JSON API. Record the publisher check as limited, and rely on provenance where present: PyPI attestations (Trusted Publishing) are available per file at

```
https://pypi.org/integrity/<project>/<version>/<filename>/provenance
```

A 404 means no attestation for that file. Present on the current version and absent on the target is a red flag.

For a private index, the JSON API may not exist; use the Simple API (`/simple/<pkg>/`) for the file list and upload times where the index provides them, and record which checks did not apply.

## Package diff

Download wheels directly, outside the repository, without invoking a build:

```bash
tmp=$(mktemp -d)
pip download <pkg>==<current> --no-deps --only-binary=:all: -d "$tmp/old"
pip download <pkg>==<target>  --no-deps --only-binary=:all: -d "$tmp/new"
( cd "$tmp/old" && unzip -q *.whl -d x ) ; ( cd "$tmp/new" && unzip -q *.whl -d x )
diff -ru "$tmp/old/x" "$tmp/new/x"
```

`--only-binary=:all:` matters here: without it `pip download` may build an sdist to read its metadata, which runs `setup.py`. If the package publishes no wheel, fetch the sdist archive by URL from the JSON API's `urls` list and unpack it with `tar` instead; do not let pip touch it.

Look especially at: `setup.py` / `pyproject.toml` build configuration, `*.pth` files, `__init__.py` top-level code, new compiled extensions (`.so`, `.pyd`) that the previous version did not have, and `entry_points.txt`.

## Vulnerability scan

- OSV (see `security-audit.md`) with ecosystem `PyPI`, for the exact target version.
- `pip-audit` if the project already has it (`pip-audit -r requirements.txt`, or against the environment). It is itself a third-party tool: do not install it just for this run without asking.
- The PyPI JSON API includes a `vulnerabilities` array per version.

## Install without building

Always name the exact audited version.

| Tool | Bump one dependency | Install from lockfile |
| :-- | :-- | :-- |
| uv (project) | `uv lock --upgrade-package <pkg>==<ver>` then `uv sync --no-build` (edit the constraint in `pyproject.toml` with `uv add '<pkg>>=<ver>' --no-sync` if the declared range excludes the target) | `uv sync --frozen --no-build` |
| poetry | `poetry add <pkg>@<ver> --lock` (or `poetry update <pkg> --lock` when the range already allows it), then `poetry install` with `POETRY_INSTALLER_ONLY_BINARY=:all:` | same install command |
| pip-tools | change the `.in` file constraint, `pip-compile --upgrade-package <pkg>==<ver>`, then `pip-sync` with `PIP_ONLY_BINARY=:all:` | `pip-sync` |
| pip | change the pin in `requirements.txt` through the project's usual means, then `pip install -r requirements.txt --only-binary=:all:` | same |

Notes:

- `--no-build` (uv) and `--only-binary=:all:` (pip) fail when a package has no wheel for this platform. That failure is information: the package needs an sdist build. Read its build configuration (and its build dependencies), then allow a source build for that one package: with pip, `--only-binary=:all: --no-binary <pkg>`; with uv, the error names the packages that lack wheels, so re-run without `--no-build` only once every one of them has been read. A package that had wheels at the current version and has none at the target is worth a sentence in the security file.
- Keep the manifest's constraint style: `==` stays `==`, `>=x,<y` keeps its shape, `~=` stays `~=`.
- A plain `requirements.txt` with no lockfile gives no record of transitive versions. Say so in the baseline; the lockfile-diff review in Phase 5 becomes a before/after `pip freeze` comparison.

## Lockfile

- `uv.lock`, `poetry.lock`, compiled `requirements.txt`: written by the tool, never by hand.
- Review the diff after every bump: packages added, packages whose source changed (index URL, or registry → VCS/URL), hashes changing for an unchanged version, and unrelated packages moving.
- `uv lock --upgrade` and `poetry update` with no package argument re-resolve everything. That is a lockfile refresh: its own unit of work, committed separately, with every moved package listed and scanned.

## Pins

Under rule 8 these are pins. `==` in a requirements file or `pyproject.toml` is a style, not a pin.

| Mechanism | Where |
| :-- | :-- |
| `constraint-dependencies`, `override-dependencies` | `[tool.uv]` |
| Constraints files | `-c constraints.txt`, `PIP_CONSTRAINT` |
| Upper caps added for a stated reason | an inline `# comment` next to a `<x` bound in requirements or `pyproject.toml` |
| `[tool.poetry.dependencies]` entries for packages the project does not import | transitive pins disguised as direct dependencies; look for a comment |
| Renovate / Dependabot ignore rules | their config files |

Python manifests allow comments, so read them. Otherwise:

```bash
git log -S'<name>' --format='%h %ad %an%n  %s%n%b' --date=short -- pyproject.toml requirements*.txt constraints*.txt
```

To test whether a constraint is still needed, check what the requiring package asks for at its target version (`requires_dist` from the JSON API) and whether the version that would resolve without the constraint is outside the problem range.

## Native cooldown settings

- uv: `--exclude-newer <date>` (or `exclude-newer` in `[tool.uv]`) ignores anything uploaded after that date.
- pip: recent versions have `--uploaded-prior-to <date>`; check `pip install --help`.

If the project already sets one, use the larger of that and the run's cooldown.

## Coupled groups

- A framework and its plugins that pin each other (`django` + `djangorestframework` compatibility ranges, `pydantic` + `pydantic-core` + `pydantic-settings`, `sqlalchemy` + `alembic`, `pytest` + plugins that cap pytest, `boto3` + `botocore` + `s3transfer`, `grpcio` + `grpcio-tools`, `opentelemetry-*`).
- Type stubs (`types-<pkg>`) with their package.
- Anything whose `requires_dist` at the target requires a specific range of another direct dependency.

Confirm coupling from `requires_dist`, not from the name.
