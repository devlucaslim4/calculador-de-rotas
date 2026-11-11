"""Fila em memória para chamadas longas feitas pelo agente.

O serviço Render deste projeto executa uma instância Uvicorn. A fila usa um
único trabalhador para não multiplicar consultas à API do Checklist Fácil.
Os resultados ficam disponíveis temporariamente e nunca persistem os dados
PIX em disco.
"""

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import RLock
from typing import Callable, Generic, TypeVar
from uuid import UUID, uuid4

T = TypeVar("T")


@dataclass(frozen=True)
class ProcessingJob(Generic[T]):
    job_id: str
    created_at: int
    expires_at: int
    future: Future[T]


class ProcessingJobCapacityError(RuntimeError):
    """The short queue is full and cannot accept another request yet."""


class ProcessingJobStore(Generic[T]):
    """Thread-safe, process-local job registry with bounded queue capacity."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 3_600,
        max_queued_jobs: int = 4,
    ) -> None:
        self.ttl_seconds = max(60, ttl_seconds)
        self.max_queued_jobs = max(1, max_queued_jobs)
        self._lock = RLock()
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="route-processing",
        )
        self._jobs: dict[str, ProcessingJob[T]] = {}

    def _cleanup_locked(self, now: int) -> None:
        expired = [
            job_id
            for job_id, job in self._jobs.items()
            if job.expires_at < now and job.future.done()
        ]
        for job_id in expired:
            del self._jobs[job_id]

    def submit(self, operation: Callable[[], T]) -> ProcessingJob[T]:
        now = int(time.time())
        with self._lock:
            self._cleanup_locked(now)
            queued = sum(not job.future.done() for job in self._jobs.values())
            if queued >= self.max_queued_jobs:
                raise ProcessingJobCapacityError(
                    "A fila de processamento está ocupada. Aguarde a conclusão do pedido atual."
                )
            job_id = str(uuid4())
            future = self._executor.submit(operation)
            job = ProcessingJob(
                job_id=job_id,
                created_at=now,
                expires_at=now + self.ttl_seconds,
                future=future,
            )
            self._jobs[job_id] = job
            return job

    def get(self, job_id: str, *, now: int | None = None) -> ProcessingJob[T] | None:
        try:
            normalized = str(UUID(job_id))
        except (TypeError, ValueError):
            return None
        current = int(time.time()) if now is None else int(now)
        with self._lock:
            self._cleanup_locked(current)
            job = self._jobs.get(normalized)
            if job is None or job.expires_at < current:
                return None
            return job
