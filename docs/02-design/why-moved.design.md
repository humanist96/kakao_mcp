# 「왜움직여?」 MCP 서버 설계서

> 작성일: 2026-07-05 | 상태: Design v1.0
> 상위 문서: [계획서](../01-plan/agentic-player-10-plan.md)
> 서비스명 가칭: 왜움직여? (후보: 개미가드, 공시통역사 — 확정 대기)

---

## 1. 시스템 개요

```
카카오톡(Kakao Tools) / PlayMCP 클라이언트
        │  MCP (Streamable HTTP)
        ▼
┌─ MCP 서버 (Python 3.12 + FastMCP) ─────────────────┐
│  Tools: why_moved / risk_check / explain_disclosure │
│         stock_health / insider_signal / daily_digest│
│         screen_stocks                               │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────┐ │
│  │ 해석 엔진   │ │ 점수화 엔진   │ │ 위험신호 룰셋  │ │
│  │(템플릿+사전)│ │(5축+A~F학점) │ │(15개 룰)      │ │
│  └────────────┘ └──────────────┘ └───────────────┘ │
│  ┌─────────────────────────────────────────────┐   │
│  │ 캐시 레이어 (SQLite/Redis, TTL 정책)          │   │
│  └─────────────────────────────────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────┐ ┌───────────┐ │
│  │DART 어댑터│ │KRX 어댑터 │ │KIND  │ │공공데이터  │ │
│  └──────────┘ └──────────┘ └──────┘ └───────────┘ │
└─────────────────────────────────────────────────────┘
```

- **원칙 1 — 출처 필수**: 모든 tool 응답에 `sources[]` (DART rcept_no 원문 URL, KRX 데이터 기준일) 포함
- **원칙 2 — 고지 필수**: 모든 tool 응답 말미에 `disclaimer` 필드 고정 ("본 정보는 공시·시세 사실의 요약이며 투자 권유가 아닙니다")
- **원칙 3 — 추천 금지**: 응답 텍스트에 매수/매도/보유 권유 표현 생성 금지 (해석 엔진 템플릿 차원에서 차단)
- **원칙 4 — 초보자 언어**: 전문용어 등장 시 괄호 한 줄 설명 자동 부착 (용어사전 참조)

## 2. MCP Tool 스펙

### 2.1 `why_moved` — 종목 급등락 원인 설명 [Hero #1]

```yaml
input:
  query: string            # 종목명 또는 종목코드 (예: "삼성전자", "005930")
  date: string?            # YYYY-MM-DD, 기본값 최근 거래일
output:
  stock: {name, code, market}
  price_move: {close, change_pct, volume_ratio}   # 전일비, 거래량배율
  explanation: string       # 3줄 요약 (초보자 언어)
  factors:                  # 원인 후보, 신뢰도순
    - {type: disclosure|flow|market|sector, summary, source_url}
  investor_flow: {개인, 외국인, 기관}   # 당일 순매수 (억원)
  sources: [{title, url, date}]
  disclaimer: string
```

로직: ① KRX에서 등락률·거래량 조회 → ② 당일~D-3 DART 공시 검색(수시공시·조회공시답변 우선) → ③ 투자자별 수급 조회 → ④ 섹터지수 대비 상대 움직임 판별 → ⑤ 해석 템플릿으로 조합. 공시·수급·섹터 어느 것도 특이점이 없으면 **"뚜렷한 공개 요인 없음"을 정직하게 답변** (환각 금지).

### 2.2 `risk_check` — 위험신호 진단 [Hero #2, 공익]

```yaml
input:
  query: string             # 종목명/코드
output:
  stock: {name, code, market}
  risk_level: 안전|주의|경고|위험    # 룰 가중합
  signals:
    - {rule_id, severity, title, easy_explanation, source_url}
  checked_rules: int         # 전체 점검 룰 수 (예: 15)
  sources, disclaimer
```

**위험신호 룰셋 v1 (15개):**

| ID | 룰 | 데이터 | severity |
|---|---|---|---|
| R01 | 감사의견 비적정(한정/부적정/의견거절) | DART 감사보고서 | 위험 |
| R02 | 자본잠식 (부분/완전) | DART 재무 | 위험 |
| R03 | 관리종목 지정 | KIND | 위험 |
| R04 | 거래정지 이력 (1년 내) | KIND | 경고 |
| R05 | 불성실공시법인 지정 (1년 내) | KIND | 경고 |
| R06 | CB/BW 발행 3회 이상 (2년 내) | DART 지분공시 | 경고 |
| R07 | 유상증자 반복 (2년 내 2회+) | DART | 주의 |
| R08 | 최대주주 변경 2회+ (2년 내) | DART | 경고 |
| R09 | 임원 대량 매도 (1개월 내) | DART 임원·주요주주 보고 | 주의 |
| R10 | 3년 연속 영업적자 | DART 재무 | 주의 |
| R11 | 횡령·배임 공시 이력 | DART | 위험 |
| R12 | 소송 공시 (분기 내) | DART | 주의 |
| R13 | 공매도 잔고 급증 | KRX | 주의 |
| R14 | 단기 거래량 이상 급증 + 뚜렷한 공시 부재 | KRX+DART | 주의 |
| R15 | 상장폐지 사유 발생 공시 | KIND | 위험 |

