# Users App Structure & Logic

단순한 로그인/회원가입을 넘어, **신뢰 기반의 거래 환경(평판 시스템)**과 **금융 연동(지갑 생성)**을 시작하는 `users` 앱의 로직입니다.

---

## 1. 데이터 구조 (Models) 
Django의 기본 유저 모델을 확장하여 프로젝트에 필요한 지역 정보와 신뢰도 지표를 추가했습니다.

### `models.py`
* **`User` 모델 (커스텀 유저)**
    * **`AbstractUser` 상속**: Django가 제공하는 강력한 인증 시스템(로그인, 비번 암호화 등)을 그대로 쓰면서 필드만 추가했습니다.
    * **`region`**: `common` 앱의 `Region` 모델과 연결됩니다. 사용자가 사는 곳을 저장하여 지역 기반 경매의 기준점이 됩니다.
    * **`reputation_score`**: 판매자의 신용 점수(0~100점)입니다. 후기를 받을 때마다 변동되며, 구매자가 믿을만한 판매자인지 판단하는 척도가 됩니다.

* **`Review` 모델 (거래 후기)**
    * **`OneToOneField(Auction)`**: 경매 물품 하나당 후기는 딱 1개만 남길 수 있도록 제한합니다. (중복 후기 방지)
    * **`rating`**: 1점에서 5점 사이의 별점을 저장합니다.

---

## 2. 핵심 비즈니스 로직 (Views) 🧠
사용자의 행동에 따라 데이터가 어떻게 변하는지 처리하는 로직입니다.

### `views.py`
* **`signup(request)` (회원가입)**
    * **[핵심] 지갑 자동 생성**: 회원가입 성공 시점(`form.save()`)에 맞춰 `Wallet.objects.create(user=user, balance=0)`를 호출합니다.
        * 유저가 별도로 "지갑 만들기" 버튼을 누를 필요 없이, 가입 즉시 경매에 참여할 준비를 마치는 중요한 UX/로직 처리입니다.
* **`create_review(request, auction_id)` (후기 작성)**
    * **보안 검사 (Validation)**:
        1. 실제 낙찰자(`last_bid.bidder`)가 맞는지 확인합니다.
        2. 이미 후기를 작성했는지(`hasattr`) 확인하여 중복 작성을 막습니다.
    * **[핵심] 평판 점수 업데이트**:
        * 리뷰가 저장되면, 해당 판매자의 모든 리뷰 평점 평균(`Avg`)을 다시 계산합니다.
        * 평균 점수를 100점 만점으로 환산하여 판매자의 `reputation_score`에 즉시 반영합니다. (실시간 신용도 갱신)
* **`seller_profile`**: 판매자의 판매 물품을 '진행 중'과 '종료됨'으로 나누어 보여줍니다.

---

## 3. 입력 폼 (Forms) 📝

### `forms.py`
* **`RegisterForm`**: `UserCreationForm`을 상속받아 비밀번호 확인 로직은 그대로 쓰고, 닉네임과 지역(`region`) 입력을 추가했습니다.
* **`ReviewForm`**: 별점과 내용을 입력받습니다.

---

## 4. 관리자 및 URL 설정 (Admin & URL) ⚙️

### `admin.py`
* **`CustomUserAdmin`**: Django 관리자 페이지에서 기본 유저 정보 외에 우리가 추가한 `nickname`, `reputation_score`를 볼 수 있도록 `fieldsets`를 확장했습니다.

### `urls.py`
* **`auth_views`**: 로그인(`LoginView`), 로그아웃(`LogoutView`)은 별도 구현 없이 Django 내장 뷰를 사용하여 보안성을 챙겼습니다.

---

## 💡 요약: 유기적 연결성

이 앱은 독립적으로 존재하지 않고 다른 앱들과 강하게 연결되어 있습니다.

1.  **Users ↔ Wallet**: `signup` 뷰에서 **지갑(Wallet)을 생성**합니다. (회원가입 = 계좌개설)
2.  **Users ↔ Common**: `User` 모델이 **지역(Region)을 참조**합니다. (거주지 기반 필터링의 근거)
3.  **Users ↔ Auctions**: `Review` 시스템이 경매 완료 후 **신용도(Reputation)를 갱신**합니다. (거래 종료 -> 평가 -> 신뢰도 상승의 선순환)