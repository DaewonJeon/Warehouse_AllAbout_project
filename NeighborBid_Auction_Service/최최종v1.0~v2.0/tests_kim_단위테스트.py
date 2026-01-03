# auctions/tests.py
"""
View-Service-DB 연동 통합 테스트
05_TESTING_STRATEGY.md 4.1절 기반
"""

from django.test import TestCase, Client, TransactionTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import threading

from .models import Auction, Bid
from .services import place_bid
from wallet.models import Wallet, Transaction
from common.models import Region, Category

User = get_user_model()


# ==============================================================
# 1. View-Service-DB 통합 테스트 (HTTP 요청 기반)
# ==============================================================
class AuctionViewIntegrationTest(TestCase):
    """HTTP 요청을 통한 입찰 및 지갑 충전 통합 테스트"""
    
    def setUp(self):
        """테스트 데이터 준비"""
        self.client = Client()
        
        # 1. 공통 데이터 생성
        self.region = Region.objects.create(name="서울", depth=1)
        self.category = Category.objects.create(name="전자기기", slug="electronics")
        
        # 2. 판매자 생성
        self.seller = User.objects.create_user(
            username='seller',
            password='test123',
            email='seller@test.com',
            region=self.region
        )
        Wallet.objects.create(user=self.seller, balance=0)
        
        # 3. 입찰자 생성
        self.bidder = User.objects.create_user(
            username='bidder',
            password='test123',
            email='bidder@test.com',
            region=self.region
        )
        self.bidder_wallet = Wallet.objects.create(user=self.bidder, balance=Decimal('50000'))
        
        # 4. 테스트 경매 생성
        self.auction = Auction.objects.create(
            seller=self.seller,
            title="테스트 상품",
            description="테스트 설명입니다.",
            start_price=10000,
            current_price=0,
            bid_unit=1000,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=1),
            status='ACTIVE',
            region=self.region,
            category=self.category
        )

    def test_bid_via_http_request(self):
        """TC-INT-001: HTTP 요청을 통한 입찰 통합 테스트"""
        # 1. 로그인
        login_success = self.client.login(username='bidder', password='test123')
        self.assertTrue(login_success, "로그인 실패")
        
        # 2. 입찰 요청 (POST)
        response = self.client.post(
            reverse('auction_detail', args=[self.auction.id]),
            {'amount': 10000}
        )
        
        # 3. 리다이렉트 확인 (성공 시 302)
        self.assertEqual(response.status_code, 302, 
            f"예상: 302 리다이렉트, 실제: {response.status_code}")
        
        # 4. DB 상태 확인 - 경매 현재가
        self.auction.refresh_from_db()
        self.assertEqual(self.auction.current_price, 10000,
            f"현재가가 10000원이어야 함. 실제: {self.auction.current_price}")
        
        # 5. DB 상태 확인 - Bid 레코드 생성
        self.assertEqual(Bid.objects.count(), 1, "Bid 레코드가 1개 생성되어야 함")
        bid = Bid.objects.first()
        self.assertEqual(bid.amount, 10000)
        self.assertEqual(bid.bidder, self.bidder)
        
        # 6. DB 상태 확인 - Wallet 상태
        self.bidder_wallet.refresh_from_db()
        self.assertEqual(self.bidder_wallet.balance, Decimal('40000'),
            f"잔액이 40000원이어야 함. 실제: {self.bidder_wallet.balance}")
        self.assertEqual(self.bidder_wallet.locked_balance, Decimal('10000'),
            f"잠긴 금액이 10000원이어야 함. 실제: {self.bidder_wallet.locked_balance}")
        
        print("\n✅ TC-INT-001: HTTP 입찰 통합 테스트 성공!")

    def test_wallet_charge_integration(self):
        """TC-INT-002: 지갑 충전 통합 테스트"""
        # 1. 로그인
        self.client.login(username='bidder', password='test123')
        
        # 2. 충전 요청 (POST)
        response = self.client.post(
            reverse('charge_wallet'),
            {'amount': 50000}
        )
        
        # 3. 리다이렉트 확인 (mypage로 이동)
        self.assertEqual(response.status_code, 302,
            f"예상: 302 리다이렉트, 실제: {response.status_code}")
        
        # 4. 잔액 확인 (기존 50000 + 충전 50000 = 100000)
        self.bidder_wallet.refresh_from_db()
        self.assertEqual(self.bidder_wallet.balance, Decimal('100000'),
            f"잔액이 100000원이어야 함. 실제: {self.bidder_wallet.balance}")
        
        # 5. Transaction 기록 확인
        transactions = Transaction.objects.filter(wallet=self.bidder_wallet, transaction_type='DEPOSIT')
        self.assertEqual(transactions.count(), 1, "충전 기록이 1개 있어야 함")
        self.assertEqual(transactions.first().amount, Decimal('50000'))
        
        print("\n✅ TC-INT-002: 지갑 충전 통합 테스트 성공!")

    def test_seller_cannot_bid_own_auction(self):
        """TC-INT-003: 판매자 본인 경매 입찰 불가 테스트"""
        # 판매자 지갑 생성 (잔액 추가)
        seller_wallet = Wallet.objects.get(user=self.seller)
        seller_wallet.balance = Decimal('100000')
        seller_wallet.save()
        
        # 판매자로 로그인
        self.client.login(username='seller', password='test123')
        
        # 본인 경매에 입찰 시도
        response = self.client.post(
            reverse('auction_detail', args=[self.auction.id]),
            {'amount': 10000}
        )
        
        # 리다이렉트는 되지만 입찰은 실패해야 함
        self.assertEqual(response.status_code, 302)
        
        # Bid 레코드가 생성되지 않아야 함
        self.assertEqual(Bid.objects.count(), 0, "판매자의 입찰은 거부되어야 함")
        
        print("\n✅ TC-INT-003: 판매자 입찰 차단 테스트 성공!")

    def test_insufficient_balance_bid(self):
        """TC-INT-004: 잔액 부족 시 입찰 실패 테스트"""
        # 잔액 설정 (5000원)
        self.bidder_wallet.balance = Decimal('5000')
        self.bidder_wallet.save()
        
        # 로그인
        self.client.login(username='bidder', password='test123')
        
        # 10000원 입찰 시도 (잔액 부족)
        response = self.client.post(
            reverse('auction_detail', args=[self.auction.id]),
            {'amount': 10000}
        )
        
        # 리다이렉트는 됨 (에러 메시지와 함께)
        self.assertEqual(response.status_code, 302)
        
        # Bid 레코드가 생성되지 않아야 함
        self.assertEqual(Bid.objects.count(), 0, "잔액 부족으로 입찰 실패해야 함")
        
        # 잔액 변동 없어야 함
        self.bidder_wallet.refresh_from_db()
        self.assertEqual(self.bidder_wallet.balance, Decimal('5000'))
        
        print("\n✅ TC-INT-004: 잔액 부족 입찰 차단 테스트 성공!")


