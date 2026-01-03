# E-Commerce Crawler Project Summary

> **프로젝트 전체 버전별 개발 과정 및 기술적 의사결정 기록**  
> 버전: v0.9 ~ v2.1 (총 6개 버전)

---

## 📋 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [기술 스택 총괄](#2-기술-스택-총괄)
3. [버전별 개발 히스토리](#3-버전별-개발-히스토리)
   - [v0.9 - 동기식 크롤러 (Sync Bot)](#v09---동기식-크롤러-sync-bot)
   - [v1.0 - 비동기 크롤러 (Async Bot)](#v10---비동기-크롤러-async-bot)
   - [v1.1 - 최적화 및 안정성 강화](#v11---최적화-및-안정성-강화)
   - [v1.2 - 분산 처리 아키텍처 (Celery + Redis)](#v12---분산-처리-아키텍처-celery--redis)
   - [v2.0 - 무신사 크롤러 + OpenSearch 파이프라인](#v20---무신사-크롤러--opensearch-파이프라인)
   - [v2.1 - 검색 엔진 API 서비스 구축](#v21---검색-엔진-api-서비스-구축)
4. [핵심 문제 해결 로그](#4-핵심-문제-해결-로그)
5. [아키텍처 진화 과정](#5-아키텍처-진화-과정)
6. [회고 및 교훈](#6-회고-및-교훈)

---

## 1. 프로젝트 개요

### 1.1 프로젝트 배경
이커머스 플랫폼에서 **판매자 메타데이터**(상호, 사업자번호, 연락처 등)를 수집하여 분석하는 데이터 파이프라인 구축 프로젝트입니다.

### 1.2 개발 여정

> 쿠팡 (v0.9 ~ v1.1) → ip차단(vpn) → 무신사 (v2.0 ~ v2.1)


| 단계 | 타겟 플랫폼 | 버전 | 결과 |
|------|-------------|------|------|
| 초기 개발 | 쿠팡 | v0.9 ~ v1.1 | 봇 탐지 시스템에 의해 IP 차단 |
| 아키텍처 고도화 | Books to Scrape (Sandbox) | v1.2 | 분산 처리 시스템 검증 |
| 타겟 변경 | 무신사 | v2.0 ~ v2.1 | 검색 엔진 서비스 구축 성공 |

### 1.3 핵심 성과
- **속도 개선**: 5건당 50초(Sync) → 5초(Async) 
- **안정성**: CSV 파일 충돌 → SQLite Batch → OpenSearch Bulk Insert
- **확장성**: 단일 스크립트 → Django + Celery + Redis 분산 처리
- **서비스화**: ETL 파이프라인 + FastAPI REST API + 웹 프론트엔드

---

## 2. 기술 스택 총괄

### 2.1 버전별 기술 스택 진화

#### 🔹쿠팡 크롤러 (v0.9 ~ v1.2)

| 구분 | v0.9 | v1.0 | v1.1 | v1.2 |
|------|------|------|------|------|
| **실행 방식** | Sync | Async | Async | Async + Celery |
| **브라우저** | Playwright CDP | Playwright CDP | Playwright CDP | Playwright |
| **데이터 저장** | CSV | CSV + Lock | SQLite Batch | Django ORM |
| **메시지 브로커** | - | - | - | Redis |
| **웹 프레임워크** | - | - | - | Django |
| **컨테이너** | - | - | - | Docker (Redis) |

#### 🔹 무신사 크롤러 (v2.0 ~ v2.1)

| 구분 | v2.0 | v2.1 |
|------|------|------|
| **실행 방식** | Async | Async |
| **브라우저** | Playwright | Playwright |
| **데이터 저장** | OpenSearch | OpenSearch |
| **검색 엔진** | OpenSearch | OpenSearch |
| **웹 프레임워크** | - | FastAPI |
| **컨테이너** | Docker (OpenSearch) | Docker |

### 2.2 주요 라이브러리
```
# Core
playwright==1.56.0          # 브라우저 자동화
asyncio                      # 비동기 처리

# Backend Framework
Django==5.2.8               # 웹 프레임워크 (v1.2)
FastAPI                      # REST API (v2.1)
celery==5.5.3               # 분산 작업 큐 (v1.2)

# Database & Search
sqlite3                      # 로컬 DB (v1.1)
opensearch-py               # 검색 엔진 클라이언트 (v2.0+)
redis==7.1.0                # 메시지 브로커 (v1.2)

# Utilities
pandas                       # 데이터 처리
uvicorn                      # ASGI 서버
```

---

## 3. 버전별 개발 히스토리

---

### v0.9 - 동기식 크롤러 (Sync Bot)
```
`v0.9_sync_bot.py`
🔹목표
쿠팡 검색 결과에서 상품 목록과 판매자 정보를 수집하는 MVP(Minimum Viable Product) 개발

🔹아키텍처
[크롬 CDP 연결] → [검색 결과 수집] → [상세 페이지 순회] → [CSV 저장]
```

####  핵심 구현 사항

**1. Chrome DevTools Protocol (CDP) 연결**
```python
# 봇 탐지 회피를 위해 사용자가 직접 실행한 크롬에 연결
browser = p.chromium.connect_over_cdp("http://localhost:9222")
```
- **문제**: Playwright 기본 브라우저 사용 시 봇 탐지 차단
- **해결**: 사용자가 직접 실행한 크롬 브라우저에 기생하는 방식 
- **실행 방법**: `chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome_debug_temp"`

**2. XPath 기반 데이터 추출**
```python
# 고정된 라벨 텍스트를 기준으로 값 추출 (클래스명 변경 대비)
seller = page.locator("//th[contains(., '상호')]/following-sibling::td[1]").inner_text()
```

**3. 데이터 저장**
```python
def save_to_csv(data):
    with open(FILE_NAME, mode='a', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([...])
```

####  문제점
| 문제 | 원인 | 영향 |
|------|------|------|
| **느린 속도** | 동기식 처리 (순차 실행) | 5건당 약 50초 소요 |
| **봇 탐지 차단** | User-Agent, 행동 패턴 감지 | Access Denied 발생 |
| **동적 렌더링 이슈** | Lazy Loading 컨텐츠 | 판매자 정보 미로딩 |
| **새 탭 이슈** | `target="_blank"` 링크 | 크롤러가 새 탭 추적 실패 |

####  성능 지표
- **처리 속도**: 5건/50초 (10초/건)
- **안정성**: 낮음 (봇 탐지 빈번)
- **확장성**: 없음 (단일 프로세스)

---

### v1.0 - 비동기 크롤러 (Async Bot)
```
- `v1.0_async_bot.py`
🔹목표
동기식 처리의 성능 한계를 극복하고, 병렬 수집을 통한 속도 개선

🔹아키텍처 개선

                    ┌─ [Tab 1] → 상품 A 수집 ─┐
[URL 수집] → [분배] ─┼─ [Tab 2] → 상품 B 수집 ─┼→ [CSV 저장]
                    ├─ [Tab 3] → 상품 C 수집 ─┤
                    ├─ [Tab 4] → 상품 D 수집 ─┤
                    └─ [Tab 5] → 상품 E 수집 ─┘
                    
                    (Semaphore: 동시 5개 제한)
```

#### 핵심 구현 사항

**1. 비동기 아키텍처 전환 (Sync → Async)**
```python
# v0.9 (동기)
from playwright.sync_api import sync_playwright
time.sleep(1)

# v1.0 (비동기)
from playwright.async_api import async_playwright
await asyncio.sleep(1)
```

**2. Semaphore를 활용한 동시성 제어**
```python
semaphore = asyncio.Semaphore(5)  # 동시 5개 탭 제한

async def process_product(context, prod, semaphore):
    async with semaphore:
        page = await context.new_page()
        # ...
```
- **이유**: 무제한 동시 접속 시 메모리 폭주 및 봇 탐지 위험 증가

**3. asyncio.gather를 활용한 병렬 실행**
```python
tasks = [process_product(context, prod, semaphore) for prod in product_list]
await asyncio.gather(*tasks)
```

**4. 리소스 차단을 통한 속도 최적화**
```python
await page.route("**/*", lambda route: route.abort() 
    if route.request.resource_type in ["image", "media", "font"] 
    else route.continue_())
```
- 이미지, 미디어, 폰트 로딩 차단 → 네트워크 대역폭 감소 및 로딩속도 증가.

**5. 파일 쓰기 충돌 방지 (asyncio.Lock)**
```python
file_lock = asyncio.Lock()

async def save_to_csv(data):
    async with file_lock: # ← 한 번에 하나의 탭만 파일에 접근 가능
        with open(FILE_NAME, mode='a', ...) as f:
            writer.writerow([...])
```

#### 발견된 문제점
| 문제 | 상세 | 해결 방향 |
|------|------|----------|
| **파일 충돌** | 여러 탭이 동시에 CSV 파일 접근 시 `PermissionError` | v1.1에서 DB 전환 |
| **쿠키 기반 차단** | 쿠팡이 쿠키에 신뢰점수를 부여하여 차단 | 쿠키 주기적 초기화 |
| **gather 한계** | 모든 작업 완료까지 대기해야 함 | v1.1에서 as_completed 전환 |

#### 성능 지표
- **처리 속도**: 5건/5초 (**10배 개선**)
- **안정성**: 중간 (파일 충돌 가능성)
- **확장성**: 제한적 (단일 프로세스 내 병렬화)

---

### v1.1 - 최적화 및 안정성 강화
```
`v1.1_async_bot.py`
🔹목표
파일 I/O 병목 해소 및 대량 데이터 처리 안정성 확보

🔹아키텍처 개선
[수집 Worker Pool]
       │
       ▼
[메모리 Buffer] ──(10개 모이면)──→ [SQLite Batch Insert]
```

#### 핵심 구현 사항

**1. CSV → SQLite DB 전환**

- **장점**: 파일 잠금 충돌 해소, 중복 데이터 자동 처리 (`UNIQUE` 제약)

**2. Batch 저장 전략 (10건 단위)**
```python
def save_batch_to_db(batch_data):
    cursor.executemany(
        #중복처리
        INSERT OR REPLACE INTO sellers (rank, product_name, ...)
        VALUES (..)
        , batch_data ) # <- 리스트 10개 단위
    conn.commit()
```
- **장점**: 트랜잭션 오버헤드 감소, I/O 최적화

**3. asyncio.as_completed로 실시간 결과 처리**
```python
# v1.0: gather (일괄 대기)
await asyncio.gather(*tasks)

# v1.1: as_completed (완료 순 처리)
for future in asyncio.as_completed(tasks):
    result = await future
    if result:
        batch_buffer.append(result)
    
    if len(batch_buffer) >= 10:
        save_batch_to_db(batch_buffer)
        batch_buffer = []
```
- **장점**: 메모리 효율성 향상, 실시간 진행 상황 확인 가능


#### 🔺v1.1 차단 사건....
```
상황: VPN 적용 후 50건 수집 중 Access Denied 발생
시도: 쿠키/캐시 삭제, 시크릿 모드 → 여전히 차단
결론: IP 차단 + VPN 대역 전체 차단
```

**쿠팡 차단 매커니즘 분석**
```
+@ 대국민 보안 이슈 때문에 더 예민..?
1. 식별용 쿠키 발급
2. 이상 징후 감지 → 쿠키 신뢰점수 하락
3. 임계치 도달 → 세션 차단
4. VPN 대역 감지 → IP 대역 전체 차단
```

####  버전 비교표

| 구분 | v1.0 | v1.1 |
|------|------|------|
| **저장소** | CSV 파일 | SQLite DB |
| **저장 방식** | 1건씩 (Lock) | 10건씩 (Batch) |
| **속도 최적화** | 이미지/폰트 차단 | + CSS 차단, 대기 0.5초 |
| **병렬 처리** | `gather` | `as_completed` |
| **안정성** | 파일 충돌 가능 | DB 트랜잭션 안전 |

---

### v1.2 - 분산 처리 아키텍처 (Celery + Redis)
```
관련 파일
- `config/celery.py`
- `config/settings.py`
- `crawler/tasks.py`
- `crawler/models.py`
- `docker-compose.yml` (Redis용)

- 쿠팡 차단으로 인한 타겟 변경 및 연습 
- 확장 가능한 분산 처리 시스템 아키텍처 검증
- 웹 서버와 크롤링 워커 분리

[User/Admin]
     │
     ▼
[Django] ─Task 발행─→ [Redis] ─Task 소비─→ [Celery Worker]
(Producer)            (Broker)               (Consumer)
                                                  │
                                                  ▼
                                             [Database]
```

#### 구현 사항

**1. Celery 설정 (config/celery.py)**

**2. Django 설정 연동 (settings.py)**

**3. Celery Task 정의 (crawler/tasks.py)**
```python

@shared_task
def start_book_crawler():
    #Django에서 호출 진입
    asyncio.run(crawl_books_logic())
    return "수집 완료"

async def crawl_books_logic():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 크롤링 로직
        
        # Django ORM 비동기 호출
        await sync_to_async(Book.objects.update_or_create)(
            ...
        )
```

#### 성능 지표 
- **확장성**: 워커 수평 확장 가능 (여러 서버에 분산)
- **안정성**: 웹 서버 부하와 크롤링 작업 분리
- **모니터링**: Django Admin을 통한 실시간 데이터 확인

---

### v2.0 - 무신사 크롤러 + OpenSearch 파이프라인
```
- `v2.0_musinsa.py`
- `init_opensearch.py`
- `docker-compose.yml`

- 쿠팡 차단으로 인한 타겟 변경 (무신사)
- RDBMS 한계 극복을 위한 검색 엔진(OpenSearch) 도입
- 한국어 형태소 분석기 적용

┌──────────────────────────────────────┐
│           [무신사 웹사이트]          │
│                  │                   │
│         Playwright 비동기 수집       │
│                  ▼                   │
│     [ETL] 파싱/정제 → JSON 변환      │
│                  │                   │
│            Bulk Insert               │
│                  ▼                   │
│   [OpenSearch + Nori] 전문 검색      │
│                  │                   │
│                  ▼                   │
│       [Dashboards] 시각화            │
└──────────────────────────────────────┘
```

#### MySQL vs OpenSearch 비교

| 특징 | MySQL (RDBMS) | OpenSearch (NoSQL/검색엔진) |
|------|---------------|----------------------------|
| **주요 목적** | 데이터 저장, 수정, 삭제, 무결성 | 빠른 검색, 대용량 로그 분석 |
| **데이터 구조** | 테이블 (행/열) | 문서 (JSON Document) |
| **검색 능력** | 정확한 값 찾기에 유리 | 전문 검색, 유사도 검색, 오타 보정 |
| **속도** | 복잡한 검색 시 느려짐 | 대용량에서도 매우 빠름 |
| **트랜잭션** | 지원 (ACID) | 미지원 (Eventual Consistency) |

#### 🔹핵심 구현 사항

**1. OpenSearch 인덱스 설정 (init_opensearch.py)**
```python
index_body = ...
        "nori_user_dict": {
               "type": "nori_tokenizer",
               "decompound_mode": "mixed"  # 합성어 분리
        } ...
    "mappings": {...}
```

**2. 동적 클래스명 대응 전략**
```python
# 문제: CSS 클래스명이 랜덤 생성 (sc-m8pxwf-2)
# 해결 1: Meta Tag 활용
title = await page.locator("meta[property='og:title']").first.get_attribute("content")

# 해결 2: XPath Relative Query (라벨 기준 상대 위치)
async def get_value(label):
    locator = page.locator(f"//dt[contains(., '{label}')]/following-sibling::dd[1]")
    if await locator.count() > 0:
        return await locator.inner_text()
    return ""
```

**3. Playwright Strict Mode 대응**
```python
# 문제: 동일 속성 태그 2개 이상 시 에러
# "resolved to 2 elements"

# 해결: .first 체이닝
title_loc = page.locator("meta[property='og:title']").first
title = await title_loc.get_attribute("content")
```

**4. 판매자 정보 아코디언 처리**
```python
# 숨겨진 판매자 정보 펼치기
seller_btn = page.locator("button", has_text="판매자 정보")
if await seller_btn.count() > 0:
    expanded = await seller_btn.get_attribute("aria-expanded")
    if expanded != "true":
        await seller_btn.click()
        await asyncio.sleep(0.5)
```

**5. Bulk Insert를 통한 효율적 적재**
```python
from opensearchpy import helpers

docs = []
for url in url_list:
    doc = {
        "_index": INDEX_NAME,
        "_source": {
            "url": url,
            "title": title,
            "brand": brand,
            "price": price,
            "seller_info": {...}
        }
    }
    docs.append(doc)

# 한 번에 밀어넣기
success, failed = helpers.bulk(client, docs)
```

####  Docker (OpenSearch / Dashboards)
```yaml
version: '3'
services:
  opensearch-node:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - discovery.type=single-node
      - plugins.security.disabled=true
    ports:
      - "9200:9200"  # REST API

  opensearch-dashboards:
    image: opensearchproject/opensearch-dashboards:2.11.0
    ports:
      - "5601:5601"  # Web UI
    environment:
      OPENSEARCH_HOSTS: '["http://opensearch-node:9200"]'
```

---

### v2.1 - 검색 엔진 API 서비스 구축
```
- `v2.1_musinsa.py`
- `api_server.py`
- `index.html`

End-to-End 검색 서비스 구축 (크롤링 → 저장 → API → 웹 UI)

┌─────────────────────────────────────────────────────────────┐
│     [무신사 웹사이트]                                       │
│            │                                                │
│            │ (1. 비동기 수집: Playwright)                   │
│            ▼                                                │
│     [데이터 전처리 Worker]                                  │
│            │                                                │
│            │ (2. Bulk Insert)                               │
│            ▼                                                │
│     [OpenSearch + Nori]                                     │
│            │                                                │
│            │ (3. Search Query)                              │
│            ▼                                                │
│     [FastAPI Server] ─────────────────────────              │
│            │                      │                         │
│            │ REST API             │ Swagger UI              │
│            │                      │                         │
│            ▼                      ▼                         │
│     [Web Frontend]        [API Docs]                        │
│     (index.html)          (/docs)                           │
└─────────────────────────────────────────────────────────────┘
```

#### 💡 핵심 구현 사항

**1. FastAPI 서버 구축 (api_server.py)**
```python
from fastapi import FastAPI, Query
from opensearchpy import OpenSearch
from pydantic import BaseModel
app = FastAPI(...)
# CORS 설정 (프론트엔드 연동)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**2. Pydantic 스키마 정의**
```python
class SellerInfo(BaseModel):
    ...
class ProductSchema(BaseModel):
    ...
```

**3. 검색 API 엔드포인트**
```python
@app.get("/search", response_model=List[ProductSchema])
def search_products(
    keyword: str = Query(..., description="검색할 상품명"),
    min_price: int = Query(None, description="최소 가격"),
    max_price: int = Query(None, description="최대 가격")
):
    search_query = {
        "query": {
            "bool": {
                "must": [{
                    "multi_match": {
                        "query": keyword,
                        "fields": ["title^2", "brand"],  # 제목 가중치 2배
                        "analyzer": "nori"
                    }
                }],
                "filter": []
            }
        }
    }
    
    # 가격 범위 필터
    if min_price or max_price:
        price_range = {"range": {"price": {}}}
        if min_price: price_range["range"]["price"]["gte"] = min_price
        if max_price: price_range["range"]["price"]["lte"] = max_price
        search_query["query"]["bool"]["filter"].append(price_range)
    
    response = client.search(body=search_query, index=INDEX_NAME)
    return [hit["_source"] for hit in response["hits"]["hits"]]
```

**4. 웹 프론트엔드 (index.html)**
```javascript
async function doSearch() {...}
```

---

## 4. 핵심 문제 해결 로그

### 4.1 봇 탐지 차단 문제 (v0.9 ~ v1.1)

| 시도 | 방법 | 결과 |
|------|------|------|
| 1차 | User-Agent 변경 | 실패 |
| 2차 | Referer 헤더 조작 | 실패 |
| 3차 | playwright-stealth 라이브러리 | 실패 |
| 4차 | **Chrome CDP (기생 모드)** |🔹성공 |

**최종 해결책**: 사용자가 직접 실행한 크롬 브라우저에 Playwright가 연결
```bash
# 크롬 디버깅 모드 실행
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome_debug_temp"
```

### 4.2 동적 렌더링 및 새 탭 이슈 (v0.9)

| 문제 | 원인 | 해결책 |
|------|------|--------|
| 판매자 정보 미로딩 | Lazy Loading | `mouse.wheel` + `keyboard.press("End")` |
| 새 탭에서 봇 이탈 | `target="_blank"` | URL 수집 후 직접 이동 방식 |

### 4.3 파일 동시 쓰기 충돌 (v1.0 → v1.1)

```python
# v1.0: asyncio.Lock() - 여전히 PermissionError 가능
async with file_lock:
    with open(FILE_NAME, ...) as f:
# v1.1: SQLite DB 전환 + Batch Insert
def save_batch_to_db(batch_data):
    cursor.executemany(... , batch_data)
```

### 4.4 쿠팡 최종 차단 사건 (v1.1)

```
 시점: v1.1 VPN 적용 후 50건 수집 중
 증상: Access Denied
 시도: 쿠키 삭제, 시크릿 모드 → 여전히 차단
 결론: IP 차단 + VPN 서버 대역 전체 차단
 결정: 타겟 변경 (쿠팡 → 무신사)
```

**쿠팡 보안 분석**
```
1. 식별용 쿠키 발급
2. 이상 행동 감지 → 신뢰점수 하락
3. 세션/쿠키 차단 (IP는 유지 - 다수 사용자 고려)
4. 반복 시 IP 차단 → VPN 감지 시 대역 차단
5. 일반 ip보다 vpn에 더 엄격히 대응하는듯함.
```

### 4.5 동적 클래스명 대응 (v2.0)

```python
# 문제: 클래스명이 배포마다 변경 (sc-m8pxwf-2)

# 해결 1: 불변하는 Meta Tag 활용
title = await page.locator("meta[property='og:title']").first.get_attribute("content")

# 해결 2: XPath Relative Query
locator = page.locator(f"//dt[contains(., '{label}')]/following-sibling::dd[1]")
```

### 4.6 Playwright Strict Mode Violation (v2.0)

```python
# 문제: "resolved to 2 elements" 에러

# 해결: .first 명시적 선택
title_loc = page.locator("meta[property='og:title']").first
```

---
## 5. 아키텍처 진화 과정
```
5.1 데이터 저장소 진화
CSV 파일 (v0.9, v1.0)
     │ 파일 충돌 문제
     ▼
SQLite DB + Batch (v1.1)
     │ 검색 기능 한계
     ▼
Django ORM (v1.2)
     │ 전문 검색 요구
     ▼
OpenSearch (v2.0, v2.1)

==========================
5.2 처리 방식 진화
Sync (v0.9)
  │ 성능 개선 필요
  ▼
Async + Semaphore (v1.0)
  │ 실시간 처리 필요
  ▼
Async + as_completed + Batch (v1.1)
  │ 웹 서버 분리 필요
  ▼
Celery + Redis (v1.2)

==========================
5.3 서비스 형태 진화
스크립트 (v0.9 ~ v1.1)
     │ 관리 기능 필요
     ▼
Django Admin (v1.2)
     │ API 서비스 필요
     ▼
FastAPI + Web UI (v2.1)
```

---

## 6. 회고 및 교훈

### 6.1 기술적 교훈

| 영역 | 교훈 |
|------|------|
| **봇 탐지 회피** | 라이브러리 수준의 회피는 한계가 있음. 실제 사용자 브라우저 세션을 활용하는 것이 효과적 |
| **비동기 프로그래밍** | `asyncio.gather` vs `as_completed` - 실시간 처리 필요 여부에 따라 선택 |
| **데이터 저장** | 대량 데이터는 Batch 처리가 필수. 파일보다 DB, DB보다 검색 엔진 |
| **확장성 설계** | 초기부터 Producer-Consumer 패턴을 고려하면 나중에 확장이 쉬움 |

### 6.2 아키텍처 설계 교훈

> "시스템 설계"의 중요성

- 초기: 단순 스크립트로 시작
- 중기: 차단, 성능, 안정성 문제 직면
- 현재: 분산 처리 + 검색 엔진 + REST API 아키텍처

### 6.3 프로젝트 결정 사항

| 결정 | 이유 | 결과 |
|------|------|------|
| **CDP 방식 도입** | 일반 방법으로는 봇 탐지 회피 불가 | 쿠팡 일시적 수집 성공 |
| **타겟 변경 (쿠팡 → 무신사)** | IP 차단 + VPN 대역 차단 | 안정적 수집 환경 확보 |
| **OpenSearch 도입** | RDBMS의 전문 검색 한계 | 고속 검색 서비스 구축 |
| **FastAPI 선택** | Django보다 빠른 API 개발 | 실시간 검색 API 구축 |

### 6.4 향후 개선 계획

1. **Airflow 도입**: 주기적 자동 수집 스케줄링
2. **Fuzzy Search**: 오타 교정 검색 기능
3. **Synonym 사전**: 동의어 검색 지원
4. **Kibana 대시보드**: 브랜드별 상품 수, 가격대 분포 시각화
5. **Redis 캐싱**: 검색 결과 캐싱으로 응답 속도 개선

---


> **문서 작성**: DH / Z
> **프로젝트 기간**: 2025-11 ~ 2026-01 
