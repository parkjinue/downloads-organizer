#!/usr/bin/env python3
"""
Downloads Organizer - Menu Bar App (자동 업데이트 + 폴더 설정)
"""

import rumps
import subprocess
import threading
import shutil
import time
import json
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# ── 설정 ──────────────────────────────────────────────────
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".svg", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".mxf", ".prproj"}
IGNORE_KEYWORDS = {"freepik", "hf", "magnifics", "kling"}

GITHUB_REPO = "parkjinue/downloads-organizer"
CURRENT_VERSION = "v1.0.26"

# 설정 파일 경로
PREFS_PATH = Path.home() / "Library" / "Application Support" / "DownloadsOrganizer" / "prefs.json"


# ── 설정 저장/불러오기 ────────────────────────────────────
def load_prefs():
    if PREFS_PATH.exists():
        with open(PREFS_PATH) as f:
            return json.load(f)
    return {"watch_dir": str(Path.home() / "Downloads")}


def save_prefs(prefs):
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PREFS_PATH, "w") as f:
        json.dump(prefs, f)


# ── 폴더 선택 다이얼로그 ──────────────────────────────────
def pick_folder():
    script = '''
    tell application "System Events"
        activate
    end tell
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
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "DownloadsOrganizer"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read())
            latest = data.get("tag_name", "")
            download_url = None
            for asset in data.get("assets", []):
                if asset["name"].endswith(".zip"):
                    download_url = asset["browser_download_url"]
                    break
            return latest, download_url
    except:
        return None, None


def download_and_update(download_url):
    try:
        tmp_zip = Path.home() / "Downloads" / "downloads_organizer_update.zip"
        app_path = Path("/Applications/Downloads Organizer.app")

        urllib.request.urlretrieve(download_url, tmp_zip)

        extract_dir = Path.home() / "Downloads" / "organizer_update"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(tmp_zip, 'r') as z:
            z.extractall(extract_dir)

        new_app = extract_dir / "Downloads Organizer.app"
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


# ── 메뉴바 앱 ─────────────────────────────────────────────
class OrganizerApp(rumps.App):
    def __init__(self):
        super().__init__("📁", quit_button=None)
        self.observer = None
        self.prefs = load_prefs()
        self.watch_dir = Path(self.prefs["watch_dir"])

        self.menu = [
            rumps.MenuItem("🟢 감시 중", callback=None),
            rumps.MenuItem(f"버전 {CURRENT_VERSION}", callback=None),
            None,
            rumps.MenuItem("중지", callback=self.stop_watching),
            rumps.MenuItem(f"📂 {self.watch_dir.name}", callback=None),
            rumps.MenuItem("폴더 변경", callback=self.change_folder),
            rumps.MenuItem("업데이트 확인", callback=self.check_for_update),
            None,
            rumps.MenuItem("종료", callback=self.quit_app),
        ]
        self.start_watching()
        threading.Thread(target=self._auto_check_update, daemon=True).start()

    def change_folder(self, _):
        folder = pick_folder()
        if folder:
            self.stop_watching()
            self.watch_dir = Path(folder)
            self.prefs["watch_dir"] = folder
            save_prefs(self.prefs)
            # 메뉴 폴더명 갱신
            for key in list(self.menu.keys()):
                if key.startswith("📂") or key.startswith("🗂") or "Documents" in key or "Downloads" in key or "Desktop" in key:
                    self.menu[key].title = f"📂 {self.watch_dir.name}"
                    break
            self.start_watching()
            send_notification("📁 폴더 변경 완료", f"감시 폴더: {self.watch_dir.name}")

    def _auto_check_update(self):
        time.sleep(3)
        latest, download_url = check_update()
        if latest and latest != CURRENT_VERSION:
            self._prompt_update(latest, download_url)

    def check_for_update(self, _):
        def _check():
            latest, download_url = check_update()
            if latest and latest != CURRENT_VERSION:
                self._prompt_update(latest, download_url)
            elif latest:
                send_notification("✅ 최신 버전", f"현재 {CURRENT_VERSION} 이 최신 버전입니다.")
            else:
                send_notification("❌ 확인 실패", "업데이트 서버에 연결할 수 없습니다.")
        threading.Thread(target=_check, daemon=True).start()

    def _prompt_update(self, latest, download_url):
        response = rumps.alert(
            title="업데이트 available",
            message=f"새 버전 {latest} 이 있습니다. 업데이트할까요?",
            ok="업데이트",
            cancel="나중에"
        )
        if response == 1 and download_url:
            threading.Thread(target=download_and_update, args=(download_url,), daemon=True).start()

    def start_watching(self):
        if self.observer and self.observer.is_alive():
            return
        self.observer = Observer()
        self.observer.schedule(DownloadHandler(self.watch_dir), str(self.watch_dir), recursive=False)
        self.observer.start()
        self.title = "📁"
        self.menu["🟢 감시 중"].title = "🟢 감시 중"
        self.menu["중지"].title = "중지"
        self.menu["중지"].set_callback(self.stop_watching)

    def stop_watching(self, _=None):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
        self.title = "📁✕"
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
    OrganizerApp().run()
