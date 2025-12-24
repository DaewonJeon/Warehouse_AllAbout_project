users / models.py

`from django.contrib.auth.models import AbstractUser` : 장고가 미리 만들어둔 '이미 완벽한 기본회원(AbstractUser)' 설계도를 가져와라'

`from common.models import Region` : common 앱에 있는 models.py 파일에서 Region 클래스를 가져온다 (User 클래스에 정보 넣기위해) (users 앱과 common 앱 사이 관계 생겨납니다)

**class User(AbstractUser):**

 `nickname = models.CharField(max_length=50, blank=True, null=True)` : blank=True, null=True 입력안해도 상관없다

 `reputation_score (신용 점수)` : default=0: 처음 가입한 사람은 0점부터 시작합니다.

 `related_name='residents'` : 역참조 별명 > common models 코드리뷰 참고


**class Review(models.Model):

`OneToOneField (일대일 관계)` : **"경매 물건 하나당 리뷰는 딱 하나만 쓸 수 있다"**는 강력한 규칙입니다. 도배를 시스템적으로 차단 
> models 안에 기본적으로 포함되어 있는 표준 필드
- ex) ForeignKey를 썼다면? (다대일 관계) : 악플 차단 불가능. **부모 하나에 자식 여러 명**이 매달릴 수 있는 관계 한명의 사용자가 여러 악플 도배 가능.

`rating (별점)` : 별점주기

