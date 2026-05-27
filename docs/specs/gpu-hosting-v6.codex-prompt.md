# Codex Review Prompt — GPU Hosting Dashboard v6 (단일 서버 + 인사이트 중심)

> 첨부: 라이브 URL `http://192.168.0.63:33000/gpu-hosting` (접근 가능하면) +
> `frontend/src/routes/gpu-hosting/+page.svelte`, `frontend/src/lib/components/gpu/*.svelte`.

---

## Task

HyperCube GPU Hosting Dashboard v6 평가. 이전 5번의 reject 를 거쳐 만들어진 화면이다.
**작성자의 의도와 시각 디자인 양쪽이 진짜로 reject 를 해소했는지** 정밀하게 판단하라.

## Reject 이력 (v1 → v6)

| 버전 | 사용자 비판 → 대응 |
|---|---|
| v1 | 토큰만 minimal — 단조롭다 → 컬러풀 KPI 6박스로 |
| v2 | 무지개 KPI 가 AI 같다 → 다크 카드 + 액센트 띠로 |
| v3 | 색만 바뀌고 구조 동일하다 → mini viz 6종으로 |
| v3-rev | Codex reject (여전히 AI) → master-detail split + KPI 4 + chart stack 폐기 |
| v3-rev2 | "실속 없음" → KPI + Gauge + 모델별 area + cuda 막대 복원 + GPU 카드 list |
| v3.4 / v4 | KPI 그리드 AI 같다 → 자연어 status + visual map + Hero |
| v5 | "데이터 나열만 한다" → 인사이트 + 액션 카드 + 사용자 랭킹 |
| **v6** (현재) | "서버 한 대 대시보드여야 한다 + 정렬 + 퀄리티" → **단일 서버 집중 + Action Bar 큰 디자인 + Insight 카드 polish + slice grid 4 column** |

## v6 의 핵심 결정

1. **단일 서버 집중** — `selectedServer` default = `HOSTS[0]` (Seoul-A). 전체 서버 보기 폐기.
2. **상단 Action Bar** — alert glyph + "지금 처리해야 할 일 2건 대기" + 번호 박스 + action row + CTA chip ("즉시 점검 필요 →")
3. **Insight 4 카드** — 가장 인기 서비스 / 가장 많이 쓰는 사람 / 자원 효율 / 가용 자원 (각 카드: icon + label + detail + action chip, 4 카드 동일 height, placeholder 도 같은 layout)
4. **GPU 카드** — host scope 안에서 각 GPU = 한 큰 카드 (header + metrics 4 동일 height + slice grid **4 column** 명시)
5. **Slice Tile** — 각 슬라이스 = mini 카드 (사용자 + 모델 + 마켓 chip + 컨테이너 + compute% + VRAM)
6. **우측 사이드** — UserUsageRanking + ServiceListPanel (마켓 공유 chip) + ActivityFeed (자연어)
7. **언어** — 한국어 자연어 ("님이 ... 운영 중", "신청 가능", "1초마다 / 5초마다 / 1분마다")
8. **layout** — `body { overflow: hidden }` 우회를 위해 shell flex column / page flex column with overflow-y:auto. 모든 자식 `flex-shrink: 0; min-width: 0;`

## 검증 초점 (5개)

각 항목 라벨: `[Yes / No / Partial]` + 근거 + 권고 (CHANGE / KEEP / DEFER).

### 1. "단일 서버 집중" 의도 충실도
- 화면이 진짜 한 서버 집중인지, 또는 사이드 패널 등이 전체 서버 데이터를 흘려 보내는지
- 서버 selector 의 명확성 (default 가 Seoul-A 인 게 자연스러운가, "전체 서버" 옵션 폐기는 합리적인가)
- header 의 host 정보 (Seoul-A · host-gpu-01.seoul.hc · "GPU 3대 중 1대 장애 발생 · 점검 필요" status pill) 가 충분히 강조됐는가

