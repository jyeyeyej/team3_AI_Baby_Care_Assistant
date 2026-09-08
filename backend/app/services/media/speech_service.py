"""Speech-to-text boundary with strict file validation and safe errors."""

import io
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from openai import AsyncOpenAI
from app.core.config import OPENAI_API_KEY, STT_MODEL
from app.core.record_policy import ALLOWED_STT_AUDIO_TYPES, ALLOWED_STT_SUFFIXES, MAX_STT_AUDIO_BYTES


async def transcribe_audio(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_STT_SUFFIXES or upload.content_type not in ALLOWED_STT_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="MP3, WAV, M4A, WebM 파일만 지원합니다.")
    raw = await upload.read(MAX_STT_AUDIO_BYTES + 1)
    if len(raw) > MAX_STT_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="음성 파일은 최대 20MB입니다.")
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="음성 인식 서비스 설정이 없습니다.")
    try:
        audio = io.BytesIO(raw)
        audio.name = f"{uuid4()}{suffix}"
        return (await AsyncOpenAI(api_key=OPENAI_API_KEY).audio.transcriptions.create(
            model=STT_MODEL, file=audio
        )).text.strip()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="음성을 텍스트로 변환하지 못했습니다.") from exc
