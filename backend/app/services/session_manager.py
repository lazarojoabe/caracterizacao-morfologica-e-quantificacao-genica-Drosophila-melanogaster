from __future__ import annotations

import csv
import io
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from ..models.schemas import ImageDescriptor, SegmentationConfig
from ..processing.algorithm import process_arrays, recompute_nucleus, validate_polygon
from ..processing.image_io import ImageInfo, decode_image, mask_png, preview_png, safe_filename
from ..repositories.sqlite import SQLiteRepository


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    job_id: str
    session_id: str
    status: str = "queued"
    progress: int = 0
    message: str = "Aguardando processamento"
    error: str | None = None


@dataclass
class SessionState:
    session_id: str
    job_id: str
    config: SegmentationConfig
    warnings: list[str]
    descriptors: list[ImageDescriptor]
    nucleus_image: np.ndarray | None = None
    protein_image: np.ndarray | None = None
    labels: np.ndarray | None = None
    mask: np.ndarray | None = None
    nuclei: list[dict[str, Any]] = field(default_factory=list)
    aggregate: dict[str, Any] = field(default_factory=dict)
    revision: int = 0
    status: str = "queued"
    input_files: dict[str, str] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    redo_stack: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


class SessionManager:
    def __init__(self, data_dir: Path, repository: SQLiteRepository | None = None) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.repository = repository or SQLiteRepository(data_dir / "analysis.sqlite3")
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="nuclei-worker")
        self.sessions: dict[str, SessionState] = {}
        self.jobs: dict[str, Job] = {}
        self.events: dict[str, list[dict[str, Any]]] = {}
        self.lock = threading.RLock()

    def create_session(self, nucleus_data: bytes, nucleus_name: str, protein_data: bytes, protein_name: str, config: SegmentationConfig) -> SessionState:
        nucleus_name = safe_filename(nucleus_name, "nuclei.tif")
        protein_name = safe_filename(protein_name, "protein.tif")
        nucleus_image, nucleus_info = decode_image(nucleus_data, nucleus_name)
        protein_image, protein_info = decode_image(protein_data, protein_name)
        if nucleus_info.width != protein_info.width or nucleus_info.height != protein_info.height:
            raise ValueError("As imagens devem ter as mesmas dimensões")
        if config.nucleus_channel >= nucleus_info.channels or config.protein_channel >= protein_info.channels:
            raise ValueError(f"Canais inválidos: núcleos têm {nucleus_info.channels}, proteína tem {protein_info.channels}")
        if nucleus_name == protein_name:
            raise ValueError("Os nomes dos arquivos devem ser diferentes")
        warnings: list[str] = []
        if config.input_mode.value == "derived" or nucleus_info.derived or protein_info.derived:
            warnings.append("A entrada contém nomes compatíveis com resultados derivados; as intensidades podem incluir overlays e não representam necessariamente os TIFFs brutos.")
        if config.input_mode.value == "auto" and not (nucleus_info.derived or protein_info.derived):
            warnings.append("Validação biológica da segmentação não substitui uma máscara anotada manualmente.")
        session_id, job_id = uuid.uuid4().hex, uuid.uuid4().hex
        directory = self.data_dir / session_id
        directory.mkdir(parents=True, exist_ok=False)
        nucleus_path = directory / nucleus_name
        protein_path = directory / protein_name
        nucleus_path.write_bytes(nucleus_data)
        protein_path.write_bytes(protein_data)
        state = SessionState(
            session_id=session_id,
            job_id=job_id,
            config=config,
            warnings=warnings,
            descriptors=[
                ImageDescriptor(name=nucleus_name, role="nucleus", width=nucleus_info.width, height=nucleus_info.height, channels=nucleus_info.channels, dtype=nucleus_info.dtype, derived=nucleus_info.derived),
                ImageDescriptor(name=protein_name, role="protein", width=protein_info.width, height=protein_info.height, channels=protein_info.channels, dtype=protein_info.dtype, derived=protein_info.derived),
            ],
            input_files={"nucleus": nucleus_name, "protein": protein_name},
        )
        job = Job(job_id, session_id)
        with self.lock:
            self.sessions[session_id] = state
            self.jobs[job_id] = job
            self.events[session_id] = []
        self.repository.save_session(session_id, job_id, 0, "queued", model_dump(config), {"warnings": warnings, "images": [model_dump(item) for item in state.descriptors]}, utc_now())
        self._emit(session_id, job)
        self.executor.submit(self._run_job, state, job, nucleus_image, protein_image)
        return state

    def _run_job(self, state: SessionState, job: Job, nucleus_image: np.ndarray, protein_image: np.ndarray) -> None:
        try:
            job.status, job.progress, job.message = "running", 15, "Validando canais e segmentando"
            self._emit(state.session_id, job)
            result = process_arrays(nucleus_image, protein_image, state.config)
            with state.lock:
                state.nucleus_image, state.protein_image = nucleus_image, protein_image
                state.labels, state.mask = result["labels"], result["mask"]
                state.nuclei, state.aggregate = result["nuclei"], aggregate(result["nuclei"])
                state.status = "ready"
            job.status, job.progress, job.message = "completed", 100, "Processamento concluído"
            self._persist(state)
            self._emit(state.session_id, job)
        except Exception as error:  # pragma: no cover - caminho exercitado por endpoint
            state.status = "error"
            job.status, job.progress, job.message, job.error = "error", 100, "Falha no processamento", str(error)
            self._persist(state)
            self._emit(state.session_id, job)

    def _emit(self, session_id: str, job: Job) -> None:
        with self.lock:
            self.events.setdefault(session_id, []).append({"event": "job", "data": job_payload(job)})

    def events_after(self, session_id: str, cursor: int) -> tuple[int, list[dict[str, Any]]]:
        with self.lock:
            events = self.events.get(session_id, [])[cursor:]
            return cursor + len(events), events

    def get(self, session_id: str) -> SessionState:
        state = self.sessions.get(session_id)
        if state is None:
            raise KeyError(session_id)
        return state

    def job(self, job_id: str) -> Job:
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def apply_edit(self, session_id: str, request: Any) -> dict[str, Any]:
        state = self.get(session_id)
        with state.lock:
            self._check_revision(state, request.base_revision)
            before = self._snapshot(state)
            affected = request.nucleus_ids or ([request.nucleus_id] if request.nucleus_id else [])
            by_id = {item["nucleus_id"]: item for item in state.nuclei}
            if request.operation == "edit_contour":
                if len(affected) != 1 or request.polygon is None:
                    raise ValueError("edit_contour exige nucleus_id e polygon")
                if affected[0] not in by_id or state.labels is None or state.nucleus_image is None or state.protein_image is None:
                    raise KeyError("Núcleo não encontrado")
                validate_polygon(request.polygon, state.labels.shape[1], state.labels.shape[0])
                by_id[affected[0]] = recompute_nucleus(by_id[affected[0]], state.labels, state.nucleus_image.astype(np.float32), state.protein_image.astype(np.float32), state.config, request.polygon)
            else:
                if not affected:
                    raise ValueError("Informe pelo menos um nucleus_id")
                for nucleus_id in affected:
                    if nucleus_id not in by_id:
                        raise KeyError(f"Núcleo não encontrado: {nucleus_id}")
                    if request.operation == "hide" and by_id[nucleus_id]["state"] != "excluded":
                        by_id[nucleus_id]["state"] = "hidden"
                    elif request.operation == "exclude":
                        by_id[nucleus_id]["state"] = "excluded"
                    elif request.operation == "restore":
                        by_id[nucleus_id]["state"] = "active"
            state.nuclei = [by_id[item["nucleus_id"]] for item in state.nuclei]
            state.aggregate = aggregate(state.nuclei)
            state.revision += 1
            state.history.append(before)
            state.redo_stack.clear()
            self.repository.append_history(session_id, state.revision, request.operation, {"nucleus_ids": affected}, utc_now())
            self._persist(state)
            return self.result(session_id)

    def undo(self, session_id: str, revision: int, redo: bool = False) -> dict[str, Any]:
        state = self.get(session_id)
        with state.lock:
            self._check_revision(state, revision)
            stack = state.redo_stack if redo else state.history
            if not stack:
                raise ValueError("Não há edição para refazer" if redo else "Não há edição para desfazer")
            current = self._snapshot(state)
            target = stack.pop()
            (state.history if redo else state.redo_stack).append(current)
            self._restore_snapshot(state, target)
            state.revision += 1
            self._persist(state)
            return self.result(session_id)

    def reprocess(self, session_id: str, revision: int, config: SegmentationConfig | None = None) -> Job:
        state = self.get(session_id)
        with state.lock:
            self._check_revision(state, revision)
            if state.nucleus_image is None or state.protein_image is None:
                raise ValueError("A sessão ainda não terminou o processamento inicial")
            if config is not None:
                state.config = config
            state.status = "queued"
            state.revision += 1
            state.history.clear(); state.redo_stack.clear()
            job_id = uuid.uuid4().hex
            job = Job(job_id, session_id)
            state.job_id = job_id
            with self.lock:
                self.jobs[job_id] = job
            self._persist(state)
            self.executor.submit(self._run_job, state, job, state.nucleus_image, state.protein_image)
            return job

    def result(self, session_id: str) -> dict[str, Any]:
        state = self.get(session_id)
        with state.lock:
            return {"session_id": state.session_id, "revision": state.revision, "status": state.status, "config": model_dump(state.config), "warnings": state.warnings, "shape": self._shape(state), "nuclei": state.nuclei, "aggregate": state.aggregate, "job_id": state.job_id}

    def export_csv(self, session_id: str) -> bytes:
        result = self.result(session_id)
        output = io.StringIO(); rows = result["nuclei"]
        fields = sorted({key for row in rows for key in row if key != "polygon"})
        writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader()
        for row in rows: writer.writerow({key: value for key, value in row.items() if key in fields})
        return output.getvalue().encode("utf-8-sig")

    def export_json(self, session_id: str) -> bytes:
        state = self.get(session_id)
        payload = {**self.result(session_id), "history": state.history}
        return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    def image_bytes(self, session_id: str, kind: str) -> bytes:
        state = self.get(session_id)
        with state.lock:
            if kind == "nucleus" and state.nucleus_image is not None:
                return preview_png(state.nucleus_image, state.config.nucleus_channel)
            if kind == "protein" and state.protein_image is not None:
                return preview_png(state.protein_image, state.config.protein_channel)
            if kind == "mask" and state.labels is not None:
                return mask_png(state.labels)
        raise ValueError("Imagem ainda não disponível")

    def _check_revision(self, state: SessionState, base_revision: int) -> None:
        if base_revision != state.revision:
            raise RevisionConflict(state.revision, self.result(state.session_id))

    def _snapshot(self, state: SessionState) -> dict[str, Any]:
        return {"nuclei": json.loads(json.dumps(state.nuclei)), "config": model_dump(state.config), "revision": state.revision}

    def _restore_snapshot(self, state: SessionState, snapshot: dict[str, Any]) -> None:
        state.nuclei = snapshot["nuclei"]
        state.config = SegmentationConfig(**snapshot["config"])
        state.aggregate = aggregate(state.nuclei)

    def _shape(self, state: SessionState) -> dict[str, int] | None:
        return {"width": int(state.labels.shape[1]), "height": int(state.labels.shape[0])} if state.labels is not None else None

    def _persist(self, state: SessionState) -> None:
        self.repository.update_session(state.session_id, state.revision, state.status, model_dump(state.config), {"warnings": state.warnings, "images": [model_dump(item) for item in state.descriptors]}, utc_now())


class RevisionConflict(Exception):
    def __init__(self, current_revision: int, result: dict[str, Any]) -> None:
        super().__init__("A revisão da sessão mudou")
        self.current_revision, self.result = current_revision, result


def model_dump(model: Any) -> dict[str, Any]:
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def aggregate(nuclei: list[dict[str, Any]]) -> dict[str, Any]:
    from ..processing.metrics import aggregate_metrics
    return aggregate_metrics(nuclei)


def job_payload(job: Job) -> dict[str, Any]:
    return {"job_id": job.job_id, "session_id": job.session_id, "status": job.status, "progress": job.progress, "message": job.message, "error": job.error}
