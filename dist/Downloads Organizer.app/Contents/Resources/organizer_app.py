#!/usr/bin/env python3
"""
Downloads Organizer - Menu Bar App
"""

import rumps
import subprocess
import threading
import shutil
import time
from datetime import datetime
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

WATCH_DIR = Path.home() / "Downloads"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".svg", ".avif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v", ".mxf", ".prproj"}
IGNORE_KEYWORDS = {"freepik", "hf", "magnifics", "kling"}


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


def process_file(file_path):
    if file_path.name.startswith(".") or file_path.suffix in (".crdownload", ".part", ".tmp"):
        return
    if file_path.parent != WATCH_DIR:
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
    dest_dir = WATCH_DIR / project_name / media_type
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
    def on_created(self, event):
        if not event.is_directory:
            time.sleep(1.0)
            process_file(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            time.sleep(0.5)
            process_file(Path(event.dest_path))


class OrganizerApp(rumps.App):
    def __init__(self):
        super().__init__("📁", quit_button=None)
        self.observer = None
        self.menu = [
            rumps.MenuItem("● 감시 중", callback=None),
            None,
            rumps.MenuItem("중지", callback=self.stop_watching),
            None,
            rumps.MenuItem("종료", callback=self.quit_app),
        ]
        # 앱 시작 시 자동으로 감시 시작
        self.start_watching()

    def start_watching(self):
        if self.observer and self.observer.is_alive():
            return

        self.observer = Observer()
        self.observer.schedule(DownloadHandler(), str(WATCH_DIR), recursive=False)
        self.observer.start()

        self.title = "📁"
        self.menu["● 감시 중"].title = "● 감시 중"
        self.menu["중지"].title = "중지"
        self.menu["중지"].set_callback(self.stop_watching)

    def stop_watching(self, _=None):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        self.title = "📁✕"
        self.menu["● 감시 중"].title = "○ 중지됨"
        self.menu["중지"].title = "시작"
        self.menu["중지"].set_callback(self.resume_watching)

    def resume_watching(self, _=None):
        self.start_watching()
        self.menu["● 감시 중"].title = "● 감시 중"
        self.menu["중지"].title = "중지"
        self.menu["중지"].set_callback(self.stop_watching)

    def quit_app(self, _):
        self.stop_watching()
        rumps.quit_application()


if __name__ == "__main__":
    OrganizerApp().run()
