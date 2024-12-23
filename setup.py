# setup.py

from setuptools import setup
import os

APP = ['TMP-Networks-Browser-Mini.py']
OPTIONS = {
    'argv_emulation': True,
    'iconfile': os.path.join('assets', 'logo.icns'),  # Pfad zum .icns-Icon
    'packages': ['PyQt6', 'vlc', 'requests'],
    'includes': [
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebChannel'
    ],
    'resources': [os.path.join('assets', 'logo.icns')],  # Weitere Ressourcen einbinden, falls nötig
    'excludes': ['PyQt5', 'tkinter'],
    'plist': {  # Optional: macOS-spezifische Einstellungen
        'CFBundleName': 'TMP-Networks Browser Mini',
        'CFBundleShortVersionString': '1.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleIdentifier': 'com.mtsmash.tmpnetworksbrowsermini',
    },
}

setup(
    app=APP,
    name='TMP-Networks-Browser-Mini',
    version='1.0',
    author='Dein Name',
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
