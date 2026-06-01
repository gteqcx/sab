# 🧠 SAB — Smart Agent Brain

A Python MCP server that gives Claude Code autonomous, persistent memory backed by **NotebookLM** as a RAG (Retrieval-Augmented Generation) knowledge base.

No bash scripts. No flat files. No third-party vector DBs. Just Claude ↔ NotebookLM, directly.

[![Ko-fi](https://img.shields.io/badge/support%20the%20project-ko--fi-FF5E5B?logo=ko-fi)](https://ko-fi.com/gteqcx)

---

## What it does

SAB gives Claude 6 memory tools, available in every session:

| Tool | Description |
|------|-------------|
| `ask_memory(query)` | Query your NotebookLM notebook — recall past work, patterns, decisions |
| `store_checkpoint(title, content)` | Save a session milestone as a source in NotebookLM |
| `store_pattern(class_name, content, confidence)` | Persist a reusable problem→solution pattern |
| `create_project(name)` | Create a new NotebookLM notebook and switch to it |
| `list_projects()` | List all registered notebooks |
| `set_active_project(name)` | Switch the active notebook context |

Claude follows a **5-phase learning loop** on every non-trivial task:

```
SURVEY → RECALL → EXECUTE → REFLECT → PERSIST
```

- **SURVEY / RECALL** — at task start, Claude queries memory for relevant patterns and prior context
- **EXECUTE** — works with that context in hand
- **REFLECT / PERSIST** — after completion, stores what was learned as a reusable pattern

---

## Architecture

```
Claude Code
    │  JSON-RPC / stdio
    ▼
server.py  (FastMCP)
    ├── auth.py          — session management + Playwright auth recovery
    ├── registry.py      — notebook_registry.json  (name → NotebookLM ID)
    ├── config.py        — paths and constants
    ├── utils.py         — privacy filter (secret scrubbing) + SHA-256 dedup
    └── auto_capture.py  — PostToolUse hook: captures git commits, deploys, file writes
```

**Auth recovery**: if your Google session expires, SAB opens a non-headless browser window, waits for you to log in, then saves the new session state — no manual intervention with cookies or tokens.

---

## Built-in protections

**Privacy filter** — automatically redacts secrets before anything is uploaded to NotebookLM:

```
sk-...           → [OPENAI_KEY]
tvly-...         → [TAVILY_KEY]
ghp_...          → [GITHUB_TOKEN]
Bearer <token>   → Bearer [REDACTED]
password=...     → password=[REDACTED]
```

**SHA-256 deduplication** — identical content uploaded within 5 minutes is silently skipped. No duplicate sources in your notebooks.

**Auto-capture** — a PostToolUse hook backgrounds a Python process that uploads meaningful events to NotebookLM automatically:
- `git commit`, `git push`
- `npm install`, `pip install`, `brew install`
- Docker builds and deploys
- Significant new files (>100 chars, non-ignored paths)

---

## Requirements

- Python 3.11+
- A Google account with access to [NotebookLM](https://notebooklm.google.com)
- [Claude Code](https://claude.ai/code)

---

## Installation

```bash
git clone https://github.com/gteqcx/sab.git ~/.claude/memory-mcp
cd ~/.claude/memory-mcp
pip3 install -r requirements.txt
playwright install chromium
python3 setup.py          # interactive: auth + create notebooks + register MCP
```

`setup.py` will:
1. Open a browser for Google login
2. Create your Memory / Knowledge / Projects notebooks
3. Print the `claude mcp add` command to register SAB

### Auto-capture hook (optional)

To capture git commits, deploys, and file writes automatically, add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash|Write",
        "hooks": [{
          "type": "command",
          "command": "bash ~/.claude/memory-mcp/scripts/auto_capture.sh",
          "timeout": 2
        }]
      }
    ],
    "PreCompact": [
      {
        "hooks": [{
          "type": "command",
          "command": "bash ~/.claude/memory-mcp/scripts/pre_compact_save.sh",
          "timeout": 5
        }]
      }
    ]
  }
}
```

Create the scripts directory:

```bash
mkdir -p ~/.claude/memory-mcp/scripts
```

**`scripts/auto_capture.sh`**:
```bash
#!/bin/bash
TMPFILE="/tmp/claude_ac_$$.json"
cat > "$TMPFILE"
(python3 ~/.claude/memory-mcp/auto_capture.py < "$TMPFILE"; rm -f "$TMPFILE") 2>/dev/null &
```

**`scripts/pre_compact_save.sh`**:
```bash
#!/bin/bash
echo "⚠️ PRE-COMPACT — $(date '+%Y-%m-%d %H:%M')"
echo ""
echo "Context window is nearly full. You MUST do this RIGHT NOW before compaction:"
echo ""
echo "1. Call store_checkpoint(title=\"Auto-Checkpoint $(date '+%Y-%m-%d %H:%M')\", content=\"...\")"
echo "   Content must include: what was done, key decisions, current task state, exact next step, relevant file paths."
echo ""
echo "2. If mid-task with a recognizable pattern: also call store_pattern(class_name, content, confidence)."
echo ""
echo "Do NOT skip. Do NOT wait. Call the tool immediately."
```

---

## How Claude uses it

SAB injects a `HEURISTICS_PROMPT` into the MCP server's `instructions` field. Claude reads this and follows the rules automatically — no slash commands needed.

Key behaviors:
- **Session start** → `ask_memory("recent context, active project, and relevant patterns")`
- **New project** → `create_project(name)` + `set_active_project(name)`
- **Task complete** → `store_pattern(class_name, solution, confidence)`
- **Milestone / context shift** → `store_checkpoint(title, summary)`
- **User says** "save", "checkpoint", "сохрани", "закончили" → immediate checkpoint

---

## Credits & Inspirations

| Source | What we borrowed |
|--------|-----------------|
| [AgentMemory](https://github.com/rohitg00/agentmemory) by @rohitg00 | Privacy filter pattern, SHA-256 deduplication, PostToolUse auto-capture concept |
| [notebooklm-py](https://pypi.org/project/notebooklm/) | Python client for NotebookLM API |
| [FastMCP](https://github.com/jlowin/fastmcp) | MCP server framework |
| Hermes Agent (Agentic-OS) | 5-phase SURVEY→RECALL→EXECUTE→REFLECT→PERSIST learning loop |

---

## Support

If SAB is useful to you:

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/gteqcx)

---

## Co-authors

- **gteqcx** — architecture, integration, real-world testing
- **Claude** (Anthropic) — implementation, system design, documentation

---

## License

MIT

<!-- last updated: 2026-06-01 -->
