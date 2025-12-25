### 경매 테이블 구조
<img src="/NeighborBid_Auction_Service/images/database_1차.png" width="100%">

### 테이블 설계 
1. Domain-Driven Design (DDD) / 비즈니스 로직을 중심으로 설계
> 추후 확장성~고려해

2. User / Wallet 분리(1:1)
> 결제시스템 실제로 도입시 분리.

3. `is_national` 필드 하나로 동네거래 / 실시간 두가지 분리.
> ..

4. 정규화 (3정규형)
- Auction.current_price : Bid테이블 다 뒤져서 max값 계산하지 않고 조회속도 증가를 위해 경매테이블에 값 복사 (read 최적화)

5. region 계층 구조 설계 
> 깊이가 깊어질 시 조회가 느려질 가능성 존재

6. 트랜잭션 설계 (Escrow Pattern)
- 에스크로 보증금 패턴
- 변경이력 event log 남기기 위함

7. 최적화 
- 인덱싱 (Indexing): Auction(Region, Status)
처럼 자주 검색하는 필드에 복합 인덱스를 걸어야 합니다.
- Redis 활용: 현재가(current_price) 갱신이 1초에 100번 일어나는 '핫딜'의 경우, 매번 DB에 쓰지 말고 Redis에서 카운팅하다가 나중에 한 번만 저장하는 Write-Behind 전략이 필요합니다.
- 샤딩 (Sharding): Transaction
테이블은 무한히 커지므로, 월별로 테이블을 쪼개는 파티셔닝이 필요합니다.

---


- **Common (공통 기초)**
    - Region: 동네/지역 정보 (서울 > 강남구 > 역삼동)
    - Category: 경매 물품 카테고리 (디지털, 가구 등)
    - Notification: 사용자 알림 메시지

- **Users (회원 관리)**
    - User: 회원 정보 (아이디, 닉네임, 사는 곳, 평판)
    - Review: 거래 후기 (별점 1~5점)

- **Wallet (금융/결제)**
    - Wallet: 개인 지갑 (현재 잔액 vs 묶인 돈)
    - Transaction: 모든 입출금/결제 거래 장부

- **Auctions (경매 비즈니스)**
    - Auction: 경매 물품 메인 정보
    - Bid: 입찰 내역 (금액, 시간)
    - Comment: 문의 댓글 (Q&A)
