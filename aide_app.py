#!/usr/bin/env python3
"""
AIDE - AI Creative Assistant
메뉴바 앱 + 프롬프트 라이브러리
"""

import rumps
import subprocess
import threading
import shutil
import time
import json
import urllib.request
import zipfile
import os
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler, BaseHTTPRequestHandler
import urllib.parse
from datetime import datetime
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ── 설정 ──────────────────────────────────────────────────
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".svg", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".mxf", ".prproj"}
IGNORE_KEYWORDS = {"freepik", "hf", "magnifics", "kling"}

GITHUB_REPO = "parkjinue/downloads-organizer"
CURRENT_VERSION = "v1.0.13"

PREFS_PATH = Path.home() / "Library" / "Application Support" / "AIDE" / "prefs.json"
LIBRARY_PATH = Path.home() / "Library" / "Application Support" / "AIDE" / "library.json"
HTML_PATH = Path(__file__).parent / "aide_library.html"


# ── 데이터 저장/불러오기 ──────────────────────────────────
def load_prefs():
    if PREFS_PATH.exists():
        with open(PREFS_PATH) as f:
            return json.load(f)
    return {"watch_dir": str(Path.home() / "Downloads")}


def save_prefs(prefs):
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PREFS_PATH, "w") as f:
        json.dump(prefs, f)


def load_library():
    if LIBRARY_PATH.exists():
        with open(LIBRARY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"projects": [], "prompts": []}


def save_library(data):
    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LIBRARY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 폴더 선택 ─────────────────────────────────────────────
