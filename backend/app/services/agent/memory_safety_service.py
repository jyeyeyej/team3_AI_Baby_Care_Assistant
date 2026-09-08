"""Conservative allowlist for durable, non-sensitive conversation preferences."""

import re

SENSITIVE = re.compile(r"(api[_ -]?key|password|비밀번호|카드번호|주민등록|전화번호|주소)", re.I)
PREFERENCE = re.compile(r"(짧게|간단히|자세히|단위|말투|답변)")

def extract_safe_memory(message: str) -> tuple[str, list[str]] | None:
    if SENSITIVE.search(message) or not PREFERENCE.search(message):
        return None
    if len(message) > 300:
        return None
    return message.strip(), ["answer_preference"]
