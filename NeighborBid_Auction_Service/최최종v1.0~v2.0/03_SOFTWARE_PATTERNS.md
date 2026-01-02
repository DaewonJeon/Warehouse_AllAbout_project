# [Architecture] 유지보수성을 높이는 소프트웨어 패턴의 적용

> 좋은 코드는 기능 구현을 넘어, 유지보수가 쉽고 확장에 열려 있어야 합니다. 이 문서는 A1_NeighborBid_Auction 프로젝트에 적용된 주요 **디자인 패턴(Design Pattern)과** **아키텍처 패턴을** 소개하고, 각 패턴을 도입하게 된 **구체적인 상황과 근거를** 설명합니다.

---

## 1. 서비스 계층 패턴 (Service Layer Pattern)

### 1.1 도입 배경: Fat View 문제

초기 개발 단계에서는 Django의 관행대로 `views.py`에 비즈니스 로직을 작성했습니다.

```python
# 초기 코드 (🔺 Fat View)
# auctions/views.py
@login_required
def auction_detail(request, auction_id):
    auction = get_object_or_404(Auction, id=auction_id)
    
    if request.method == 'POST':
        amount = int(request.POST.get('amount'))
        
        # 비즈니스 로직이 View에 직접 들어감
        with transaction.atomic():
            auction = Auction.objects.select_for_update().get(id=auction_id)
            if auction.status != 'ACTIVE':
                raise ValueError("...")
            
            wallet = Wallet.objects.select_for_update().get(user=request.user)
            if wallet.balance < amount:
                raise ValueError("...")
            
            # ... 100줄 이상의 로직 ...
            
            wallet.balance -= amount
            wallet.locked_balance += amount
            wallet.save()
            
            Bid.objects.create(...)
            auction.current_price = amount
            auction.save()
            
            # 알림 전송 로직까지...
```

**문제점:**
| 문제 | 설명 |
|---|---|
| **코드 중복** | 같은 입찰 로직을 WebSocket Consumer에서도 작성해야 함 |
| **테스트 어려움** | HTTP 요청을 만들어야만 비즈니스 로직 테스트 가능 |
| **가독성 저하** | 한 함수가 200줄 이상으로 비대해짐 |
| **역할 혼재** | View가 "요청 처리"와 "비즈니스 로직" 모두 담당 |

### 1.2 적용: Thin View + Service Layer

비즈니스 로직을 `services.py`로 분리하여 View의 역할을 명확히 했습니다.

```python
# 개선된 구조 (🔹 Thin View)

# auctions/services.py - 비즈니스 로직 전담
def place_bid(auction_id, user, amount):
    """순수한 비즈니스 로직만 담당"""
    with transaction.atomic():
        auction = Auction.objects.select_for_update().get(id=auction_id)
        # ... 검증 및 처리 로직 ...
        return f"성공! {amount}원에 입찰했습니다."

# auctions/views.py - HTTP 요청 처리만 담당
@login_required
def auction_detail(request, auction_id):
    auction = get_object_or_404(Auction, id=auction_id)
    
    if request.method == 'POST':
        try:
            msg = place_bid(auction.id, request.user, int(request.POST.get('amount')))
            messages.success(request, msg)
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('auction_detail', auction_id=auction.id)
    
    return render(request, 'auctions/auction_detail.html', {'auction': auction})

# auctions/consumers.py - WebSocket에서도 동일 로직 재사용!
@database_sync_to_async
def save_bid(self, auction_id, user, amount):
    try:
        return place_bid(auction_id, user, amount)  # 같은 함수 호출
    except ValueError as e:
        return str(e)
```

### 1.3 도입 효과

| 지표 | Before | After |
|:---:|:---:|:---:|
| 코드 중복 | 2곳 (View, Consumer) | 0곳 (Service만) |
| 테스트 용이성 | HTTP 요청 필요 | 함수 직접 호출 |
| View 코드량 | ~200줄 | ~30줄 |
| 로직 변경 시 수정 파일 | 2개 | 1개 |

---

## 2. 옵저버 패턴 (Observer Pattern)

### 2.1 도입 배경: 실시간 알림 요구사항

경매 시스템에서는 **"누군가 입찰하면 다른 참여자도 알아야 한다"** 는 요구사항이 있습니다.

**관계 구조:**
- **Subject (주체):** `Auction` (경매 물품) - 상태가 변하는 객체
- **Observer (구독자):** 경매 페이지를 보고 있는 사용자들

### 2.2 적용: Django Channels의 Group 기능

Django Channels의 `Group`은 옵저버 패턴을 인프라 레벨에서 지원합니다.