# ==============================================================
# 2. 기본 입찰 서비스 단위 테스트
# ==============================================================
class PlaceBidTestCase(TestCase):
    """place_bid 서비스 함수 단위 테스트"""
    
    def setUp(self):
        """테스트 데이터 준비"""
        self.region = Region.objects.create(name="서울", depth=1)
        self.category = Category.objects.create(name="전자기기", slug="electronics-unit")
        
        # 판매자 생성
        self.seller = User.objects.create_user(
            username='seller',
            password='test123',
            email='seller@unit.com',
            region=self.region
        )
        Wallet.objects.create(user=self.seller, balance=0)
        
        # 입찰자 생성
        self.bidder = User.objects.create_user(
            username='bidder',
            password='test123',
            email='bidder@unit.com',
            region=self.region
        )
        self.bidder_wallet = Wallet.objects.create(user=self.bidder, balance=Decimal('50000'))
        
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
            status='ACTIVE',
            region=self.region,
            category=self.category
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
        self.assertEqual(self.bidder_wallet.balance, Decimal('40000'))
        self.assertEqual(self.bidder_wallet.locked_balance, Decimal('10000'))
        
        print("\n✅ TC-001: 정상 입찰 성공 테스트 통과!")

    def test_tc002_insufficient_balance(self):
        """TC-002: 잔액 부족 시 ValueError"""
        with self.assertRaises(ValueError) as context:
            place_bid(self.auction.id, self.bidder, 100000)  # 10만원 입찰 (잔액 5만원)
        
        self.assertIn("잔액", str(context.exception))
        
        # Wallet 변동 없음 확인
        self.bidder_wallet.refresh_from_db()
        self.assertEqual(self.bidder_wallet.balance, Decimal('50000'))
        
        print("\n✅ TC-002: 잔액 부족 테스트 통과!")

    def test_tc003_ended_auction(self):
        """TC-003: 종료된 경매에 입찰 시도"""
        self.auction.status = 'ENDED'
        self.auction.save()
        
        with self.assertRaises(ValueError) as context:
            place_bid(self.auction.id, self.bidder, 10000)
        
        self.assertIn("진행 중인 경매가 아닙니다", str(context.exception))
        
        print("\n✅ TC-003: 종료된 경매 입찰 차단 테스트 통과!")

    def test_tc004_low_amount_bid(self):
        """TC-004: 최소 금액 미달 입찰"""
        # 먼저 정상 입찰로 현재가 설정
        place_bid(self.auction.id, self.bidder, 10000)
        
        # 새 입찰자 생성
        bidder2 = User.objects.create_user(
            username='bidder2',
            password='test123',
            email='bidder2@unit.com',
            region=self.region
        )
        Wallet.objects.create(user=bidder2, balance=Decimal('50000'))
        
        # 현재가(10000) + 단위(1000) = 11000원 이상 필요, 10500원 입찰 시도
        with self.assertRaises(ValueError) as context:
            place_bid(self.auction.id, bidder2, 10500)
        
        self.assertIn("최소", str(context.exception))
        
        print("\n✅ TC-004: 최소 금액 미달 테스트 통과!")

    def test_tc005_refund_previous_bidder(self):
        """TC-005: 상위 입찰 시 이전 입찰자 환불"""
        # 첫 입찰
        place_bid(self.auction.id, self.bidder, 10000)
        
        # 새 입찰자
        bidder2 = User.objects.create_user(
            username='bidder2',
            password='test123',
            email='bidder2@unit.com',
            region=self.region
        )
        wallet2 = Wallet.objects.create(user=bidder2, balance=Decimal('50000'))
        
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
        
        print("\n✅ TC-005: 이전 입찰자 환불 테스트 통과!")


