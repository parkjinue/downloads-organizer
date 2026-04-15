#!/usr/bin/env python3
"""
AIDE - AI Creative Assistant
"""

import re
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
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".svg", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".mxf", ".prproj"}
IGNORE_KEYWORDS = {"freepik", "hf", "magnifics", "kling"}

GITHUB_REPO = "parkjinue/downloads-organizer"
CURRENT_VERSION = "v1.0.26"

PREFS_PATH = Path.home() / "Library" / "Application Support" / "AIDE" / "prefs.json"
LIBRARY_PATH = Path.home() / "Library" / "Application Support" / "AIDE" / "library.json"
HTML_PATH = Path(__file__).parent / "aide_library.html"

# 업데이트 중 파일 처리 차단 플래그
_updating = False

# 배치 동의 캐시: {project: expiry_timestamp}
_batch_consent = {}
_batch_lock = threading.Lock()
_pending_files = []
_pending_lock = threading.Lock()
_batch_timer = None


# ── 설정 ──────────────────────────────────────────────────
def load_prefs():
    if PREFS_PATH.exists():
        with open(PREFS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"watch_dir": str(Path.home() / "Downloads"), "current_project": "", "foldering": True}


def save_prefs(prefs):
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False)


def load_library():
    if LIBRARY_PATH.exists():
        with open(LIBRARY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"projects": [], "prompts": []}


def save_library(data):
    LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LIBRARY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 다이얼로그 ──────────────────────────────────────────
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


def input_dialog(title, message, default=""):
    script = f'tell application "System Events" to set r to text returned of (display dialog "{message}" with title "{title}" default answer "{default}")'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def confirm_dialog(title, message):
    script = f'tell application "System Events" to set r to button returned of (display dialog "{message}" with title "{title}" buttons {{"취소", "확인"}} default button "확인")'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.returncode == 0 and "확인" in result.stdout


def send_notification(title, message):
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], capture_output=True)


