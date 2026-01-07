N+1 문제를 해결한다"는 주석은 **"N+1 문제를 해결하기 위한 토대(Relationship)를 만든다"**는 의미입니다.

구체적인 근거와 이유는 다음과 같습니다:

ForeignKey는 '길'을 만드는 역할입니다.

만약 restaurant = models.ForeignKey(...)가 아니라 restaurant_id = models.IntegerField()로 저장했다면, Django는 이것이 '식당'인지 단순히 숫자인지 모릅니다.
이 경우, 주문 목록을 가져올 때 식당 정보를 알기 위해 매번 Restaurant.objects.get(id=...)를 따로 호출해야 하며, 이것이 바로 N+1 문제입니다.

ForeignKey로 관계를 맺어주었기 때문에, 나중에 뷰(View)나 로직에서 Order.objects.select_related('restaurant')를 사용할 수 있습니다.
이 명령어는 "주문을 가져올 때 SQL JOIN을 사용해 식당 데이터도 한 번에 가져오라"는 뜻이며, 이것이 N+1 문제의 해결책입니다.


```
erDiagram
    RESTAURANT ||--o{ ORDER : "has (1 : N)"
    RIDER ||--o{ ORDER : "delivers (1 : N)"
    RESTAURANT {
        string name "맛있는 치킨집"
        string address
    }
    RIDER {
        string name "김라이더"
    }
    ORDER {
        int id
        string status
        FK restaurant_id "식당 참조"
        FK rider_id "라이더 참조"
    }
```

기존코드 남아있는이유

# 간단하게 구현하기 위해 레스토랑 정보 등은 생략하고 상태에 집중합니다.
    restaurant_name = models.CharField(max_length=100, default="맛있는 치킨집") # 기존 필드 유지 (V1 호환성)
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING_PAYMENT
    )


```
    restaurant_name이 계속 남아있는 이유
가장 큰 이유는 **"과도기적 호환성(V1 호환성)"**과 "데이터 스냅샷" 때문입니다.

V1 호환성 (리팩토링 전략):
기존 시스템(V1)은 복잡한 Restaurant 테이블 없이 단순히 주문에 restaurant_name 텍스트만 저장했을 수 있습니다.
시스템을 업그레이드한다고 해서 기존 데이터를 싹 다 지우거나, 기존 V1 API를 사용하는 앱들을 갑자기 중단시킬 수는 없습니다.
따라서 새로운 구조(Class Restaurant)를 도입하되, 당분간은 기존 필드(restaurant_name)도 남겨두어 에러를 방지하는 것입니다.
```

