##  `auctions` 앱 Structure & Logic

> **Django 경매 프로젝트의 핵심 기능인 auctions 앱의 파일 구조와 로직 설명입니다.**

---

## 1. 핵심 비즈니스 로직 (Core Logic) 🧠
이 앱의 **'두뇌'** 역할을 하는 파일들입니다. 특히 결제, 환불, 정산 등 돈과 관련된 중요한 처리가 이곳에 모여 있습니다.

### `services.py` (비즈니스 로직 담당)
View나 Consumer에서 호출하는 실질적인 경매 처리 함수 모음입니다. **트랜잭션(Transaction)** 처리가 가장 중요한 부분입니다.

* **`place_bid(auction_id, user, amount)`**
    * **[핵심]** 입찰을 수행하는 메인 함수입니다.
    * `transaction.atomic()` & `select_for_update()`: 동시에 여러 명이 입찰해도 데이터가 꼬이지 않도록 **DB Lock**을 겁니다.
    * **환불 로직**: 더 높은 금액이 입찰되면, 이전 1등 입찰자의 `locked_balance`(묶인 돈)를 `balance`(사용 가능 잔액)로 즉시 반환합니다.
    * **자금 잠금**: 새 입찰자의 돈을 지갑에서 차감하고 `locked_balance`로 이동시킵니다.
* **`determine_winner(auction_id)`**
    * 경매 종료 시 정산을 처리합니다.
    * 낙찰자의 묶인 돈을 차감하고, 판매자의 지갑에 수익금을 입금하며 `Transaction` 기록을 생성합니다.
    * 입찰자가 없으면 유찰 처리합니다.
* **`buy_now(auction_id, buyer)`**
    * 즉시 구매 기능입니다.
    * **자금 검증**: 사용자의 잔액 + (본인이 이미 1등 입찰자인 경우) 묶인 돈까지 합쳐서 구매 능력을 검증합니다.
    * 검증 통과 시 기존 입찰자들을 모두 환불해주고, 즉시 거래를 성사시킵니다.

---

## 2. 실시간 통신 (Websocket) ⚡
페이지 새로고침 없이 경매 입찰과 정보 업데이트가 실시간으로 진행되도록 하는 부분입니다.

### `consumers.py` (웹소켓 핸들러)
Django View가 HTTP 요청을 처리하듯, 웹소켓 연결을 처리합니다.

* **`connect`**
    * 사용자가 경매방(`ws/auction/1/`)에 입장하면 해당 채널 그룹(Group)에 추가합니다.
* **`receive`**
    * **[핵심]** 사용자가 입찰 버튼을 눌렀을 때(JS 전송) 실행됩니다.
    * `save_bid`: 동기 함수인 `services.place_bid`를 비동기 환경에서 실행하여 DB에 저장합니다.
    * `group_send`: 입찰 성공 시, 같은 방에 있는 **모든 사람**에게 "새 입찰 발생(금액, 입찰자)" 메시지를 방송(Broadcast)합니다.
* **`auction_update`**
    * `group_send`로 받은 메시지를 실제 사용자의 브라우저(JSON)로 전송합니다.

### `routing.py` (웹소켓 URL)
* `ws/auction/(?P<auction_id>\d+)/$`: 사용자가 이 주소로 웹소켓 연결을 요청하면 `consumers.AuctionConsumer`로 연결해줍니다. (Django의 `urls.py`와 동일한 역할)

---

## 3. 데이터 구조 (Model) 🗄️
데이터베이스 테이블 스키마 정의입니다.

### `models.py`
* **`Auction`**: 경매 물품 정보
    * `is_national`: 전국 경매(웹소켓 사용)인지 지역 한정 경매인지 구분
    * `start_price`, `current_price`, `instant_price`: 가격 정보
    * `watchers`: 찜하기 기능을 위한 User와의 M:N 관계
* **`Bid`**: 입찰 기록 (누가, 언제, 얼마에 입찰했는지 저장)
* **`Comment`**: 경매 물품에 달린 댓글 및 문의사항

---

## 4. 웹 인터페이스 (View & URL) 🌐
사용자가 웹 브라우저를 통해 보는 페이지 렌더링과 HTTP 요청을 처리합니다.

### `views.py` (HTTP 요청 처리)
* **`auction_list`**: 경매 목록 조회
    * `get_all_descendants`: **[핵심]** 재귀 함수를 사용하여 선택한 지역의 모든 하위 지역(구, 동 등)을 찾아 필터링합니다.
    * 카테고리, 가격 범위, 정렬 등 다양한 필터 로직 포함.
* **`auction_detail`**: 상세 페이지
    * `POST` 요청 시 `place_bid` 서비스를 호출하여 입찰을 시도하고 결과를 메시지로 반환.
* **`mypage`**: 내 입찰 내역, 내가 올린 경매, 지갑 잔액 확인.
* **`auction_create`**: `AuctionForm`을 이용해 새 경매 생성.
* **`close_auction`, `auction_buy_now`**: 버튼 클릭 시 `services.py`의 함수를 실행하고 리다이렉트.

### `forms.py` (입력 폼)
* **`AuctionForm`**: 경매 등록 시 입력받을 필드, 위젯(CSS 스타일), 라벨 정의 (`is_national` 체크박스 등).
* **`CommentForm`**: 댓글 입력 폼.

### `urls.py` (URL 연결)
* 브라우저 주소창의 URL(예: `/auction/1/`)을 `views.py`의 함수와 매핑합니다.

### `admin.py` (관리자 페이지)
* Django 관리자 페이지(`admin/`)에서 `Auction` 모델을 쉽게 관리할 수 있도록 설정합니다.

---

## 5. 기타 설정 ⚙️
* **`apps.py`**: Auctions 앱 설정 파일.
* **`tests.py`**: 테스트 코드 작성 파일 (현재 비어있음).

---

## 💡 요약: 데이터 흐름 예시

### 1. 사용자 입찰 (웹소켓 / 전국 경매)
> **`routing.py`** (주소 확인) ➡ **`consumers.py`** (메시지 수신) ➡ **`services.py`** (돈 계산 및 DB 잠금/저장) ➡ **`consumers.py`** (결과를 모든 참여자에게 방송)

### 2. 사용자 입찰 (일반 HTTP / 지역 경매)
> **`urls.py`** (주소 확인) ➡ **`views.py`** (요청 확인) ➡ **`services.py`** (돈 계산 및 DB 저장) ➡ **`views.py`** (결과 메시지와 함께 페이지 새로고침)