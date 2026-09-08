"""Backend-wide values that form part of the frontend/API contract."""

CHAT_RESPONSE_TYPES = frozenset({
    "text", "options", "record_confirmation", "hospital_list", "diaper_analysis",
    "stt_record_approval", "speech_transcription", "out_of_scope",
    "unsupported_feature", "clarification_required", "policy_blocked", "error",
})
CARE_EVENT_TYPES = frozenset({"feeding", "sleep", "diaper", "growth"})
CARE_INPUT_SOURCES = frozenset({"text", "ui", "stt"})
DEFAULT_FEEDING_INTERVAL_MINUTES = 180
SESSION_TTL_SECONDS = 24 * 60 * 60
TRACE_TTL_SECONDS = 24 * 60 * 60
