## 일반적인 웹 요청(HTTP)과 실시간 통신 요청(WebSocket)을 구분

`django.setup()`
- 설정(settings), 앱 등록, 모델 등 초기화!!


`from django.core.asgi import get_asgi_application`
- 기본 Django ASGI 애플리케이션 생성기
- 기존 Django의 HTTP 요청 처리 담당

`from channels.routing import ProtocolTypeRouter, URLRouter`

`ProtocolTypeRouter`
- 요청 프로토콜 기준 분기 라우터

`URLRouter`
- WebSocket 전용 URL 라우터
- websocket 요청은 -> 로그인 검사(Auth) -> 라우팅(URLRouter) -> 컨슈머로 전달

`from channels.auth import AuthMiddlewareStack`
- WebSocket 연결 상태에서도 장고연동

```
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # websocket 요청은 -> 로그인 검사(Auth) -> 라우팅(URLRouter) -> 컨슈머로 전달
    "websocket": AuthMiddlewareStack(
        URLRouter(
            auctions.routing.websocket_urlpatterns
        )
    ),
})
```
딕셔너리 구조! 

- key: 프로토콜 이름 (문자열)

- value: 해당 프로토콜을 처리할 ASGI 애플리케이션
