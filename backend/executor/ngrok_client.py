import os

import httpx


async def get_ngrok_public_url() -> str:
    """
    ngrok 대시보드 API로 현재 활성 HTTPS 터널 URL 동적 조회.
    docker-compose 재시작 시 URL이 바뀌므로 항상 호출 시마다 최신값을 가져온다.

    NGROK_API_URL 환경변수로 주소 변경 가능:
      - 로컬 직접 실행 시: http://localhost:4040 (기본값)
      - Docker 컨테이너 내부 실행 시: http://ngrok:4040
    """
    api_url = os.getenv("NGROK_API_URL", "http://localhost:4040")

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{api_url}/api/tunnels")
        response.raise_for_status()
        tunnels = response.json().get("tunnels", [])

    https_tunnels = [t for t in tunnels if t.get("proto") == "https"]
    if not https_tunnels:
        raise RuntimeError(
            "ngrok HTTPS 터널을 찾을 수 없습니다. "
            "docker-compose에 ngrok 서비스가 실행 중인지 확인하세요."
        )

    return https_tunnels[0]["public_url"]
