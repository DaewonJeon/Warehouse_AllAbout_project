common/ models.py

- from django.db import models
우리가 만드는 클래스(class Region(models.Model))가 단순한 파이썬 클래스가 아니라, 데이터베이스 테이블이 되도록 변신시켜 줍니다.

- from django.conf import settings
Django는 "회원 모델이 누구냐?"를 settings.py에 AUTH_USER_MODEL = 'users.User'라고 정의해 두는 것을 권장합니다.

- class Region
parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='sub_regions')
<자신을 가리키는 외래키 (Self-Referencing ForeignKey)" 입니다. 이것이 필요한 이유는 **'지역'이 계층 구조(트리 구조)**로 되어 있기 때문입니다.>

- class category
**"사용자 경험(UX)"**과 **"검색 엔진 최적화(SEO)"**
slug (인터넷용 별명)  **인터넷 주소창(URL)**에 들어가기 위해 만든 별명입니다.
Auction 모델, views.py

- Auto increment
자동으로 장고가 알아서 추가해줌. `id` 라는 필드는 장고 자체에서 하드코딩 되어있다.
따로 숫자가 아닌 문자로도 가능

- 보안고려측면 uuid
id = models.UUIDField(primary_key=True

- 실무에선 uuid, Auto increment 뭐 많이 쓰나
1위 Auto increment
성능 최고: 데이터베이스가 숫자를 다루는 게 가장 빠릅니다 (검색, 정렬 속도).
예측 가능함(보안 이슈): 단점 

2위 UUID 보안관점에서 유리 (급부상중인 것 )

- **+ slug 를 쓰는 이유**
slug 는 DB에서 데이터를 넣을때 URL 로 연결시켜주는데
파일이나 url 은 공백이 안되므로, 사람들이 많이 사용하는 이름들에서
미리 오류를 방지하기 위해 Slug를 사용함


- class Notification
경매 시스템에서 사용자 경험(UX)을 결정짓는 핵심 기능인 '알림 시스템'의 데이터베이스 설계도
`recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')`

`settings.AUTH_USER_MODEL` : users 앱에서 커스텀 유저 모델을 만들었기 때문에 settings.py에서 AUTH_USER_MODEL = 'users.User'로 설정했습니다.

`.CASCADE` : 회원이 없는데 "낙찰되었습니다"라는 쪽지만 DB에 남아있으면 용량 낭비(연쇄삭제) 
> <탈퇴시에도 DB가 남아있는게 맞을것 같다는 생각이 든다.>

`related_name=notifications` : 역참조 별명 / 코드에서 user.notifications.all()이라고 치면, "이 유저한테 온 모든 알림을 가져와!" 라고 아주 쉽게 명령할 수 있게 해줍니다

`class Meta (정렬 규칙)` <클래스 안에 클래스 (정렬)>
class Meta:
- ordering = ['-created_at']
> 역할: DB에서 알림을 꺼낼 때 무조건 최신순으로 정렬해서 가져옵니다.

> 이유: 알림창을 열었는데 1년 전 알림부터 보이면 안 되니까요. -(마이너스)가 붙으면 **내림차순(최신순)**을 의미합니다.