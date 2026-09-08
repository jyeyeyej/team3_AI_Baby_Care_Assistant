from datetime import datetime
from typing import Any, Literal
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import httpx

from schemas.hospital import EmergencyHospital, HospitalToolResponse, PediatricHospital

HospitalKind = Literal["pediatric", "emergency"]

# 국민건강보험공단 의료기관 API의 시·도 코드. 세부 구·군 코드는 API마다
# 달라서 지역명 주소 필터로 처리한다.
SIDO_CODES = {
    "서울특별시": "110000", "부산광역시": "210000", "대구광역시": "220000",
    "인천광역시": "230000", "광주광역시": "240000", "대전광역시": "250000",
    "울산광역시": "260000", "세종특별자치시": "290000", "경기도": "310000",
    "강원특별자치도": "320000", "충청북도": "330000", "충청남도": "340000",
    "전북특별자치도": "350000", "전라남도": "360000", "경상북도": "370000",
    "경상남도": "380000", "제주특별자치도": "390000",
}
CITY_ALIASES = {
    "서울": "서울특별시", "서울시": "서울특별시",
    "부산": "부산광역시", "부산시": "부산광역시",
    "대구": "대구광역시", "대구시": "대구광역시",
    "인천": "인천광역시", "인천시": "인천광역시",
    "광주": "광주광역시", "광주시": "광주광역시",
    "대전": "대전광역시", "대전시": "대전광역시",
    "울산": "울산광역시", "울산시": "울산광역시",
    "세종": "세종특별자치시", "세종시": "세종특별자치시",
    "제주": "제주특별자치도", "제주시": "제주특별자치도",
}
PEDIATRIC_DEPARTMENT_CODE = "11"
PEDIATRIC_BATCH_SIZE = 100
PEDIATRIC_TIMEOUT_SECONDS = 20.0
SEOUL_ONLY_DISTRICTS = frozenset({
    # 강서구·중구처럼 여러 시·도에 있는 이름은 사용자의 시·도 입력이 필요하다.
    "강남구", "강동구", "강북구", "관악구", "광진구", "구로구", "금천구",
    "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
    "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중랑구",
})


class ExternalApiError(RuntimeError):
    pass


class RateLimitError(ExternalApiError):
    pass


