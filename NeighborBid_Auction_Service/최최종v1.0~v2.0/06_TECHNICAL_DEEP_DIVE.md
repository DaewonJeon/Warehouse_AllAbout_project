# [Backend] Django Channels와 Redis를 활용한 실시간 경매 시스템 심층 분석

> 이 문서는 A1_NeighborBid_Auction 프로젝트의 **기술적 심층 분석**을 다룹니다. Django Channels의 동작 원리, Redis Channel Layer 설정, 그리고 동기-비동기 코드 간의 통합 방법을 상세히 설명합니다.

---

## 1. 기술 스택 상세

### 1.1 핵심 기술 선택 이유

| 기술 | 선택 이유 | 대안 비교 |
|---|---|---|
| **Django** | 풍부한 ORM, Admin, 인증 시스템 내장 | FastAPI (경량, 비동기 우선) |
| **Django Channels** | Django와 자연스러운 통합, WebSocket 지원 | Socket.IO (별도 서버 필요) |
| **Redis** | 초고속 인메모리, Pub/Sub 지원 | RabbitMQ (더 복잡한 설정) |
| **SQLite3** | 개발 단계 편의성, 설정 불필요 | PostgreSQL (프로덕션 계획) |
| **Daphne** | Django Channels 공식 ASGI 서버 | Uvicorn (Starlette 기반) |

### 1.2 Django 설정 (settings.py)

```python
# config/settings.py

INSTALLED_APPS = [
    'daphne',        # 최상단에 위치해야 ASGI 서버로 동작
    'channels',      # Django Channels
    # ... 기본 앱들 ...
    'users',
    'wallet',
    'auctions',
    'common',
]

# ASGI 애플리케이션 지정
ASGI_APPLICATION = 'config.asgi.application'

# Channel Layer 설정 (Redis 연결)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # Docker Compose에서 서비스 이름으로 접근
            "hosts": [("redis", 6379)],
        },
    },
}
```

---

## 2. ASGI vs WSGI: 프로토콜 이해

### 2.1 WSGI의 한계

전통적인 Django는 WSGI(Web Server Gateway Interface) 기반입니다.

```
[WSGI 동작 방식]
Request → 처리 → Response (연결 종료)
    │
    └─ 요청 1개 = 처리 1회 = 응답 1개
       연결 유지 불가능 🔺
```

**문제:** WebSocket은 연결을 유지하면서 양방향 통신이 필요한데, WSGI는 이를 지원하지 않음.

### 2.2 ASGI의 등장

ASGI(Asynchronous Server Gateway Interface)는 비동기 처리와 장기 연결을 지원합니다.

```
[ASGI 동작 방식]
                    ┌─ HTTP 요청 처리
Connection ─────────┼─ WebSocket 연결 유지
                    └─ 백그라운드 태스크

    │
    └─ 하나의 연결에서 다중 메시지 송수신 가능 🔹
```

### 2.3 ASGI 애플리케이션 구조

```python
# config/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from auctions.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = ProtocolTypeRouter({
    # HTTP 요청 → Django의 기본 처리
    "http": get_asgi_application(),
    
    # WebSocket 요청 → Channels 라우팅
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

**ProtocolTypeRouter:** 프로토콜(HTTP/WebSocket)에 따라 처리기를 분기

---

## 3. Django Channels 심층 분석

### 3.1 Consumer의 역할

Consumer는 WebSocket 연결을 처리하는 클래스로, Django의 View에 해당합니다.

```python
# auctions/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .services import place_bid

