"""Sign-in and sign-out (plan §3.1, §6). `def`, not `async def`: scrypt and the database calls are blocking, so
FastAPI runs them in its threadpool and the event loop stays free (C9)."""
from fastapi import APIRouter, Request, Response

from pipelines.api import auth
from pipelines.api.errors import request_id
from pipelines.api.routers.me import me_of
from pipelines.api.schemas import LoginIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request) -> TokenOut:
    token, expires, user = auth.sign_in(body.email, body.password, request_id(request))
    return TokenOut(token=token, expires_at=expires, me=me_of(user))


@router.post("/logout", status_code=204)
def logout(request: Request, p: auth.Signed) -> Response:
    auth.sign_out(p, request)
    return Response(status_code=204)
