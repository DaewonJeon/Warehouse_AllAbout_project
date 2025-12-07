🚛 Logis-Flow: 대용량 데이터베이스 정규화 vs 비정규화 성능 최적화
#### <문제상황 가정>
- Logis-Flow는 화주와 운송사에게 실시간 화물 위치와 상태 정보를 제공하는 SaaS 솔루션 서비스 
- 데이터 무결성을 위해 **제3정규형**을 준수하여 설계
- 데이터가 급증함에 따라 대시보드 로딩 속도가 심각하게 저하되는 병목 현상이 발생

#### 핵심 병목 (Bottleneck)

- 화물 1건당 수십 건의 상태 변경 로그가 존재. 
- 특정 화물의 '가장 최신 로그' 1건을 찾기 위해 서브쿼리 내에서 ORDER BY timestamp DESC LIMIT 1 연산이 매 행(Row)마다 발생.

#### <Tech_Stack>

    Language: Python 3.9

    Database: MySQL 8.0

    Tools: MySQL Workbench, Faker Library

    Data 
        - Shipments: 50,000 Rows (화물)
        - Shipment_Updates: 500,000 Rows (상태 변경 로그)


#### 성능 비교 및 해결 과정 
**정규화 모델 (Before)**

가장 최신의 상태를 가져오기 위해, 매 행마다 로그 테이블을 풀 스캔(Full Scan)
 
**비정규화 적용 (Solution)**

- 읽기(Read) 성능을 위해 쓰기(Write) 비용을 희생하는 비정규화를 채택 
- Shipments 테이블에 중복 데이터(current_status, last_updated_at)를 저장할 컬럼을 추가
- 데이터 마이그레이션을 수행


#### 결과 및 트레이드오프 분석 (Result & Trade-offs)

정규화 (Normalization)
> -조회 속도 (Latency) : 23.64s (서비스 불가 수준)
-쿼리 복잡도	상 (Subquery/Group By 필수)
-데이터 정합성 중복 없음
-관리 포인트	로그만 적재하면 끝	

비정규화 (Denormalization)
> -조회 속도 (Latency) : 0.01s (실시간 응답)
-쿼리 복잡도	하 (Simple Select)
-데이터 정합성 위험 (중복 존재)
-상태 변경 시 두 테이블 동시 업데이트 필수


#### 결론  "모든 상황에 비정규화가 정답은 아니다."

- 이번 프로젝트를 통해 대시보드와 같이 조회(Read) 빈도가 압도적으로 높은 기능에서는 데이터 중복을 허용하더라도 조회 성능을 최적화하는 것이 사용자 경험(UX)에 필수적임을 확인
- 단, 비정규화 적용 시 발생할 수 있는 데이터 불일치(Data Inconsistency) 문제를 방지하기 위해, 애플리케이션 레벨에서의 트랜잭션(Transaction) 관리가 더욱 중요해짐을 배움

#### 확장성



