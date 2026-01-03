# [QA] 무결점 서비스를 위한 테스트 전략 (Testing Strategy)

> "테스트 없는 코드는 빚이다."  
> 금융 성격을 띤 경매 시스템에서 버그는 곧 금전적 피해로 이어집니다. 이 문서는 A1_NeighborBid_Auction의 안정성을 검증하기 위해 수행한 **단위 테스트, 통합 테스트, 그리고 동시성 테스트** 시나리오와 실제 적용 방법을 기술합니다.

---

## 1. 테스트 전략 개요

### 1.1 테스트 피라미드 (Test Pyramid)

저희 팀은 빠른 피드백을 위해 **단위 테스트** 의 비중을 높이고, 핵심 시나리오에 대해 **통합 테스트** 를 수행하는 전략을 취했습니다.

```
            ┌─────────────┐
            │  E2E Test   │  10%
            │  (수동/UI)   │
            ├─────────────┤
            │ Integration │  20%
            │    Test     │
            ├─────────────┤
            │             │
            │  Unit Test  │  70%
            │             │
            └─────────────┘
```

| 테스트 유형 | 비중 | 목적 | 실행 속도 |
|:---:|:---:|---|:---:|
| **Unit Test** | 70% | 개별 함수/메서드 검증 | 빠름 🔹 |
| **Integration Test** | 20% | View ~ Service ~ DB 연동 | 보통 |
| **E2E/Manual Test** | 10% | 실제 사용자 시나리오 | 느림 |

### 1.2 테스트 대상 우선순위

| 우선순위 | 영역 | 이유 |
|:---:|---|---|
|  최상 | **Wallet (지갑)** 관련 로직 | 금전 거래 (버그) = 재정적 손실 |
|  최상 | **place_bid (입찰)** 로직 | 핵심 비즈니스, 동시성 이슈 |
|  상 | **buy_now (즉시 구매)** 로직 | 결제 흐름 |
|  중 | 경매 목록 필터링 | 사용자 경험 |
|  하 | UI 표시 | 치명적이지 않음 |

---

## 2. 단위 테스트 (Unit Test)

### 2.1 테스트 케이스 설계: place_bid 함수

가장 중요한 `place_bid` 함수에 대한 테스트 케이스입니다.

| TC ID | 시나리오 | 입력 조건 | 예상 결과 | 검증 포인트 |
|:---:|---|---|---|---|
| **TC-001** | 정상 입찰 | 잔액 충분, 경매 진행중 | 성공 메시지 반환 | Bid 생성, Wallet 차감 |
| **TC-002** | 잔액 부족 | balance < amount | ValueError 발생 | 잔액 변동 없음 |
| **TC-003** | 종료된 경매 | status = 'ENDED' | ValueError 발생 | Bid 미생성 |
| **TC-004** | 낮은 금액 입찰 | amount < current + unit | ValueError 발생 | 현재가 유지 |
| **TC-005** | 상위 입찰 시 환불 | 기존 1등 존재 | 이전 입찰자 환불 | locked → balance |
| **TC-006** | 첫 입찰 | current_price = 0 | 시작가 이상 필요 | start_price 기준 적용 |
| **TC-007** | 판매자 입찰 시도 | bidder = seller | ValueError 발생 | 차단됨 |

### 2.2 실제 테스트 코드

