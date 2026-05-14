<div align="center">
  <img src="https://assets.mcp-hub.info/img/logo.svg" width="72" alt="MCP Hub" />
  <h1>MCP Hub Security</h1>
  <p><strong>Security gate for MCP servers and Claude Code Skills.</strong><br/>
  Scan any Git repository or <code>SKILL.md</code> against 14+ vulnerability classes before trusting it.</p>

  [![Version](https://img.shields.io/badge/version-2.0.1-ff6b4a)](https://github.com/mcp-hub-corp/mcp/releases/tag/v2.0.1)
  [![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
  [![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
  [![MCP Hub](https://img.shields.io/badge/powered%20by-mcp--hub.info-ff6b4a)](https://mcp-hub.info)
</div>

---

**[Quick install](#quick-install)** · **[Claude Code setup](#mcp-client-configuration)** · **[How it works](#how-it-works)** · **[Tools reference](#available-tools)** · **[Get API key](https://mcp-hub.info/accounts/dashboard/)**

---

## Table of Contents

- [What is this?](#what-is-this)
- [Features](#features)
- [Quick install](#quick-install)
- [MCP client configuration](#mcp-client-configuration) — includes watchdog setup for Claude Code
- [How it works](#how-it-works)
- [Environment variables](#environment-variables)
- [Available tools](#available-tools)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

---

## What is this?

**MCP Hub Security** is an MCP server that acts as a security gate for your AI agent workflows. Before your agent runs an MCP server from a Git repository — or loads a Claude Code Skill — it can call this server to get a full vulnerability analysis from [mcp-hub.info](https://mcp-hub.info).

It detects **14 vulnerability classes** including:

- Prompt injection & instruction override
- Secret and credential exposure
- Tool poisoning & shadow tools
- SSRF and unsafe network calls
- Dangerous capabilities (exec, file write, env access)
- Data exfiltration vectors
- ...and more mapped to the [OWASP MCP Top 10](https://mcp-hub.info/owasp/)

**Skills support:** Claude Code Skills (`SKILL.md` files) are scanned by 17 dedicated analyzers covering 61 rules — detecting instruction overrides, capability abuse, prompt injection hooks, and more.

---

## Features

- **MCP server scanning** — submit any GitHub, GitLab, or Bitbucket repository and get a security score (0–100), risk level, capabilities list, OWASP coverage, and full findings.
- **Skill scanning** — scan a `SKILL.md` by content or URL; get a pass/fail verdict under configurable policy.
- **Policy engine** — configure minimum score, maximum risk level, and denied capabilities via environment variables. The server enforces policy and returns `allowed: true/false` with clear reasons.
- **Proactive watchdog hook** — a Claude Code `PostToolUse` hook that automatically scans any `SKILL.md` you create or edit and warns you immediately.
- **Credit-aware** — each scan costs 5 credits; cached results (same commit SHA) are free. Balance is always returned.
- **Zero install steps** — `uvx` fetches and runs the server on first use; no virtualenv to manage. The server itself talks to the API with the Python stdlib (no `httpx`/`requests`); the only runtime dependency is `fastmcp`.

---

## Quick install

No installation needed. All configs below use `uvx` — it fetches and runs the server automatically on first use.

**The only thing you need:** an API key → **[mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/)** → API Tokens tab.

---

## MCP client configuration

> **Before you start:** get your API key at **[mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/)** → API Tokens. You will need to replace `YOUR_API_KEY` in the configs below — that is the **only** thing you need to change.

<details>
<summary><strong>Claude Code ⭐ recommended — MCP server + Skill watchdog</strong></summary>

Claude Code is the only client with **full support**: the MCP tools for on-demand scanning AND the **proactive Skill watchdog** that automatically scans any `SKILL.md` you write or edit.

---

**1. Get your API key**

👉 [mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/) → API Tokens → Create token. Copy the key.

---

**2. Add the MCP server** — paste into `~/.claude.json` (global) or `.mcp.json` in your project:

```json
{
  "mcpServers": {
    "mcp-hub-security": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/mcp-hub-corp/mcp.git@v2.0.1", "mcp-hub-security"],
      "env": {
        "MCPHUB_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

Replace `YOUR_API_KEY` with your key. That's it for the MCP server.

---

**3. Add the Skill watchdog** — paste into `~/.claude/settings.json` (global) or `.claude/settings.json` (project):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "uvx --from git+https://github.com/mcp-hub-corp/mcp.git@v2.0.1 mcp-hub-skill-watchdog",
            "env": {
              "MCPHUB_API_KEY": "YOUR_API_KEY"
            }
          }
        ]
      }
    ]
  }
}
```

Replace `YOUR_API_KEY` with the same key. Putting the key in the `env` block avoids quoting bugs and keeps it out of the shell process list. The watchdog runs automatically — no other config needed.

---

**What the watchdog does:**

Every time Claude writes or edits a `.md` file that looks like a skill (`name:` + `description:` frontmatter), the watchdog scans it immediately and shows the verdict:

- ✅ **Safe** — brief notice with score and risk, no interruption.
- 🚫 **Blocked** — error with the exact policy violation. Claude Code stops.

Run `claude` — both the server and watchdog are active.

</details>

<details>
<summary><strong>Claude Desktop</strong></summary>

> 🔑 **Get your API key first:** [mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/) → API Tokens. Replace `YOUR_API_KEY` below.

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "mcp-hub-security": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/mcp-hub-corp/mcp.git@v2.0.1", "mcp-hub-security"],
      "env": {
        "MCPHUB_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

Restart Claude Desktop. Note: the proactive Skill watchdog is not available in Claude Desktop (no hooks support).

</details>

<details>
<summary><strong>VS Code (GitHub Copilot)</strong></summary>

> 🔑 **Get your API key first:** [mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/) → API Tokens. Replace `YOUR_API_KEY` below.

Add to `.vscode/mcp.json` in your workspace (or `~/.vscode/mcp.json` globally):

```json
{
  "servers": {
    "mcp-hub-security": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/mcp-hub-corp/mcp.git@v2.0.1", "mcp-hub-security"],
      "env": {
        "MCPHUB_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Cursor</strong></summary>

> 🔑 **Get your API key first:** [mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/) → API Tokens. Replace `YOUR_API_KEY` below.

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "mcp-hub-security": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/mcp-hub-corp/mcp.git@v2.0.1", "mcp-hub-security"],
      "env": {
        "MCPHUB_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

Restart Cursor after saving.

</details>

<details>
<summary><strong>Windsurf</strong></summary>

> 🔑 **Get your API key first:** [mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/) → API Tokens. Replace `YOUR_API_KEY` below.

Add to `~/.windsurf/mcp.json`:

```json
{
  "mcpServers": {
    "mcp-hub-security": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/mcp-hub-corp/mcp.git@v2.0.1", "mcp-hub-security"],
      "env": {
        "MCPHUB_API_KEY": "YOUR_API_KEY"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Zed</strong></summary>

> 🔑 **Get your API key first:** [mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/) → API Tokens. Replace `YOUR_API_KEY` below.

Add to `~/.config/zed/settings.json` under `"context_servers"`:

```json
{
  "context_servers": {
    "mcp-hub-security": {
      "command": {
        "path": "uvx",
        "args": ["--from", "git+https://github.com/mcp-hub-corp/mcp.git@v2.0.1", "mcp-hub-security"],
        "env": {
          "MCPHUB_API_KEY": "YOUR_API_KEY"
        }
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Continue.dev</strong></summary>

> 🔑 **Get your API key first:** [mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/) → API Tokens. Replace `YOUR_API_KEY` below.

Add to `.continue/config.json`:

```json
{
  "mcpServers": [
    {
      "name": "mcp-hub-security",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/mcp-hub-corp/mcp.git@v2.0.1", "mcp-hub-security"],
      "env": {
        "MCPHUB_API_KEY": "YOUR_API_KEY"
      }
    }
  ]
}
```

</details>

---

## Environment variables

### MCP servers

| Variable | Required | Default | Description |
|---|---|---|---|
| `MCPHUB_API_KEY` | **yes** | — | API token from [mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/) |
| `MCPHUB_API_URL` | no | `https://api.mcp-hub.info/api/v1` | API base URL (override for self-hosted) |
| `MCPHUB_MIN_SCORE` | no | `80` | Minimum security score (0–100). Scans below this are blocked. |
| `MCPHUB_MAX_RISK` | no | `low` | Maximum risk level: `none` \| `low` \| `medium` \| `high` \| `critical` |
| `MCPHUB_DENIED_CAPABILITIES` | no | *(none)* | Comma-separated capabilities to always block. E.g. `file_write,process_exec,secret_access,code_eval,env_access,db_access,network_egress` |
| `MCPHUB_POLL_INTERVAL` | no | `2` | Seconds between status polls while scan is running |
| `MCPHUB_POLL_TIMEOUT` | no | `300` | Maximum seconds to wait for a scan result |

### Skills

| Variable | Required | Default | Description |
|---|---|---|---|
| `MCPHUB_SKILL_MIN_SCORE` | no | `70` | Minimum skill score (0–100). Skills below this are blocked. |
| `MCPHUB_SKILL_MAX_RISK` | no | `medium` | Maximum skill risk level: `none` \| `low` \| `medium` \| `high` \| `critical` |

> Skills use a tighter analyzer (17 analyzers, 61 rules) that is separate from the MCP server scanner. Using different thresholds for each is intentional.

> **Optional vars:** if you do not want to override a default, **omit the variable entirely**. Do not set it to the empty string. (The server normalizes `""` to the default, but some MCP clients refuse to forward empty-string `env` entries at all, leading to confusing behavior.)

---

## How it works

### MCP server scan pipeline

`check_mcp_safety(url)` runs four steps automatically:

```
1. POST /scans/          →  submit repo URL, receive check_token
2. GET  /scans/checking/{token}/  (poll every 2 s, up to 5 min)
3. GET  /scans/{id}/verdict/      →  score, risk, capabilities, findings
4. Policy engine         →  evaluate against your env vars → allowed: true/false
```

Cached results (same repo + same commit SHA) skip steps 1–3 and cost **0 credits**.

### Skill scan pipeline

`check_skill_safety` and `check_skill_safety_url` are **synchronous** — no polling needed. The API analyses the SKILL.md content immediately and returns the result in a single request.

### Policy engine

The policy engine runs **locally** after every scan. It blocks if any of these conditions are true:

| Condition | Controlled by |
|---|---|
| `security_score` < minimum | `MCPHUB_MIN_SCORE` / `MCPHUB_SKILL_MIN_SCORE` |
| `risk_level` > maximum | `MCPHUB_MAX_RISK` / `MCPHUB_SKILL_MAX_RISK` |
| Any detected capability is in the deny list | `MCPHUB_DENIED_CAPABILITIES` (MCP only) |
| Critical findings detected when max risk is `low` or below | `MCPHUB_MAX_RISK` |

When blocked, the response includes `allowed: false`, a human-readable `reason`, and `blocked_by_policy` with the list of violations.

Risk levels are ordered: `safe = none < low < medium < high < critical`.

### Why MCPs and Skills have separate thresholds

The MCP server scanner and the Skill scanner are different analyzers with different scoring scales and sensitivity levels. Skills get **slightly more permissive defaults** (`min_score: 70`, `max_risk: medium`) because the skill analyzer is purpose-built for SKILL.md structure and has fewer false positives than the general-purpose MCP scanner. You can tighten skill policy independently of MCP policy.

### Credits

| Operation | Cost |
|---|---|
| New scan (MCP or Skill, new commit) | **5 credits** |
| Cached scan (same commit SHA already scanned) | **0 credits** |
| `get_verdict`, `get_scan_result`, `get_skill_scan` | **0 credits** |

---

## Available tools

### MCP server tools

| Tool | Credits | Description |
|---|---|---|
| `check_mcp_safety(url)` | 5 (cached=0) | Full pipeline: scan → poll → verdict → policy. Main entry point. |
| `get_verdict(scan_id)` | 0 | Re-evaluate policy on an existing scan with current env vars. |
| `get_scan_result(scan_id)` | 0 | Full raw result for an existing scan (findings, file paths, CWEs). |
| `get_credit_balance()` | 0 | Current credit balance and account email. |

### Skill tools

| Tool | Credits | Description |
|---|---|---|
| `check_skill_safety(content)` | 5 (cached=0) | Scan a `SKILL.md` provided as a string. Returns verdict + policy. |
| `check_skill_safety_url(url)` | 5 (cached=0) | Fetch a raw `SKILL.md` from a URL and scan it. |
| `get_skill_scan(scan_id)` | 0 | Retrieve a previous skill scan result by UUID. |

---

## Examples

### Scan an MCP server before installing it

> *"Before we add the Playwright MCP, check if it's safe: https://github.com/microsoft/playwright-mcp"*

Claude will call `check_mcp_safety` and report the score, capabilities, OWASP risks, and whether it passes your policy.

```
allowed: true
security_score: 91
risk_level: low
capabilities: [browser_control, network_egress]
owasp_risks: []
credits_consumed: 0   ← cached result, same commit
```

### Block a server that exceeds your policy

If a repo returns `risk_level: high` and your `MCPHUB_MAX_RISK` is `low`:

```
allowed: false
reason: "MCP server blocked by security policy: Risk level 'high' exceeds maximum 'low'"
blocked_by_policy: ["Risk level 'high' exceeds maximum 'low'"]
```

### Scan a Skill before running it

> *"Check if this skill is safe before loading it"*

```python
check_skill_safety(content="---\nname: my-skill\ndescription: ...\n---\n...")
```

Returns:

```
allowed: true
score: 92
risk_level: low
finding_count: 0
has_critical: false
```

### Re-evaluate policy on an existing scan

Change your policy env vars and re-apply them to a previous scan without consuming credits:

```python
get_verdict(scan_id="550e8400-e29b-41d4-a716-446655440000")
```

### Check your credit balance

```python
get_credit_balance()
# → {"credits": 285, "email": "you@example.com"}
```

---

## Troubleshooting

### Claude Code says "Failed to connect"

That four-word message is everything Claude Code shows by default when an MCP server fails to start. The real error is captured in a debug file but you have to ask for it.

**Step 1 — run a health check yourself.** From your terminal, run the same command Claude Code runs, but skip stdio and just print the diagnostic table:

```bash
MCPHUB_API_KEY=your-key uvx --from git+https://github.com/mcp-hub-corp/mcp.git@v2.0.1 mcp-hub-security --health
```

This prints every `MCPHUB_*` env var the server sees, validates them, and ends with `status: OK` or `status: UNHEALTHY`. Exit code 0 means the server can start; exit code 2 means a config problem (missing API key, invalid risk level, malformed URL).

**Step 2 — capture the full stderr.** Start Claude Code with `--debug-file=/tmp/claude.log`:

```bash
claude --debug-file=/tmp/claude.log
```

Then `tail -f /tmp/claude.log` to see every stderr line from every MCP server — including the actual exception that Claude Code is hiding.

**Step 3 — for Claude Desktop**, logs go to `~/Library/Logs/Claude/mcp-server-mcp-hub-security.log` on macOS.

### `ModuleNotFoundError` or stale uvx cache

If you ran an older version once, `uvx` may have a broken wheel cached. Force a fresh fetch:

```bash
uv cache clean mcp-hub-security
```

Then re-run the original `uvx --from git+...@v2.0.1 …` command — it will resolve the pinned tag again.

### `MCPHUB_API_KEY is required`

The server now fail-fasts when the API key is missing instead of silently breaking. Set it in the `env` block of your MCP config (not inline on the command). Get a key at [mcp-hub.info/accounts/dashboard/](https://mcp-hub.info/accounts/dashboard/).

> **Heads-up on empty strings:** for any *optional* `MCPHUB_*` variable, leave it out entirely instead of setting it to `""`. Empty strings are normalized to the default, but tooling that round-trips JSON may interpret them inconsistently.

### What version am I running?

```bash
uvx --from git+https://github.com/mcp-hub-corp/mcp.git@v2.0.1 mcp-hub-security --version
# → mcp-hub-security 2.0.1
```

---

<div align="center">
  <a href="https://mcp-hub.info">mcp-hub.info</a> ·
  <a href="https://mcp-hub.info/accounts/dashboard/">Get API key</a> ·
  <a href="https://mcp-hub.info/owasp/">OWASP MCP Top 10</a>
</div>