def pick_folder():
    script = '''
    tell application "Finder"
        activate
        set chosen to choose folder with prompt "감시할 폴더를 선택하세요"
        return POSIX path of chosen
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    return None


# ── 자동 업데이트 ─────────────────────────────────────────
def check_update():
    try:
        import ssl
        ctx = ssl.create_default_context()
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 AIDE/1.0",
            "Accept": "application/vnd.github.v3+json"
        })
        with urllib.request.urlopen(req, timeout=10, context=ctx) as res:
            data = json.loads(res.read().decode("utf-8"))
            latest = data.get("tag_name", "")
            download_url = None
            for asset in data.get("assets", []):
                if asset["name"].endswith(".zip"):
                    download_url = asset["browser_download_url"]
                    break
            return latest, download_url
    except Exception as e:
        print(f"업데이트 확인 실패: {e}")
        return None, None


def download_and_update(download_url):
    try:
        tmp_zip = Path.home() / "Downloads" / f"aide_update_{int(time.time())}.zip"
        app_path = Path("/Applications/AIDE.app")
        urllib.request.urlretrieve(download_url, tmp_zip)
        extract_dir = Path.home() / "Downloads" / f"aide_update_{int(time.time())}"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(tmp_zip, 'r') as z:
            z.extractall(extract_dir)
        new_app = extract_dir / "AIDE.app"
        if app_path.exists():
            shutil.rmtree(app_path)
        shutil.move(str(new_app), str(app_path))
        tmp_zip.unlink()
        shutil.rmtree(extract_dir)
        send_notification("✅ 업데이트 완료", "앱을 재실행해주세요.")
    except Exception as e:
        send_notification("❌ 업데이트 실패", str(e))


# ── 파일 처리 ─────────────────────────────────────────────
def get_media_type(ext):
    ext = ext.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    elif ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def should_ignore(project_name):
    if project_name.isdigit():
        return True
    if project_name.lower() in IGNORE_KEYWORDS:
        return True
    return False


def send_notification(title, message):
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


def get_unique_path(target_path):
    if not target_path.exists():
        return target_path
    stem = target_path.stem
    suffix = target_path.suffix
    parent = target_path.parent
    counter = 1
    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def process_file(file_path, watch_dir):
    if file_path.name.startswith(".") or file_path.suffix in (".crdownload", ".part", ".tmp"):
        return
    if file_path.parent != watch_dir:
        return
    if not file_path.exists() or not file_path.is_file():
        return
    name = file_path.stem
    ext = file_path.suffix
    if "_" not in name:
        return
    parts = name.split("_", 1)
    project_name = parts[0]
    rest_name = parts[1]
    if not project_name or not rest_name:
        return
    if should_ignore(project_name):
        return
    media_type = get_media_type(ext)
    if media_type is None:
        return
    date_prefix = datetime.now().strftime("%m%d")
    dest_dir = watch_dir / project_name / media_type
    dest_dir.mkdir(parents=True, exist_ok=True)
    new_filename = f"{date_prefix}_{rest_name}{ext}"
    dest_path = dest_dir / new_filename
    dest_path = get_unique_path(dest_path)
    try:
        prev_size = -1
        for _ in range(10):
            curr_size = file_path.stat().st_size
            if curr_size == prev_size:
                break
            prev_size = curr_size
            time.sleep(0.3)
        shutil.move(str(file_path), str(dest_path))
        send_notification("📁 파일 정리 완료", f"{dest_path.name} → {project_name}/{media_type}/")
    except Exception as e:
        print(f"❌ 오류: {e}")


class DownloadHandler(FileSystemEventHandler):
    def __init__(self, watch_dir):
        self.watch_dir = watch_dir

    def on_created(self, event):
        if not event.is_directory:
            time.sleep(1.0)
            process_file(Path(event.src_path), self.watch_dir)

    def on_moved(self, event):
        if not event.is_directory:
            time.sleep(0.5)
            process_file(Path(event.dest_path), self.watch_dir)


# ── JS API (웹뷰 ↔ Python 통신) ───────────────────────────
class LibraryAPI:
    def __init__(self):
        self.data = load_library()

    def get_data(self):
        return json.dumps(self.data, ensure_ascii=False)

    def save_data(self, data_str):
        self.data = json.loads(data_str)
        save_library(self.data)
        return "ok"


# ── 메뉴바 앱 ─────────────────────────────────────────────
class AIDEApp(rumps.App):
    def __init__(self):
        super().__init__("✦", quit_button=None)
        self.observer = None
        self.prefs = load_prefs()
        self.watch_dir = Path(self.prefs["watch_dir"])
        self.window = None
        self.api = LibraryAPI()

        self.folder_item = rumps.MenuItem(f"📂 {self.watch_dir.name}", callback=None)
        self.menu = [
            rumps.MenuItem("🟢 감시 중", callback=None),
            rumps.MenuItem(f"버전 {CURRENT_VERSION}", callback=None),
            None,
            rumps.MenuItem("📚 라이브러리 열기", callback=self.open_library),
            None,
            rumps.MenuItem("중지", callback=self.stop_watching),
            self.folder_item,
            rumps.MenuItem("폴더 변경", callback=self.change_folder),
            rumps.MenuItem("업데이트 확인", callback=self.check_for_update),
            None,
            rumps.MenuItem("종료", callback=self.quit_app),
        ]
        self.start_watching()
        threading.Thread(target=self._auto_check_update, daemon=True).start()

    def open_library(self, _=None):
        api = self.api
        html_dir = str(HTML_PATH.parent)

        class AIDEHandler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass

            def do_GET(self):
                if self.path == '/api/data':
                    data = api.get_data().encode('utf-8')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    path = self.path.split('?')[0]
                    filepath = os.path.join(html_dir, path.lstrip('/'))
                    if not os.path.exists(filepath):
                        filepath = os.path.join(html_dir, 'aide_library.html')
                    try:
                        with open(filepath, 'rb') as f:
                            content = f.read()
                        self.send_response(200)
                        if filepath.endswith('.html'):
                            self.send_header('Content-Type', 'text/html; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(content)
                    except:
                        self.send_response(404)
                        self.end_headers()

            def do_POST(self):
                if self.path == '/api/save':
                    length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(length).decode('utf-8')
                    api.save_data(body)
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(b'ok')

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()

        if not hasattr(self, '_server_started'):
            self._server_started = True
            server = HTTPServer(('localhost', 18765), AIDEHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            time.sleep(0.3)
        webbrowser.open('http://localhost:18765/aide_library.html')

    def change_folder(self, _=None):
        folder = pick_folder()
        if folder:
            self.stop_watching()
            self.watch_dir = Path(folder)
            self.prefs["watch_dir"] = folder
            save_prefs(self.prefs)
            self.folder_item.title = f"📂 {self.watch_dir.name}"
            self.start_watching()
            send_notification("📁 폴더 변경 완료", f"감시 폴더: {self.watch_dir.name}")

    def _auto_check_update(self):
        time.sleep(3)
        latest, download_url = check_update()
        if latest and latest != CURRENT_VERSION:
            send_notification(
                "🆕 AIDE 업데이트",
                f"새 버전 {latest} 이 있습니다. 메뉴바에서 업데이트 확인을 눌러주세요."
            )
            self._pending_update = (latest, download_url)

    def check_for_update(self, _=None):
        latest, download_url = check_update()
        if latest and latest != CURRENT_VERSION:
            send_notification(
                "🆕 업데이트 발견",
                f"새 버전 {latest} 다운로드 중..."
            )
            threading.Thread(target=download_and_update, args=(download_url,), daemon=True).start()
        elif latest:
            send_notification("✅ 최신 버전", f"{CURRENT_VERSION} 이 최신 버전입니다.")
        else:
            send_notification("❌ 확인 실패", "업데이트 서버에 연결할 수 없습니다.")

    def _prompt_update(self, latest, download_url):
        pass

    def start_watching(self):
        if self.observer and self.observer.is_alive():
            return
        self.observer = Observer()
        self.observer.schedule(DownloadHandler(self.watch_dir), str(self.watch_dir), recursive=False)
        self.observer.start()
        self.title = "✦"
        self.menu["🟢 감시 중"].title = "🟢 감시 중"
        self.menu["중지"].title = "중지"
        self.menu["중지"].set_callback(self.stop_watching)

    def stop_watching(self, _=None):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.title = "✦✕"
        self.menu["🟢 감시 중"].title = "🟡 중지됨"
        self.menu["중지"].title = "시작"
        self.menu["중지"].set_callback(self.resume_watching)

    def resume_watching(self, _=None):
        self.start_watching()
        self.menu["🟡 중지됨"].title = "🟢 감시 중"
        self.menu["중지"].title = "중지"
        self.menu["중지"].set_callback(self.stop_watching)

    def quit_app(self, _):
        self.stop_watching()
        rumps.quit_application()


if __name__ == "__main__":
    AIDEApp().run()
