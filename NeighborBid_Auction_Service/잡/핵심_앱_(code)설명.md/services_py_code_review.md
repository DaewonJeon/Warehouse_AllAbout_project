`from django.db import transaction`: django.db.transaction: 돈과 관련된 로직이므로 원자성(Atomicity) 보장이 필수입니다. 중간에 에러가 나면 모든 DB 작업을 없던 일로 되돌리기(Rollback) 위해 사용합니다.

```
django.db.transaction: 돈과 관련된 로직이므로 원자성(Atomicity) 보장이 필수입니다. 중간에 에러가 나면 모든 DB 작업을 없던 일로 되돌리기(Rollback) 위해 사용합니다.

channels & asgiref: 이 코드는 단순한 REST API가 아니라, **웹소켓(WebSocket)**을 통해 실시간으로 입찰 현황을 다른 사용자들에게 알리기 위한 준비가 되어 있음을 보여줍니다. (동기 함수 안에서 비동기 채널 레이어를 호출하기 위해 async_to_sync를 사용)
```

- ForeignKey(연결 클래스, on_delete=...) : 외래키 필수 조건 **<연결 클래스와, 삭제 조건>**

`def place_bid(auction_id, user, amount):` 

**`with transaction.atomic():`** 전체 성공 OR 전체 취소 <해당 코드 블록 끝까지 원자성 실행!!>

**`atomic()` 코드블록 내부에서** `select_for_update().get()` 락을 걸어준다. <.get() 자체로 행 단위 락!!> 코드가 실행되는 순간, DB에서 해당 auction 행(Row)에 **잠금(Lock)**을 겁니다. id의 경매 정보를 가져오고, auction 은 DB에서 퍼온 데이터를 메모리에 들고 있으면서 변수들과 하나씩 비교

`raise` : 에러를 발생시킵니다(문구 작성)

---

## 정합성(Consistency)


**last_bid = auction.bids.order_by('-amount').first()** : 금액 큰 1명 찾기

`.bids` 

`auction.bids` : auction 테이블에 연결된 bids 테이블이지만, auction은 Auction 클래스의 변수이고, Auction은 외래키로 Bid 클래스와 연결되어 있습니다.
그래서 **Auction 클래스를 참고했지만, Auction 에는 bids가 없음**
장고에서 DB 를 통해 테이블 확인
Auction 은 Bid 와 외래키로 연결되어 있기 때문에 Bid의 내부에 있는 bids를 사용할 수 있음



`if auction.current_price > 0:
    last_bid = auction.bids.order_by('-amount').first()` : 입찰 기록들 중 금액이 가장 큰(-amount) 1등을 찾아냅니다. 바로 이 사람이 환불 대상입니다.

```
prev_bidder_wallet.locked_balance -= last_bid.amount
                prev_bidder_wallet.balance += last_bid.amount
                prev_bidder_wallet.save()
```
locked_balance -= amount: 경매에 묶여있던 돈을 풉니다.

balance += amount: 그 돈을 다시 자유롭게 쓸 수 있는 잔액으로 옮깁니다.

`wallet = Wallet.objects.select_for_update().get(user=user)` : 락의 효과 A 경매 입찰이 지갑을 잡고 있으면, B 경매 입찰 요청은 대기합니다. A가 끝나고 잔액이 0원이 된 후에야 B가 실행되므로, B는 ValueError를 뱉고 안전하게 거절됩니다.

`.order_by('-amount')` : 금액(amount)이 큰 순서대로(내림차순) 정렬, - 는 DESC
`.first()` : 가장 앞의 데이터를 가져옴

`save()` : 메모리상에서 수정한 데이터를 실제 데이터베이스(DB) 파일에 영구적으로 기록(Update)하라는 명령어

```
Wallet, Auction)는 models.Model을 상속받아 만들어집니다. 이 상속 과정에서 save()라는 메서드가 자동으로 포함됩니다.

메모리 단계: prev_bidder_wallet.balance += last_bid.amount를 실행하면, 현재 실행 중인 Python 프로그램의 메모리 안에서만 숫자가 바뀝니다.

DB 반영 단계: prev_bidder_wallet.save()를 호출하는 순간, Django가 UPDATE wallet_table SET balance = ... WHERE id = ... 와 같은 SQL 문을 생성하여 DB에 전송합니다.
```

---

```
Transaction.objects.create(
            wallet=wallet,
            amount=-amount, # 내역에는 음수로 표시하거나 0으로 표시 (잠금이니까)
            transaction_type='BID_LOCK',
            description=f"경매({auction.title}) 입찰 예약금"
        )
```

.create() : Transaction 모델의 데이터를 생성합니다. (클래스에 내장된 표준적인 함수)
Django ORM 에서의 동작과정

1. SQL 생성(컬럼에 값 들어가고)
2. 행 1개 생성
3. 모두 성공적으로 오류없을 시 DB에 기록됨

> .save() 호출 없이도 이 함수가 실행되는 즉시 DB에 새로운 행(Row)을 추가하라는 요청을 보냅니다.

> with transaction.atomic() 로 인해 전체가 성공해야만 저장

---

```
channel_layer = get_channel_layer()
async_to_sync(channel_layer.group_send)(f'auction_{auction_id}', { ... })
```

- get_channel_layer(): 프로젝트에 설정된 채널 레이어(보통 Redis)를 가져오는 함수입니다

- async_to_sync(): 비동기 함수를 동기 함수로 변환하는 함수입니다

- 채널 레이어는 기본적으로 비동기(Async) 방식으로 작동합니다. **하지만 현재 buy_now 함수는 동기(Sync) 함수** 이므로, 비동기 작업을 동기 작업처럼 실행할 수 있게 변환해주는 도구입니다.

- `buyer_wallet.refresh_from_db()` : (내장)DB에서 가장 최신의 데이터를 가져오도록 합니다.

- `transaction.on_commit(send_sold_out_notification)` : (내장)현재 진행 중인 DB 트랜잭션이 성공적으로 커밋(확정)된 직후에 `send_sold_out_notification` 함수를 실행합니다.