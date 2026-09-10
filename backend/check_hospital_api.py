"""실행 중인 FastAPI의 인증·병원 검색 전체 경로를 확인합니다."""

import argparse
import json

import requests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    login = requests.post(
        f"{base_url}/api/test-login",
        json={"user_id": "user-001"},
        timeout=10,
    )
    login.raise_for_status()
    session = login.json()["data"]
    response = requests.get(
        f"{base_url}/api/hospitals/search",
        params={"region": "신대방동", "type": "pediatric", "page": 1, "limit": 3},
        headers={
            "X-User-Id": session["user_id"],
            "X-Session-Id": session["session_id"],
        },
        timeout=40,
    )
    print(f"HTTP {response.status_code}")
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    response.raise_for_status()


if __name__ == "__main__":
    main()
