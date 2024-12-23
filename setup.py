# setup.py

from setuptools import setup
import os

APP = ['TMP-Networks-Browser-Mini.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'iconfile': 'assets/logo.icns',  # Pfad zum .icns-Icon
    'packages': ['PyQt6', 'vlc', 'requests'],  # Stelle sicher, dass alle benötigten Pakete enthalten sind
    'includes': ['PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets', 'PyQt6.QtWebChannel'],
    'resources': ['assets/logo.icns'],  # Optional: Weitere Ressourcen einbinden
    'excludes': ['PyQt5', 'tkinter'],  # Optional: Nicht benötigte Pakete ausschließen
    'plist': {  # Optional: macOS-spezifische Einstellungen
        'CFBundleName': 'TMP-Networks Browser Mini',
        'CFBundleShortVersionString': '1.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleIdentifier': 'com.deinname.tmpnetworksbrowsermini',
    },
}

setup(
    app=APP,
    name='TMP-Networks-Browser-Mini',
    version='1.0',
    author='Dein Name',
    options={'py2app': OPTIONS},
    data_files=DATA_FILES,
    setup_requires=['py2app'],
)