# ==============================================================
# 3. 동시성 테스트 (이중 지출 방지)
# ==============================================================
class ConcurrencyTestCase(TransactionTestCase):
    """
    동시성 테스트 (이중 지출 방지)
    TransactionTestCase 사용: 실제 커밋이 일어나서 스레드 간 DB 공유 가능
    """
    
    def setUp(self):
        """테스트 데이터 준비"""
        self.region = Region.objects.create(name="서울", depth=1)
        self.category = Category.objects.create(name="전자기기", slug="electronics-conc")
        
        # 판매자 생성
        self.seller = User.objects.create_user(
            username='seller',
            password='test123',
            email='seller@conc.com',
            region=self.region
        )
        Wallet.objects.create(user=self.seller, balance=0)
        
        # 입찰자 생성 - 딱 10,000원만 지급!
        self.bidder = User.objects.create_user(
            username='bidder',
            password='test123',
            email='bidder@conc.com',
            region=self.region
        )
        self.bidder_wallet = Wallet.objects.create(
            user=self.bidder,
            balance=Decimal('10000')  # 딱 10,000원만!
        )
        
        # 경매 2개 생성 (각각 10,000원씩 입찰 가능)
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
        - 잔액 10,000원인 사용자
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
        print(" 🔒 동시성 테스트 결과")
        print("="*60)
        print(f"초기 잔액: 10,000원")
        print(f"입찰 시도: 경매 A에 10,000원, 경매 B에 10,000원 (동시)")
        print("-"*60)
        
        for r in results:
            status_icon = "✅" if r['status'] == 'success' else "❌"
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
        
        # ✅ 검증: 정확히 1개만 성공해야 함
        success_count = sum(1 for r in results if r['status'] == 'success')
        self.assertEqual(success_count, 1,
            f"1개만 성공해야 하는데 {success_count}개 성공함!")
        
        # ✅ 검증: 잔액이 음수가 되면 안 됨
        self.assertGreaterEqual(self.bidder_wallet.balance, 0,
            f"잔액이 음수가 됨! balance={self.bidder_wallet.balance}")
        
        # ✅ 검증: 총 자산은 여전히 10,000원이어야 함
        total = self.bidder_wallet.balance + self.bidder_wallet.locked_balance
        self.assertEqual(total, Decimal('10000'),
            f"총 자산이 변함! {total}원")
        
        print("✅ 테스트 통과: 이중 지출이 정상적으로 차단됨!")
