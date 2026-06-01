import json
from dataclasses import dataclass
from pathlib import Path

from config import BUILTIN_NOTEBOOKS, REGISTRY_PATH


@dataclass
class NotebookRegistry:
    path: Path = REGISTRY_PATH

    def _default(self) -> dict:
        return {"active": "Memory", "projects": dict(BUILTIN_NOTEBOOKS)}

    def load(self) -> dict:
        if not self.path.exists():
            data = self._default()
            self.save(data)
            return data
        with open(self.path) as f:
            return json.load(f)

    def save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_active_id(self) -> str:
        data = self.load()
        active = data.get("active")
        if not active:
            raise ValueError("No active project set. Call set_active_project first.")
        notebook_id = data["projects"].get(active)
        if not notebook_id:
            raise ValueError(f"Active project '{active}' not found in registry.")
        return notebook_id

    def get_active_name(self) -> str:
        return self.load().get("active", "Memory")

    def set_active(self, name: str) -> None:
        data = self.load()
        if name not in data["projects"]:
            raise ValueError(f"Project '{name}' not found. Use create_project first.")
        data["active"] = name
        self.save(data)

    def add(self, name: str, notebook_id: str) -> None:
        data = self.load()
        data["projects"][name] = notebook_id
        self.save(data)

    def list_all(self) -> dict[str, str]:
        return self.load()["projects"]

    def exists(self, name: str) -> bool:
        return name in self.load()["projects"]
