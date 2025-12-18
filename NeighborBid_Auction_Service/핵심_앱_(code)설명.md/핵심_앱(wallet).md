# 📂 Wallet App Structure & Logic

경매 시스템에서 가장 중요한 **자산(돈)의 흐름과 기록**을 담당하는 `wallet` 앱의 핵심 로직입니다.

---

## 1. 데이터 구조 및 핵심 로직 (Models) 💰
`wallet` 앱의 심장부로, 사용자의 잔액 관리와 거래 내역 기록을 담당합니다.

### `models.py`
* **`Wallet` 모델 (지갑)**
    * **[핵심] `locked_balance` (입찰 잠금액)**: 단순히 잔액(`balance`)만 관리하는 것이 아니라, 경매에 입찰하는 순간 돈을 묶어두는 필드입니다.
        * 이 기능 덕분에 사용자가 같은 돈으로 여러 경매에 동시에 입찰하는 **이중 지출(Double Spending)을 방지**할 수 있습니다.
    * **`balance`**: 현재 즉시 사용 가능한 잔액입니다.
    * **`user`**: `OneToOneField`를 사용하여 회원 1명당 딱 1개의 지갑만 가지도록 강제합니다.

* **`Transaction` 모델 (거래 내역)**
    * **금융 로그(Financial Log)** 역할을 합니다. 돈이 움직이는 모든 순간을 기록하여 나중에 문제가 생겼을 때 추적할 수 있게 합니다.
    * **`transaction_type`**: 돈이 움직인 '이유'를 명확히 정의합니다.
        * `BID_LOCK`: 입찰 시 자금 잠금
        * `BID_REFUND`: 상위 입찰 발생 시 환불
        * `PAYMENT`: 낙찰 후 실제 결제
        * `EARNING`: 판매 수익
    * **`amount`**: 양수(+)는 입금, 음수(-)는 출금을 의미하여 계산을 단순화합니다.

---

## 2. 관리자 페이지 설정 (Admin) 🛠️
금융 데이터는 민감하기 때문에 관리자가 데이터를 함부로 조작하지 못하도록 안전장치를 걸어둔 설정입니다.

### `admin.py`
* **`TransactionInline` 클래스**
    * **[핵심] 데이터 무결성 보호**: `can_delete = False` 옵션을 설정하여, 관리자라도 거래 내역(로그)을 함부로 **삭제할 수 없도록** 막았습니다. 거래 내역은 증거 자료이므로 보존되어야 하기 때문입니다.
    * **`readonly_fields`**: 거래 유형, 금액 등 중요한 정보는 수정조차 불가능하게 '읽기 전용'으로 설정했습니다.
* **`WalletAdmin` 클래스**
    * **`inlines`**: 지갑 정보를 볼 때, 해당 지갑에서 발생한 모든 `Transaction` 내역을 한 페이지에서 리스트로 볼 수 있게 연결했습니다.

---

## 3. 앱 설정 (Configuration) ⚙️

### `apps.py`
* **`WalletConfig`**: Django 프로젝트 내에서 이 앱의 이름을 `wallet`으로 등록하고, 기본 키(PK) 필드 타입을 설정합니다.

---

## 4. 아직 비어있는 파일들 (Empty Files) 📝
현재 기능 구현이 되어 있지 않은 파일들입니다. 추후 개발이 필요할 수 있습니다.

* **`views.py`**: 현재 비어있습니다.
    * *추후 제안*: 지갑 충전 페이지, 내 거래 내역 조회 페이지 등의 로직이 이곳에 들어갈 수 있습니다.
* **`tests.py`**: 현재 비어있습니다.
    * *추후 제안*: 입찰 시 `locked_balance`가 제대로 잠기는지, 환불 시 다시 `balance`로 돌아오는지 검증하는 테스트 코드가 필요합니다.

---

## 💡 요약: 자금 흐름 로직

이 앱은 코드는 짧지만 시스템의 **안전성**을 담당합니다.

1. **입찰 시**: `Wallet`의 `balance` 감소 ➡ `locked_balance` 증가 ➡ `Transaction` (BID_LOCK) 생성
2. **환불 시**: `Wallet`의 `locked_balance` 감소 ➡ `balance` 증가 ➡ `Transaction` (BID_REFUND) 생성
3. **낙찰 시**: `Wallet`의 `locked_balance` 차감(소멸) ➡ 판매자 `balance` 증가 ➡ `Transaction` (PAYMENT/EARNING) 생성