```python
# auctions/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Auction, Bid
from .services import place_bid
from wallet.models import Wallet
from common.models import Region, Category
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class PlaceBidTestCase(TestCase):
    def setUp(self):
        """테스트 데이터 준비"""
        # 판매자 생성
        self.seller = User.objects.create_user(username='seller', password='test123')
        Wallet.objects.create(user=self.seller, balance=0)
        
        # 입찰자 생성
        self.bidder = User.objects.create_user(username='bidder', password='test123')
        self.bidder_wallet = Wallet.objects.create(user=self.bidder, balance=50000)
        
        # 경매 생성
        self.auction = Auction.objects.create(
            seller=self.seller,
            title="테스트 상품",
            description="테스트 설명",
            start_price=10000,
            current_price=0,
            bid_unit=1000,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
            status='ACTIVE'
        )

    def test_tc001_normal_bid_success(self):
        """TC-001: 정상 입찰 성공"""
        result = place_bid(self.auction.id, self.bidder, 10000)
        
        # 1. 성공 메시지 확인
        self.assertIn("성공", result)
        
        # 2. Bid 레코드 생성 확인
        self.assertEqual(Bid.objects.count(), 1)
        bid = Bid.objects.first()
        self.assertEqual(bid.amount, 10000)
        self.assertEqual(bid.bidder, self.bidder)
        
        # 3. Wallet 상태 확인
        self.bidder_wallet.refresh_from_db()
        self.assertEqual(self.bidder_wallet.balance, Decimal('40000'))  # 50000 - 10000
        self.assertEqual(self.bidder_wallet.locked_balance, Decimal('10000'))

    def test_tc002_insufficient_balance(self):
        """TC-002: 잔액 부족 시 ValueError"""
        with self.assertRaises(ValueError) as context:
            place_bid(self.auction.id, self.bidder, 100000)  # 10만원 입찰 (잔액 5만원)
        
        self.assertIn("잔액", str(context.exception))
        
        # Wallet 변동 없음 확인
        self.bidder_wallet.refresh_from_db()
        self.assertEqual(self.bidder_wallet.balance, Decimal('50000'))

    def test_tc003_ended_auction(self):
        """TC-003: 종료된 경매에 입찰 시도"""
        self.auction.status = 'ENDED'
        self.auction.save()
        
        with self.assertRaises(ValueError) as context:
            place_bid(self.auction.id, self.bidder, 10000)
        
        self.assertIn("진행 중인 경매가 아닙니다", str(context.exception))

    def test_tc004_low_amount_bid(self):
        """TC-004: 최소 금액 미달 입찰"""
        # 먼저 정상 입찰로 현재가 설정
        place_bid(self.auction.id, self.bidder, 10000)
        
        # 새 입찰자 생성
        bidder2 = User.objects.create_user(username='bidder2', password='test123')
        Wallet.objects.create(user=bidder2, balance=50000)
        
        # 현재가(10000) + 단위(1000) = 11000원 이상 필요
        with self.assertRaises(ValueError) as context:
            place_bid(self.auction.id, bidder2, 10500)  # 10500원 입찰
        
        self.assertIn("최소", str(context.exception))

    def test_tc005_refund_previous_bidder(self):
        """TC-005: 상위 입찰 시 이전 입찰자 환불"""
        # 첫 입찰
        place_bid(self.auction.id, self.bidder, 10000)
        
        # 새 입찰자
        bidder2 = User.objects.create_user(username='bidder2', password='test123')
        wallet2 = Wallet.objects.create(user=bidder2, balance=50000)
        
        # 상위 입찰
        place_bid(self.auction.id, bidder2, 11000)
        
        # 이전 입찰자(bidder) 환불 확인
        self.bidder_wallet.refresh_from_db()
        self.assertEqual(self.bidder_wallet.balance, Decimal('50000'))  # 원래대로 복구
        self.assertEqual(self.bidder_wallet.locked_balance, Decimal('0'))
        
        # 새 입찰자(bidder2) 잠금 확인
        wallet2.refresh_from_db()
        self.assertEqual(wallet2.balance, Decimal('39000'))  # 50000 - 11000
        self.assertEqual(wallet2.locked_balance, Decimal('11000'))
```

### 2.3 테스트 실행

```bash
# Django 테스트 실행
python manage.py test auctions.tests.PlaceBidTestCase

# 또는 특정 테스트만
python manage.py test auctions.tests.PlaceBidTestCase.test_tc001_normal_bid_success
```

- **실행 결과: 5개 테스트 모두 성공**

---

## 3. 동시성 테스트 (Concurrency Test)

### 3.1 목적

일반적인 순차 테스트로는 잡을 수 없는 **Race Condition**을 검증합니다.

### 3.2 테스트 시나리오

| 시나리오 | 설명 | 예상 결과 |
|---|---|---|
| **이중 입찰** | 같은 유저가 동시에 2건 입찰 | 1건만 성공, 1건 잔액 부족 |
| **동시 입찰 경쟁** | 10명이 동시에 같은 경매 입찰 | 가장 높은 1명만 현재 1등 |
| **즉시 구매 경쟁** | 2명이 동시에 즉시 구매 | 1명만 성공, 1명 실패 |

