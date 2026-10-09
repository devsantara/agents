<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://assets.devsantara.com/agents/logo-dark.png">
    <img alt="@devsantara/agents logo" src="https://assets.devsantara.com/agents/logo-light.png" height="128">
  </picture>
  <h1>@devsantara/agents</h1>
  <p>Plugins for Claude, built and maintained by Devsantara</p>
  <a href="https://github.com/devsantara"><img alt="Made by Devsantara" src="https://img.shields.io/badge/Made_By-Devsantara-0F172A.svg?style=for-the-badge&labelColor=000000"></a>
  <a href="./LICENSE"><img alt="MIT License" src="https://img.shields.io/github/license/devsantara/agents?style=for-the-badge&labelColor=000000"></a>
  <a href="https://github.com/devsantara/agents/graphs/contributors"><img alt="contributors" src="https://img.shields.io/github/contributors/devsantara/agents?style=for-the-badge&labelColor=000000"></a>
</div>

## Plugins

This repository is a Claude Code plugin marketplace. Each plugin lives in its own directory under `plugins/` and is installed separately.

No plugins have been published yet. See [Adding a plugin](#adding-a-plugin).

## Install

Requires [Claude Code](https://code.claude.com/docs/en/quickstart). From inside a session, add the marketplace and install a plugin in one step:

```text
/plugin install <plugin> --marketplace devsantara/agents
```

Or from your shell, add the marketplace once and then install any plugin from it by name:

```bash
claude plugin marketplace add devsantara/agents
claude plugin install <plugin>@devsantara
```

The install id is `<plugin>@devsantara`. To pick up a new release later, run `claude plugin update <plugin>@devsantara`.

## Project layout

```text
.
├── .changeset/                 # Changesets config and pending changesets
├── .claude-plugin/
│   └── marketplace.json        # Catalog listing every plugin in plugins/
├── scripts/
│   └── sync-plugin-versions.js # Copies package.json versions into plugin.json
└── plugins/
    └── <plugin>/               # Plugin root
        ├── .claude-plugin/
        │   └── plugin.json     # Plugin manifest: name, version, metadata
        ├── skills/<name>/SKILL.md
        ├── agents/<name>.md
        ├── hooks/hooks.json
        ├── .mcp.json
        ├── package.json        # Name and version, for Changesets only
        ├── CHANGELOG.md        # Generated on release
        └── README.md
```

Inside a plugin, each kind of component lives in a fixed directory, created only when it is needed:

| Location                 | Contents                                            |
| :----------------------- | :-------------------------------------------------- |
| `skills/<name>/SKILL.md` | Skills, one directory per skill                     |
| `agents/<name>.md`       | Subagents, one Markdown file each                   |
| `hooks/hooks.json`       | Hook configuration, under a top-level `"hooks"` key |
| `.mcp.json`              | MCP server definitions                              |

Only `plugin.json` belongs in a plugin's `.claude-plugin/`. Components saved there don't load. Inside hook commands and MCP configs, refer to plugin files as `${CLAUDE_PLUGIN_ROOT}/...` rather than by relative path.

## Adding a plugin

1. Create `plugins/<plugin>/.claude-plugin/plugin.json` with at least `name`, `version`, `description`, and `author`. Start `version` at `0.0.0`. Use a kebab-case `name` and treat it as permanent, because installs are recorded under it.
2. Create `plugins/<plugin>/package.json` with the same `name` and `version`, so [Changesets](#releasing) can version the plugin:

   ```json
   {
     "name": "<plugin>",
     "version": "0.0.0",
     "private": true
   }
   ```

3. Add the plugin's components and a `README.md` at the plugin root.
4. Add an entry to `plugins` in `.claude-plugin/marketplace.json`. The entry `name` must match the `name` in `plugin.json`, and `source` is the path from the repository root:

   ```json
   {
     "name": "<plugin>",
     "source": "./plugins/<plugin>",
     "description": "What the plugin provides"
   }
   ```

5. List the plugin under [Plugins](#plugins) above.
6. Add a changeset for the first release with `pnpm changeset`, for example a `minor` bump with the summary "Initial release" to ship `0.1.0`. Without it, the plugin is tagged and released as `0.0.0`.

## Development

Install the release tooling once with [pnpm](https://pnpm.io):

```bash
pnpm install
```

Load one plugin's working copy for a session, without installing it:

```bash
claude --plugin-dir ./plugins/<plugin>
```

Or load every plugin in the repository at once:

```bash
claude --plugin-dir ./plugins
```

After editing files, run `/reload-plugins` in that session to apply the changes. Validate the marketplace and each plugin you changed before every commit. Until the first plugin is added, the marketplace check reports `Marketplace has no plugins defined`, which `--strict` treats as a failure:

```bash
claude plugin validate --strict .
claude plugin validate --strict ./plugins/<plugin>
```

If a component doesn't show up, check the **Errors** tab of `/plugin`, or run `claude --plugin-dir ./plugins plugin list`.

## Releasing

Plugins are versioned independently with [Changesets](https://changesets.dev). `version` in a plugin's `plugin.json` pins installed copies: users only receive changes when it changes. Never edit it by hand. Changesets bumps the plugin's `package.json`, and `scripts/sync-plugin-versions.js` copies that version into `plugin.json`.

1. In the pull request that changes a plugin, add a changeset. Pick the plugin, the bump type, and write a summary for the changelog:

   ```bash
   pnpm changeset
   ```

   Commit the generated `.changeset/*.md` file with the change. A change that needs no release, such as docs or tooling, needs no changeset.

2. When the pull request merges to `main`, the [Release](./.github/workflows/release.yml) workflow opens or updates a `chore(release): version plugins` pull request. It bumps each changed plugin's version, updates its `CHANGELOG.md`, and deletes the consumed changesets.
3. Merging that pull request releases the plugins: the workflow tags each one as `<plugin>@<version>` and creates a GitHub release from its changelog entry.

To cut the version bump locally instead, run `pnpm run version` with a `GITHUB_TOKEN` set (the changelog links pull requests and commits), then commit the result.

Never change a published plugin's `name`; change `displayName` for a different label.

## License

[MIT](./LICENSE)
