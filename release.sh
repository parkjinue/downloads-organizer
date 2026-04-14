#!/bin/bash
# 자동 버전 관리 및 배포 스크립트
# 사용법: bash release.sh "변경 내용 설명"

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# ── 1. 커밋 메시지 확인 ───────────────────────────────────
COMMIT_MSG="${1}"
if [ -z "$COMMIT_MSG" ]; then
    echo "❌ 변경 내용을 입력해주세요."
    echo "사용법: bash release.sh \"변경 내용\""
    exit 1
fi

# ── 2. 현재 버전 가져오기 ─────────────────────────────────
CURRENT_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
echo "📌 현재 버전: $CURRENT_TAG"

# ── 3. 버전 자동 증가 ─────────────────────────────────────
VERSION=${CURRENT_TAG#v}
MAJOR=$(echo $VERSION | cut -d. -f1)
MINOR=$(echo $VERSION | cut -d. -f2)
PATCH=$(echo $VERSION | cut -d. -f3)
NEW_PATCH=$((PATCH + 1))
NEW_TAG="v${MAJOR}.${MINOR}.${NEW_PATCH}"
echo "🆕 새 버전: $NEW_TAG"

# ── 4. 앱 버전 업데이트 ───────────────────────────────────
sed -i '' "s/CURRENT_VERSION = \"v.*\"/CURRENT_VERSION = \"${NEW_TAG}\"/" "$SCRIPT_DIR/organizer_app.py"

# ── 5. CHANGELOG.md 업데이트 ──────────────────────────────
DATE=$(date "+%Y-%m-%d")
CHANGELOG="$SCRIPT_DIR/CHANGELOG.md"

if [ ! -f "$CHANGELOG" ]; then
    echo "# Changelog" > "$CHANGELOG"
    echo "" >> "$CHANGELOG"
fi

TEMP=$(mktemp)
echo "# Changelog" > "$TEMP"
echo "" >> "$TEMP"
echo "## $NEW_TAG - $DATE" >> "$TEMP"
echo "- $COMMIT_MSG" >> "$TEMP"
echo "" >> "$TEMP"
tail -n +2 "$CHANGELOG" >> "$TEMP"
mv "$TEMP" "$CHANGELOG"

echo "✅ CHANGELOG 업데이트 완료"

# ── 6. git commit + push ──────────────────────────────────
git add .
git commit -m "$COMMIT_MSG ($NEW_TAG)"
git push

# ── 7. 태그 생성 + push ───────────────────────────────────
git tag "$NEW_TAG"
git push origin "$NEW_TAG"

echo ""
echo "🚀 배포 완료!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "버전: $NEW_TAG"
echo "변경: $COMMIT_MSG"
echo "확인: https://github.com/parkjinue/downloads-organizer/actions"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
