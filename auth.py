import time
from contextlib import asynccontextmanager
from pathlib import Path

from notebooklm import NotebookLMClient
from notebooklm.exceptions import AuthError

from config import STORAGE_PATH

# Session considered stale after 7 days without update
MAX_STORAGE_AGE_DAYS = 7


class AuthManager:
    def __init__(self, storage_path: Path = STORAGE_PATH):
        self.storage_path = storage_path

    def is_valid(self) -> bool:
        if not self.storage_path.exists():
            return False
        if self.storage_path.stat().st_size < 100:
            return False
        age_days = (time.time() - self.storage_path.stat().st_mtime) / 86400
        return age_days < MAX_STORAGE_AGE_DAYS

    async def recover(self) -> None:
        """Open a visible browser window for the user to log in manually."""
        from playwright.async_api import async_playwright

        print("[auth] Session expired or missing. Opening browser for login...", flush=True)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--no-sandbox"],
            )
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto("https://notebooklm.google.com")

            # Wait for user to complete Google login and land on the dashboard
            await page.wait_for_url(
                "**/notebooklm.google.com/**",
                timeout=300_000,  # 5 minutes
            )

            # Save fresh cookies to storage_state
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(self.storage_path))
            await browser.close()

        print("[auth] Login successful, session saved.", flush=True)

    @asynccontextmanager
    async def client(self):
        """Yields an authenticated NotebookLMClient, recovering auth if needed."""
        if not self.is_valid():
            await self.recover()

        try:
            async with NotebookLMClient.from_storage(keepalive=300) as c:
                yield c
        except AuthError:
            await self.recover()
            async with NotebookLMClient.from_storage(keepalive=300) as c:
                yield c