각 룰은 `easy_explanation` 템플릿 보유. 예: R06 → "전환사채(CB)는 나중에 주식으로 바뀔 수 있는 빚이에요. 자주 발행하면 기존 주주의 지분 가치가 희석될 수 있어요."

### 2.3 `explain_disclosure` — 공시 쉬운말 통역

```yaml
input:
  rcept_no: string?          # 공시 접수번호 (직접 지정 시)
  query: string?             # 또는 "삼성전자 최근 유상증자 공시" 식 자연어
output:
  disclosure: {title, company, date, type, url}
  what_happened: string      # 무슨 일이야?
  so_what: string            # 그래서 뭐? (일반적으로 시장이 어떻게 받아들이는 유형인지)
  why_care: string           # 나랑 무슨 상관? (주주 관점 영향 — 사실 기반)
  terms: [{term, easy_def}]  # 인라인 용어 설명
  sources, disclaimer
```

### 2.4 `stock_health` — 종목 건강진단

```yaml
input: {query: string}
output:
  stock: {name, code, sector}
  scores:                    # 각 0~100, 섹터 상대
    value | growth | profitability | stability | dividend
  grade: A+~F                # 종합 학점 (섹터 상대)
  narrative: string          # "체크 12개 중 9개 통과" 식 쉬운 문장 3~5개
  checks: [{name, passed, easy_explanation}]
  data_basis: {fiscal_period, source}
  sources, disclaimer
```

점수 로직: DART XBRL 최근 4개 분기 + KRX 시가총액 기반. 섹터 내 백분위로 산출(절대평가 금지). 애널리스트 추정치 없이 **공시 실적만으로** 계산 — 미래 예측 표현 배제.

### 2.5 `insider_signal` — 스마트머니 피드

```yaml
input:
  query: string?             # 종목 지정 시 해당 종목, 미지정 시 시장 전체 최근 피드
  days: int = 30
output:
  events:
    - {date, company, who, role, action: 매수|매도, amount, source_url}
  institutional_flow: [{company, 연기금, 외국인, 기관, period}]
  summary: string            # "최근 30일, OO 임원 3명이 자사주를 매수했습니다"
  sources, disclaimer
```

### 2.6 `daily_digest` — 오늘의 공시 다이제스트

```yaml
input:
  date: string?              # 기본 오늘
  watchlist: [string]?       # 관심종목 필터
output:
  top_disclosures:           # 중요도순 3~5건
    - {company, title, what_happened, so_what, why_care, url}
  market_note: string        # 당일 시장 한 줄
  sources, disclaimer
```

중요도 스코어링: 공시유형 가중치(합병·유상증자·감사의견 상위) × 시가총액 × 관심종목 여부.

### 2.7 `screen_stocks` — 자연어 스크리너

```yaml
input:
  condition: string          # "배당수익률 4% 이상, 부채비율 100% 이하 코스피"
output:
  parsed_conditions: [{field, op, value}]   # 변환 결과를 투명하게 노출
  results: [{name, code, matched_values}]   # 최대 20종목
  total_matched: int
  sources, disclaimer
```

LLM 클라이언트가 자연어를 던지면 서버는 조건 파싱 → 사전 구축된 재무 스냅샷 테이블 쿼리. 파싱 불가 조건은 `unsupported_conditions[]`로 정직하게 반환.

## 3. 공시유형 → 쉬운말 템플릿 사전 (v1: 20개 유형)

| 공시유형 | what_happened 템플릿 골자 | so_what 골자 |
|---|---|---|
| 유상증자 | 회사가 새 주식을 팔아 돈을 모음 | 기존 주주 지분 희석 가능. 자금 용도(시설/운영/차환)가 중요 |
| 무상증자 | 주주에게 공짜 주식 지급 | 기업가치 불변, 유통량 증가. 단기 수급 이벤트로 해석되곤 함 |
| 전환사채(CB) 발행 | 주식으로 바뀔 수 있는 빚 | 전환가 아래로 내려가면 리픽싱 조항 확인 필요 |
| 무상감자 | 자본금 축소, 보상 없음 | 통상 누적 결손 정리 목적 — 재무 위험 신호인 경우 많음 |
| 자사주 매입 | 회사가 자기 주식 삼 | 통상 주주환원·저평가 신호로 해석되는 유형 |
| 합병/분할 | ... | ... |
| 최대주주 변경 | ... | 경영권 변화 — 새 주주의 성격 확인 필요 |
| 단일판매·공급계약 | 대형 계약 수주 | 매출 대비 계약 규모(%)가 핵심 |
| 조회공시 답변 | 거래소 질문에 회사가 공식 답변 | "중요정보 없음" 답변인지 확인 |
| 영업(잠정)실적 | 분기 성적표 발표 | 전년동기·직전분기 대비가 핵심 |
| 감사보고서 제출 | ... | 의견 종류(적정/한정/부적정/의견거절) 확인 |
| 임원·주요주주 소유보고 | 내부자가 사고팔았음 | 자기 돈 매수는 통상 자신감 신호로 해석되는 유형 |
| 5% 대량보유 보고 | 큰손의 지분 변동 | 보유 목적(단순투자/경영참여) 확인 |
| 소송 제기 | ... | 소송가액 vs 자기자본 비율 |
| 횡령·배임 | ... | 거래정지·상폐 사유 가능성 — 최고 위험 |
| 배당 결정 | ... | 배당수익률·배당성향 맥락 |
| 주식분할 | ... | 가치 불변, 접근성 개선 |
| 상장폐지 사유 | ... | 즉시 위험 안내 |
| 신규시설투자 | ... | 투자금액 vs 자기자본 비율 |
| 타법인 출자 | ... | 본업 연관성 확인 포인트 |

