#!/usr/bin/env python3.11
"""NotebookLM Memory MCP Server.

Provides Claude with autonomous memory management tools backed by NotebookLM.
Run with: python3.11 server.py (stdio transport, registered as MCP in Claude Code)
"""
import sys
import os

# Ensure local modules are importable
sys.path.insert(0, os.path.dirname(__file__))

import re
import uuid
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from auth import AuthManager
from config import TEMP_DIR
from registry import NotebookRegistry
from utils import filter_secrets, is_duplicate

HEURISTICS_PROMPT = """
MEMORY MANAGEMENT RULES — follow strictly, no exceptions.

You operate a 5-phase learning loop on every non-trivial task:
SURVEY → RECALL → EXECUTE → REFLECT → PERSIST

--- SURVEY & RECALL (at session/task start) ---

MUST call ask_memory when:
- Starting a new session — query "last session summary, active project, next steps" BEFORE asking the user anything
- After context compaction — immediately call ask_memory("last session summary and current task") and continue without asking the user
- User says "remember", "recall", "continue from", "помнишь", "продолжи", "что мы делали"
- Starting a task — query for known patterns matching the problem class
- User asks about a past decision, project state, or previous work

--- EXECUTE ---
Proceed with the task using recalled patterns and context.

--- REFLECT & PERSIST (at task completion) ---

MUST call store_pattern after completing any non-trivial task:
- Extract the generalizable CLASS of problem, not the specific instance
- Name it descriptively: e.g. "supabase_rls_delete_blocked", "nextjs_env_not_loaded_at_build"
- Confidence: "low" (first time), "medium" (worked once), "high" (verified multiple times)
- Include: what triggers this problem, exact solution, pitfalls to avoid

MUST call store_session (preferred) or store_checkpoint when:
- PRE-COMPACT message received — immediately call store_session with topic = short slug of current work
- A milestone is complete (feature done, bug fixed, deploy succeeded)
- Topic or project context shifts significantly
- User writes: "save", "checkpoint", "сохрани", "закончили", "пауза", "стоп", "всё на сегодня"
- After 10+ Write/Edit tool calls without a save

Use store_session when saving a whole conversation/session (named, searchable by date+topic).
Use store_checkpoint for quick mid-session milestones.

--- PROJECT ROUTING ---

MUST call create_project when starting work on a project not in list_projects().
MUST call set_active_project when switching projects mid-session.

--- CONTENT QUALITY ---

store_session / store_checkpoint content: what was done, decisions, blockers, next steps, file paths.
store_pattern content: problem trigger, exact solution procedure, pitfalls — reusable across sessions.
"""

registry = NotebookRegistry()
auth = AuthManager()

server = FastMCP(
    name="notebooklm-memory",
    instructions=HEURISTICS_PROMPT,
)


def _make_filename(prefix: str) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-zA-Z0-9_-]', '_', prefix)[:40].strip('_')
    return f"{date}_{slug}.txt"


async def _upload_to_notebook(notebook_id: str, content: str, filename: str | None = None) -> str | None:
    content = filter_secrets(content)
    if is_duplicate(content):
        return "duplicate"
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    name = filename or f"{uuid.uuid4()}.txt"
    temp_path = TEMP_DIR / name
    try:
        temp_path.write_text(content)
        async with auth.client() as client:
            await client.sources.add_file(notebook_id, str(temp_path))
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return None


@server.tool()
async def ask_memory(query: str) -> str:
    """Query the active NotebookLM notebook — for context, patterns, decisions, or past work.

    Use at session start and before any task to recall relevant patterns (SURVEY + RECALL phase).
    """
    async with auth.client() as client:
        notebook_id = registry.get_active_id()
        result = await client.chat.ask(notebook_id, query)
        return result.answer


