# Kiro Powers

A collection of **864 Kiro Powers**, converted from [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) following the official AWS guide: [*A guide for migrating Claude Code Skills to Kiro Powers*](https://builder.aws.com/content/39DLiJ3W2dTp53IqbWNxsJYgcHB/a-guide-for-migrating-claude-code-skills-to-kiro-powers).

Kiro Powers package domain knowledge and workflows for the Kiro IDE, and can additionally bundle MCP servers — combining documentation, best practices, and executable capabilities in one package.

## What's inside

| | Count |
|---|---|
| Total powers | 864 |
| Curated productivity powers | 32 |
| Composio MCP-connector powers (bundle `mcp.json` for the Rube MCP) | 832 |
| Powers with on-demand `steering/` docs | 6 |

Every power lives in `powers/<power-name>/` and contains:

```
powers/<power-name>/
├── POWER.md          # core docs + Kiro frontmatter (always loaded)
├── steering/*.md     # deep-dive content, loaded on demand (when present)
├── mcp.json          # MCP server config (Composio/Rube connectors only)
└── scripts/ ...      # bundled tools/assets copied from the original skill
```

## How these were converted

Per the AWS migration guide's structural mapping:

| Claude Skill | Kiro Power |
|---|---|
| `SKILL.md` | `POWER.md` (with added `name`/`displayName`/`description`/`keywords`/`author` frontmatter) |
| `references/*.md` and other non-`SKILL` markdown | `steering/*.md` |
| `.claude-plugin/marketplace.json` | metadata folded into `POWER.md` frontmatter |
| `README.md`, `CHANGELOG.md`, `.claude-plugin/` | removed |
| `requires: mcp: [rube]` | `mcp.json` (Rube MCP server) |

Each `POWER.md` also gains an **Available Steering Files** section (when applicable) and a **License & Attribution** section crediting the original work.

The conversion is reproducible:

```bash
# 1. clone the source skills
git clone https://github.com/ComposioHQ/awesome-claude-skills /tmp/awesome-claude-skills

# 2. convert
python3 scripts/convert_skill_to_power.py --src /tmp/awesome-claude-skills --out powers --only all

# 3. validate against the AWS checklist
python3 scripts/validate_powers.py powers
```

`--only` accepts `top` (the 32 curated), `composio` (the 832 connectors), or `all`.

## Using a power in Kiro

1. Open the Kiro **Powers** panel.
2. Click **Add Custom Power** → **Local Directory**.
3. Enter the full path to a power directory, e.g. `/full/path/to/powers/tailored-resume-generator`.
4. Click **Add**.

### Composio / Rube MCP powers

The 832 `*-automation` powers call tools through the **Rube MCP** server (Composio). Their bundled `mcp.json` expects a `RUBE_API_KEY` environment variable:

```jsonc
{
  "mcpServers": {
    "rube": {
      "command": "npx",
      "args": ["-y", "@composio/mcp@latest", "start", "--client", "kiro"],
      "env": { "RUBE_API_KEY": "${RUBE_API_KEY}" }
    }
  }
}
```

Set your own `RUBE_API_KEY` before using these powers. **Do not commit real keys** — the value is a placeholder.

## Attribution

All powers are converted from [awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills) by **ComposioHQ and its contributors**. Original licenses are preserved inside each power (bundled `LICENSE*` files where they existed). This repository only restructures that content into the Kiro Powers format per the AWS migration guide; it does not claim original authorship of the skill content.

## Repository layout

```
kiro-powers/
├── powers/                      # 864 converted powers
├── scripts/
│   ├── convert_skill_to_power.py
│   └── validate_powers.py
└── README.md
```
