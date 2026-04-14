#!/bin/bash
# Downloads Organizer .app 빌드 스크립트

echo "📦 앱 빌드 시작..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 필요 라이브러리 설치
echo "📥 라이브러리 설치 중..."
pip3 install rumps watchdog py2app --quiet

# 기존 빌드 삭제
rm -rf build dist

# 앱 빌드
echo "🔨 앱 빌드 중..."
python3 setup.py py2app --quiet

echo ""
echo "🎉 빌드 완료!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 앱 위치: $SCRIPT_DIR/dist/Downloads Organizer.app"
echo ""
echo "👉 사용법:"
echo "   dist 폴더 안의 'Downloads Organizer.app' 을"
echo "   응용 프로그램 폴더로 이동 후 실행"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
