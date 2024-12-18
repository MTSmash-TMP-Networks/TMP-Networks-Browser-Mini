from setuptools import setup

APP = ['TMP-Networks-Browser-Mini.py']
DATA_FILES = ['icons', 'assets/logo.icns']
OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'assets/logo.icns',  # Pfad zu Ihrer .icns-Datei
    'packages': ['PyQt5', 'PyQtWebEngine'],
    'includes': ['sys', 'os'],
    'plist': {
        'CFBundleName': 'TMP-Networks-Browser-Mini',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleIdentifier': 'com.tmp.networks.browsermini',
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
