#!/usr/bin/env python3
"""Interactive first-time setup for SAB (Smart Agent Brain)."""
import asyncio
import json
import shutil
from pathlib import Path

REGISTRY_PATH = Path.home() / ".claude/memory-mcp/notebook_registry.json"
STORAGE_PATH  = Path.home() / ".notebooklm/profiles/default/storage_state.json"


async def main():
    print("\n🧠 SAB — Smart Agent Brain — Setup\n")

    if REGISTRY_PATH.exists():
        print(f"Registry already exists at {REGISTRY_PATH}")
        overwrite = input("Overwrite? [y/N] ").strip().lower()
        if overwrite != "y":
            print("Aborted.")
            return

    # Step 1: Auth
    print("\n[1/3] NotebookLM Authentication")
    print("SAB uses Playwright to authenticate with your Google account.")
    print("A browser window will open — log in to NotebookLM, then close it.")
    input("Press Enter to open the browser...")

    STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://notebooklm.google.com")
        print("Waiting for login (up to 5 minutes)...")
        await page.wait_for_url("**/notebooklm.google.com/**", timeout=300_000)
        await asyncio.sleep(2)
        await context.storage_state(path=str(STORAGE_PATH))
        await browser.close()
    print("✓ Auth saved.")

    # Step 2: Create notebooks
    print("\n[2/3] Creating NotebookLM notebooks")
    from notebooklm import NotebookLMClient

    notebooks: dict[str, str] = {}
    default_names = ["Memory", "Knowledge", "Projects"]

    client = NotebookLMClient.from_storage(str(STORAGE_PATH), keepalive=60)
    async with client:
        for name in default_names:
            create = input(f"  Create notebook '{name}'? [Y/n] ").strip().lower()
            if create in ("", "y"):
                nb = await client.notebooks.create(name)
                notebooks[name] = nb.id
                print(f"  ✓ '{name}' → {nb.id}")

        extra = input("  Add more notebook names (comma-separated, or Enter to skip): ").strip()
        if extra:
            for name in [n.strip() for n in extra.split(",") if n.strip()]:
                nb = await client.notebooks.create(name)
                notebooks[name] = nb.id
                print(f"  ✓ '{name}' → {nb.id}")

    # Step 3: Write registry
    print("\n[3/3] Writing registry")
    active = list(notebooks.keys())[0] if notebooks else ""
    registry = {"active": active, "projects": notebooks}
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2))
    print(f"✓ Registry saved to {REGISTRY_PATH}")

    # Step 4: MCP registration hint
    print("\n[Done] Add SAB to Claude Code:\n")
    server_path = Path(__file__).parent / "server.py"
    print(f'  claude mcp add notebooklm-memory python3 {server_path}')
    print("\nOr manually add to ~/.claude.json under your project's mcpServers:")
    print(json.dumps({
        "notebooklm-memory": {
            "type": "stdio",
            "command": "python3",
            "args": [str(server_path)]
        }
    }, indent=2))
    print()


if __name__ == "__main__":
    asyncio.run(main())
