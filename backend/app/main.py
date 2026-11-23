from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from .models.schemas import EditRequest, ReprocessRequest, RevisionRequest, SegmentationConfig
from .repositories.sqlite import SQLiteRepository
from .services.session_manager import RevisionConflict, SessionManager, job_payload, model_dump


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("NUCLEI_DATA_DIR", str(PROJECT_ROOT / ".nuclei_data")))
manager = SessionManager(DATA_DIR, SQLiteRepository(DATA_DIR / "analysis.sqlite3"))

app = FastAPI(
    title="Nuclei Review API",
    version="0.1.0",
    description="Revisão, edição e quantificação de núcleos e proteínas em imagens científicas.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_state(session_id: str):
    try:
        return manager.get(session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Sessão não encontrada") from error


def session_payload(session_id: str) -> dict:
    state = get_state(session_id)
    job = manager.job(state.job_id)
    return {
        "session_id": state.session_id,
        "job_id": job.job_id,
        "status": state.status,
        "revision": state.revision,
        "config": model_dump(state.config),
        "warnings": state.warnings,
        "images": [model_dump(item) for item in state.descriptors],
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/sessions", status_code=status.HTTP_202_ACCEPTED)
async def create_session(
    nucleus_file: Annotated[UploadFile, File(description="Imagem ou canal dos núcleos")],
    protein_file: Annotated[UploadFile | None, File(description="Imagem/canal da proteína; omita para usar outro canal do mesmo arquivo")]=None,
    config_json: Annotated[str, Form()] = "{}",
):
    try:
        config = SegmentationConfig(**json.loads(config_json))
        nucleus_data = await nucleus_file.read()
        protein_data = await protein_file.read() if protein_file is not None else nucleus_data
        source_name = nucleus_file.filename or "nuclei.tif"
        protein_name = protein_file.filename if protein_file is not None else f"{Path(source_name).stem}_multichannel{Path(source_name).suffix}"
        state = manager.create_session(
            nucleus_data,
            nucleus_file.filename or "nuclei.tif",
            protein_data,
            protein_name or "protein.tif",
            config,
        )
        return session_payload(state.session_id)
    except (ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    return session_payload(session_id)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return job_payload(manager.job(job_id))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Job não encontrado") from error


@app.get("/api/sessions/{session_id}/events")
async def session_events(session_id: str):
    state = get_state(session_id)

    async def stream():
        # Começa depois dos eventos antigos e envia o estado atual do job. Isso
        # evita que uma nova assinatura de reprocessamento consuma o "completed"
        # da execução anterior.
        cursor, _ = manager.events_after(session_id, 10**9)
        current = job_payload(manager.job(state.job_id))
        yield f"event: job\ndata: {json.dumps(current, ensure_ascii=False)}\n\n"
        if current["status"] in {"completed", "error"}:
            return
        idle_rounds = 0
        while idle_rounds < 900:
            cursor, events = manager.events_after(session_id, cursor)
            if events:
                idle_rounds = 0
                for event in events:
                    yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
                    if event["data"]["status"] in {"completed", "error"}:
                        return
            else:
                idle_rounds += 1
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.2)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/sessions/{session_id}/result")
def get_result(session_id: str):
    get_state(session_id)
    return manager.result(session_id)


@app.get("/api/sessions/{session_id}/nuclei/{nucleus_id}")
def get_nucleus(session_id: str, nucleus_id: int):
    state = get_state(session_id)
    for nucleus in state.nuclei:
        if nucleus["nucleus_id"] == nucleus_id:
            return nucleus
    raise HTTPException(status_code=404, detail="Núcleo não encontrado")


@app.post("/api/sessions/{session_id}/edits")
def apply_edit(session_id: str, request: EditRequest):
    get_state(session_id)
    try:
        return manager.apply_edit(session_id, request)
    except RevisionConflict as error:
        raise HTTPException(
            status_code=409,
            detail={"message": str(error), "current_revision": error.current_revision, "result": error.result},
        ) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/sessions/{session_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
def reprocess(session_id: str, request: ReprocessRequest):
    get_state(session_id)
    try:
        job = manager.reprocess(session_id, request.base_revision, request.config)
        return job_payload(job)
    except RevisionConflict as error:
        raise HTTPException(
            status_code=409,
            detail={"message": str(error), "current_revision": error.current_revision, "result": error.result},
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/sessions/{session_id}/undo")
def undo(session_id: str, request: RevisionRequest):
    get_state(session_id)
    try:
        return manager.undo(session_id, request.base_revision)
    except RevisionConflict as error:
        raise HTTPException(
            status_code=409,
            detail={"message": str(error), "current_revision": error.current_revision, "result": error.result},
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/sessions/{session_id}/redo")
def redo(session_id: str, request: RevisionRequest):
    get_state(session_id)
    try:
        return manager.undo(session_id, request.base_revision, redo=True)
    except RevisionConflict as error:
        raise HTTPException(
            status_code=409,
            detail={"message": str(error), "current_revision": error.current_revision, "result": error.result},
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/api/sessions/{session_id}/export.csv")
def export_csv(session_id: str):
    get_state(session_id)
    return Response(
        manager.export_csv(session_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="nuclei-{session_id}.csv"'},
    )


@app.get("/api/sessions/{session_id}/export.json")
def export_json(session_id: str):
    get_state(session_id)
    return Response(
        manager.export_json(session_id),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="nuclei-{session_id}.json"'},
    )


@app.get("/api/sessions/{session_id}/images/{kind}.png")
def session_image(session_id: str, kind: str):
    get_state(session_id)
    if kind not in {"nucleus", "protein", "mask"}:
        raise HTTPException(status_code=404, detail="Camada desconhecida")
    try:
        return Response(manager.image_bytes(session_id, kind), media_type="image/png")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
