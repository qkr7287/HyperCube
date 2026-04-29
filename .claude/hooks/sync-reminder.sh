#!/usr/bin/env bash
# PostToolUse hook: code 변경 시 docs sync reminder 출력 (non-blocking).
# stdin 으로 JSON 받음: { tool_name, tool_input: { file_path, ... }, ... }
# stderr 1줄 reminder, exit 0.

set -u

INPUT=$(cat)

# python 으로 file_path 파싱 (Windows + git bash 환경에서 jq 미보장)
FILE=$(printf '%s' "$INPUT" | python -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except Exception:
    pass
" 2>/dev/null)

# 매칭 안되면 침묵
[ -z "$FILE" ] && exit 0

# 경로 정규화: Windows backslash → forward slash
FILE_NORM="${FILE//\\//}"

# 매칭 패턴 → reminder
case "$FILE_NORM" in
  *backend/apps/common/consumers.py)
    echo "[sync] WS / Agent command 변경? → docs/agent-protocol.md + docs/agent-payload-contract.md 확인" >&2
    ;;
  *backend/apps/containers/*)
    echo "[sync] REST API 변경? → docs/api.md + docs/agent-payload-contract.md 확인" >&2
    ;;
  *backend/apps/agents/*)
    echo "[sync] Agent / WS 변경? → docs/agent-protocol.md + docs/agent-payload-contract.md 확인" >&2
    ;;
  *frontend/src/routes/+layout.svelte)
    echo "[sync] CSS 변수 변경? → docs/specs/design-tokens.md 확인" >&2
    ;;
  *docker-compose*.yml|*.github/workflows/deploy*.yml|*.github/workflows/build*.yml)
    echo "[sync] 배포 설정 변경? → docs/runbooks/deploy.md 확인" >&2
    ;;
esac

exit 0
