from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx

from schemas.hospital import EmergencyHospital, HospitalToolResponse, PediatricHospital

HospitalKind = Literal["pediatric", "emergency"]


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

        params = {
            "serviceKey": api_key,
            "region": region,
            "page": page,
            "limit": limit,
            "type": kind,
            "_type": "json",
        }
        payload = await self._request(base_url, params)

        raw_items = self._extract_items(payload)
        items = self._normalize_items(kind, raw_items)
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

    async def _request(self, base_url: str, params: dict[str, Any]) -> Any:
        """일시적인 네트워크 오류만 제한적으로 재시도합니다."""
        last_error: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
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
            name = HospitalService._text(row, "hospital_name", "dutyName", "name")
            address = HospitalService._text(row, "address", "dutyAddr", "addr")
            if not name or not address:
                continue
            phone = HospitalService._text(row, "phone", "dutyTel1", "tel")
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
