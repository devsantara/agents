# engineering

A directory of engineering tools for day-to-day development.

## Install

```bash
claude plugin marketplace add devsantara/agents
claude plugin install engineering@devsantara
```

## Components

Skills are invoked as `/engineering:<skill>`, or picked up automatically when a request matches.

| Skill | What it does |
| :-- | :-- |
| [`dependency-upgrade`](./skills/dependency-upgrade/SKILL.md) | Upgrades dependencies to their latest safe versions: audits each target for supply-chain risk before installing, reads every changelog entry in the range, applies the code changes one dependency per commit, and writes a per-dependency report under `docs/dependency-upgrade/<date>/`. |

## Development

```bash
claude --plugin-dir ./plugins/engineering
claude plugin validate --strict ./plugins/engineering
```
