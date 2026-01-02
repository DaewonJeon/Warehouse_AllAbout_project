# NeighborBid: 실시간 경매 플랫폼의 설계와 구현

> **"0.1초의 차이가 10만원의 차이를 만드는 시스템에서, 우리는 어떻게 데이터 무결성을 보장했는가"**

이 글은 Django와 WebSocket을 활용한 실시간 경매 플랫폼 **NeighborBid**의 핵심 설계 결정과 기술적 도전, 그리고 그 해결 과정을 담고 있습니다.

---

## 1. 프로젝트 개요

### 1.1 What We Built

**NeighborBid**는 "당근마켓의 동네 신뢰 + 실시간 경매의 스릴"을 결합한 지역 기반 경매 플랫폼입니다.

#### NeighborBid 핵심 기능 

| 구분 | 동네 경매 (Local) | 전국 실시간 경매 (National) |
| :--- | :--- | :--- |
| **통신 방식** | HTTP 기반 | WebSocket 기반 |
| **주요 품목** | 중고 가구 / 가전 | 한정판 / 인기 상품 |
| **운영 특징** | 저비용 운영 및 효율성 | ms 단위 실시간 업데이트 |


### 1.2 Tech Stack

| Layer | Technology | 선택 이유 |
|---|---|---|
| **Backend** | Django 5.2 + Channels | ORM, 인증 시스템 + 비동기 WebSocket 지원 |
| **Realtime** | Redis (Pub/Sub) | 초고속 인메모리, 다중 서버 간 메시지 브로드캐스트 |
| **Database** | SQLite3 → PostgreSQL(예정) | 개발 편의성 → 프로덕션 동시성 처리 |
| **Infra** | Docker Compose | 환경 통일, redis 설치 간편 |

---

## 2. 아키텍처 결정: 하이브리드 vs 올인원

### 2.1 핵심 질문

> **"모든 경매에 WebSocket을 붙여야 하는가?"**

초기 기획에서는 "실시간이 멋지니까 전부 WebSocket으로!"라는 의견이 있었습니다. 하지만 냉정하게 비용을 계산해봤습니다:

| 경매 유형 | 예상 입찰 빈도 | WebSocket 비용 | 실시간 필요성 |
|---|:---:|:---:|:---:|
| 동네 중고 가구 | 하루 20건 내외(예상) | Redis 상시 구동 | 🔺 불필요 |
| 한정판 스니커즈 | 초당 10~100건 | 당연히 필요 | 🔹 필수 |

**결론:** 플래그 하나(`is_national`)로 아키텍처를 분기하기로 결정.

### 2.2 구현: 단일 필드로 아키텍처 분기

```python
# auctions/models.py
class Auction(models.Model):
    is_national = models.BooleanField(default=False)
    # True  → WebSocket + Redis Pub/Sub
    # False → HTTP + DB 트랜잭션만
```

> 이 플래그 `is_national` 사용의 장점
- **인프라 비용 절감** (동네 경매는 Redis 불필요)
- **점진적 확장 가능** (나중에 동네 경매도 실시간으로 전환 가능)
- **코드 복잡도 최소화** (분기문 하나로 처리)

```python
# 프론트엔드 분기 (Template)
{% if auction.is_national %}
    <script>const ws = new WebSocket(...);</script>
{% else %}
    <form method="POST">...</form>
{% endif %}
```

---

## 3. 첫번째 문제: 동시성 제어

### 3.1 이중 지출 버그 발견

테스트 중 발견한 버그:

```
[재현]
1. 잔액 10,000원인 계정으로 로그인
2. 브라우저 탭 2개 열기 (경매 A, 경매 B)
3. 거의 동시에 두 탭에서 10,000원 입찰
4. 결과: 둘 다 성공. 잔액 = -10,000원 
```

### 3.2 원인 분석: Race Condition

