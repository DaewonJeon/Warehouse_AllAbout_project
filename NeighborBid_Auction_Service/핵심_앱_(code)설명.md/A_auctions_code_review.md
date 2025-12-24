auctions/ models.py

`from common.models import Region, Category` : common에 있는 **지역(Region)**과 **카테고리(Category)** 가져옵니다.

1. `class Auction(models.Model):` 판매자 (seller) > (1:N 관계). 판매자 한 명이 물건을 여러 개 팔 수 있습니다.

`related_name='my_auctions': `user.my_auctions.all()` 이라고 입력하면, 올린 내용 다 나옵니다.

> blank=True, null=True: 비워두기 가능

`PositiveIntegerField:`
**음수 금지.** 실수로라도 마이너스 금액이 들어오는 걸 DB 차원에서 막습니다.

`bid_unit = models.PositiveIntegerField(default=1000)` : 최소 1,000원 단위로 입찰하세요. 1원씩 올려서 장난치는 걸 방지합니다.

'ManyToManyField'(다대다) : 한 사람이 여러 물건을 찜할 수 있고, 한 물건을 여러 사람이 찜할 수 있다

'choices' : **사전처럼 (key-value) 값이라서 2개씩 짝지어진 튜플이어야 한다.**

`verbose_name` : 사람이 보는 이름. (DB에서 보는 이름과 구분하기위함)


`bidder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bids')`
ForeignKey 괄호 안에 적힌 모델(User)이 **'일(1)'**
           코드가 적힌 곳(Bid)이 **'다(N)'**입니다.


---

2. `class Bid(models.Model):`



---

3. `class Comment(models.Model):`