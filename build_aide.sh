#!/bin/bash
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "📦 AIDE 빌드 시작..."

# Python 경로
PYTHON_PATH=""
for candidate in "/opt/homebrew/bin/python3.11" "/usr/local/bin/python3.11" "$(which python3.11 2>/dev/null)"; do
    if [ -x "$candidate" ]; then PYTHON_PATH="$candidate"; break; fi
done
if [ -z "$PYTHON_PATH" ]; then echo "❌ Python 3.11 없음. brew install python@3.11 실행해주세요."; exit 1; fi

# 가상환경
if [ ! -d "venv_aide" ]; then
    "$PYTHON_PATH" -m venv venv_aide
fi
source venv_aide/bin/activate

pip install rumps watchdog pywebview py2app setuptools --quiet

rm -rf build_aide dist_aide

python3 setup_aide.py py2app --quiet

echo ""
echo "🎉 빌드 완료!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 앱 위치: $SCRIPT_DIR/dist_aide/AIDE.app"
echo "👉 응용 프로그램 폴더로 이동 후 실행하세요"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
