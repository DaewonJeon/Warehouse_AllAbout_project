wallet / models.py

`class Wallet(models.Model)` : OneToOneField (일대일 관계) >> 사람 한 명당 지갑은 무조건 하나를 만족 해야합니다.

`DecimalField`: 돈은 FloatField(부동소수점)를 쓰면 계산 오차(100원이 99.999999원이 되는 현상)가 생길 수 있어서, 금융권에서는 정확한 계산을 위해 DecimalField

`decimal_places=0`: 1원 단위까지만 쓴다. (소수점 없음) <금융권의 표준>

**왜 IntegerField가 아니라 DecimalField인가?**
확장성과 금융 계산에서의 안정성 확보

`max_digits=12` : 정수 12자리까지 가능 
> 표기상 999,999,999,999원 까지 가능

- 자릿수를 과도하게 키우면 문제점:
인덱스 크기 증가
DB 저장 공간 낭비

`class Transaction` : **ForeignKey (다대일 관계) 사용** : 지갑 하나에는 수많은 거래 내역이 쌓이기 때문입니다.

- `TRANSACTION_TYPES` : '튜플(Tuple) 속의 튜플' 구조입니다.
```
TRANSACTION_TYPES = (
    ('실제값', '보여줄이름'),
    ('DEPOSIT', '충전'),
)
```
왼쪽 값 ('DEPOSIT'): 데이터베이스(DB)에 저장되는 값
오른쪽 값 ('충전'): 사람 눈에 보이는 이름입니다.

`TRANSACTION_TYPES`
**장고에서 `choices` 는 사전처럼 (key-value) 값이라서 2개씩 짝지어진 튜플이어야 한다.**