### 2. "데이터 나열" → "인사이트 + 액션" 전환 정도
v5 reject 의 핵심: "이거는 누구나 만들 수 있는거. 어떻게 효과적으로 보여줄지 고민해야지". v6 가 이걸 해소했는가?
- Action Bar 의 추천 (즉시 점검 필요 / 추가 인스턴스 또는 분산 권장) 이 진짜 운영자에게 가치 있는가, 단순 라벨링인가
- Insight 카드 4개가 단순 KPI vs 진짜 인사이트인가
  - "가장 인기 서비스" Qwen2 12,400회 — 의미 있는가
  - "가장 많이 쓰는 사람" 김민준 3 슬라이스 — 의미 있는가
  - placeholder ("자원 효율 OK") 는 무의미한 빈 카드 아닌가

### 3. 정렬 / 시각 hierarchy / 폰트 위계
사용자가 명시적으로 "정렬 잡고 퀄리티 올려" 요청.
- ActionBar / Insight grid / GPU 카드 / 슬라이스 grid 간 간격·padding·border 일관성
- 4 Insight 카드 height 동일한가 (placeholder 포함)
- GPU 카드 안 메트릭 4개 박스 height 동일한가
- slice grid 가 4 column 으로 자연 (7 slice 면 2 row, 마지막 row 3개 + 1빈 칸 — 자연스러운가)
- 폰트 위계: h1 26px · h3 18px · KPI 큰 숫자 28-36px · body 14-15px · 보조 11-12px
- 색 hierarchy: semantic (ok/warn/error/offline) vs identity (host 색)

### 4. "AI 가 만든 것 같지 않게" 친근성 (사용자 반복 비판)
- 한국어 자연어가 진짜 자연스러운가, 기계적인 번역 같지 않은가
- "님이 ... 운영 중", "신청 가능", "조금 따뜻함/뜨거움 — 주의" 같은 표현이 운영자에게 친근한가
- mini viz / 카드 패턴이 dashboard template 의 표준 paint-by-numbers 같지 않은가
- 마켓 공유 chip ("↗ 마켓") 이 의미 있게 표시되는가

### 5. 다음 reject 위험 — 예상 비판
사용자는 v6 에서 어떤 비판을 할 가능성이 있는가? Top 3:
- 예: "Insight 카드 자체가 또 정형이다", "사이드 패널이 너무 길다", "GPU 카드 metric 4 가 어색하다"

## What "good review" looks like

- 칭찬 X. "잘 만들어졌습니다" 차단.
- 5번의 reject 이력을 알고 있으니, 이번에도 같은 비판이 반복될 가능성을 검토.
- 화면 spec 만 보지 말고 **운영자 시나리오** ("새벽 3시 알람 받고 들어옴", "한 서버에 GPU 30대로 확장") 로 평가.
- mini viz / Insight / Action 별 단호한 판단. 모호한 "괜찮음" 금지.

### Do NOT

- "v5 보다 개선됨" 일반 칭찬.
- 각 영역을 일괄 `[Yes]` 처리.
- 코드 품질 (TypeScript / Svelte 패턴) 평가에 시간 쓰지 말 것 — 본 review 는 **운영자 시점의 시각 디자인 + 정보 설계** 평가만.

## Output Format

```
## TL;DR
2-3줄. 한 줄 결론: 사용자가 v6 를 받아들일 가능성 (HIGH / MEDIUM / LOW).
가장 큰 약점 1개.

## 1. 단일 서버 집중 의도
라벨 + 근거

## 2. 인사이트 + 액션 전환
라벨 + 근거 (Action Bar / Insight 4 카드 각각 평가)

## 3. 정렬 / 시각 hierarchy / 폰트 위계
라벨 + 근거

## 4. AI 같지 않은 친근성
라벨 + 근거

## 5. 예상 다음 비판 (Top 3)
ranked

## Verdict
- [ ] v6 받아들일 가능성 HIGH
- [ ] MEDIUM — 일부 polish 권장 (ranked)
- [ ] LOW — 다시 큰 redesign 필요
```

## Constraints

- 한국어 또는 영어. 기술 용어 원어.
- 라이브 URL 가능하면 직접 보고 평가.
- 코드 참고 가능하면 file:line.

## Final Check Before Submitting

- [ ] 칭찬 문장 없는가?
- [ ] 5번의 reject 이력을 의식한 평가인가?
- [ ] 예상 다음 비판이 구체적인가?
- [ ] Verdict 가 명확한가?
