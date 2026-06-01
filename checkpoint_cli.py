#!/usr/bin/env python3.11
"""CLI wrapper for store_checkpoint — for use in shell scripts.

Usage:
    echo "content" | python3.11 checkpoint_cli.py "Title"
    echo "content" | python3.11 checkpoint_cli.py "Title" --notebook Knowledge
"""
import asyncio
import argparse
import sys
import uuid

sys.path.insert(0, '/Users/eqcx/.claude/memory-mcp')

from auth import AuthManager
from registry import NotebookRegistry
from config import TEMP_DIR
from utils import filter_secrets, is_duplicate


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('title')
    parser.add_argument('--notebook', default=None, help='Notebook name (default: active)')
    args = parser.parse_args()

    content = sys.stdin.read().strip()
    if not content:
        print("[checkpoint-cli] No content on stdin, skipping.", file=sys.stderr)
        sys.exit(0)

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = TEMP_DIR / f"{uuid.uuid4()}.txt"

    content = filter_secrets(content)
    if is_duplicate(content):
        print(f"[checkpoint-cli] Skipped (duplicate within 5 min)")
        return

    try:
        temp_path.write_text(f"# {args.title}\n\n{content}\n")

        reg = NotebookRegistry()
        auth = AuthManager()

        if args.notebook:
            nb_id = reg.list_all().get(args.notebook)
            if not nb_id:
                print(f"[checkpoint-cli] Notebook '{args.notebook}' not found in registry.", file=sys.stderr)
                sys.exit(1)
        else:
            nb_id = reg.get_active_id()

        async with auth.client() as client:
            await client.sources.add_file(nb_id, str(temp_path))

        print(f"[checkpoint-cli] Saved: {args.title}")
    finally:
        if temp_path.exists():
            temp_path.unlink()


asyncio.run(main())
