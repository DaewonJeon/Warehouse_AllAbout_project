# NeighborBid의 심장: 실시간 경매 엔진은 어떻게 돌아가는가

안녕하세요, NeighborBid 코어 개발팀입니다.
오늘은 우리 서비스의 가장 핵심이자, 가장 뜨거운 트래픽을 감당해내는 **'경매 엔진(Auction Engine)'**의 내부 로직을 뜯어보려 합니다.

경매 시스템 개발의 꽃은 단연 **'동시성 제어(Concurrency Control)'**와 **'실시간 통신(Real-time Communication)'**입니다. 수십 명이 동시에 "내가 살래!"를 외칠 때, 서버는 어떻게 0.01초의 순서를 가르고 정확하게 돈을 계산할까요?

---

## 1. 0.01초의 승부: 동시성 제어 (`services.py`)

경매의 비즈니스 로직을 담당하는 `services.py`에서 가장 중요한 함수는 단연 `place_bid`(입찰하기)입니다.

### 문제 상황: Race Condition
만약 A와 B가 동시에 10,000원을 입찰한다면 어떻게 될까요? 적절한 잠금 장치가 없다면, 데이터베이스는 두 요청을 모두 받아들여 데이터 무결성이 깨지는 **경쟁 상태(Race Condition)**가 발생할 수 있습니다.

### 해결책: `select_for_update` & `atomic`
우리는 Django의 트랜잭션 관리 기능을 활용해 이 문제를 해결했습니다.

```python
# services.py (Pseudo-code)

@transaction.atomic
def place_bid(auction_id, user, amount):
    # 1. 경매 정보를 가져올 때 'Row Lock'을 걸어버립니다.
    # 이 트랜잭션이 끝날 때까지 다른 사람은 이 경매 row를 수정할 수 없습니다.
    auction = Auction.objects.select_for_update().get(id=auction_id)

    # 2. 유효성 검사 (이미 누가 더 높게 불렀나?)
    if amount <= auction.current_price:
        raise ValueError("더 높은 금액을 입찰해야 합니다.")

    # 3. 환불 프로세스 (기존 1등에게 돈 돌려주기)
    if auction.highest_bidder:
        refund_to_wallet(auction.highest_bidder)

    # 4. 내 돈 잠그기 (지갑 -> Locked Balance)
    lock_balance(user, amount)

    # 5. 입찰 성공 처리
    auction.current_price = amount
    auction.save()
```
핵심은 `select_for_update()`입니다. 이 코드는 데이터베이스 레벨에서 해당 행(Row)에 Lock을 걸어, "내가 처리하는 동안 아무도 건들지 마!"라고 선언합니다. 덕분에 동시 접속자가 아무리 많아도 데이터 꼬임 없는 무결성을 유지할 수 있죠.

---

## 2. 멈추지 않는 소통: WebSocket 핸들러 (`consumers.py`)

기존의 HTTP 요청(새로고침) 방식은 경매장의 열기를 담아내기엔 너무 느렸습니다. 그래서 우리는 `consumers.py`를 통해 WebSocket 서버를 구축했습니다.

### 연결의 흐름 (Connect -> Receive -> Send)

1.  **입장 (`connect`)**: 사용자가 경매방에 들어오면, `channel_layer.group_add`를 통해 해당 경매 ID 그룹에 사용자를 등록시킵니다. 이제 이 방에 뿌려지는 모든 방송을 듣게 됩니다.
2.  **입찰 (`receive`)**: 사용자가 입찰 버튼을 누르면 웹소켓으로 메시지가 날아옵니다. 여기서 우리는 앞서 만든 동기 함수 `services.place_bid`를 **비동기 환경**에서 안전하게 호출합니다.
3.  **방송 (`group_send`)**: 입찰이 성공하면, 그룹에 속한 **생존자 전원**에게 메시지를 뿌립니다.

```python
async def receive(self, text_data):
    # ... 데이터 파싱 ...
    
    # DB 작업은 동기 함수이므로 database_sync_to_async로 감싸서 실행
    await database_sync_to_async(place_bid)(auction_id, user, amount)

    # "새로운 대장이 나타났다!" 라고 모두에게 방송
    await self.channel_layer.group_send(
        self.room_group_name,
        {
            'type': 'auction_update',
            'price': amount,
            'bidder': user.username
        }
    )
```

이 덕분에 나 외의 다른 사람이 입찰해도, 내 화면의 숫자가 실시간으로 호로록 올라가는 마법 같은 경험(Magic Moment)을 줄 수 있었죠.

---

## 3. One Logic, Two Paths

재미있는 점은, 전국 경매(WebSocket)와 지역 경매(HTTP)가 **동일한 비즈니스 로직**을 공유한다는 것입니다.

*   **HTTP 요청**은 `views.py`를 거쳐 `services.place_bid`를 부르고,
*   **WebSocket 요청**은 `consumers.py`를 거쳐 `services.place_bid`를 부릅니다.

입구는 다르지만, 결국 돈을 다루는 핵심 로직은 **단 하나로 관리(Single Source of Truth)**함으로써 유지보수의 효율성까지 챙겼습니다.

---

NeighborBid의 코드는 단순한 텍스트가 아니라, 사용자의 자산을 지키고 쾌적한 경험을 제공하기 위한 치열한 고민의 산물입니다.
