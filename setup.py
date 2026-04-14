from setuptools import setup

APP = ['organizer_app.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,  # 독(Dock)에 안 보이게
        'CFBundleName': 'Downloads Organizer',
        'CFBundleDisplayName': 'Downloads Organizer',
        'CFBundleVersion': '1.0.0',
        'NSUserNotificationAlertStyle': 'alert',
    },
    'packages': ['rumps', 'watchdog'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
