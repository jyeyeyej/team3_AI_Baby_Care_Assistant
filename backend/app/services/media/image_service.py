"""Safe temporary storage for diaper images passed to the Care MCP server."""

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TEMP_DIR = PROJECT_ROOT / "uploads"
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


async def save_diaper_image(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES or upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="JPG, JPEG, PNG 이미지 파일만 지원합니다.")
    content = await upload.read(MAX_IMAGE_BYTES + 1)
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="이미지 파일은 최대 10MB입니다.")
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    path = TEMP_DIR / f"{uuid4()}{suffix}"
    path.write_bytes(content)
    try:
        with Image.open(path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=415, detail="올바른 JPG 또는 PNG 이미지 파일이 아닙니다.") from None
    return path


def delete_diaper_image(path: Path) -> None:
    path.unlink(missing_ok=True)
