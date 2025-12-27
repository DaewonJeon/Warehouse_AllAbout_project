# Auction Service Core Logic
## `auctions/services.py`에 구현
경매 시스템의 특성(금융거래, 실시간입찰)을 고려,
- **데이터 무결성(Data Integrity)**
- **동시성 제어(Concurrency Control)**
을 핵심으로 설계했습니다.

---
### 1.  트랜잭션과 동시성 제어 (Transaction & Concurrency)
> **"이중 지불"** 이나 **"동시 입찰로 인한 데이터 불일치"** 이를 방지하기 위해 **Pessimistic Locking(비관적 락)** 전략을 사용하였습니다.

#### `select_for_update()`의 활용 (DB Lock)

##### 핵심 함수
``` python
#auction/services.py
    def place_bid(auction_id, user, amount) : 입찰 수행 함수
    def determine_winner(auction_id) : 경매 종료 시 낙찰자를 확정하고 돈을 이동시키는 함수
    def buy_now(auction_id, buyer) : 즉시 구매 함수 
```
1. `transaction.atomic()` 블록 안에서 실행. 
2. 주요 데이터 조회 시 `select_for_update()`를 사용.

```python
# place_bid 함수 내부
with transaction.atomic():
    auction = Auction.objects.select_for_update().get(id=auction_id)
    # ...
    wallet = Wallet.objects.select_for_update().get(user=user)
```

1.  **Row-Level Lock**: `select_for_update()`가 실행되는 순간, 해당 행(Row)은 트랜잭션이 끝날 때까지 "잠금" 상태
2.  **Race Condition 방지**: 동시에 두 명의 유저가 입찰을 시도하더라도, 먼저 DB에 도달한 트랜잭션이 끝날 때까지 다른 트랜잭션은 대기하게 됩니다. 결과적으로 순차적인 입찰 처리가 보장됩니다.
3.  **데이터 무결성**: 읽는 순간의 데이터가 수정 시점까지 변하지 않음을 보장하므로, 잔액 확인 로직 등이 안전하게 동작합니다.

---

### 2. 돈 흐름과 안전 장치 

> 서비스 레이어는 자금의 이동을 "삭제 후 생성" 방식이 아닌, **명확한 차감 및 이동** 로직으로 구현하여 돈이 증발하거나 복사되는 사고를 방지합니다.

####  입찰 시 돈 흐름 `place_bid` 함수
1.  **Lock & Check**: 내 지갑을 잠그고 잔액 확인
2.  **Refund (이전 입찰자)**: 기존 최고 입찰자가 있다면, 그 사람의 `locked_balance`(묶인 돈)를 `balance`(사용 가능 잔액)로 즉시 환불합니다.
3.  **Locking (현재 입찰자)**: 내 `balance`를 차감하고 `locked_balance`로 이동시킵니다. (돈이 빠져나가는 것이 아니라 "예약" 상태가 됨)
4.  **Update**: 경매 현재가를 갱신합니다.

- 입찰 즉시 실제 출금이 일어나는 것이 아니라 `locked_balance`로 이동시키는 설계
- 경매 실패/유찰 시 즉각적인 환불 처리를 단순화하고 사용자에게 심리적 안정감을 줍니다.

---

### 3.  즉시 구매와 이벤트 처리 `buy_now` 함수

> `buy_now` 로직은 복잡한 다자간 거래(구매자, 판매자, 이전 입찰자)를 한 번의 트랜잭션으로 처리해야 하는 고난도 로직입니다. 특히 **DB 트랜잭션과 외부 시스템(WebSocket) 간의 조율**이 돋보입니다.

####  `transaction.on_commit` 의 활용

```python
# buy_now 함수 마지막 부분
transaction.on_commit(send_sold_out_notification)
```

*   **문제 상황**: 만약 트랜잭션 내부에서 웹소켓 알림을 보냈는데, 그 직후 DB 에러로 롤백된다면? 유저들은 "판매 완료" 알림을 받았지만 실제로는 판매되지 않은 유령 상태가 됩니다.
*   **해결책**: `on_commit` 훅을 사용하여 **"DB에 모든 데이터가 확실히 저장된(Commit) 후"**에만 알림을 발송합니다. 이를 통해 시스템 상태와 사용자 경험의 불일치를 원천 차단했습니다.

---

## 4. 🏆 총평 (Code Review Summary)

이 코드는 단순한 CRUD를 넘어 엔터프라이즈급 금융/커머스 시스템에서 요구하는 안정성을 갖추고 있습니다.

*   **안정성 (Stability)**: ⭐⭐⭐⭐⭐ (모든 자금 이동 경로에 Lock과 Atomic 처리 완비)
*   **가독성 (Readability)**: ⭐⭐⭐⭐ (복잡한 로직임에도 주석과 함수 분리가 명확함)
*   **설계 (Design)**: ⭐⭐⭐⭐⭐ (재사용 가능한 서비스 패턴 적용 및 이벤트 처리의 정교함)

**결론**: 이 서비스 모듈은 트래픽이 몰리는 "핫딜"이나 "마감 임박 경매" 상황에서도 데이터가 꼬이지 않고 정확하게 동작하도록 설계된 **견고한 백엔드 로직의 표본**입니다.