※ so_what은 "통상 ~로 해석되는 유형" 화법으로 통일 — 예측·권유가 아닌 일반론 서술 (규제 방어).

**용어사전 v1**: PER, PBR, ROE, 부채비율, 유보율, 시가총액, 액면가, 리픽싱, 오버행, 보호예수, 공매도, 대차잔고, 관리종목, 감자, 증자, CB, BW, EB, 스팩, 배당락 등 50개 → `terms[]` 인라인 부착용.

## 4. 데이터 어댑터 명세

| 어댑터 | 엔드포인트 | 캐시 TTL |
|---|---|---|
| DART 공시검색 | `/api/list.json` (corp_code, bgn_de, pblntf_ty) | 10분 |
| DART 기업개황 | `/api/company.json` | 24시간 |
| DART 재무 | `/api/fnlttSinglAcntAll.json` (XBRL) | 24시간 |
| DART 지분공시 | `/api/elestock.json`, `/api/majorstock.json` | 1시간 |
| DART corp_code 매핑 | `/api/corpCode.xml` (zip) | 주 1회, 서버 내장 |
| KRX 시세/수급 | 정보데이터시스템 OTP 방식 | 종가 기준 일 1회 |
| KIND 관리종목·불성실공시 | 일 배치 수집 | 24시간 |

- DART 일 한도 20,000건 → **인기 상위 500종목 프리컴퓨트 배치(새벽)** + 롱테일은 온디맨드
- 종목명→코드 매핑: corp_code + KRX 상장종목 마스터를 서버 내장 테이블로

## 5. 기술 스택 및 비기능 요구사항

| 항목 | 선택 | 이유 |
|---|---|---|
| 런타임 | Python 3.12 + FastMCP | MCP 표준 구현 속도 최우선 |
| 저장소 | SQLite (MVP) → Redis (본선) | 배치 스냅샷 + 캐시 겸용, 운영 단순 |
| 호스팅 | 카카오클라우드 VM (공모전 가이드 준수) | 공식 노션 가이드 필수 참조 |
| 안정성 | 헬스체크 `/health`, 외부 API 타임아웃 5s + 폴백(캐시 응답), 구조화 로깅 | 심사기준 '안정성' 대응 |
| 응답 목표 | p95 < 3초 (프리컴퓨트 종목), < 8초 (온디맨드) | |
| 보안 | API 키 환경변수, 개인정보 미수집, 입력 검증(종목코드 정규식) | |

## 6. 구현 우선순위 (7/8 등록 데드라인)

| 순위 | 범위 | 목표일 |
|---|---|---|
| P0 | DART·KRX 어댑터 + `why_moved` + `risk_check` + 고지·출처 프레임 | 7/6 |
| P0 | `explain_disclosure` (템플릿 20유형 중 상위 10) + 배포 + 헬스체크 | 7/7 |
| P0 | PlayMCP 임시등록 테스트 → **정식 등록·심사 요청** | **7/8** |
| P1 | `stock_health`, `daily_digest`, 템플릿 나머지 10유형 | 7/9~7/11 |
| P2 | `insider_signal`, `screen_stocks` | 7/12~7/13 (심사 통과 후 업데이트 가능 여부 확인) |

## 7. 테스트 계획

- 유닛: 룰셋 15개 각각 (양성/음성 케이스), 템플릿 렌더링, 조건 파서
- 통합: 어댑터별 실 API 스모크 (한도 절약 위해 녹화된 응답으로 회귀 테스트)
- 시나리오: "삼성전자 왜 떨어졌어" / "이 공시 뭐야 (rcept_no)" / "OO 위험해?" / 존재하지 않는 종목 / 상장폐지 종목 / 거래정지 종목
- 품질 게이트: 환각 검증 — 답변 내 모든 사실 문장이 sources와 대응되는지 샘플 검수