### 3.3 실제 테스트 코드

```python
# auctions/tests.py

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import threading
import time

from .models import Auction, Bid
from .services import place_bid
from wallet.models import Wallet, Transaction
from common.models import Region, Category

User = get_user_model()


class ConcurrencyTestCase(TransactionTestCase):
    """
    동시성 테스트는 TransactionTestCase를 사용해야 합니다.
    - TestCase: 각 테스트를 트랜잭션으로 감싸서 롤백 (스레드 간 DB 공유 안됨)
    - TransactionTestCase: 실제 커밋이 일어나서 스레드 간 DB 공유 가능
    """
    
    def setUp(self):
        """테스트 데이터 준비"""
        # 1. 지역, 카테고리 생성
        self.region = Region.objects.create(name="서울", depth=1)
        self.category = Category.objects.create(name="전자기기", slug="electronics")
        
        # 2. 사용자 생성 (입찰자 1명, 판매자 1명)
        self.seller = User.objects.create_user(
            username='seller',
            password='testpass123',
            email='seller@test.com',
            region=self.region
        )
        self.bidder = User.objects.create_user(
            username='bidder',
            password='testpass123',
            email='bidder@test.com',
            region=self.region
        )
        
        # 3. 지갑 생성 - 입찰자에게 10,000원만 지급
        Wallet.objects.create(user=self.seller, balance=0)
        self.bidder_wallet = Wallet.objects.create(
            user=self.bidder, 
            balance=Decimal('10000')  # 딱 10,000원만!
        )
        
        # 4. 경매 2개 생성 (각각 10,000원씩 입찰 가능하게)
        self.auction1 = Auction.objects.create(
            title="경매 A",
            description="테스트 경매 A",
            seller=self.seller,
            start_price=Decimal('10000'),
            current_price=Decimal('0'),
            bid_unit=Decimal('1000'),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            status='ACTIVE',
            region=self.region,
            category=self.category
        )
        self.auction2 = Auction.objects.create(
            title="경매 B",
            description="테스트 경매 B",
            seller=self.seller,
            start_price=Decimal('10000'),
            current_price=Decimal('0'),
            bid_unit=Decimal('1000'),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            status='ACTIVE',
            region=self.region,
            category=self.category
        )
    
    def test_double_spending_prevention(self):
        """
        이중 지출 방지 테스트
        
        시나리오:
        - 잔액 10,000원인 사용자가 있음
        - 경매 A, B에 동시에 10,000원씩 입찰 시도
        - 기대 결과: 1개만 성공, 1개는 잔액 부족으로 실패
        """
        results = []
        errors = []
        
        def bid_on_auction(auction, amount):
            """스레드에서 실행될 입찰 함수"""
            try:
                place_bid(auction.id, self.bidder, Decimal(str(amount)))
                results.append({
                    'auction': auction.title,
                    'status': 'success'
                })
            except ValueError as e:
                results.append({
                    'auction': auction.title,
                    'status': 'fail',
                    'error': str(e)
                })
            except Exception as e:
                errors.append(str(e))
        
        # 두 스레드를 거의 동시에 시작
        t1 = threading.Thread(target=bid_on_auction, args=(self.auction1, 10000))
        t2 = threading.Thread(target=bid_on_auction, args=(self.auction2, 10000))
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # 결과 출력
        print("\n" + "="*60)
        print(" 동시성 테스트 결과")
        print("="*60)
        print(f"초기 잔액: 10,000원")
        print(f"입찰 시도: 경매 A에 10,000원, 경매 B에 10,000원 (동시)")
        print("-"*60)
        
        for r in results:
            status_icon = "" if r['status'] == 'success' else "x"
            print(f"{status_icon} {r['auction']}: {r['status']}")
            if 'error' in r:
                print(f"   → 사유: {r['error']}")
        
        # 최종 지갑 상태 확인
        self.bidder_wallet.refresh_from_db()
        print("-"*60)
        print(f"최종 잔액(balance): {self.bidder_wallet.balance}원")
        print(f"잠긴 금액(locked): {self.bidder_wallet.locked_balance}원")
        print(f"총 자산: {self.bidder_wallet.balance + self.bidder_wallet.locked_balance}원")
        print("="*60)
        
        #  검증: 정확히 1개만 성공해야 함
        success_count = sum(1 for r in results if r['status'] == 'success')
        self.assertEqual(success_count, 1, 
            f"1개만 성공해야 하는데 {success_count}개 성공함!")
        
        #  검증: 잔액이 음수가 되면 안 됨
        self.assertGreaterEqual(self.bidder_wallet.balance, 0,
            f"잔액이 음수가 됨! balance={self.bidder_wallet.balance}")
        
        #  검증: 총 자산은 여전히 10,000원이어야 함
        total = self.bidder_wallet.balance + self.bidder_wallet.locked_balance
        self.assertEqual(total, Decimal('10000'),
            f"총 자산이 변함! {total}원")
        
        print(" 테스트 통과: 이중 지출이 정상적으로 차단됨!")


class BasicBidTestCase(TestCase):
    """기본 입찰 테스트 (동시성 없이)"""
    
    def setUp(self):
        self.region = Region.objects.create(name="서울", depth=1)
        self.category = Category.objects.create(name="전자기기", slug="electronics2")
        
        self.seller = User.objects.create_user(
            username='seller', password='test', email='s@t.com', region=self.region
        )
        self.bidder = User.objects.create_user(
            username='bidder', password='test', email='b@t.com', region=self.region
        )
        
        Wallet.objects.create(user=self.seller, balance=0)
        self.wallet = Wallet.objects.create(user=self.bidder, balance=Decimal('50000'))
        
        self.auction = Auction.objects.create(
            title="테스트 경매",
            description="설명",
            seller=self.seller,
            start_price=Decimal('10000'),
            current_price=Decimal('0'),
            bid_unit=Decimal('1000'),
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(hours=1),
            status='ACTIVE',
            region=self.region,
            category=self.category
        )
    
    def test_successful_bid(self):
        """정상 입찰 테스트"""
        place_bid(self.auction.id, self.bidder, Decimal('10000'))
        
        self.wallet.refresh_from_db()
        self.auction.refresh_from_db()
        
        self.assertEqual(self.wallet.balance, Decimal('40000'))
        self.assertEqual(self.wallet.locked_balance, Decimal('10000'))
        self.assertEqual(self.auction.current_price, Decimal('10000'))
    
    def test_insufficient_balance(self):
        """잔액 부족 테스트"""
        self.wallet.balance = Decimal('5000')
        self.wallet.save()
        
        with self.assertRaises(ValueError) as ctx:
            place_bid(self.auction.id, self.bidder, Decimal('10000'))
        
        self.assertIn("잔액", str(ctx.exception))
    
    def test_bid_below_minimum(self):
        """최소 입찰가 미만 테스트"""
        with self.assertRaises(ValueError) as ctx:
            place_bid(self.auction.id, self.bidder, Decimal('5000'))
        
        self.assertIn("최소", str(ctx.exception))

```