@server.tool()
async def store_session(topic: str, content: str) -> str:
    """Save a full session/conversation to the active notebook with a named, searchable file.

    Use when PRE-COMPACT fires or at session end. Topic becomes part of the filename,
    making sessions individually retrievable: session_2026-06-01_SAB-github.txt

    Args:
        topic: Short slug describing this session, e.g. "SAB-github-publish", "grilldiscount-fix"
        content: Full session summary — what was done, decisions, next steps, file paths.
    """
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    filename = _make_filename(f"session_{topic}")
    full_content = (
        f"Session: {topic}\n"
        f"Date: {date}\n"
        f"Type: session_log\n\n"
        f"{content}\n"
    )
    notebook_id = registry.get_active_id()
    await _upload_to_notebook(notebook_id, full_content, filename=filename)
    return f"Session '{topic}' saved as '{filename}' in notebook '{registry.get_active_name()}'."


@server.tool()
async def store_checkpoint(title: str, content: str) -> str:
    """Save a mid-session milestone into the active notebook (PERSIST phase).

    For quick milestone saves within a session. Use store_session for full session saves.
    Content: what was done, decisions made, blockers, next steps, relevant file paths.
    """
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    filename = _make_filename(f"checkpoint_{title}")
    full_content = f"Checkpoint: {title}\nDate: {date}\nType: session_log\n\n{content}\n"
    notebook_id = registry.get_active_id()
    await _upload_to_notebook(notebook_id, full_content, filename=filename)
    return f"Checkpoint '{title}' saved to notebook '{registry.get_active_name()}'."


@server.tool()
async def store_pattern(class_name: str, content: str, confidence: str = "medium") -> str:
    """Save a generalizable problem-solution pattern into the active notebook (REFLECT phase).

    Use after completing any non-trivial task. Extract the reusable CLASS of problem, not the instance.

    Args:
        class_name: Snake_case problem class, e.g. "supabase_rls_delete_blocked", "nextjs_hydration_mismatch"
        content: Problem trigger, exact solution procedure, pitfalls. Must be reusable across sessions.
        confidence: "low" (first occurrence), "medium" (worked once), "high" (verified multiple times)
    """
    if confidence not in ("low", "medium", "high"):
        confidence = "medium"

    date = datetime.now().strftime("%Y-%m-%d")
    full_content = (
        f"# Pattern: {class_name}\n"
        f"**Confidence:** {confidence}\n"
        f"**Date:** {date}\n"
        f"**Type:** learned_pattern\n\n"
        f"{content}\n"
    )
    notebook_id = registry.get_active_id()
    await _upload_to_notebook(notebook_id, full_content)
    return f"Pattern '{class_name}' ({confidence} confidence) saved to notebook '{registry.get_active_name()}'."


@server.tool()
async def create_project(project_name: str) -> str:
    """Create a new NotebookLM notebook, register it, and make it active.

    Call when starting work on a project not present in list_projects().
    """
    if registry.exists(project_name):
        registry.set_active(project_name)
        return f"Project '{project_name}' already exists. Switched to it as active."

    async with auth.client() as client:
        notebook = await client.notebooks.create(project_name)
        notebook_id = notebook.id

    registry.add(project_name, notebook_id)
    registry.set_active(project_name)
    return f"Created notebook '{project_name}' (id: {notebook_id}) and set as active."


@server.tool()
async def list_projects() -> str:
    """List all registered projects/notebooks and the currently active one."""
    projects = registry.list_all()
    active = registry.get_active_name()
    lines = []
    for name, nb_id in projects.items():
        marker = " ← active" if name == active else ""
        lines.append(f"  {name}: {nb_id}{marker}")
    return "Projects:\n" + "\n".join(lines)


@server.tool()
async def set_active_project(name: str) -> str:
    """Switch the active notebook context to a different project."""
    registry.set_active(name)
    nb_id = registry.list_all()[name]
    return f"Active project set to '{name}' (id: {nb_id})."


if __name__ == "__main__":
    server.run(transport="stdio")