| 시간 | 요청 A | 요청 B | DB 상태 (balance) |
| :--- | :--- | :--- | :--- |
| **$T=0$** | 잔액 조회 $\rightarrow$ 10,000원 | 잔액 조회 $\rightarrow$ 10,000원 | `10,000` |
| **$T=1$** | 🔹검증 통과  | 🔹검증 통과  | `10,000` |
| **$T=2$** | 차감 실행 (`balance = 0`) | 차감 실행 (`balance = -10,000`) | 🔺**`-10,000` (오류)** |

**문제의 본질:** 애플리케이션 레벨의 `if balance >= amount` 검사가 **원자적(Atomic)**이지 않음.

### 3.3 해결 과정 by 3가지 시도

#### 시도 1: Python threading.Lock 🔺

```python
import threading
lock = threading.Lock()

def place_bid(...):
    with lock:  # 문제: 멀티 프로세스에서는 못씀
        ...
```

**실패 이유:** Gunicorn/Daphne는 멀티 프로세스 환경. 각 프로세스는 별도 메모리 공간을 사용하므로 Lock이 공유되지 않음.

#### 시도 2: 낙관적 락 (Optimistic Lock) 🔺

```python
# 버전 필드 추가
class Wallet(models.Model):
    version = models.IntegerField(default=0)

# 저장 시 버전 체크
updated = Wallet.objects.filter(
    user=user, version=old_version
).update(balance=F('balance') - amount, version=F('version') + 1)

if updated == 0:
    raise ConflictError("재시도 필요")
```

**한계:** 
- 마감 직전에는 재시도 중 경매가 종료될 수 있음
- 충돌이 빈번한 경매에서는 성능 저하

#### 시도 3: 비관적 락 (Pessimistic Lock) 🔹 최종 채택

```python
from django.db import transaction

def place_bid(auction_id, user, amount):
    with transaction.atomic():
        # DB 레벨에서 Row Lock - 다른 트랜잭션은 대기
        wallet = Wallet.objects.select_for_update().get(user=user)
        auction = Auction.objects.select_for_update().get(id=auction_id)
        
        if wallet.balance < amount:
            raise ValueError("잔액 부족")
        
        # 이제 안전하게 처리
        wallet.balance -= amount
        wallet.locked_balance += amount
        wallet.save()
```

**채택 이유:**

| 기준 | 낙관적 락 | 비관적 락 |
|---|:---:|:---:|
| 마감 직전 트래픽 | 재시도 폭발  | 🔹순차 처리  |
| 금융 데이터 정확성 | 재시도 중 오류 가능 | 🔹무조건 보장  |
| 구현 복잡도 | 재시도 로직 필요 | 🔹단순  |

---

## 4. 두 번째 문제: 가짜 알림 문제 

### 4.1 현상

```
[재현]
1. 사용자가 "즉시 구매" 클릭
2. "구매 성공!" 알림 수신 
3. 새로고침 이후 상품이 여전히 "판매 중" 
```

### 4.2 원인: 트랜잭션 롤백 vs 알림 전송

```python
# 문제 
with transaction.atomic():
    auction.status = 'ENDED'
    auction.save()
    
    #  알림을 트랜잭션 안에서 전송
    channel_layer.group_send(...)  # 즉시 전송됨
    
    validate_something()  # Exception → 롤백
    # 알림은 이미 전송됨
```

**문제:** WebSocket 메시지 전송은 **롤백되지 않는 외부 시스템 호출**.

### 4.3 해결: transaction.on_commit

```python
def buy_now(auction_id, buyer):
    def send_notification():
        channel_layer.group_send(f'auction_{auction_id}', {...})

    with transaction.atomic():
        # ... 구매 로직 ...
        auction.status = 'ENDED'
        auction.save()
        
        # 커밋이 확정된 후에만 실행
        transaction.on_commit(send_notification)
```

**원칙 수립:**
> **"사이드 이펙트(알림, 이메일, 외부 API)는 반드시 DB 커밋 후에 실행"**

---