---

## 4. 통합 테스트 (Integration Test)

### 4.1 View-Service-DB 연동 테스트

```python
# auctions/tests.py
from django.test import TestCase, Client
from django.urls import reverse

class AuctionViewIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        # 사용자 및 경매 데이터 설정...

    def test_bid_via_http_request(self):
        """HTTP 요청을 통한 입찰 통합 테스트"""
        # 로그인
        self.client.login(username='bidder', password='test123')
        
        # 입찰 요청
        response = self.client.post(
            reverse('auction_detail', args=[self.auction.id]),
            {'amount': 10000}
        )
        
        # 리다이렉트 확인 (성공 시)
        self.assertEqual(response.status_code, 302)
        
        # DB 상태 확인
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, 10000)

    def test_wallet_charge_integration(self):
        """지갑 충전 통합 테스트"""
        self.client.login(username='bidder', password='test123')
        
        response = self.client.post(
            reverse('charge_wallet'),
            {'amount': 50000}
        )
        
        # 리다이렉트 확인
        self.assertEqual(response.status_code, 302)
        
        # 잔액 확인
        wallet = Wallet.objects.get(user=self.bidder)
        self.assertEqual(wallet.balance, Decimal('100000'))  # 기존 50000 + 충전 50000
```
| 테스트 클래스 | 테스트 케이스 | 결과 |
| :--- | :--- | :---: |
| **AuctionViewIntegrationTest**<br>(View-Service-DB 통합 테스트) | TC-INT-001: HTTP 요청 입찰 | 🔹 |
| | TC-INT-002: 지갑 충전 | 🔹 |
| | TC-INT-003: 판매자 입찰 차단 | 🔹 |
| | TC-INT-004: 잔액 부족 입찰 차단 | 🔹 |
| **PlaceBidTestCase**<br>(단위 테스트) | TC-001: 정상 입찰 성공 | 🔹 |
| | TC-002: 잔액 부족 | 🔹 |
| | TC-003: 종료된 경매 입찰 차단 | 🔹 |
| | TC-004: 최소 금액 미달 | 🔹 |
| | TC-005: 이전 입찰자 환불 |🔹 |
| **ConcurrencyTestCase**<br>(동시성 테스트) | 이중 지출 방지 | 🔹 |
---

