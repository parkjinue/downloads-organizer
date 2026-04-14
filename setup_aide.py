from setuptools import setup

APP = ['aide_app.py']
DATA_FILES = [('', ['aide_library.html', 'AIDE.icns'])]
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,
        'CFBundleName': 'AIDE',
        'CFBundleDisplayName': 'AIDE',
        'CFBundleVersion': '1.0.0',
        'CFBundleIconFile': 'AIDE',
        'NSUserNotificationAlertStyle': 'alert',
    },
    'packages': ['rumps', 'watchdog', 'webview'],
    'dist_dir': 'dist_aide',
    'bdist_base': 'build_aide',
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
