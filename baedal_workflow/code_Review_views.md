
```
def get_etag(self, order):
        # ETag 생성 로직: "order-{id}-v{version}"의 해시
        raw_data = f"order-{order.id}-v{order.version}"
        return hashlib.md5(raw_data.encode()).hexdigest()
```
> get_etag : 주문 정보를 암호문(해시)으로 바꿉니다.
> "order-1-v2" -> "a1b2c3..."
> 버전(v2)이 바뀌면 암호문도 바뀝니다.

`hashlib.md5` :

> hashlib.md5는 데이터를 **"짧고 고유한 식별표(지문)"**로 압축해서, 
> 버전 관리를 쉽고 빠르고 안전하게 하기 위해 쓴 것입니다.

### N+1 Resolve

```
# N+1 문제 해결을 위해 select_related 사용
        if 'restaurant' in include_params and 'rider' in include_params:
            queryset = queryset.select_related('restaurant', 'rider')
        elif 'restaurant' in include_params:
            queryset = queryset.select_related('restaurant')
        elif 'rider' in include_params:
            queryset = queryset.select_related('rider')
```
> 해당 코드가 없을 때는, 주문 10개 가져올 때 식당 정보 가져오려고
> DB를 10번 더 찔러야 합니다. (1번 + 10번 = 11번 쿼리)
> select_related를 통해, SQL의 JOIN 문법을 사용해서
> **"주문 가져오는 김에 식당 정보도 옆에 붙여서 딱 1번만 가져와!"**라고 명령합니다.


### 사이드 로딩 고려

> 같은 곳에서 주문을 100번 시켰는데, 식당 이름/주소를 100번이나 보내는 건 낭비니까, "주문 목록"과 "식당 목록"을 분리해서 보내주는 >기술입니다.

```
 if 'rider' in include_params:
                rider_ids = set()
                riders = []
                for order in (page if page else queryset):
                     if order.rider and order.rider.id not in rider_ids:
                         rider_ids.add(order.rider.id)
                         riders.append({
                             "id": order.rider.id,
                             "name": order.rider.name
                         })
                included['riders'] = riders
                        
```


if - match

`status.HTTP_400_BAD_REQUEST == 400`
> If-Match라는 필수 헤더를 안 보냈을 때 에러입니다.

`HTTP_412_PRECONDITION_FAILED`
> 낙관적 락(Optimistic Lock) 알리는 코드입니다. 클라이언트는 412 에러를 받으면 "누군가 수정했구나. 다시 조회해서 재시도해야겠다"라고 판단합니다.

## 앞으로 리펙토링 해야할 코드 아직(미완) 

>  정의만 되어 있고 호출되는 곳이 없습니다. save 도 각함수내에서 함

```
    def perform_action_with_locking(self, request, action_func):
        order = self.get_object()
        
        # Optimistic Locking Check
        is_valid, error_response = self.check_etag(request, order)
        if not is_valid:
            return error_response
            
        response = action_func(request, order)
        
        # 상태가 변경되었다면 버전 증가 및 저장 (action_func 내부에서 save() 하지 말고 여기서 처리)
        # 하지만 action_func 내부 로직이 복잡할 수 있으니, 
        # action_func에서 business logic만 수행하고 여기서 save하는 패턴으로 리팩토링합니다.
        # 또는 action_func에서 save() 하고 버전을 증가시킵니다.
        
        return response
```

###  이후 코드들 @idempotent

```
 @idempotent
    @action(detail=True, methods=['post'], url_path='payment')
    def payment(self, request, pk=None):
        order = self.get_object()
        
        # ETag Check
        is_valid, error_response = self.check_etag(request, order)
        if not is_valid: return error_response

        if order.status != Order.Status.PENDING_PAYMENT:
            return Response({"error": "Invalid state"}, status=status.HTTP_400_BAD_REQUEST)
            
        order.status = Order.Status.PENDING_ACCEPTANCE
        # 버전 증가
        order.version += 1
        time.sleep(0.5)
        order.save()
        
        response = Response(OrderV2Serializer(order).data)
        response['ETag'] = f'"{self.get_etag(order)}"'
        return response
```

- @idempotent: 1차 방어선 <멱등성 고려>

- `if not is_valid: return error_response` : 2차 방어선 <낙관적 락 (동시성 고려)>

- `if order.status != Order.Status.PENDING_PAYMENT` : 3차 방어선 <상태 고려>


`response['ETag'] = f'"{self.get_etag(order)}"'` : 다음 etag 발급 