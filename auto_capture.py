#!/usr/bin/env python3.11
"""PostToolUse auto-capture: saves meaningful events to NotebookLM.

Triggered by the shell wrapper auto_capture.sh — never blocks Claude.
Captures: git commits/push, package installs, new significant files, deploys.
"""
import json
import sys
import os
import asyncio
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from utils import filter_secrets, is_duplicate
from auth import AuthManager
from registry import NotebookRegistry
from config import TEMP_DIR

# Meaningful bash patterns worth capturing
_BASH_TRIGGERS = [
    'git commit',
    'git push',
    'npm install',
    'npm ci',
    'pip install',
    'pip3 install',
    'brew install',
    'docker build',
    'docker push',
    'vercel',
    'railway up',
    'fly deploy',
    'npx prisma migrate',
    'supabase db push',
]

# Paths too noisy to capture (partial match)
_IGNORE_PATHS = [
    'node_modules', '.cache', '__pycache__', '.git/',
    '/tmp/', 'dist/', 'build/', '.next/',
]


def _is_ignored_path(path: str) -> bool:
    return any(p in path for p in _IGNORE_PATHS)


def _parse_event(raw: str) -> dict:
    try:
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _should_capture(event: dict) -> tuple[bool, str]:
    tool = event.get('tool_name') or event.get('tool') or ''
    inp = event.get('tool_input') or event.get('input') or {}
    if not isinstance(inp, dict):
        inp = {}

    # New file creation (Write tool)
    if tool == 'Write':
        path = inp.get('file_path', '')
        if _is_ignored_path(path):
            return False, ''
        content = inp.get('content', '')
        if len(content) < 100:  # Skip trivial files
            return False, ''
        return True, f"new_file"

    # Meaningful bash commands
    if tool == 'Bash':
        cmd = inp.get('command', '')
        for trigger in _BASH_TRIGGERS:
            if trigger in cmd:
                return True, 'command'

    return False, ''


def _build_content(event: dict, reason: str) -> str:
    tool = event.get('tool_name') or event.get('tool') or ''
    inp = event.get('tool_input') or event.get('input') or {}
    out = str(event.get('tool_output') or event.get('output') or '')
    if not isinstance(inp, dict):
        inp = {}
    date = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = [
        f"# Auto-Capture: {reason}",
        f"**Date:** {date}",
        f"**Tool:** {tool}",
        f"**Type:** auto_capture",
        "",
    ]

    if tool == 'Write':
        path = inp.get('file_path', '')
        preview = inp.get('content', '')[:400]
        lines += [f"**File:** `{path}`", "", "```", preview, "```"]

    elif tool == 'Bash':
        cmd = inp.get('command', '')
        lines += [f"**Command:**", "```bash", cmd, "```", ""]
        if out and out not in ('None', ''):
            lines += ["**Output:**", "```", out[:500], "```"]

    return "\n".join(lines)


async def _upload(content: str) -> None:
    content = filter_secrets(content)
    if is_duplicate(content):
        return
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = TEMP_DIR / f"{uuid.uuid4()}.md"
    try:
        tmp.write_text(content)
        reg = NotebookRegistry()
        auth = AuthManager()
        async with auth.client() as client:
            await client.sources.add_file(reg.get_active_id(), str(tmp))
    finally:
        if tmp.exists():
            tmp.unlink()


def main():
    raw = sys.stdin.read()
    event = _parse_event(raw)

    should, reason = _should_capture(event)
    if not should:
        return

    content = _build_content(event, reason)
    asyncio.run(_upload(content))


if __name__ == '__main__':
    main()
