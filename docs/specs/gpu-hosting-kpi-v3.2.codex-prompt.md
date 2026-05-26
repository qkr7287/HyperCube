# Codex Review Prompt — GPU Hosting Dashboard KPI v3.2 Redesign

> 첨부: `frontend/src/routes/gpu-hosting/+page.svelte`, `frontend/src/lib/components/gpu/KpiStat.svelte`, `frontend/src/lib/components/gpu/MiniViz.svelte`.
> 라이브 URL (접근 가능하면): `http://192.168.0.63:33000/gpu-hosting`

---

## Task

HyperCube GPU Hosting Dashboard 의 **KPI Row 재디자인 (v3.2)** 의 결과물을 평가하라.
사용자가 v3.1 (다크 카드 + 좌측 컬러 액센트 띠) 디자인을 보고 **"장난해? 똑같구만 색깔만 바꾸고"** 라고 비판했다. 작성자가 그 비판을 받고 v3.2 를 만들었다.
이번 review 의 유일한 목적: **v3.2 가 진짜로 새 디자인인지, 또 여전히 AI 같은 인공적 느낌인지** 정밀하게 평가하라.

## v3 진화 요약

| 버전 | KPI 패턴 |
|---|---|
| v3.0 | 6 박스 컬러풀 그라데이션 (cyan/yellow/orange/violet/pink/green) + 큰 숫자만 |
| v3.1 | 6 박스 다크 카드 + 좌측 4px flat 컬러 액센트 띠 + 큰 숫자만 |
| **v3.2** | **6 box, 각 box 안 = 좌측(label/value/sub) + 우측 mini viz**. 6 mini viz 가 각각 **종류가 다름**: stacked-bar / donut / progress / sparkline / dot-grid / thermal |

## 검증 초점 (5개)

### 1. 구조 변화 진위
사용자 비판의 핵심: "색만 바뀌고 구조는 동일". 평가:
- (a) v3.2 의 6 KPI 가 실제로 서로 **다른 정보 구조** 인가, 아니면 형식만 그대로고 mini viz 만 추가한 것인가?
- (b) v3.1 → v3.2 가 진짜 **redesign** 인가, **decoration** 인가?
- 라벨: `[Genuine redesign / Decoration / Cosmetic]`

### 2. AI 같음 (artificial / canned) 제거 여부
- v3.0 의 무지개 그라데이션 = 명백히 AI 가 만든 듯한 인공 색
- v3.2 가 그 느낌을 진짜 제거했나? mini viz 자체가 또 **모든 KPI 에 동일 패턴 (1 라벨 + 1 큰 숫자 + 1 우측 viz)** 적용이라 새로운 의미의 "templating" 이 보이지는 않나?
- 라벨: `[Resolved / Reduced / Still feels AI-generated]`

### 3. Mini viz 6종의 의미 적합성
각 mini viz 가 해당 KPI 의 핵심 정보를 잘 전달하는가? 사용자가 viz 만 봐도 "아, 이게 호스트 분포구나/슬라이스 가동률이구나" 라고 즉시 읽히는가?

| # | KPI | Mini viz | 적합성 평가 |
|---|---|---|---|
| 1 | 총 GPU | stacked-bar (host) | ? |
| 2 | 슬라이스 가동 | donut (%) | ? |
| 3 | VRAM | progress bar | ? |
| 4 | Compute 평균 | sparkline 60s | ? |
| 5 | 장애·Idle | dot grid (severity) | ? |
| 6 | 평균 온도·전력 | thermal bar | ? |

각 항목 라벨: `[Fits / Mismatch / Better alternative: X]`

### 4. 참고 자료 vocabulary 매칭
v3.2 가 다음 참고들의 시각 언어를 진짜 차용했는지 vs 일반 admin dashboard 톤에 그쳤는지:
- Google AI Studio "GPU & MCP 통합관리" (첫 출처)
- Vexel Bootstrap (`Total Sales by Unit` + `Total Revenue` 처럼 KPI 안 mini chart)
- Grafana 22424 (컬러풀 stat + gauge)
- cuda_monitoring (가로 막대 + 큰 숫자)
- OVH DCGM (반원 게이지 + 큰 숫자)

라벨: `[Aligned / Mixed / Off-base]`

### 5. Codex v3 review 의 색 정책 일관성
이전 v3 brief 에서 작성자가 결정한 색 체계:
- semantic palette (ok/warn/error/offline) ↔ identity palette (GPU 별) 분리
- 모든 status 표현은 색 + 라벨/aria 병용 (색만으로 표현 금지)

v3.2 mini viz 가 이 규칙과 충돌하는지:
- stacked-bar 의 host 색 (cyan/violet/pink/yellow) 은 identity 인가, 임의 컬러풀인가?
- thermal bar 의 빨강·노랑·녹 gradient 는 semantic 인가?
- dot grid 의 색 은 semantic OK 인가?

라벨: `[Consistent / Drift / Conflict with brief §5.3]`

## What "good review" looks like

- 칭찬 X. "잘 만들어졌습니다" 류 차단.
- 사용자 비판("색만 바뀜")이 정당했는지 v3.0/v3.1/v3.2 를 직접 비교해 평가.
- mini viz 별 **단호한 판단** (Fits / Mismatch). 모호한 "괜찮음" 금지.
- v3.2 도 여전히 AI 가 만든 듯 보인다면 어느 부분이 그러한지 구체적으로.
- 사용자 입장에서 다음 비판이 나올 만한 약점 1-3개 미리 지적.

### Do NOT

- "v3.1 보다 개선됐습니다" 류 일반 칭찬.
- 모든 mini viz 를 `[Fits]` 로 일괄 처리.
- 코드 품질 (TypeScript / Svelte 패턴) 평가에 시간 쓰지 말 것 — 본 review 는 **시각 디자인 평가** 만.

## Output Format

```
## TL;DR
2-3줄.
- 사용자 비판이 v3.2 에서 진짜 해소됐는지 한 줄 결론 (YES / PARTIAL / NO)
- 가장 큰 약점 1개

## 1. 구조 변화 진위
라벨 + 근거 + v3.1 ↔ v3.2 차이 핵심 1-2개

## 2. AI 같음 제거 여부
라벨 + 근거. 만약 STILL_FEELS_AI 면 어느 부분이 그렇게 느껴지는지 구체

## 3. Mini viz 6종 적합성
각 항목 표 형식 (1-6 라벨 + 근거)

## 4. 참고 자료 매칭
라벨 + 어느 참고에 가장 가까운가 / 어느 참고는 미반영

## 5. Brief §5.3 색 정책 일관성
라벨 + 충돌 항목 (있다면)

## Anticipated next user complaint (예상 다음 비판 1-3개)
사용자가 v3.3 에서 어떤 비판을 할 가능성이 있는지

## Verdict
- [ ] 사용자가 v3.2 받아들일 가능성 높음
- [ ] 받아들이지 못할 가능성 — 수정 권고 (있다면 ranked)
```

## Constraints

- 한국어 또는 영어. 기술 용어 원어.
- 코드 인용 시 파일 경로 + line 번호.
- 라이브 URL 접근 가능하면 직접 보고 평가. 안 되면 코드만 보고 추론하되 "라이브 미확인" 명시.

## Final Check Before Submitting

- [ ] 사용자 비판 ("색만 바뀜") 에 대한 직접 답이 있는가?
- [ ] mini viz 6종 모두 각각 평가했는가 (일괄 X)?
- [ ] 칭찬 문장 없는가?
- [ ] "예상 다음 비판" 섹션이 비어 있지 않은가?