```python
# 옵저버 패턴 흐름

# 1️. 구독 등록 (Subscribe)
async def connect(self):
    # 사용자가 경매 페이지에 접속하면 그룹에 등록
    await self.channel_layer.group_add(
        f'auction_{auction_id}',  # 그룹 이름 = 경매 ID
        self.channel_name         # 이 소켓의 고유 채널
    )

# 2. 상태 변경 시 통지 (Notify)
async def receive(self, text_data):
    if "입찰 성공":
        # Subject가 모든 Observer에게 알림
        await self.channel_layer.group_send(
            f'auction_{auction_id}',
            {'type': 'auction_update', 'amount': new_price}
        )

# 3. 알림 수신 (Update)
async def auction_update(self, event):
    # 각 Observer가 개별적으로 UI 업데이트
    await self.send(text_data=json.dumps({
        'type': 'update',
        'amount': event['amount']
    }))

# 4. 구독 해제 (Unsubscribe)
async def disconnect(self, close_code):
    await self.channel_layer.group_discard(
        f'auction_{auction_id}',
        self.channel_name
    )
```

### 2.3 패턴 적용의 장점

| 특성 | 설명 |
|---|---|
| **느슨한 결합 (Loose Coupling)** | 입찰자 A는 다른 참여자 B, C, D의 존재를 몰라도 됨 |
| **동적 구독** | 사용자가 페이지에 접속/이탈할 때 자동으로 구독 관리 |
| **확장성** | 새로운 Observer 유형 추가 시 기존 코드 수정 불필요 |

---

## 3. 에스크로 패턴 (Escrow Pattern)

### 3.1 도입 배경: 이중 지출 방지

경매에서 가장 큰 리스크는 **"같은 돈으로 여러 경매에 입찰"**하는 것입니다.

```
시나리오: 잔액 10,000원
├─ 경매 A에 10,000원 입찰 🔹
├─ 경매 B에 10,000원 입찰 🔹 (아직 잔액이 있는 것처럼 보임!)
└─ 결과: 잔액 -10,000원🔺
```

### 3.2 적용: balance + locked_balance 이중 장부

실제 결제 시스템에서 사용하는 **에스크로(임치)** 개념을 적용했습니다.

```python
# wallet/models.py
class Wallet(models.Model):
    # 가용 잔액 (실제로 사용 가능한 금액)
    balance = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    
    # 잠긴 잔액 (입찰 중이라 사용 불가, 하지만 내 돈)
    locked_balance = models.DecimalField(max_digits=12, decimal_places=0, default=0)
```

**자금 흐름:**

```
┌────────────────────────────────────────────────────────┐
│  [입찰 시]                                              │
│  balance: 10,000 → 0      (가용 잔액에서 차감)          │
│  locked:  0 → 10,000      (잠긴 잔액으로 이동)          │
│  총 자산: 10,000 (변동 없음)                            │
├────────────────────────────────────────────────────────┤
│  [낙찰 시]                                              │
│  locked: 10,000 → 0       (잠긴 잔액 해제)              │
│  → 판매자에게 송금                                      │
├────────────────────────────────────────────────────────┤
│  [유찰/상위입찰 시]                                     │
│  locked: 10,000 → 0       (잠긴 잔액 해제)              │
│  balance: 0 → 10,000      (가용 잔액 복구)              │
└────────────────────────────────────────────────────────┘
```

### 3.3 실제 구현

```python
# auctions/services.py

def place_bid(auction_id, user, amount):
    with transaction.atomic():
        # 입찰자 지갑 확인
        wallet = Wallet.objects.select_for_update().get(user=user)
        
        # balance만 체크 (locked는 이미 다른 경매에 묶여있음)
        if wallet.balance < amount:
            raise ValueError("잔액이 부족합니다.")
        
        # 에스크로: balance → locked로 이동
        wallet.balance -= amount
        wallet.locked_balance += amount
        wallet.save()
```

### 3.4 도입 효과

| 상황 | 단일 balance | **이중 장부 (에스크로)** |
|---|:---:|:---:|
| 이중 입찰 시도 | 가능 (버그) | **차단됨** |
| 유찰 시 환불 | 로직 복잡 | **자동 복구** |
| 사용자 인식 | "돈이 사라졌다!" | "입찰 중 10,000원" 표시 가능 |

---

## 4. 트랜잭션 스크립트 패턴 (Transaction Script)

### 4.1 도입 배경: MVP 단계의 현실적 선택

