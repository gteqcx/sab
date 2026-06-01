from pathlib import Path

REGISTRY_PATH = Path.home() / ".claude/memory-mcp/notebook_registry.json"
STORAGE_PATH  = Path.home() / ".notebooklm/profiles/default/storage_state.json"
TEMP_DIR      = Path("/tmp/memory-mcp")

# Add your own NotebookLM notebook IDs here after setup.
# Run: python3 setup.py  — it will guide you through creating notebooks.
# Or use the create_project() MCP tool from within Claude Code.
BUILTIN_NOTEBOOKS: dict[str, str] = {}
