#!/bin/bash
# 자동 버전 관리 및 배포 스크립트
# 사용법: bash release.sh "변경 내용 설명"

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# ── 1. 커밋 메시지 ────────────────────────────────────────
COMMIT_MSG="${1:-update}"

# ── 2. 현재 버전 가져오기 ─────────────────────────────────
CURRENT_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
echo "📌 현재 버전: $CURRENT_TAG"

# ── 3. 버전 자동 증가 (v1.0.1 → v1.0.2) ──────────────────
VERSION=${CURRENT_TAG#v}
MAJOR=$(echo $VERSION | cut -d. -f1)
MINOR=$(echo $VERSION | cut -d. -f2)
PATCH=$(echo $VERSION | cut -d. -f3)
NEW_PATCH=$((PATCH + 1))
NEW_TAG="v${MAJOR}.${MINOR}.${NEW_PATCH}"
echo "🆕 새 버전: $NEW_TAG"

# ── 4. organizer_app.py 버전 자동 업데이트 ────────────────
sed -i '' "s/CURRENT_VERSION = \"v.*\"/CURRENT_VERSION = \"${NEW_TAG}\"/" "$SCRIPT_DIR/organizer_app.py"
echo "✅ 앱 버전 업데이트: $NEW_TAG"

# ── 5. git commit + push ──────────────────────────────────
git add .
git commit -m "$COMMIT_MSG ($NEW_TAG)"
git push

# ── 6. 태그 생성 + push (GitHub Actions 자동 빌드 시작) ───
git tag "$NEW_TAG"
git push origin "$NEW_TAG"

echo ""
echo "🚀 배포 완료!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "버전: $NEW_TAG"
echo "GitHub Actions 빌드 시작됨"
echo "확인: https://github.com/parkjinue/downloads-organizer/actions"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