## 5. 데이터 설계: 에스크로 패턴

### 5.1 문제: 입찰 중인 돈의 상태

사용자가 10,000원을 입찰했을 때:
- 🔺 바로 차감하면 → "낙찰도 안됐는데 내 돈이 사라졌음." (UX 문제)
- 🔺 차감 안 하면 → 같은 돈으로 여러 경매에 입찰 가능 (이중 지출)

### 5.2 해결: 이중 장부 

```python
# wallet/models.py
class Wallet(models.Model):
    balance = models.DecimalField(...)        # 가용 잔액
    locked_balance = models.DecimalField(...) # 입찰 중 잠긴 금액
```

- **에스크로(Escrow) 패턴**을 적용
-  **총 자산** = `balance` + `locked_balance`
- 거래의 신뢰성을 시스템 레벨에서 보장

**자금 흐름**
| 구분 | 가용 잔액 (Balance) | 예치금 (Locked) | 총 자산 | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **입찰 시** | 10,000 → **0** | 0 → **10,000** | 10,000 | 잔액 차감 및 금액 잠금 |
| **낙찰 시** | 0 | 10,000 → **0** | **0** | 잠금 해제 및 판매자 송금 |
| **유찰 시** | 0 → **10,000** | 10,000 → **0** | 10,000 | 잠금 해제 및 잔액 복구 |

**효과**
- 사용자는 "입찰 중 10,000원"을 확인 가능 (투명성)
- 시스템은 `balance`만 체크하면 이중 지출 자동 차단

---

## 6. 서비스 레이어 분리: view 파일

### 6.1 초기 상태 (Fat view.py)

```python
# views.py 
def auction_detail(request, auction_id):
    if request.method == 'POST':
        with transaction.atomic():
            auction = Auction.objects.select_for_update().get(...)
            wallet = Wallet.objects.select_for_update().get(...)
            # ... 100줄의 비즈니스 로직 
            # ... 검증, 환불, 입찰, 알림 
```

**문제:**
- WebSocket Consumer에서 같은 로직을 또 작성 - 코드 중복, 재사용성 낮음
- 테스트하려면 HTTP 요청을 만들어야 함 

### 6.2 개선 후 (Service Layer)

```python
# services.py - 비즈니스 로직 전담
def place_bid(auction_id, user, amount):
    with transaction.atomic():
        # 핵심 로직
        return "성공!"

# views.py - HTTP 처리만
def auction_detail(request, auction_id):
    msg = place_bid(auction_id, request.user, amount) 
    messages.success(request, msg)

# consumers.py - WebSocket에서 재사용
@database_sync_to_async
def save_bid(self, auction_id, user, amount):
    return place_bid(auction_id, user, amount)  
```

**효과:** 코드 중복 제거, 테스트 용이성 확보, 유지보수성 향상

---

## 7. 동기-비동기 경계:  헷갈렸던 부분

### 7.1 문제 상황
비동기(Async) 루프 안에서 동기(Sync) 방식의 DB 호출
```python
# Consumer는 비동기
class AuctionConsumer(AsyncWebsocketConsumer):
    async def receive(self, text_data):
        # Django ORM은 동기
        auction = Auction.objects.get(id=1)  
```

### 7.2 해결: database_sync_to_async

```python
from channels.db import database_sync_to_async

@database_sync_to_async
def get_auction(auction_id):
    return Auction.objects.get(id=auction_id)

async def receive(self, text_data):
    auction = await get_auction(1)  # 🔹ok
```

**동작 원리:**
- 동기 코드를 **스레드 풀**에서 실행
- 이벤트 루프가 차단되지 않고 다른 요청 처리 가능

### 7.3 반대 방향: async_to_sync

동기 함수(services.py)에서 비동기 Channel Layer를 호출해야 할 때:

```python
from asgiref.sync import async_to_sync

def buy_now(auction_id, buyer):
    def send_notification():
        # 동기 함수 안에서 비동기 호출
        async_to_sync(channel_layer.group_send)(
            f'auction_{auction_id}', {...}
        )
    
    with transaction.atomic():
        # ...
        transaction.on_commit(send_notification)
```

