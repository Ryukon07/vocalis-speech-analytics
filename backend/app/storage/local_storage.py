import json
import re
from uuid import uuid4
from pathlib import Path
from app.core.exceptions import AppError
from .base import Storage


class LocalStorage(Storage):
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}\.(wav|mp3|flac|json)", key):
            raise AppError("INVALID_STORAGE_KEY", "Invalid managed file identifier.")
        target = (self.root / key).resolve()
        if target.parent != self.root:
            raise AppError("INVALID_STORAGE_KEY", "Invalid managed file identifier.")
        return target

    def save(self, stream, suffix: str, limit: int):
        key = uuid4().hex + suffix
        target = self.path(key)
        size = 0
        try:
            with target.open("xb") as output:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > limit:
                        raise AppError(
                            "UPLOAD_TOO_LARGE",
                            f"Upload exceeds the configured {limit // 1048576} MB limit.",
                            413,
                        )
                    output.write(chunk)
            if size == 0:
                raise AppError("EMPTY_UPLOAD", "Audio file is empty.")
            return key, size
        except BaseException:
            target.unlink(missing_ok=True)
            raise

    def delete(self, key: str):
        self.path(key).unlink(missing_ok=True)

    def save_json(self, value):
        from io import BytesIO

        return self.save(
            BytesIO(json.dumps(value, allow_nan=False).encode()), ".json", 100 * 1048576
        )[0]

    def read_json(self, key):
        return json.loads(self.path(key).read_text(encoding="utf-8"))
