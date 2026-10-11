import json
import os
from pathlib import Path
from typing import Optional, List
from ..interfaces.storage import Storage, StorageValue

class JsonStorage(Storage):
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, key: str) -> Path:
        return self.base_dir / f"{key}.json"

    async def get(self, key: str) -> Optional[StorageValue]:
        path = self._get_path(key)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return StorageValue(**data)
        except Exception:
            return None

    async def put(self, key: str, value: StorageValue) -> None:
        path = self._get_path(key)
        with open(path, "w", encoding="utf-8") as f:
            f.write(value.model_dump_json())

    async def delete(self, key: str) -> None:
        path = self._get_path(key)
        if path.exists():
            path.unlink()

    async def list_keys(self, prefix: Optional[str] = None) -> List[str]:
        keys = []
        for file in self.base_dir.glob("*.json"):
            key = file.stem
            if prefix is None or key.startswith(prefix):
                keys.append(key)
        return keys

    async def close(self) -> None:
        pass
