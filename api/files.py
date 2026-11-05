"""Armazenamento efêmero de planilhas geradas pela API."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4


class GeneratedFileError(RuntimeError):
    """Erro seguro relacionado a um arquivo temporário."""


@dataclass(frozen=True)
class StoredFile:
    file_id: str
    filename: str
    path: Path
    created_at: int
    expires_at: int


class TemporaryFileStore:
    def __init__(self, root: Path, *, ttl_seconds: int, max_size_mb: int) -> None:
        self.root = root.resolve()
        self.ttl_seconds = ttl_seconds
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._lock = RLock()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validated_id(file_id: str) -> str:
        try:
            return str(UUID(file_id))
        except (TypeError, ValueError) as exc:
            raise GeneratedFileError("Identificador de arquivo inválido.") from exc

    def _paths(self, file_id: str) -> tuple[Path, Path]:
        valid_id = self._validated_id(file_id)
        return self.root / f"{valid_id}.xlsx", self.root / f"{valid_id}.json"

    def cleanup(self, *, now: int | None = None) -> None:
        current = int(time.time()) if now is None else int(now)
        with self._lock:
            for metadata_path in self.root.glob("*.json"):
                try:
                    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                    expired = int(metadata.get("expires_at", 0)) < current
                except (OSError, ValueError, TypeError):
                    expired = True
                if not expired:
                    continue
                file_path = metadata_path.with_suffix(".xlsx")
                file_path.unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)

    def save(self, content: bytes, filename: str, *, now: int | None = None) -> StoredFile:
        if not content:
            raise GeneratedFileError("A planilha gerada está vazia.")
        if len(content) > self.max_size_bytes:
            raise GeneratedFileError("A planilha gerada excede o limite permitido.")
        current = int(time.time()) if now is None else int(now)
        self.cleanup(now=current)
        file_id = str(uuid4())
        file_path, metadata_path = self._paths(file_id)
        safe_name = Path(filename).name
        stored = StoredFile(
            file_id=file_id,
            filename=safe_name,
            path=file_path,
            created_at=current,
            expires_at=current + self.ttl_seconds,
        )
        metadata = {
            "file_id": stored.file_id,
            "filename": stored.filename,
            "created_at": stored.created_at,
            "expires_at": stored.expires_at,
        }
        with self._lock:
            file_path.write_bytes(content)
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        return stored

    def get(self, file_id: str, *, now: int | None = None) -> StoredFile:
        current = int(time.time()) if now is None else int(now)
        file_path, metadata_path = self._paths(file_id)
        with self._lock:
            if not file_path.is_file() or not metadata_path.is_file():
                raise GeneratedFileError("Arquivo não encontrado ou já removido.")
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                stored = StoredFile(
                    file_id=self._validated_id(str(metadata["file_id"])),
                    filename=Path(str(metadata["filename"])).name,
                    path=file_path,
                    created_at=int(metadata["created_at"]),
                    expires_at=int(metadata["expires_at"]),
                )
            except (KeyError, OSError, TypeError, ValueError) as exc:
                raise GeneratedFileError("Metadados do arquivo inválidos.") from exc
            if stored.expires_at < current:
                file_path.unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)
                raise GeneratedFileError("O link da planilha expirou.")
            return stored

    def renew(self, file_id: str, *, now: int | None = None) -> StoredFile:
        current = int(time.time()) if now is None else int(now)
        stored = self.get(file_id, now=current)
        renewed = StoredFile(
            file_id=stored.file_id,
            filename=stored.filename,
            path=stored.path,
            created_at=stored.created_at,
            expires_at=current + self.ttl_seconds,
        )
        _, metadata_path = self._paths(file_id)
        metadata = {
            "file_id": renewed.file_id,
            "filename": renewed.filename,
            "created_at": renewed.created_at,
            "expires_at": renewed.expires_at,
        }
        with self._lock:
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        return renewed
