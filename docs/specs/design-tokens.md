---
last-synced-commit: 36a827e
source-of-truth: frontend/src/routes/+layout.svelte
verify: grep -E "^\s+--(bg|accent|error|text|tag|radius|border)" frontend/src/routes/+layout.svelte
---

# Design Tokens

Frontend의 모든 색상/간격/반경 값. `frontend/src/routes/+layout.svelte`의 `:global(:root)` 블록이 source-of-truth.

## CSS 변수 (`:root`)

### 배경 (Background)
- `--bg-base: #0d1117` — 페이지 베이스
- `--bg-card: #121720` — 카드 배경
- `--bg-card-hover: #1e293b` — 카드 hover
- `--bg-tab: #151c27` — 탭 배경

### 강조 (Accent)
- `--accent: #30d5c8` — 메인 accent (시안 계열)
- `--accent-dark: #094b66` — accent 짙은 톤

### 보더
- `--border: #1f2937`

### 에러
- `--error: #ef4444` — 일반 에러
- `--error-soft: #ef3e5e` — 부드러운 에러 (warning 톤)

### 텍스트
- `--text-primary: #cbd5e1` — 본문
- `--text-secondary: #64748b` — 보조
- `--text-muted: #475569` — 약함

### 태그/뱃지
- `--tag-bg: #334155`

### 반경 (Border Radius)
- `--radius-sm: 8px`
- `--radius-md: 12px`
- `--radius-full: 9999px` — pill / circle

## 폰트
- 기본: `'Pretendard GOV', 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- 라인 높이: 1.5

## 스크롤바 (커스텀)
- 너비: 4px
- thumb: `rgba(100, 116, 139, 0.3)`, `border-radius: 2px`

## Figma 참조
- File key: `MM5pHeO3gfXDchAlBVfs89`
- 주요 프레임: `01.메인`, `02.메인 > 리스트`, `04~06.컨테이너 상세 정보`
- 아이콘: `frontend/src/lib/assets/icons/` (이미 추출 완료)

## 변경 시 절차
1. `frontend/src/routes/+layout.svelte`의 `:root` 변경
2. 이 파일 (`docs/specs/design-tokens.md`) 동기화
3. 상단 frontmatter `last-synced-commit`을 현재 HEAD short SHA로 갱신
4. `verify` 명령 실행해서 변수 누락 없는지 확인
