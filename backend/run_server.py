"""Windows에서 FastAPI 백엔드를 실행하는 진입점입니다.

psycopg의 비동기 연결은 Windows 기본 ProactorEventLoop와 호환되지 않으므로,
uvicorn이 이벤트 루프를 만들기 전에 Selector 정책을 설정해야 합니다.
"""

import asyncio


if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn

    # ``uvicorn.run``은 일부 Windows/Uvicorn 조합에서 Proactor 루프를 다시
    # 생성할 수 있습니다. Selector 루프를 직접 생성해 서버 코루틴을 실행합니다.
    config = uvicorn.Config("app.main:app", host="0.0.0.0", port=8000, loop="none")
    server = uvicorn.Server(config)
    event_loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(event_loop)
    try:
        event_loop.run_until_complete(server.serve())
    finally:
        event_loop.close()
