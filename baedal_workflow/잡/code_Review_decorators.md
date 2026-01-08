### 
```
def idempotent(func):
    @functools.wraps(func)
    def wrapper(view_set, request, *args, **kwargs):
```

> @functools.wraps(func): 매우 중요합니다. 이걸 안 쓰면 디버깅할 때 함수 이름이 죄다 wrapper로 나와서 지옥을 맛보게 됩니다. 원본 함수의 > 정체성을 유지시켜 줍니다.

### 캐싱된 응답 확인

```
existing_key = IdempotencyKey.objects.filter(key=uuid_key).first()
if existing_key:
    return Response(existing_key.response_body, status=existing_key.response_status)
```
> 이미 처리된 키가 발견되는 순간, 실제 비즈니스 로직(func)을 아예 실행하지 않습니다.
> DB에 저장해뒀던 "과거의 성공 결과"를 그대로 꺼내서 리턴합니다

### 실제 로직 실행 및 결과 저장

```
response = func(view_set, request, *args, **kwargs) # 실제 로직 실행(결제 등)
if 200 <= response.status_code < 300:
    IdempotencyKey.objects.create(...)
```
> 실패(4xx, 5xx)한 요청은 재시도했을 때 성공할 수도 있습니다. (예: 잔액 부족으로 실패했다가 입금 후 다시 시도). 따라서 실패는 기억하지 
> 않고, 성공한 건들만 "이미 성공했음"이라고 대못을 박아두는 전략입니다.

앞으로  decorators 를 만들어두었으므로 
`@idempotent` 를 통해 결제처리할때 멱등성을 바로 부여할 수 있게 되었습니다

def idempotent() 한 번만 만들어 두면, 이제 수십, 수백 개의 함수 위에 @idempotent만 붙여서 똑같은 기능(중복 방지)을 적용 가능합니다.

`if 200 <= response.status_code < 300:`   
> HTTP 상태 코드에서 200번대(200 OK, 201 Created 등)는 무조건 **"성공"**을 의미합니다.
> 반대로 400(잘못된 요청)이나 500(서버 에러)은 실패입니다.
> 의도: "에러가 난 요청은 기억하지 않겠다. 오직 성공적으로 처리된 요청만 기억하겠다.