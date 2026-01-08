## 시리얼라이저(Serializer)는 "통역사"입니다.

우리가 파이썬(Python)으로 만든 Order 객체(데이터)는 파이썬만 이해할 수 있는 형태입니다. 하지만 웹 세상(프론트엔드, 모바일 앱 등)은 JSON이라는 공용어를 사용합니다.

파이썬 객체: Order(id=1, status='배달중', ...) -> 파이썬만 아는 언어
JSON: {"id": 1, "status": "배달중"} -> 웹 세상의 공용어
시리얼라이저는 파이썬 객체를 JSON으로 **번역(직렬화)**해주고, 반대로 JSON 데이터를 받아서 파이썬 객체로 **해석(역직렬화)**해주는 역할을 합니다.

```
class OrderV1Serializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = '__all__'
```

> model = Order:

 "내가 번역할 대상(교과서)은 Order라는 모델이야"라고 지정해줍니다.

> fields = '__all__':

 모델에 있는 모든 필드를 다 번역해서 보여줘 라는 뜻입니다.

 ---

 ## v2 시리얼라이저

 ```
 class OrderV2Serializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'restaurant_name', 'status', 'created_at', 'version', 'restaurant', 'rider']
```
> fields를 명시적으로 지정했습니다. (V1의 __all__과 대조됨)

`read_only_fields ['id', 'created_at', 'version']:` 이 필드들은 사용자가 절대로 건드려서는 안 되는 값들입니다. API로 데이터를 입력받을 때 이 값들이 들어오더라도 무시합니다. 
특히 version은 시스템이 자동으로 관리해야 하므로 읽기 전용이어야 합니다.


```
Empty Serializers (Pass):
OrderAcceptanceSerializer (접수), OrderPreparationCompleteSerializer (조리완료) 
```
**"입력받을 데이터는 없지만, 이 행동을 한다는 것 자체가 명세에 남아야 한다"** 는 의미입니다.
빈 클래스(pass)로 둠으로써, API 문서 자동화 도구가 "이 API는 바디(Body)가 필요 없구나"라고 인식하게 합니다.

>코드를 실행하는 데는 아무 기능이 없지만, 자동 생성되는 문서(사용 설명서)를 깔끔하고 명확하게 만들기 위한 "이름표" 같은 것입니다. "실수로 >뺀 게 아니라, 원래 입력값이 없는 거야"라고 알려주는 것입니다.

- 클라이언트 (웹/앱): JSON을 사용합니다.
>웹 브라우저나 앱은 파이썬을 모릅니다. 그래서 전 세계 공용어인 JSON({"name": "치킨"})으로 데이터를 포장해서 서버에 보냅니다.

- 서버 (Django): Python 객체를 사용합니다.

받을 때: 클라이언트가 보낸 JSON을 받아서 Serializer가 Python 데이터로 번역해 줍니다.
일할 때: Django 내부 로직은 전부 Python(order.name = "치킨")으로 돌아갑니다.
보낼 때: DB에 저장할 때는 Python 데이터를 SQL로 번역해서 DB에 명령을 내립니다.

- 데이터베이스 (DB): **Raw Data (행/열)**를 저장합니다.

- DB는 기본적으로 JSON이나 파이썬 객체를 그대로 저장하는 게 아니라, 엑셀 표처럼 **테이블(Table)의 행(Row)**으로 쪼개서 저장합니다.

>(참고: JSONField 같은 특수 기능을 쓰면 텍스트 형태의 JSON을 통째로 저장하기도 하지만, 기본 원칙은 구조화된 데이터입니다.)

> [클라이언트] --(JSON)--> [서버/Serializer] --(Python)--> [서버/Model] --(SQL)--> [DB]