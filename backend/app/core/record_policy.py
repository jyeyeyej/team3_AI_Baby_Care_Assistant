"""Care-record approval policy."""

RECORD_APPROVAL_POLICY = {"text": False, "ui": False, "stt": True}
STT_APPROVAL_TTL_SECONDS = 600
ALLOWED_STT_AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/webm"}
ALLOWED_STT_SUFFIXES = {".mp3", ".wav", ".m4a", ".webm"}
MAX_STT_AUDIO_BYTES = 20 * 1024 * 1024
