# 왜움직여? — 주식 초보자를 위한 공시·시세 AI 통역 MCP 서버

> 카카오 PlayMCP **AGENTIC PLAYER 10** 출품작.
> "내 주식이 오늘 왜 움직였는지"를 DART 공시·시세·수급을 연결해 초보자 언어로 설명하고,
> 상장폐지·자본잠식 같은 위험신호를 미리 경고하는 투자자 보호형 MCP 서버입니다.

## MCP Tools (7종)

| Tool | 설명 |
|---|---|
| `why_moved` | 종목 급등락 원인 설명 — 공시 + 기관·외국인 수급 + 시장 흐름 3줄 요약 |
| `risk_check` | 위험신호 15개 룰 진단 (감사의견, 자본잠식, 관리종목, CB 남발, 횡령·배임 등) |
| `explain_disclosure` | 공시 쉬운말 통역 — 무슨 일이야? / 그래서 뭐? / 나랑 무슨 상관? |
| `stock_health` | 재무 건강진단 — 5축 점수 + A~F 학점 + 쉬운 문장 |
| `insider_signal` | 내부자·5% 큰손 매매와 기관·외국인 수급 피드 |
| `daily_digest` | 오늘의 주요 공시 3문항 다이제스트 (관심종목 우선) |
| `screen_stocks` | 자연어 스크리너 — "배당 4% 이상 PBR 1 이하 코스피" |

### 설계 원칙
1. **모든 응답에 출처**(DART 원문 링크) + **투자권유 아님 고지** 필수 — 스키마 레벨 강제
2. 매수·매도 **추천 표현 생성 금지** (`FORBIDDEN_PHRASES` 안전망이 응답 전체를 검사)
3. 원인을 못 찾으면 **"뚜렷한 공개 요인 없음"을 정직하게** 답변 (환각 금지)
4. 데이터 확인 불가 시 크래시 대신 `unavailable_rules`로 정직하게 보고

## 데이터 소스 (100% 무료·공개)

| 소스 | 용도 | 비고 |
|---|---|---|
| DART OpenAPI | 공시·재무제표·지분공시 | 무료 키 필요, 일 20,000건 → SQLite TTL 캐시 |
| 네이버 금융 공개 API | 시세·수급·밸류에이션 | KRX 정보데이터시스템이 로그인 필수로 전환되어 대체 |
| KIND | 관리종목·불성실공시법인 | best-effort, 실패 시 "확인 불가"로 강등 |

## 실행 방법

```bash
# 1. 의존성 설치 (uv)
uv sync

# 2. DART API 키 설정 — https://opendart.fss.or.kr 에서 무료 발급 (1분)
cp .env.example .env
# .env 파일에 DART_API_KEY=발급받은키 입력

# 3. 서버 실행 (Streamable HTTP, 기본 포트 8000)
uv run why-moved

# 4. 확인
curl http://localhost:8000/health
# MCP 엔드포인트: http://localhost:8000/mcp
```

## 테스트

```bash
uv run pytest --cov    # 83 tests, 커버리지 82%
```

## PlayMCP 등록 체크리스트 (사용자 직접 작업)

1. [ ] DART API 키 발급 → `.env` 설정
2. [ ] 카카오클라우드 VM 생성 (공모전 공식 노션 가이드 참조) 후 본 서버 배포
   - `uv sync && DART_API_KEY=... uv run why-moved` (또는 systemd/도커)
   - HTTPS 리버스 프록시 권장 (caddy/nginx)
3. [ ] PlayMCP 개발자 콘솔에 `https://<도메인>/mcp` 엔드포인트 임시 등록 → 테스트
4. [ ] "등록 및 심사 요청" (심사 최대 7영업일 — **7/8까지 요청 권장**)
5. [ ] 심사 통과 후 "전체 공개"로 변경 → 예선 접수 (마감 7/14)

## 아키텍처

```
src/why_moved/
├── server.py              # FastMCP 서버 + tool 등록 + /health
├── context.py             # 어댑터 조립 (DI)
├── config.py              # 환경변수 설정
├── common/                # 응답 envelope(출처·고지), 도메인 에러
├── cache/                 # SQLite TTL 캐시
├── adapters/              # DART / 네이버시세 / KIND / 종목코드 매핑
├── engine/                # 해석 엔진 (순수 함수 — 테스트 용이)
│   ├── disclosure_templates.py   # 공시 20유형 3문항 템플릿
│   ├── glossary.py               # 초보자 용어사전 50개
│   ├── risk_rules.py             # 위험신호 룰 15개
│   ├── health_score.py           # 5축 점수 + A~F 학점
│   ├── financial_extract.py      # DART XBRL 계정 추출
│   └── screener_parser.py        # 자연어 조건 파서
└── tools/                 # MCP tool 7종 (어댑터 조합 + envelope 부착)
```

## 면책

본 서비스의 모든 응답은 공개 데이터의 사실 요약이며 투자 자문·권유가 아닙니다.
투자의 최종 판단과 책임은 투자자 본인에게 있습니다.
