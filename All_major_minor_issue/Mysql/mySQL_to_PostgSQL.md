### MySQL to PostgreSQL 마이그레이션 기술 리포트

#### 1. 핵심 문제점: 인코딩(Encoding) 에러
왜 PostgreSQL 서버 인코딩이 `UTF-8`인데, `EUC-KR`로 인코딩된 CSV 파일이 깨지지 않고 잘 들어갔는가?

> **핵심**
> PostgreSQL 서버 자체는 UTF-8이지만, 클라이언트(psql)가 'EUC-KR 파일을 읽어서 → 전송 단계에서 UTF-8로 자동 변환'하여 서버에 넘겨주었기 때문에
---

#### 2. DDL 문법 마이그레이션
MySQL에서 작성된 스키마(DDL)를 PostgreSQL에 적용하기 위해 수정해야 할 필수 변경 사항 2가지입니다.

##### 기본 키 자동 증가 (Auto Increment)
MySQL의 `AUTO_INCREMENT` 키워드는 PostgreSQL에 존재하지 않습니다. 대신 `SERIAL` 을 사용하여 시퀀스(Sequence)를 생성해야 합니다.

**MySQL**  `id INT AUTO_INCREMENT`  테이블에 종속적인 자동 증가 설정 
**PostgreSQL**  `id SERIAL`  내부적으로 `SEQUENCE` 객체를 생성하여 연결 

```sql
-- [MySQL]
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,  -- (X) PostgreSQL에서 에러 발생
    name VARCHAR(100)
);

-- [PostgreSQL]
CREATE TABLE users (
    id SERIAL PRIMARY KEY,              -- (O) 정상 동작
    name VARCHAR(100)
);
```