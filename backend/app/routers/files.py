import os
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from jose import JWTError

from app.auth.file_tokens import decode_file_access_token
from app.config import get_settings

router = APIRouter(tags=["files"])


def _resolved_upload_path(upload_dir: str, rel: str) -> str:
    rel = rel.replace("\\", "/").strip()
    if ".." in rel or rel.startswith("/"):
        raise HTTPException(400, detail="Invalid path")
    if rel.startswith("uploads/"):
        rel = rel[len("uploads/") :]
    base = os.path.abspath(upload_dir)
    full = os.path.abspath(os.path.join(base, rel))
    if not full.startswith(base + os.sep) and full != base:
        raise HTTPException(400, detail="Invalid path")
    return full


@router.get("/files/access")
async def access_file(token: Annotated[str, Query(..., min_length=10)]):
    """Redeem signed URL (expires quickly). JWT `sub` = stored file path e.g. uploads/abc.jpg"""
    try:
        payload = decode_file_access_token(token)
    except JWTError:
        raise HTTPException(401, detail="Invalid or expired token")
    rel = payload.get("sub")
    if not rel or not isinstance(rel, str):
        raise HTTPException(400, detail="Invalid path")
    settings = get_settings()
    try:
        full = _resolved_upload_path(settings.upload_dir, rel)
    except HTTPException:
        raise
    if not os.path.isfile(full):
        raise HTTPException(404, detail="File not found")
    return FileResponse(full)