## 5. 수동 검증 프로세스 (Manual QA)

### 5.1 배포 전 체크리스트

자동화 테스트가 놓칠 수 있는 **UX 이슈**를 잡기 위한 체크리스트:

| 항목 | 확인 내용 | 결과 |
|---|---|:---:|
|  WebSocket 연결 | 네트워크 끊김 후 재연결 동작 | ☐ |
|  알림 표시 | 낙찰/유찰 시 팝업 알림 | ☐ |
|  응답 속도 | 입찰 버튼 클릭 → 화면 갱신 < 1초 | ☐ |
|  반응형 UI | 모바일에서 버튼 클릭 가능 | ☐ |
|  권한 체크 | 비로그인 시 입찰 불가 | ☐ |
|  금액 표시 | 천 단위 콤마, 음수 표시 없음 | ☐ |

### 5.2 테스트 시나리오

```
[시나리오 1: 전체 거래 플로우]
1. 회원가입 → 로그인
2. 지갑 충전 (50,000원)
3. 경매 등록 (시작가 10,000원)
4. 다른 계정으로 로그인
5. 해당 경매에 입찰 (10,000원)
6. 상위 입찰 (15,000원)
7. 즉시 구매 또는 경매 종료
8. 최종 잔액 확인

[시나리오 2: 실시간 경매]
1. 전국 경매로 등록 (is_national=True)
2. 브라우저 탭 2개 열기
3. 한 탭에서 입찰
4. 다른 탭에서 실시간 가격 업데이트 확인
```

---

## 6. 테스트 커버리지 목표

| 영역 | 현재 커버리지 | 목표 | 우선순위 |
|---|:---:|:---:|:---:|
| `services.py` (place_bid, buy_now) | - | 90%+ | 🔹 |
| `views.py` (HTTP 입찰) | - | 80%+ | 🔹 |
| `consumers.py` (WebSocket) | - | 70%+ | 🔹 |
| `models.py` | - | 60%+ | 🔹 |

---

## 7. 결론

완벽한 테스트는 없지만, **"가장 치명적인 실패"**를 예방하는 테스트는 필수입니다.

저희는 특히 **'돈(Wallet)'**과 관련된 로직에 대해서는 편집증에 가까울 정도로 반복적인 테스트를 수행하여, 금융 무결성을 보장하고자 했습니다.

> **테스트 원칙:**
> 1. 🔹 돈 관련 로직은 무조건 테스트
> 2. 🔹 동시성 이슈가 있는 곳은 스레드 테스트
> 3. 🔹 Happy Path뿐 아니라 Exception Path도 테스트
> 4. 🔹 실제 사용자 시나리오로 수동 검증

> **작성자:** DH / Z
> **관련 문서:** [04_TRIALS_AND_ERRORS.md](04_TRIALS_AND_ERRORS.md) | [데이터베이스(설계과정).md](데이터베이스(설계과정).md)