class AuctionConsumer(AsyncWebsocketConsumer):
    """
    각 WebSocket 연결마다 하나의 Consumer 인스턴스가 생성됨
    """
    
    async def connect(self):
        """
        WebSocket 연결 시 호출
        - URL에서 auction_id 추출
        - 해당 경매 그룹에 참여
        """
        self.auction_id = self.scope['url_route']['kwargs']['auction_id']
        self.room_group_name = f'auction_{self.auction_id}'
        
        # Redis Channel Layer를 통해 그룹 참여
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name  # 이 소켓의 고유 식별자
        )
        
        await self.accept()  # 연결 수락

    async def disconnect(self, close_code):
        """
        연결 종료 시 호출
        - 그룹에서 제거하여 메모리 누수 방지
        """
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        클라이언트로부터 메시지 수신 시 호출
        """
        data = json.loads(text_data)
        action = data.get('action')
        
        if action == 'bid':
            amount = int(data['amount'])
            user = self.scope['user']  # AuthMiddlewareStack이 제공
            
            if not user.is_authenticated:
                await self.send(text_data=json.dumps({
                    'error': '로그인이 필요합니다.'
                }))
                return
            
            # DB 작업은 동기 → 비동기로 래핑
            result = await self.save_bid(self.auction_id, user, amount)
            
            if "성공" in result:
                # 그룹 전체에 브로드캐스트
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'auction_update',  # 핸들러 메서드 이름
                        'amount': amount,
                        'bidder': user.username,
                        'msg': result
                    }
                )
            else:
                # 에러는 본인에게만
                await self.send(text_data=json.dumps({'error': result}))

    async def auction_update(self, event):
        """
        group_send의 'type': 'auction_update'가 호출하는 핸들러
        - 언더스코어(_)를 점(.)으로 변환하여 메서드 매칭
        """
        await self.send(text_data=json.dumps({
            'type': 'update',
            'amount': event['amount'],
            'bidder': event['bidder'],
            'msg': event['msg']
        }))

    async def auction_end_notification(self, event):
        """즉시 구매 완료 시 호출되는 핸들러"""
        await self.send(text_data=json.dumps({
            'type': 'sold_out',
            'amount': event['amount'],
            'bidder': event['bidder'],
            'msg': event['msg']
        }))

    @database_sync_to_async
    def save_bid(self, auction_id, user, amount):
        """
        동기 함수(place_bid)를 비동기로 래핑
        - 스레드 풀에서 실행되어 이벤트 루프 차단 방지
        """
        try:
            return place_bid(auction_id, user, amount)
        except ValueError as e:
            return str(e)
```

### 3.2 WebSocket URL 라우팅

```python
# auctions/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # ws://localhost:8000/ws/auction/1/
    re_path(r'ws/auction/(?P<auction_id>\d+)/$', consumers.AuctionConsumer.as_asgi()),
]
```

### 3.3 동기-비동기 경계 처리

Django의 ORM은 **동기적**으로 동작하지만, Channels Consumer는 **비동기**입니다.

```python
# 🔺 잘못된 방법: 비동기 함수에서 직접 ORM 호출
async def receive(self, text_data):
    auction = Auction.objects.get(id=1)  # SynchronousOnlyOperation 에러!

# 🔹 올바른 방법 1: database_sync_to_async 데코레이터
from channels.db import database_sync_to_async

@database_sync_to_async
def get_auction(auction_id):
    return Auction.objects.get(id=auction_id)

async def receive(self, text_data):
    auction = await get_auction(1)  # OK

# 🔹 올바른 방법 2: sync_to_async 래퍼 (일회성)
from asgiref.sync import sync_to_async

async def receive(self, text_data):
    auction = await sync_to_async(Auction.objects.get)(id=1)  # OK
```

**동작 원리:**
- `database_sync_to_async`는 동기 코드를 **스레드 풀**에서 실행
- 이벤트 루프가 차단되지 않고 다른 요청 처리 가능

---

## 4. Redis Channel Layer 상세

### 4.1 Channel Layer의 역할

```
[단일 프로세스 환경]
Consumer A ─────────────────────── Consumer B
              (같은 메모리 공유)
              직접 통신 가능 🔹

[멀티 프로세스/서버 환경]
Server 1                           Server 2
├─ Consumer A                      ├─ Consumer C
└─ Consumer B                      └─ Consumer D
    │                                  │
    └────────── Redis ─────────────────┘
              (중앙 메시지 브로커)
              Pub/Sub으로 통신 🔹
```

### 4.2 Group 동작 방식

```python
# 그룹 추가 (Subscribe)
await self.channel_layer.group_add(
    "auction_1",           # 그룹 이름
    self.channel_name      # 이 Consumer의 고유 채널
)
# Redis 내부: SADD auction_1 {channel_name}

# 그룹 메시지 전송 (Publish)
await self.channel_layer.group_send(
    "auction_1",
    {"type": "auction_update", "amount": 15000}
)
# Redis 내부: 그룹 내 모든 채널에 메시지 전파

# 그룹 제거 (Unsubscribe)
await self.channel_layer.group_discard(
    "auction_1",
    self.channel_name
)
# Redis 내부: SREM auction_1 {channel_name}
```

### 4.3 Redis 설정 (docker-compose.yml)

```yaml
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    # 영속성보다 성능 우선 (인메모리 모드)
    # 경매 세션 데이터는 휘발되어도 됨 (DB에 저장됨)
```

---

## 5. 동기 함수에서 비동기 Channel Layer 호출

### 5.1 문제 상황

`services.py`의 `buy_now` 함수는 **동기 함수**입니다.  
하지만 WebSocket 알림을 보내려면 **비동기** Channel Layer를 호출해야 합니다.

```python
# 🔺 문제: 동기 함수에서 await 사용 불가
def buy_now(auction_id, buyer):
    # ... 구매 로직 ...
    
    await channel_layer.group_send(...)  # SyntaxError!
```

### 5.2 해결: async_to_sync 래퍼

```python
# auctions/services.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def buy_now(auction_id, buyer):
    def send_notification():
        channel_layer = get_channel_layer()
        
        # async_to_sync: 비동기 함수를 동기적으로 호출
        async_to_sync(channel_layer.group_send)(
            f'auction_{auction_id}',
            {
                'type': 'auction_end_notification',
                'bidder': buyer.username,
                'amount': instant_price_val,
                'msg': f" {buyer.username}님이 즉시 구매했습니다!"
            }
        )

    with transaction.atomic():
        # ... 구매 로직 ...
        
        # 트랜잭션 성공 시에만 알림 전송
        transaction.on_commit(send_notification)
    
    return "구매 완료"
```

**동작 원리:**
1. `async_to_sync`는 새 이벤트 루프를 생성
2. 비동기 코루틴을 해당 루프에서 실행
3. 결과가 반환될 때까지 동기적으로 대기

---

## 6. 데이터 흐름 전체 요약

### 6.1 HTTP 입찰 흐름 (동네 경매)

```
┌─────────────────────────────────────────────────────────────┐
│  1. POST /auction/1/                                        │
│     └─ views.auction_detail()                               │
│         └─ services.place_bid()                             │
│             └─ transaction.atomic()                         │
│                 ├─ select_for_update (Row Lock)             │
│                 ├─ Wallet 업데이트                           │
│                 ├─ Bid 생성                                  │
│                 └─ Auction.current_price 갱신               │
│                                                             │
│  2. Response: 302 Redirect                                  │
│     └─ messages.success("입찰 성공!")                       │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 WebSocket 입찰 흐름 (전국 실시간 경매)

```
┌─────────────────────────────────────────────────────────────┐
│  1. WS Message: {"action": "bid", "amount": 15000}          │
│     └─ AuctionConsumer.receive()                            │
│         └─ database_sync_to_async                           │
│             └─ services.place_bid() (스레드 풀에서 실행)     │
│                                                             │
│  2. 성공 시: channel_layer.group_send()                     │
│     └─ Redis Pub/Sub                                        │
│         └─ 그룹 내 모든 Consumer에게 전파                    │
│             └─ AuctionConsumer.auction_update()             │
│                 └─ self.send() → 각 브라우저로 JSON 전송     │
│                                                             │
│  3. 실패 시: self.send({"error": "..."})                    │
│     └─ 요청자에게만 에러 전송                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 성능 고려사항 및 향후 계획

### 7.1 현재 구조의 한계

| 항목 | 현재 상태 | 잠재적 문제 |
|---|---|---|
| DB Lock | `select_for_update` | 고트래픽 시 병목 |
| Channel Layer | 단일 Redis | SPOF (Single Point of Failure) |
| ASGI 서버 | 단일 Daphne | 확장성 제한 |

### 7.2 향후 확장 계획

1. **분산 락 (Distributed Lock)**
   ```python
   # Redis를 이용한 분산 락 (DB Lock 보조)
   from redis import Redis
   from contextlib import contextmanager
   
   @contextmanager
   def distributed_lock(lock_name, timeout=10):
       redis = Redis()
       lock = redis.lock(lock_name, timeout=timeout)
       try:
           lock.acquire()
           yield
       finally:
           lock.release()
   ```

2. **Redis Cluster**
   - 고가용성을 위한 Redis Sentinel 또는 Cluster 구성
   
3. **ASGI 서버 Scale-out**
   - 다중 Daphne 인스턴스 + Nginx 로드밸런싱

---

## 8. 결론

Django Channels와 Redis를 활용한 실시간 경매 시스템은 **동기와 비동기의 경계**를 잘 이해하고 처리해야 합니다.

| 핵심 포인트 | 설명 |
|---|---|
| **ASGI** | HTTP와 WebSocket을 단일 애플리케이션에서 처리 |
| **Consumer** | WebSocket 연결의 생명주기 관리 |
| **Channel Layer** | 프로세스/서버 간 메시지 브로드캐스트 |
| **sync/async 변환** | `database_sync_to_async`, `async_to_sync` 활용 |
| **트랜잭션 훅** | `on_commit`으로 DB 커밋 후 알림 전송 |

> **작성자:** A1_NeighborBid_Auction 백엔드 개발팀  
> **관련 문서:** [02_CORE_LOGIC_ANALYSIS.md](02_CORE_LOGIC_ANALYSIS.md) | [07_INFRASTRUCTURE_AND_DEPLOYMENT.md](07_INFRASTRUCTURE_AND_DEPLOYMENT.md)