class HospitalService:
    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timezone: str = "Asia/Seoul",
        timeout_seconds: float = 5.0,
        retry_count: int = 1,
        *,
        pediatric_api_url: str = "",
        pediatric_api_key: str = "",
        emergency_api_url: str = "",
        emergency_api_key: str = "",
    ) -> None:
        self.endpoints = {
            "pediatric": (pediatric_api_url or base_url, pediatric_api_key or api_key),
            "emergency": (emergency_api_url or base_url, emergency_api_key or api_key),
        }
        self.timezone = ZoneInfo(timezone)
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count

    async def search(self, kind: HospitalKind, region: str, page: int, limit: int) -> dict[str, Any]:
        base_url, api_key = self.endpoints[kind]
        if not base_url or not api_key:
            raise ExternalApiError("공공데이터 API 설정이 필요합니다.")

        region = self._normalize_region(region)
        provider_limit = max(limit, PEDIATRIC_BATCH_SIZE) if kind == "pediatric" else limit
        params = self._build_params(kind, api_key, region, page, provider_limit)
        payload = await self._request(
            base_url,
            params,
            timeout_seconds=max(self.timeout_seconds, PEDIATRIC_TIMEOUT_SECONDS)
            if kind == "pediatric"
            else self.timeout_seconds,
        )

        raw_items = self._extract_items(payload)
        raw_items = self._filter_region(kind, raw_items, region)
        items = self._normalize_items(kind, raw_items)[:limit]
        notice = (
            "운영시간과 진료 가능 여부는 방문 전 의료기관에 확인해 주세요."
            if kind == "pediatric"
            else "실시간 진료 가능 여부는 의료기관에 확인하고 위급한 경우 119에 연락하세요."
        )
        return HospitalToolResponse(
            region=region,
            data=items,
            checked_at=datetime.now(self.timezone),
            notice=notice,
        ).model_dump(mode="json")

    @staticmethod
    def _build_params(
        kind: HospitalKind, api_key: str, region: str, page: int, limit: int
    ) -> dict[str, Any]:
        """Build the documented, provider-specific request shape."""
        province, district, locality = HospitalService._parse_region(region)
        # 공공데이터포털 키는 .env에 URL 인코딩된 형태로 저장되는 경우가 많다.
        # httpx가 query parameter를 인코딩하므로 먼저 한 번만 원문으로 되돌린다.
        common = {
            "serviceKey": unquote(api_key),
            "pageNo": page,
            "numOfRows": limit,
            "_type": "json",
        }
        if kind == "emergency":
            return {**common, "Q0": province, "Q1": district, "QZ": "A", "ORD": "ADDR"}
        code = SIDO_CODES.get(province)
        return {
            **common,
            "dgsbjtCd": PEDIATRIC_DEPARTMENT_CODE,
            **({"sidoCd": code} if code else {}),
            **({"emdongNm": locality} if locality else {}),
        }

    @staticmethod
    def _normalize_region(region: str) -> str:
        """Normalize city aliases and expand an unambiguous Seoul district prefix."""
        parts = region.split()
        if not parts:
            return ""
        parts[0] = CITY_ALIASES.get(parts[0], parts[0])
        if parts[0] in SEOUL_ONLY_DISTRICTS:
            parts.insert(0, "서울특별시")
        normalized = " ".join(parts)
        return normalized

    @staticmethod
    def _parse_region(region: str) -> tuple[str, str, str]:
        """Parse normalized 시·도 / 구·군 / 읍·면·동 components independently."""
        parts = region.split()
        if not parts:
            return "", "", ""
        province = parts.pop(0) if parts[0] in SIDO_CODES else ""
        if not province:
            # A lone 동·읍·면 is searched through the provider locality filter.
            locality = parts[0] if len(parts) == 1 and parts[0].endswith(("동", "읍", "면")) else ""
            if locality:
                return "", "", locality
            return "", " ".join(parts), ""
        locality = ""
        if parts and parts[-1].endswith(("동", "읍", "면")):
            locality = parts.pop()
        return province, " ".join(parts), locality

    @staticmethod
    def _filter_region(kind: HospitalKind, rows: list[dict[str, Any]], region: str) -> list[dict[str, Any]]:
        """Keep the requested locality after the provider's specialty filter."""
        province, district, locality = HospitalService._parse_region(region)
        filtered: list[dict[str, Any]] = []
        for row in rows:
            address = HospitalService._text(row, "address", "dutyAddr", "addr") or ""
            if ((province and province not in address)
                    or (district and district not in address)
                    or (locality and locality not in address)):
                continue
            filtered.append(row)
        return filtered

    async def _request(
        self, base_url: str, params: dict[str, Any], *, timeout_seconds: float | None = None
    ) -> Any:
        """일시적인 네트워크 오류만 제한적으로 재시도합니다."""
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                # hospInfoServicev2는 실제 제공 주소로 302를 반환한다. 공공 API의
                # 정상 리다이렉트를 따라가야 HTTP 302가 백엔드의 503으로 변환되지 않는다.
                async with httpx.AsyncClient(
                    timeout=timeout_seconds or self.timeout_seconds, follow_redirects=True
                ) as client:
                    response = await client.get(base_url, params=params)
                if response.status_code == 429:
                    raise RateLimitError("공공데이터 API 호출 한도를 초과했습니다.")
                response.raise_for_status()
                payload = response.json()
                self._raise_if_payload_error(payload)
                return payload
            except RateLimitError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < self.retry_count:
                    continue
                break
            except (httpx.HTTPStatusError, ValueError) as exc:
                raise ExternalApiError("공공데이터 API를 호출할 수 없습니다.") from exc

        raise ExternalApiError("공공데이터 API를 호출할 수 없습니다.") from last_error

    @staticmethod
    def _raise_if_payload_error(payload: Any) -> None:
        """공공데이터 API가 HTTP 200과 함께 반환하는 업무 오류를 구분합니다."""
        if not isinstance(payload, dict):
            return
        response = payload.get("response", payload)
        header = response.get("header") if isinstance(response, dict) else None
        if not isinstance(header, dict):
            return
        result_code = header.get("resultCode", header.get("resultCd"))
        if result_code is not None and str(result_code) not in {"00", "0", "NORMAL_SERVICE"}:
            raise ExternalApiError("공공데이터 API가 업무 오류를 반환했습니다.")

    @staticmethod
    def _extract_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        candidates: Any = payload
        for key in ("response", "body", "items"):
            if isinstance(candidates, dict) and key in candidates:
                candidates = candidates[key]
        if isinstance(candidates, dict) and "item" in candidates:
            candidates = candidates["item"]
        if isinstance(candidates, dict):
            candidates = [candidates]
        return [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []

    @staticmethod
    def _normalize_items(kind: HospitalKind, rows: list[dict[str, Any]]) -> list[PediatricHospital | EmergencyHospital]:
        result: list[PediatricHospital | EmergencyHospital] = []
        for row in rows:
            name = HospitalService._text(row, "hospital_name", "dutyName", "yadmNm", "name")
            address = HospitalService._text(row, "address", "dutyAddr", "addr")
            if not name or not address:
                continue
            phone = HospitalService._text(row, "phone", "dutyTel1", "telno", "tel")
            if kind == "pediatric":
                result.append(PediatricHospital(
                    hospital_name=name,
                    address=address,
                    phone=phone,
                    operating_hours=HospitalService._text(row, "operating_hours", "dutyTime", "hours"),
                ))
            else:
                result.append(EmergencyHospital(
                    hospital_name=name,
                    address=address,
                    phone=phone,
                    emergency_level=HospitalService._text(row, "emergency_level", "hvec", "level"),
                ))
        return result

    @staticmethod
    def _text(row: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None