# ── 자동 업데이트 ──────────────────────────────────────
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
    global _updating
    _updating = True
    try:
        import sys
        ts = int(time.time())
        tmp_zip = Path.home() / "Downloads" / f"aide_update_{ts}.zip"
        extract_dir = Path.home() / "Downloads" / f"aide_update_{ts}"

        exe_path = Path(sys.executable)
        if "Contents" in str(exe_path):
            app_path = exe_path.parent.parent.parent
        else:
            app_path = Path("/Applications/AIDE.app")

        send_notification("⬇️ 다운로드 중", "새 버전 다운로드 중...")
        urllib.request.urlretrieve(download_url, str(tmp_zip))

        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(str(tmp_zip), "r") as z:
            z.extractall(str(extract_dir))

        new_app = None
        for item in extract_dir.rglob("*.app"):
            new_app = item
            break

        if new_app is None:
            raise Exception("App file not found")

        app_path_str = str(app_path)
        new_app_str = str(new_app)
        extract_dir_str = str(extract_dir)
        tmp_zip_str = str(tmp_zip)
        update_script_path = str(Path.home() / "Downloads" / f"aide_updater_{ts}.sh")

        lines_sh = [
            "#!/bin/bash",
            "sleep 2",
            f'cp -R "{app_path_str}" "{app_path_str}.bak" 2>/dev/null || true',
            f'rm -rf "{app_path_str}"',
            f'mv "{new_app_str}" "{app_path_str}"',
            "if [ $? -eq 0 ]; then",
            f'    rm -rf "{app_path_str}.bak"',
            f'    rm -rf "{extract_dir_str}"',
            f'    rm -f "{tmp_zip_str}"',
            f'    xattr -rd com.apple.quarantine "{app_path_str}" 2>/dev/null || true',
            f'    xattr -cr "{app_path_str}" 2>/dev/null || true',
            f'    chmod -R 755 "{app_path_str}"',
            f'    open "{app_path_str}"',
            "else",
            f'    mv "{app_path_str}.bak" "{app_path_str}"',
            f'    open "{app_path_str}"',
            "fi",
            f'rm -f "{update_script_path}"',
        ]
        script_content = "\n".join(lines_sh) + "\n"

        with open(update_script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        os.chmod(update_script_path, 0o755)

        subprocess.Popen(["bash", update_script_path])
        send_notification("✅ 업데이트 준비 완료", "앱이 재시작됩니다.")
        time.sleep(1)
        rumps.quit_application()

    except Exception as e:
        _updating = False
        send_notification("❌ 업데이트 실패", str(e))


# ── 파일 처리 ──────────────────────────────────────────
def get_media_type(ext):
    ext = ext.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    elif ext in VIDEO_EXTENSIONS:
        return "video"
    return None


def should_ignore_keyword(name):
    first = name.split("_")[0] if "_" in name else name
    if first.isdigit():
        return True
    if first.lower() in IGNORE_KEYWORDS:
        return True
    return False


def is_date_prefix(name):
    """MMDD 형식인지 정확히 검사 (월 01-12, 일 01-31)"""
    m = re.match(r'^(\d{2})(\d{2})_', name)
    if not m:
        return False
    month, day = int(m.group(1)), int(m.group(2))
    return 1 <= month <= 12 and 1 <= day <= 31


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


def has_batch_consent(project):
    """5분 배치 동의 캐시 확인"""
    with _batch_lock:
        expiry = _batch_consent.get(project, 0)
        return time.time() < expiry


def set_batch_consent(project, minutes=5):
    with _batch_lock:
        _batch_consent[project] = time.time() + minutes * 60


def move_file(file_path, dest_path):
    prev_size = -1
    for _ in range(10):
        try:
            curr_size = file_path.stat().st_size
        except:
            return False
        if curr_size == prev_size:
            break
        prev_size = curr_size
        time.sleep(0.3)
    try:
        shutil.move(str(file_path), str(dest_path))
        return True
    except Exception as e:
        send_notification("❌ 파일 이동 실패", f"{file_path.name}: {e}")
        return False


def process_file(file_path, watch_dir, current_project, foldering):
    global _updating
    if _updating:
        return

    if file_path.name.startswith(".") or file_path.suffix in (".crdownload", ".part", ".tmp"):
        return
    if file_path.parent != watch_dir:
        return
    if not file_path.exists() or not file_path.is_file():
        return

    name = file_path.stem
    ext = file_path.suffix
    media_type = get_media_type(ext)

    if media_type is None:
        return

    date_prefix = datetime.now().strftime("%m%d")

    # ── 프로젝트 모드 ON ──────────────────────────────
    if current_project:
        # 다른 프로젝트명 감지 시 확인 (배치 동의 없을 때만)
        if "_" in name:
            file_project = name.split("_")[0]
            if (file_project != current_project
                    and not should_ignore_keyword(name)
                    and not has_batch_consent(current_project)):
                confirmed = confirm_dialog(
                    "프로젝트 확인",
                    f"파일명의 프로젝트({file_project})가\n현재 설정된 프로젝트({current_project})와 다릅니다.\n\n{current_project} 폴더로 이동할까요?\n(확인 시 5분간 자동 동의)"
                )
                if confirmed:
                    set_batch_consent(current_project)
                else:
                    return

        # 파일명: 날짜 없으면 추가, 있으면 그대로
        if is_date_prefix(name):
            new_stem = name
        else:
            new_stem = f"{date_prefix}_{name}"

        if foldering:
            dest_dir = watch_dir / current_project / media_type
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{new_stem}{ext}"
        else:
            dest_path = watch_dir / f"{new_stem}{ext}"

    # ── 프로젝트 모드 OFF ─────────────────────────────
    else:
        if "_" not in name:
            return
        if should_ignore_keyword(name):
            return

        parts = name.split("_", 1)
        project_name = parts[0]
        rest_name = parts[1]

        if is_date_prefix(name):
            new_stem = name
        else:
            new_stem = f"{date_prefix}_{rest_name}"

        if foldering:
            dest_dir = watch_dir / project_name / media_type
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{new_stem}{ext}"
        else:
            dest_path = watch_dir / f"{new_stem}{ext}"

    dest_path = get_unique_path(dest_path)

    if move_file(file_path, dest_path):
        if foldering and current_project:
            send_notification("📁 파일 정리 완료", f"{dest_path.name} → {current_project}/{media_type}/")
        elif foldering:
            send_notification("📁 파일 정리 완료", f"{dest_path.name} → {dest_path.parent.name}/")
        else:
            send_notification("📝 파일명 변경 완료", f"{file_path.name} → {dest_path.name}")


# ── 배치 처리 (3개 이상 동시) ──────────────────────────
def handle_batch(files, watch_dir, current_project, foldering):
    """3개 이상 파일 동시 감지 시 한번에 확인"""
    if not current_project:
        for f in files:
            process_file(f, watch_dir, current_project, foldering)
        return

    if has_batch_consent(current_project):
        for f in files:
            process_file(f, watch_dir, current_project, foldering)
        return

    names = "\n".join([f.name for f in files[:5]])
    if len(files) > 5:
        names += f"\n... 외 {len(files)-5}개"

    confirmed = confirm_dialog(
        "파일 일괄 이동",
        f"파일 {len(files)}개가 감지됐습니다.\n\n{names}\n\n모두 [{current_project}] 폴더로 이동할까요?\n(확인 시 5분간 자동 동의)"
    )
    if confirmed:
        set_batch_consent(current_project)
        for f in files:
            process_file(f, watch_dir, current_project, foldering)


class DownloadHandler(FileSystemEventHandler):
    def __init__(self, watch_dir, app):
        self.watch_dir = watch_dir
        self.app = app
        self._pending = []
        self._timer = None
        self._lock = threading.Lock()

    def _flush(self):
        with self._lock:
            files = list(self._pending)
            self._pending.clear()
            self._timer = None
        if not files:
            return
        if len(files) >= 3:
            threading.Thread(
                target=handle_batch,
                args=(files, self.watch_dir, self.app.current_project, self.app.foldering),
                daemon=True
            ).start()
        else:
            for f in files:
                threading.Thread(
                    target=process_file,
                    args=(f, self.watch_dir, self.app.current_project, self.app.foldering),
                    daemon=True
                ).start()

    def _schedule(self, path):
        with self._lock:
            self._pending.append(Path(path))
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(1.5, self._flush)
            self._timer.start()

    def on_created(self, event):
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._schedule(event.dest_path)


# ── JS API ────────────────────────────────────────────
class LibraryAPI:
    def __init__(self):
        self.data = load_library()

    def get_data(self):
        return json.dumps(self.data, ensure_ascii=False)

    def save_data(self, data_str):
        self.data = json.loads(data_str)
        save_library(self.data)
        return "ok"


# ── 메뉴바 앱 ─────────────────────────────────────────
class AIDEApp(rumps.App):
    def __init__(self):
        super().__init__("✦", quit_button=None)
        self.observer = None
        self.prefs = load_prefs()
        self.watch_dir = Path(self.prefs["watch_dir"])
        self.current_project = self.prefs.get("current_project", "")
        self.foldering = self.prefs.get("foldering", True)
        self.api = LibraryAPI()
        self.folder_item = rumps.MenuItem(f"📂 {self.watch_dir.name}", callback=None)

        self._build_menu()
        self.start_watching()
        threading.Thread(target=self._auto_check_update, daemon=True).start()

    def _build_menu(self):
        proj_label = self.current_project if self.current_project else "설정 안됨"
        fold_label = "🟢 폴더링 [  켜짐  ]" if self.foldering else "🔴 폴더링 [  꺼짐  ]"

        self.project_item = rumps.MenuItem(f"🎯 ─── {proj_label} ───", callback=self.set_project)
        self.foldering_item = rumps.MenuItem(fold_label, callback=self.toggle_foldering)

        self.menu = [
            rumps.MenuItem("🟢 감시 중", callback=None),
            rumps.MenuItem(f"버전 {CURRENT_VERSION}", callback=None),
            None,
            self.project_item,
            self.foldering_item,
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

    def set_project(self, _=None):
        def _ask():
            current = self.current_project or ""
            result = input_dialog(
                "현재 프로젝트 설정",
                "프로젝트명을 입력하세요.\n(비우면 파일명 기준으로 자동 분류)",
                current
            )
            if result is not None:
                self.current_project = result.strip()
                self.prefs["current_project"] = self.current_project
                save_prefs(self.prefs)
                label = self.current_project if self.current_project else "설정 안됨"
                self.project_item.title = f"🎯 ─── {label} ───"
        threading.Thread(target=_ask, daemon=True).start()

    def toggle_foldering(self, _=None):
        self.foldering = not self.foldering
        self.prefs["foldering"] = self.foldering
        save_prefs(self.prefs)
        self.foldering_item.title = "🟢 폴더링 [  켜짐  ]" if self.foldering else "🔴 폴더링 [  꺼짐  ]"

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
            send_notification("🆕 AIDE 업데이트", f"새 버전 {latest} 이 있습니다. 메뉴바에서 업데이트 확인을 눌러주세요.")

    def check_for_update(self, _=None):
        latest, download_url = check_update()
        if latest and latest != CURRENT_VERSION:
            send_notification("🆕 업데이트 발견", f"새 버전 {latest} 다운로드 중...")
            threading.Thread(target=download_and_update, args=(download_url,), daemon=True).start()
        elif latest:
            send_notification("✅ 최신 버전", f"{CURRENT_VERSION} 이 최신 버전입니다.")
        else:
            send_notification("❌ 확인 실패", "업데이트 서버에 연결할 수 없습니다.")

    def start_watching(self):
        if self.observer and self.observer.is_alive():
            return
        self.observer = Observer()
        self.observer.schedule(DownloadHandler(self.watch_dir, self), str(self.watch_dir), recursive=False)
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