복잡한 도메인 모델(DDD의 Entity, Value Object, Aggregate 등)을 도입하기보다, **하나의 비즈니스 동작 = 하나의 함수**로 정의하는 절차지향적 패턴을 선택했습니다.

### 4.2 적용: 함수 단위 트랜잭션

```python
# auctions/services.py

def place_bid(auction_id, user, amount):
    """입찰하기 - 하나의 완결된 비즈니스 로직"""
    with transaction.atomic():
        # 1. 경매 조회 및 검증
        # 2. 이전 입찰자 환불
        # 3. 새 입찰자 금액 잠금
        # 4. 입찰 기록 생성
        # 5. 현재가 갱신
        return "성공"

def buy_now(auction_id, buyer):
    """즉시 구매 - 또 다른 완결된 비즈니스 로직"""
    with transaction.atomic():
        # 1. 경매 조회 및 검증
        # 2. 기존 입찰자 환불
        # 3. 구매자 결제 처리
        # 4. 판매자 수익 입금
        # 5. 경매 종료 처리
        # 6. 알림 예약
        return "성공"

def determine_winner(auction_id):
    """낙찰자 결정 - 또 다른 완결된 비즈니스 로직"""
    with transaction.atomic():
        # ...
```

### 4.3 이 패턴을 선택한 이유

| 고려 사항 | DDD (복잡한 도메인 모델) | **Transaction Script (채택)** |
|---|:---:|:---:|
| 학습 곡선 | 높음 | 낮음 |
| 초기 개발 속도 | 느림 | **빠름** |
| 로직 추적 | 여러 클래스 탐색 | **하나의 함수에서 확인** |
| 확장성 | 높음 | 중간 (리팩토링 가능) |
| 적합한 상황 | 대규모 팀, 복잡한 도메인 | **MVP, 스타트업** |

**결론:** 현재 프로젝트는 도메인이 비교적 단순하고, 빠른 개발이 중요한 MVP 단계이므로 Transaction Script가 적합합니다. 추후 비즈니스 로직이 복잡해지면 점진적으로 도메인 모델을 추출할 수 있습니다.

---

## 5. 전략 패턴 (Strategy Pattern) - is_national 플래그

### 5.1 도입 배경

같은 "입찰"이라는 동작이지만, 경매 유형에 따라 **처리 방식이 완전히 다릅니다**.

| 동네 경매 | 전국 실시간 경매 |
|---|---|
| HTTP 요청으로 처리 | WebSocket 메시지로 처리 |
| 단순 DB 저장 | + Redis Pub/Sub |
| 페이지 새로고침 필요 | 자동 UI 업데이트 |

### 5.2 적용: 플래그 기반 분기

```python
# auctions/models.py
class Auction(models.Model):
    is_national = models.BooleanField(default=False)

# 프론트엔드 (Template)에서 분기
{% if auction.is_national %}
    <script>
        // WebSocket 연결
        const socket = new WebSocket(`ws://${location.host}/ws/auction/${auctionId}/`);
        socket.onmessage = (e) => { updatePrice(JSON.parse(e.data)); };
    </script>
{% else %}
    <!-- 일반 폼 제출 -->
    <form method="POST">
        <button type="submit">입찰하기</button>
    </form>
{% endif %}
```

### 5.3 효과

- **비용 최적화:** 동네 경매는 Redis 없이 운영 가능
- **유연한 전환:** 나중에 동네 경매도 실시간으로 바꾸고 싶다면 플래그만 변경
- **점진적 적용:** 인프라 비용을 보면서 단계적으로 실시간 범위 확대 가능

---

## 6. 결론: 패턴 적용의 원칙

저희 팀은 **"패턴을 위한 패턴"** 은 지양했습니다.

| 문제 | 해결책 (패턴) |
|---|---|
| "View가 너무 뚱뚱해요" | **서비스 레이어** |
| "실시간으로 알려야 해요" | **옵저버 패턴** |
| "이중 지출을 막아야 해요" | **에스크로 패턴** |
| "빨리 개발해야 해요" | **트랜잭션 스크립트** |
| "경매 유형별로 처리가 달라요" | **전략 패턴** |

각 패턴은 **구체적인 문제를 해결하기 위해** 도입되었으며, 이는 프로젝트의 유지보수성과 확장성을 한 단계 끌어올렸습니다.

> **작성자:** A1_NeighborBid_Auction 백엔드 개발팀  
> **관련 문서:** [02_CORE_LOGIC_ANALYSIS.md](02_CORE_LOGIC_ANALYSIS.md) | [04_TRIALS_AND_ERRORS.md](04_TRIALS_AND_ERRORS.md)

