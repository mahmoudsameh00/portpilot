"""Uploads in a conversation (plan §3.3; ADR-042 – ADR-044): the existing validator, layered screening and local
embedding (`SessionStore.add_upload`), behind the conversation's owner check. `def` routes: the reader runs in a child
process and bge-m3 embeds on the CPU (≈ 3–4 s a small PDF), so FastAPI's threadpool carries them, never the event loop.

An upload holds its conversation busy (a question meanwhile → 409, and back), so a search never reads a session that
is being changed. A refused upload is a 422 problem whose `upload` member lists the reasons (codes + where), never the
document's text.
"""
from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile

from pipelines.api import audit
from pipelines.api.auth import Signed
from pipelines.api.errors import ApiError, request_id
from pipelines.api.routers.ask import conversation_for
from pipelines.api.schemas import PromotionIn, PromotionOut, Reason, UploadOut, UploadSummary
from pipelines.lib import session_store

router = APIRouter(tags=["uploads"])


def _reasons(items) -> list[Reason]:
    return [Reason(code=r.code, where=r.where, message=r.message) for r in items]


def _report(rep) -> UploadOut:
    doc = rep.document or {}
    return UploadOut(accepted=rep.accepted, filename=rep.filename, document_id=doc.get("document_id"),
                     document_code=doc.get("document_code"), title=doc.get("title"), chunks=len(rep.chunks),
                     reasons=_reasons(rep.reasons), removed=_reasons(rep.removed), notes=_reasons(rep.notes),
                     message=rep.message())


@router.post("/conversations/{conversation_id}/uploads", response_model=UploadOut, status_code=201)
def upload(conversation_id: str, file: Annotated[UploadFile, File()], p: Signed, request: Request) -> UploadOut:
    conversation_for(conversation_id, p, write=True)
    data, name = file.file.read(), file.filename or "upload"
    sessions = request.app.state.uploads
    with request.app.state.runner.conversation(conversation_id):
        s = sessions.get(conversation_id, p.employee_id, create=True)
        rep = sessions.store.add_upload(s, data, name, p.user)
    out = _report(rep)
    audit.record(employee_id=p.employee_id, resource_type="upload", resource_id=out.document_id or name,
                 action="upload", decision="allowed" if rep.accepted else "denied", request_id=request_id(request),
                 detail={"conversation_id": conversation_id, "codes": rep.codes(), "removed": len(rep.removed),
                         "chunks": out.chunks})
    if not rep.accepted:
        raise ApiError(422, f"'{name}' was not accepted", slug="upload_refused",
                       extra={"upload": out.model_dump(mode="json")})
    return out


@router.get("/conversations/{conversation_id}/uploads", response_model=list[UploadSummary])
def list_uploads(conversation_id: str, p: Signed, request: Request) -> list[UploadSummary]:
    conv = conversation_for(conversation_id, p, write=False)
    s = request.app.state.uploads.get(conversation_id, conv["employee_id"], create=False)
    if s is None:
        return []
    return [UploadSummary(document_id=d, document_code=u.document["document_code"], title=u.document["title"],
                          filename=u.filename, chunks=len(u.rows), removed=len(u.removed)) for d, u in s.uploads.items()]


@router.delete("/conversations/{conversation_id}/uploads/{document_id}", status_code=204)
def remove_upload(conversation_id: str, document_id: str, p: Signed, request: Request) -> None:
    conversation_for(conversation_id, p, write=True)
    sessions = request.app.state.uploads
    with request.app.state.runner.conversation(conversation_id):
        s = sessions.get(conversation_id, p.employee_id, create=False)
        if s is None or not sessions.store.remove_upload(s, document_id):
            raise ApiError(404, "no such upload in this conversation", slug="not_found")


@router.post("/conversations/{conversation_id}/uploads/{document_id}/promotion", status_code=202,
             response_model=PromotionOut)
def promote(conversation_id: str, document_id: str, body: PromotionIn, p: Signed, request: Request) -> dict:
    """A manager asks for their own department's upload to join the corpus (ADR-044): the file is kept for the owner's
    offline review; nothing is promoted here."""
    conversation_for(conversation_id, p, write=True)
    if p.user.role not in session_store.PROMOTING_ROLES:
        raise ApiError(403, "only a manager can ask to add a document to the corpus", slug="not_allowed")
    sessions = request.app.state.uploads
    s = sessions.get(conversation_id, p.employee_id, create=False)
    if s is None or document_id not in s.uploads:
        raise ApiError(404, "no such upload in this conversation", slug="not_found")
    out = sessions.store.request_promotion(s, document_id, p.user, note=body.note)
    audit.record(employee_id=p.employee_id, resource_type="upload", resource_id=document_id, action="promote",
                 decision="allowed" if out["accepted"] else "denied", request_id=request_id(request),
                 detail={"request_id": out.get("request_id"), "problems": len(out.get("problems", []))})
    if not out["accepted"]:
        raise ApiError(422, "the promotion request was refused", slug="promotion_refused",
                       extra={"problems": out["problems"]})
    return {"request_id": out["request_id"], "status": "requested"}       # the folder stays on the server