---

## 8. 테스트: 동시성 버그

### 8.1 일반 테스트로는 불가

```python
def test_normal(self):
    place_bid(auction_id, user, 10000)
    place_bid(auction_id, user, 10000)  # 순차 실행이기 때문에 의미없음.
```

### 8.2 스레드를 활용한 동시성 테스트

```python
import threading
def test_double_spending_prevention(self):
    results = []
    def bid_request(auction_id):
        try:
            place_bid(auction_id, user, 10000)
            results.append("success")
        except ValueError:
            results.append("fail")
    # 동시에 2개 요청
    t1 = threading.Thread(target=bid_request, args=(auction1.id,))
    t2 = threading.Thread(target=bid_request, args=(auction2.id,))
    t1.start(); t2.start()
    t1.join(); t2.join()
    # 검증: 1개만 성공해야 함 
    assert results.count("success") == 1
```
### 8.3 동시성 테스트 결과 요약

### 8.3 테스트 결과

| 검증 항목 | 기대 | 실제 |
| :--- | :--- | :--- |
| 동시 입찰 2건 | 1건만 성공 |  Pass |
| 잔액 음수 | 발생 안 함 |  Pass |
| 총 자산 보존 | 10,000원 |  Pass |

### 8.4 핵심 테스트 기법

| 기법 | 역할 | 선택 이유 |
| :--- | :--- | :--- |
| `TransactionTestCase` | 실제 커밋 발생 | 스레드 간 DB 공유 필요 |
| `threading.Thread` | 동시 요청 | Race Condition 재현 |
| `select_for_update()` | DB 락 | 순차 처리 보장 |

## 9. 배운 것들

### 9.1 기술적 교훈

| 상황 | 🔺잘못된 직관/생각 | 🔹수정된 접근 |
|---|---|---|
| 실시간 기능 | 전부 WebSocket | 비용 대비 효과 분석 후 하이브리드 |
| 동시성 제어 | 애플리케이션에서 if문 | DB 레벨 Lock (select_for_update) |
| 알림 전송 | 트랜잭션 안에서 바로 | on_commit 훅으로 커밋 확정 후 |
| 금융 데이터 | balance 하나면 충분 | 에스크로 패턴 (balance + locked) |


---

## 10. 아키텍처 및 데이터베이스 구조 

<img src="/NeighborBid_Auction_Service/images/architecture.png" width="100%">
<img src="/NeighborBid_Auction_Service/images/All_database_2.png" width="100%">

---

## 11. 마치며

이 프로젝트를 통해 배운 가장 큰 교훈은:

> **"단순해 보이는 문제에 숨어있는 복잡한 여러가지 케이스들.."**

**입찰 버튼** 뒤에는:
- 동시성 제어
- 분산 시스템 간 메시지 동기화
- 금융 데이터 무결성
- 트랜잭션과 외부 호출의 순서

이런 고민들이 숨어있었습니다. 그리고 이 고민들을 해결하는 과정에서 진짜 "시스템 설계"가 무엇인지 배울 수 있었습니다.

---

**Tech Stack:** Python 3.11, Django 5.2, Django Channels, Redis, SQLite3, Docker Compose

**Repository:** A1_NeighborBid_Auction

**Related Docs:** 
- [02_CORE_LOGIC_ANALYSIS.md](최최종v1.0~v2.0/02_CORE_LOGIC_ANALYSIS.md) - 동시성 제어 상세
- [03_SOFTWARE_PATTERNS.md](최최종v1.0~v2.0/03_SOFTWARE_PATTERNS.md) - 적용된 디자인 패턴
- [06_TECHNICAL_DEEP_DIVE.md](최최종v1.0~v2.0/06_TECHNICAL_DEEP_DIVE.md) - Channels 심층 분석
