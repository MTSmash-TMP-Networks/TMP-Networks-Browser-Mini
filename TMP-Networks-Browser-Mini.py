#!/usr/bin/env python3
# TMP-Networks-Browser-Mini.py
#
# NEU (Instagram/yt-dlp):
# - Exportiert Cookies für yt-dlp aus dem QtWebEngine Profil:
#  1) bevorzugt aus Chromium Cookie DB (persistenter Store)
#   2) fallback: aus QWebEngineCookieStore Events
# - Übergibt an yt-dlp:
#   - cookiefile
#   - user_agent (aus QWebEngineProfile)
#   - http_headers (Accept-Language, Referer)
#
# Hinweis: Instagram Stories sind sehr restriktiv. Oft braucht yt-dlp eine konkrete Story-URL (mit ID).

import os
import sys

# ---------------------------------------------------------
# MUSS vor allen QtWebEngine-Imports passieren (macOS .app)
# ---------------------------------------------------------
def _early_disable_proxy_for_qtwebengine():
    for k in (
        "http_proxy", "https_proxy", "all_proxy", "no_proxy",
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"
    ):
        os.environ.pop(k, None)

    extra = "--no-proxy-server --proxy-auto-detect=false"
    existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (existing + " " + extra).strip() if existing else extra

_early_disable_proxy_for_qtwebengine()

import json
import re
import socket
import sqlite3
import shutil
import time
from datetime import datetime
from functools import partial
import importlib.util
from collections import deque
from urllib.parse import quote_plus

import whois
import vlc
import yt_dlp

from PyQt6.QtNetwork import QNetworkProxy, QNetworkProxyFactory, QNetworkCookie
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QLineEdit, QWidget,
    QTabWidget, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QDialog, QPushButton, QLabel, QMenu, QListWidget, QListWidgetItem, QHBoxLayout,
    QSizePolicy, QFrame, QSlider, QTextEdit, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar
)
from PyQt6.QtGui import QAction, QFont, QDesktopServices, QIcon
from PyQt6.QtCore import QUrl, QSize, Qt, QTimer, QThread
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineSettings, QWebEngineDownloadRequest, QWebEngineProfile
)
from PyQt6.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from appdirs import AppDirs


# ---------------------------
# Datenpfade
# ---------------------------
dirs = AppDirs("TMPNetworksBrowserMini", "DeinName")
json_dir = dirs.user_data_dir
json_path = os.path.join(json_dir, "favoriten_und_passwoerter.json")
os.makedirs(json_dir, exist_ok=True)
DATA_FILE = json_path


# ---------------------------
# Styling (Epic Dark Theme)
# ---------------------------
EPIC_QSS = """
QMainWindow { background: #0b0f17; }
QMenuBar { background: #0e1420; color: #e7eefc; padding: 6px; }
QMenuBar::item { background: transparent; padding: 6px 10px; border-radius: 8px; }
QMenuBar::item:selected { background: #1a2740; }
QMenu { background: #0e1420; color: #e7eefc; border: 1px solid #22314f; padding: 6px; }
QMenu::item { padding: 8px 14px; border-radius: 8px; }
QMenu::item:selected { background: #1a2740; }

QToolBar { background: #0e1420; border: none; spacing: 8px; padding: 8px; }
QToolButton { background: #121b2b; color: #e7eefc; border: 1px solid #22314f; padding: 8px 10px; border-radius: 10px; }
QToolButton:hover { background: #17223a; border: 1px solid #2f4675; }
QToolButton:pressed { background: #0f1728; }

QLineEdit {
    background: #0b1220; color: #e7eefc;
    border: 1px solid #22314f; border-radius: 12px;
    padding: 10px 12px; selection-background-color: #2f6cff;
}
QLineEdit:focus { border: 1px solid #2f6cff; }

QTabWidget::pane { border: 1px solid #22314f; top: -1px; background: #0b0f17; }
QTabBar::tab {
    background: #0e1420; color: #cfe0ff;
    border: 1px solid #22314f;
    padding: 10px 14px; margin-right: 6px;
    border-top-left-radius: 12px; border-top-right-radius: 12px;
}
QTabBar::tab:selected { background: #121b2b; color: #ffffff; border: 1px solid #2f4675; }
QTabBar::tab:hover { background: #17223a; }

QStatusBar { background: #0e1420; color: #cfe0ff; border-top: 1px solid #22314f; }
QProgressBar {
    border: 1px solid #22314f; border-radius: 8px;
    text-align: center; color: #e7eefc; background: #0b1220;
}
QProgressBar::chunk { border-radius: 8px; background-color: #2f6cff; }

QDialog { background: #0b0f17; color: #e7eefc; }
QLabel { color: #e7eefc; }
QPushButton {
    background: #121b2b; color: #e7eefc;
    border: 1px solid #22314f; padding: 10px 12px; border-radius: 10px;
}
QPushButton:hover { background: #17223a; border: 1px solid #2f4675; }
QPushButton:pressed { background: #0f1728; }

QTableWidget { background: #0b1220; color: #e7eefc; border: 1px solid #22314f; gridline-color: #22314f; }
QHeaderView::section { background: #0e1420; color: #cfe0ff; padding: 8px; border: 1px solid #22314f; }
QListWidget { background: #0b1220; color: #e7eefc; border: 1px solid #22314f; }
QListWidget::item { padding: 10px; border-radius: 10px; }
QListWidget::item:selected { background: #1a2740; }
"""


def get_emoji_font():
    return QFont("Noto Color Emoji", 16)


def looks_like_url(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if re.match(r'^[a-zA-Z][a-zA-Z0-9+\-.]*://', t):
        return True
    if " " in t:
        return False
    if t.lower().startswith("localhost"):
        return True
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}(:\d+)?(/.*)?$', t):
        return True
    if "." in t and not t.startswith(".") and not t.endswith("."):
        return True
    return False


def normalize_to_url(text: str) -> QUrl:
    t = text.strip()
    q = QUrl(t)
    if q.scheme() == "":
        q.setScheme("http")
    return q


def google_search_url(query: str) -> QUrl:
    return QUrl(f"https://www.google.com/search?q={quote_plus(query)}")


# ---------------------------
# Cookie Export (Fallback): QWebEngineCookieStore -> cookies.txt
# ---------------------------
class WebEngineCookieStoreJar:
    """
    Fallback: sammelt Cookies aus cookieStore() Events und schreibt Netscape cookies.txt.
    Das kann bei Instagram unvollständig sein, ist aber besser als nichts.
    """
    def __init__(self, profile: QWebEngineProfile, cookie_txt_path: str, parent=None):
        self.profile = profile
        self.cookie_txt_path = cookie_txt_path
        self.cookies = {}  # (domain, path, name) -> dict

        store = self.profile.cookieStore()
        store.cookieAdded.connect(self._on_cookie_added)
        store.cookieRemoved.connect(self._on_cookie_removed)
        store.loadAllCookies()

        self._save_timer = QTimer(parent)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self.save_to_netscape)

    def _cookie_key(self, c: QNetworkCookie):
        name = bytes(c.name()).decode("utf-8", "ignore")
        domain = c.domain()
        path = c.path() or "/"
        return (domain, path, name)

    def _on_cookie_added(self, c: QNetworkCookie):
        key = self._cookie_key(c)
        name = bytes(c.name()).decode("utf-8", "ignore")
        value = bytes(c.value()).decode("utf-8", "ignore")

        exp = c.expirationDate()
        expires = int(exp.toSecsSinceEpoch()) if exp.isValid() else 0

        domain = (c.domain() or "").strip()
        path = c.path() or "/"
        secure = bool(c.isSecure())

        self.cookies[key] = {
            "domain": domain,
            "include_subdomains": True,
            "path": path,
            "secure": secure,
            "expires": expires,
            "name": name,
            "value": value,
        }
        self._save_timer.start(700)

    def _on_cookie_removed(self, c: QNetworkCookie):
        key = self._cookie_key(c)
        if key in self.cookies:
            del self.cookies[key]
        self._save_timer.start(700)

    def save_to_netscape(self):
        try:
            os.makedirs(os.path.dirname(self.cookie_txt_path), exist_ok=True)
            with open(self.cookie_txt_path, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Generated by TMP-Networks-Browser-Mini (QtWebEngine cookieStore)\n\n")
                for _, c in self.cookies.items():
                    domain = c["domain"]
                    if not domain:
                        continue
                    if not domain.startswith("."):
                        domain = "." + domain
                    include_sub = "TRUE" if c["include_subdomains"] else "FALSE"
                    path = c["path"] or "/"
                    secure = "TRUE" if c["secure"] else "FALSE"
                    expires = str(c["expires"])
                    f.write(f"{domain}\t{include_sub}\t{path}\t{secure}\t{expires}\t{c['name']}\t{c['value']}\n")
        except Exception as e:
            print(f"[CookieStoreJar] Fehler: {e}")


# ---------------------------
# Cookie Export (Preferred): Chromium Cookie DB -> cookies.txt
# ---------------------------
class ChromiumCookieDBExporter:
    """
    Liest Cookies aus QtWebEngine persistent storage (Chromium Cookie DB) und
    exportiert sie als Netscape cookies.txt für yt-dlp.

    Das ist i.d.R. näher an "echten Browser Cookies" als cookieStore Events.
    """
    def __init__(self, profile: QWebEngineProfile, cookie_txt_path: str, parent=None):
        self.profile = profile
        self.cookie_txt_path = cookie_txt_path
        self._timer = QTimer(parent)
        self._timer.setInterval(4000)  # alle 4 Sekunden aktualisieren (leichtgewichtig)
        self._timer.timeout.connect(self.export_now)
        self._timer.start()

    def _possible_cookie_db_paths(self) -> list[str]:
        base = self.profile.persistentStoragePath()
        # QtWebEngine legt je nach Version/OS unterschiedliche Strukturen an.
        candidates = [
            os.path.join(base, "Default", "Cookies"),
            os.path.join(base, "Cookies"),
            os.path.join(base, "Profile 1", "Cookies"),
            os.path.join(base, "Network", "Cookies"),
            os.path.join(base, "Default", "Network", "Cookies"),
        ]
        # zusätzlich: alles durchsuchen (nur 1 Ebene tief)
        try:
            if os.path.isdir(base):
                for root, dirs, files in os.walk(base):
                    if "Cookies" in files:
                        candidates.append(os.path.join(root, "Cookies"))
        except Exception:
            pass

        # unique
        out = []
        for p in candidates:
            if p not in out:
                out.append(p)
        return out

    def _find_cookie_db(self) -> str | None:
        for p in self._possible_cookie_db_paths():
            if os.path.isfile(p):
                return p
        return None

    def export_now(self):
        db_path = self._find_cookie_db()
        if not db_path:
            return

        # Chromium hält DB oft gelockt -> copy to temp
        tmp_db = os.path.join(os.path.dirname(self.cookie_txt_path), "Cookies.tmp.sqlite")
        try:
            shutil.copy2(db_path, tmp_db)
        except Exception:
            return

        # Chrome/Chromium cookies schema:
        # host_key, name, value, path, expires_utc, is_secure, is_httponly, samesite, encrypted_value
        # value kann leer sein, dann encrypted_value gesetzt (macOS Keychain nötig).
        # QtWebEngine speichert auf macOS oft ebenfalls encrypted_value.
        # -> Wir können nur die unencrypted "value" exportieren. Wenn alles encrypted ist,
        #    geht es ohne Entschlüsselung nicht.
        #
        # Trotzdem: häufig sind genug Cookies unencrypted oder yt-dlp kommt mit csrftoken/sessionid klar.
        try:
            con = sqlite3.connect(tmp_db)
            cur = con.cursor()

            # Tabelle heißt meist "cookies"
            cur.execute("""
                SELECT host_key, name, value, path, expires_utc, is_secure, is_httponly
                FROM cookies
            """)
            rows = cur.fetchall()
            con.close()
        except Exception:
            try:
                con.close()
            except Exception:
                pass
            return
        finally:
            try:
                os.remove(tmp_db)
            except Exception:
                pass

        # Netscape export
        try:
            os.makedirs(os.path.dirname(self.cookie_txt_path), exist_ok=True)
            with open(self.cookie_txt_path, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Generated by TMP-Networks-Browser-Mini (QtWebEngine Chromium Cookie DB)\n\n")

                for host_key, name, value, path, expires_utc, is_secure, is_httponly in rows:
                    if not host_key or not name:
                        continue
                    # Wenn value leer ist, ist es evtl. encrypted_value -> können wir hier nicht
                    if value is None:
                        continue
                    value = str(value)
                    if value == "":
                        continue

                    domain = host_key.strip()
                    if not domain.startswith("."):
                        domain = "." + domain

                    include_sub = "TRUE"
                    secure = "TRUE" if int(is_secure) == 1 else "FALSE"

                    # expires_utc ist "microseconds since 1601-01-01" (Chrome time)
                    # convert to unix epoch seconds
                    try:
                        exp = int(expires_utc)
                        if exp <= 0:
                            expires = "0"
                        else:
                            unix = int(exp / 1000000 - 11644473600)
                            expires = str(max(0, unix))
                    except Exception:
                        expires = "0"

                    p = path or "/"
                    f.write(f"{domain}\t{include_sub}\t{p}\t{secure}\t{expires}\t{name}\t{value}\n")
        except Exception as e:
            print(f"[CookieDBExporter] Export Fehler: {e}")


# ---------------------------
# Adblock Interceptor (Basis)
# ---------------------------
class AdBlockInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, enabled=True, parent=None):
        super().__init__(parent)
        self.enabled = enabled
        self.block_hosts = {
            "doubleclick.net", "googlesyndication.com", "google-analytics.com",
            "adsystem.com", "adservice.google.com", "adservice.google.de",
            "facebook.net", "connect.facebook.net",
            "analytics.twitter.com",
            "scorecardresearch.com",
            "adnxs.com", "taboola.com", "outbrain.com",
            "criteo.com", "criteo.net",
        }
        self.block_substrings = [
            "/ads?", "/ads/", "adserver", "adsystem", "doubleclick",
            "analytics", "collect?", "pixel", "tracker", "beacon",
        ]

    def setEnabled(self, enabled: bool):
        self.enabled = enabled

    def interceptRequest(self, info):
        if not self.enabled:
            return
        url = info.requestUrl()
        host = url.host().lower()
        path = url.path().lower()
        full = url.toString().lower()

        for h in self.block_hosts:
            if host == h or host.endswith("." + h):
                info.block(True)
                return
        for s in self.block_substrings:
            if s in path or s in full:
                info.block(True)
                return


class GlowProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0
        self._anim = QTimer(self)
        self._anim.setInterval(40)
        self._anim.timeout.connect(self._tick)
        self.setTextVisible(False)
        self.setRange(0, 100)
        self.setMaximumWidth(220)
        self.setFixedHeight(10)
        self._apply_style()

    def startGlow(self):
        if not self._anim.isActive():
            self._anim.start()

    def stopGlow(self):
        if self._anim.isActive():
            self._anim.stop()

    def _tick(self):
        self._phase = (self._phase + 6) % 100
        self._apply_style()

    def _apply_style(self):
        p = self._phase
        self.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid #22314f; border-radius: 6px; background: #0b1220; }}
            QProgressBar::chunk {{
                border-radius: 6px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2f6cff,
                    stop:{max(0.0, (p-15)/100):.2f} #2f6cff,
                    stop:{p/100:.2f} #8fb6ff,
                    stop:{min(1.0, (p+15)/100):.2f} #2f6cff,
                    stop:1 #2f6cff
                );
            }}
        """)


# ---------------------------
# Download Worker (yt-dlp)
# ---------------------------
class DownloadWorker(QWidget):
    from PyQt6.QtCore import pyqtSignal
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, url, output_path, cookiefile=None, user_agent=None, referer=None):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.cookiefile = cookiefile
        self.user_agent = user_agent
        self.referer = referer
        self._is_cancelled = False

    def run(self):
        def progress_hook(d):
            if self._is_cancelled:
                raise yt_dlp.utils.DownloadError('Download cancelled by user.')
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                if total:
                    percent = int(d.get('downloaded_bytes', 0) / total * 100)
                    self.progress.emit(max(0, min(100, percent)))
            elif d['status'] == 'finished':
                self.progress.emit(100)
                self.status.emit('Fertig')

        ydl_opts = {
            'outtmpl': self.output_path,
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
        }

        if self.cookiefile and os.path.exists(self.cookiefile):
            ydl_opts['cookiefile'] = self.cookiefile

        if self.user_agent:
            ydl_opts['user_agent'] = self.user_agent

        # Viele Services brauchen gleiche Header wie Browser
        headers = {"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"}
        if self.referer:
            headers["Referer"] = self.referer
        ydl_opts["http_headers"] = headers

        try:
            self.status.emit('Läuft')
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished.emit()
        except yt_dlp.utils.DownloadError as e:
            if self._is_cancelled:
                self.status.emit('Abgebrochen')
            else:
                self.status.emit('Fehlgeschlagen')
                self.error.emit(str(e))
            self.finished.emit()

    def cancel(self):
        self._is_cancelled = True


# ---------------------------
# VLC Player Dialog
# ---------------------------
class VLCPlayerDialog(QDialog):
    def __init__(self, video_url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video abspielen mit VLC")
        self.resize(900, 650)
        self.video_url = video_url

        self.is_seeking = False

        layout = QVBoxLayout(self)
        self.videoframe = QFrame(self)
        self.videoframe.setFrameShape(QFrame.Shape.Box)
        self.videoframe.setLineWidth(2)
        layout.addWidget(self.videoframe)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.setValue(0)
        layout.addWidget(self.position_slider)

        self.position_slider.sliderPressed.connect(self.slider_pressed)
        self.position_slider.sliderReleased.connect(self.slider_released)

        playback_layout = QHBoxLayout()
        self.play_button = QPushButton("Play/Pause")
        self.play_button.clicked.connect(self.toggle_play)
        playback_layout.addWidget(self.play_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_playback)
        playback_layout.addWidget(self.stop_button)
        layout.addLayout(playback_layout)

        volume_layout = QHBoxLayout()
        self.volume = 100
        self.vol_down_button = QPushButton("Leiser")
        self.vol_down_button.clicked.connect(self.volume_down)
        volume_layout.addWidget(self.vol_down_button)

        self.vol_up_button = QPushButton("Lauter")
        self.vol_up_button.clicked.connect(self.volume_up)
        volume_layout.addWidget(self.vol_up_button)

        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.download_video)
        volume_layout.addWidget(self.download_button)
        layout.addLayout(volume_layout)

        self.instance = vlc.Instance()
        self.media_player = self.instance.media_player_new()
        media = self.instance.media_new(self.video_url)
        self.media_player.set_media(media)
        self.media_player.audio_set_volume(self.volume)

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start()

        self.media_player.play()
        self.set_video_widget()

    def set_video_widget(self):
        if sys.platform.startswith('win'):
            self.media_player.set_hwnd(self.videoframe.winId())
        elif sys.platform.startswith('linux'):
            self.media_player.set_xwindow(int(self.videoframe.winId()))
        elif sys.platform.startswith('darwin'):
            self.media_player.set_nsobject(int(self.videoframe.winId()))

    def toggle_play(self):
        if self.media_player.is_playing():
            self.media_player.pause()
        else:
            self.media_player.play()

    def stop_playback(self):
        self.media_player.stop()

    def volume_up(self):
        self.volume = min(self.volume + 10, 200)
        self.media_player.audio_set_volume(self.volume)

    def volume_down(self):
        self.volume = max(self.volume - 10, 0)
        self.media_player.audio_set_volume(self.volume)

    def slider_pressed(self):
        self.is_seeking = True

    def slider_released(self):
        self.is_seeking = False
        self.media_player.set_time(self.position_slider.value())

    def download_video(self):
        parent_browser = self.parent()
        if not parent_browser or not isinstance(parent_browser, Browser):
            QMessageBox.warning(self, "Fehler", "Der Browser ist nicht verfügbar.")
            return
        parent_browser.download_video_url(self.video_url)
        QMessageBox.information(self, "Download", "Download wurde zur Queue hinzugefügt (Download-Manager).")

    def update_frame(self):
        if not self.is_seeking:
            current_time = self.media_player.get_time()
            total_length = self.media_player.get_length()
            if total_length > 0:
                self.position_slider.setRange(0, total_length)
                self.position_slider.setValue(current_time)

    def closeEvent(self, event):
        self.timer.stop()
        self.media_player.stop()
        super().closeEvent(event)


# ---------------------------
# WebEngine Page/View
# ---------------------------
class MyWebEnginePage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        self.featurePermissionRequested.connect(self.onFeaturePermissionRequested)

    def onFeaturePermissionRequested(self, security_origin, feature):
        if feature == QWebEnginePage.Feature.Geolocation:
            self.setFeaturePermission(
                security_origin, feature,
                QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
            )
        else:
            self.setFeaturePermission(
                security_origin, feature,
                QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
            )


class CustomWebEngineView(QWebEngineView):
    def __init__(self, browser, profile):
        super().__init__()
        self.browser = browser
        self.setPage(MyWebEnginePage(profile, self))

    def createWindow(self, requested_window_type):
        reply = QMessageBox.question(
            self.browser,
            "Pop-up anfordern",
            "Eine Webseite möchte ein neues Fenster/Tab öffnen. Erlauben?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply != QMessageBox.StandardButton.Yes:
            return None

        popup_view = self.browser.create_configured_webview()
        i = self.browser.tabs.addTab(popup_view, "Neues Fenster")
        self.browser.tabs.setCurrentIndex(i)
        self.browser.update_url_bar()
        return popup_view


# ---------------------------
# Reader Mode Dialog
# ---------------------------
class ReaderDialog(QDialog):
    def __init__(self, title: str, text: str, url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reader Mode")
        self.resize(900, 650)

        layout = QVBoxLayout(self)
        header = QLabel(f"<h2>{title}</h2><div style='color:#9fb3d9'>{url}</div>")
        header.setTextFormat(Qt.TextFormat.RichText)
        header.setWordWrap(True)
        layout.addWidget(header)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(text.strip())
        layout.addWidget(self.text)

        btns = QHBoxLayout()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(close_btn)
        layout.addLayout(btns)


# ---------------------------
# Kleine Dialoge (Favoriten/Passwörter/History/Downloads/Plugins)
# (wie zuvor, unverändert)
# ---------------------------
class LoginDialog(QDialog):
    def __init__(self, parent=None, username="", password=""):
        super().__init__(parent)
        self.setWindowTitle("Zugangsdaten speichern")
        layout = QVBoxLayout(self)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Benutzername")
        self.username_edit.setText(username)
        layout.addWidget(QLabel("Benutzername:"))
        layout.addWidget(self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Passwort")
        self.password_edit.setText(password)
        layout.addWidget(QLabel("Passwort:"))
        layout.addWidget(self.password_edit)

        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)

    def get_credentials(self):
        return self.username_edit.text(), self.password_edit.text()


class CredentialsManagerDialog(QDialog):
    def __init__(self, parent=None, credentials_dict=None):
        super().__init__(parent)
        self.setWindowTitle("Passwörter verwalten")
        self.resize(520, 340)
        self.credentials = credentials_dict.copy() if credentials_dict else {}

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        for domain in sorted(self.credentials.keys()):
            self.list_widget.addItem(QListWidgetItem(domain))
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        edit_btn = QPushButton("Bearbeiten")
        delete_btn = QPushButton("Löschen")
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        edit_btn.clicked.connect(self.edit_credentials)
        delete_btn.clicked.connect(self.delete_credentials)

    def edit_credentials(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.information(self, "Info", "Bitte wählen Sie einen Eintrag aus.")
            return
        domain = item.text()
        creds = self.credentials[domain]
        dlg = LoginDialog(self, username=creds["username"], password=creds["password"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            u, p = dlg.get_credentials()
            if u and p:
                self.credentials[domain] = {"username": u, "password": p}
                QMessageBox.information(self, "Erfolg", f"Zugangsdaten für {domain} geändert.")
            else:
                QMessageBox.warning(self, "Warnung", "Benutzername und Passwort dürfen nicht leer sein.")

    def delete_credentials(self):
        item = self.list_widget.currentItem()
        if not item:
            QMessageBox.information(self, "Info", "Bitte wählen Sie einen Eintrag aus.")
            return
        domain = item.text()
        if QMessageBox.question(self, "Löschen", f"{domain} wirklich löschen?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            del self.credentials[domain]
            self.list_widget.takeItem(self.list_widget.row(item))


class EditFavoriteDialog(QDialog):
    def __init__(self, parent=None, title="", url=""):
        super().__init__(parent)
        self.setWindowTitle("Favorit bearbeiten")
        layout = QVBoxLayout(self)

        self.title_edit = QLineEdit()
        self.title_edit.setText(title)
        layout.addWidget(QLabel("Titel:"))
        layout.addWidget(self.title_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setText(url)
        layout.addWidget(QLabel("URL:"))
        layout.addWidget(self.url_edit)

        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)

    def get_values(self):
        return self.title_edit.text(), self.url_edit.text()


class FavoritesManagerDialog(QDialog):
    def __init__(self, parent=None, favorites_list=None):
        super().__init__(parent)
        self.setWindowTitle("Favoriten verwalten")
        self.resize(560, 360)
        self.favorites = favorites_list.copy() if favorites_list else []

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self.refresh_list()

        btn_layout = QHBoxLayout()
        edit_btn = QPushButton("Bearbeiten")
        delete_btn = QPushButton("Löschen")
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        layout.addLayout(btn_layout)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        edit_btn.clicked.connect(self.edit_favorite)
        delete_btn.clicked.connect(self.delete_favorite)

    def refresh_list(self):
        self.list_widget.clear()
        for fav in sorted(self.favorites, key=lambda x: x["title"]):
            self.list_widget.addItem(QListWidgetItem(f"{fav['title']}\n{fav['url']}"))

    def edit_favorite(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        lines = item.text().split("\n")
        if len(lines) < 2:
            return
        old_title, old_url = lines[0], lines[1]
        dlg = EditFavoriteDialog(self, old_title, old_url)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_title, new_url = dlg.get_values()
            if new_title and new_url:
                for fav in self.favorites:
                    if fav["title"] == old_title and fav["url"] == old_url:
                        fav["title"] = new_title
                        fav["url"] = new_url
                        break
                self.refresh_list()

    def delete_favorite(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        lines = item.text().split("\n")
        if len(lines) < 2:
            return
        t, u = lines[0], lines[1]
        if QMessageBox.question(self, "Löschen", f"'{t}' wirklich löschen?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.favorites = [f for f in self.favorites if not (f["title"] == t and f["url"] == u)]
            self.refresh_list()


class HistoryDialog(QDialog):
    def __init__(self, parent=None, history_list=None):
        super().__init__(parent)
        self.setWindowTitle("Chronik")
        self.resize(560, 360)
        self.history = history_list if history_list else []

        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        for entry in self.history:
            title = entry.get("title", "Ohne Titel")
            url = entry.get("url", "")
            self.list_widget.addItem(QListWidgetItem(f"{title}\n{url}"))
        layout.addWidget(self.list_widget)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.list_widget.itemDoubleClicked.connect(self.navigate_from_history)

    def navigate_from_history(self, item):
        lines = item.text().split("\n")
        if len(lines) >= 2:
            url = lines[-1]
            main_window = self.parent()
            if hasattr(main_window, "navigate_to_url_string"):
                main_window.navigate_to_url_string(url)
            self.accept()


class WhoisDialog(QDialog):
    def __init__(self, domain_info, ip_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WHOIS Informationen")
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll_layout = QVBoxLayout(content)

        whois_label = QLabel("WHOIS Daten:")
        whois_text = QTextEdit()
        whois_text.setReadOnly(True)
        whois_text.setText(domain_info)

        ip_label = QLabel("IP Informationen:")
        ip_text = QTextEdit()
        ip_text.setReadOnly(True)
        ip_text.setText(ip_info)

        scroll_layout.addWidget(whois_label)
        scroll_layout.addWidget(whois_text)
        scroll_layout.addWidget(ip_label)
        scroll_layout.addWidget(ip_text)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class DownloadManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download-Manager")
        self.resize(860, 460)
        self.browser = parent

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Dateiname", "Fortschritt", "Status", "Zielpfad", "Typ"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Abbrechen")
        self.delete_btn = QPushButton("Entfernen")
        self.close_btn = QPushButton("Schließen")
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.cancel_btn.clicked.connect(self.cancel_download)
        self.delete_btn.clicked.connect(self.delete_download)
        self.close_btn.clicked.connect(self.accept)
        self.table.itemDoubleClicked.connect(self.open_download)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(500)
        self.refresh_timer.timeout.connect(self.refresh_table)
        self.refresh_timer.start()

    def refresh_table(self):
        if not self.browser:
            return
        downloads = self.browser.all_downloads_info
        self.table.setRowCount(len(downloads))

        for row, dl in enumerate(downloads):
            filename_item = QTableWidgetItem(dl.get("filename", ""))
            filename_item.setData(Qt.ItemDataRole.UserRole, dl)

            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(dl.get("progress_percent", 0))
            progress_bar.setTextVisible(True)

            status_item = QTableWidgetItem(dl.get("status", ""))
            path_item = QTableWidgetItem(dl.get("target_path", ""))
            typ_item = QTableWidgetItem(dl.get("type", "web"))

            self.table.setItem(row, 0, filename_item)
            self.table.setCellWidget(row, 1, progress_bar)
            self.table.setItem(row, 2, status_item)
            self.table.setItem(row, 3, path_item)
            self.table.setItem(row, 4, typ_item)

    def _selected(self):
        items = self.table.selectedItems()
        if not items:
            QMessageBox.information(self, "Info", "Bitte wählen Sie einen Download aus.")
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def cancel_download(self):
        info = self._selected()
        if not info:
            return
        self.browser.cancel_download(info)

    def delete_download(self):
        info = self._selected()
        if not info:
            return
        self.browser.delete_download(info)

    def open_download(self, item):
        info = item.data(Qt.ItemDataRole.UserRole)
        target_path = info.get("target_path")
        if target_path and os.path.exists(target_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(target_path))
        else:
            QMessageBox.warning(self, "Fehler", f"Datei nicht gefunden:\n{target_path}")


class PluginManagerDialog(QDialog):
    def __init__(self, parent=None, plugins_list=None):
        super().__init__(parent)
        self.setWindowTitle("Plugins verwalten")
        self.resize(700, 420)
        self.plugins = plugins_list.copy() if plugins_list else []

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Plugin-Pfad"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Hinzufügen")
        remove_btn = QPushButton("Entfernen")
        close_btn = QPushButton("Schließen")
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        add_btn.clicked.connect(self.add_plugin)
        remove_btn.clicked.connect(self.remove_plugin)
        close_btn.clicked.connect(self.accept)

        self.refresh_table()

    def refresh_table(self):
        self.table.setRowCount(len(self.plugins))
        for row, plugin in enumerate(self.plugins):
            self.table.setItem(row, 0, QTableWidgetItem(plugin["path"]))

    def add_plugin(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Plugin hinzufügen", "", "Python-Dateien (*.py);;Alle Dateien (*)")
        if not file_path:
            return
        self.plugins.append({"path": file_path})
        self.refresh_table()

    def remove_plugin(self):
        row = self.table.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "Entfernen", "Plugin wirklich entfernen?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.plugins.pop(row)
            self.refresh_table()


# ---------------------------
# Browser
# ---------------------------
class Browser(QMainWindow):
    MAX_PARALLEL_YTDLP = 2

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TMP-Networks Browser Mini")
        self.setGeometry(100, 100, 1320, 860)

        self.load_data()
        self.data.setdefault("history", [])
        self.data.setdefault("plugins", [])
        self.data.setdefault("adblock_enabled", True)

        self.active_downloads_info = []
        self.all_downloads_info = []

        self.ytdlp_queue = deque()
        self.ytdlp_running = 0

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_current_tab)
        self.tabs.currentChanged.connect(lambda _: self.update_url_bar())
        self.setCentralWidget(self.tabs)

        menu_bar = self.menuBar()

        self.fav_menu = QMenu("Favoriten", self)
        menu_bar.addMenu(self.fav_menu)
        add_fav_action = QAction("Favorit hinzufügen", self)
        add_fav_action.triggered.connect(self.add_favorite)
        self.fav_menu.addAction(add_fav_action)
        self.fav_menu.addSeparator()
        manage_fav_action = QAction("Favoriten verwalten", self)
        manage_fav_action.triggered.connect(self.manage_favorites)
        self.fav_menu.addAction(manage_fav_action)
        self.update_favorites_menu()

        self.pass_menu = QMenu("Passwörter", self)
        menu_bar.addMenu(self.pass_menu)
        save_pass_action = QAction("Zugangsdaten speichern", self)
        save_pass_action.triggered.connect(self.save_credentials_for_current_page)
        self.pass_menu.addAction(save_pass_action)
        view_pass_action = QAction("Gespeicherte Zugangsdaten anzeigen", self)
        view_pass_action.triggered.connect(self.view_credentials)
        self.pass_menu.addAction(view_pass_action)
        manage_pass_action = QAction("Passwörter verwalten", self)
        manage_pass_action.triggered.connect(self.manage_credentials)
        self.pass_menu.addAction(manage_pass_action)

        self.history_menu = QMenu("Chronik", self)
        menu_bar.addMenu(self.history_menu)
        show_history_action = QAction("Chronik anzeigen", self)
        show_history_action.triggered.connect(self.view_history)
        self.history_menu.addAction(show_history_action)

        self.download_menu = QMenu("Downloads", self)
        menu_bar.addMenu(self.download_menu)
        show_download_mgr_action = QAction("Download-Manager öffnen", self)
        show_download_mgr_action.triggered.connect(self.open_download_manager)
        self.download_menu.addAction(show_download_mgr_action)

        self.view_menu = QMenu("Ansicht", self)
        menu_bar.addMenu(self.view_menu)
        reader_action = QAction("Reader Mode (Lesansicht)", self)
        reader_action.triggered.connect(self.open_reader_mode)
        self.view_menu.addAction(reader_action)

        self.privacy_menu = QMenu("Privacy", self)
        menu_bar.addMenu(self.privacy_menu)
        self.adblock_action = QAction("Adblock aktiv", self)
        self.adblock_action.setCheckable(True)
        self.adblock_action.setChecked(bool(self.data.get("adblock_enabled", True)))
        self.adblock_action.triggered.connect(self.toggle_adblock)
        self.privacy_menu.addAction(self.adblock_action)

        self.plugin_menu = QMenu("Plugins", self)
        menu_bar.addMenu(self.plugin_menu)
        add_plugin_action = QAction("Plugin hinzufügen", self)
        add_plugin_action.triggered.connect(self.add_plugin)
        self.plugin_menu.addAction(add_plugin_action)
        manage_plugins_action = QAction("Plugins verwalten", self)
        manage_plugins_action.triggered.connect(self.manage_plugins)
        self.plugin_menu.addAction(manage_plugins_action)

        navigation_bar = QToolBar("Navigation")
        navigation_bar.setIconSize(QSize(24, 24))
        navigation_bar.setMovable(False)
        self.addToolBar(navigation_bar)

        emoji_font = get_emoji_font()

        back_button = QAction("👈", self)
        back_button.setToolTip("Zurück")
        back_button.setFont(emoji_font)
        back_button.triggered.connect(lambda: self.tabs.currentWidget().back())
        navigation_bar.addAction(back_button)

        forward_button = QAction("👉", self)
        forward_button.setToolTip("Vorwärts")
        forward_button.setFont(emoji_font)
        forward_button.triggered.connect(lambda: self.tabs.currentWidget().forward())
        navigation_bar.addAction(forward_button)

        reload_button = QAction("🌀", self)
        reload_button.setToolTip("Neu laden")
        reload_button.setFont(emoji_font)
        reload_button.triggered.connect(lambda: self.tabs.currentWidget().reload())
        navigation_bar.addAction(reload_button)

        new_tab_button = QAction("🆕", self)
        new_tab_button.setToolTip("Neuer Tab")
        new_tab_button.setFont(emoji_font)
        new_tab_button.triggered.connect(lambda: self.add_new_tab())
        navigation_bar.addAction(new_tab_button)

        home_button = QAction("🏠", self)
        home_button.setToolTip("Startseite")
        home_button.setFont(emoji_font)
        home_button.triggered.connect(self.navigate_home)
        navigation_bar.addAction(home_button)

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("URL eingeben oder suchen …")
        self.url_bar.returnPressed.connect(self.navigate_to_url_or_search)
        navigation_bar.addWidget(self.url_bar)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        navigation_bar.addWidget(spacer)

        video_scan_button = QAction("🎥", self)
        video_scan_button.setToolTip("Videos scannen und abspielen (yt-dlp)")
        video_scan_button.setFont(emoji_font)
        video_scan_button.triggered.connect(self.scan_and_play_videos)
        navigation_bar.addAction(video_scan_button)

        whois_button = QAction("ℹ️", self)
        whois_button.setToolTip("WHOIS Informationen anzeigen")
        whois_button.setFont(emoji_font)
        whois_button.triggered.connect(self.show_whois_info)
        navigation_bar.addAction(whois_button)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.download_progress_bar = QProgressBar()
        self.download_progress_bar.setVisible(False)
        self.download_progress_bar.setRange(0, 100)
        self.status.addPermanentWidget(self.download_progress_bar)

        self.glow_bar = GlowProgressBar()
        self.glow_bar.setVisible(False)
        self.status.addPermanentWidget(self.glow_bar)

        # Profile
        self.profile = QWebEngineProfile("TMPNetworksBrowserProfile", self)
        self.profile.setPersistentStoragePath(json_dir)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.downloadRequested.connect(self.on_downloadRequested)

        # Cookie export paths
        self.cookie_txt_path = os.path.join(json_dir, "cookies.txt")

        # Preferred: export from Chromium cookie DB (best chance)
        self.cookie_db_exporter = ChromiumCookieDBExporter(self.profile, self.cookie_txt_path, parent=self)

        # Fallback: cookieStore events (also writes cookies.txt)
        self.cookie_store_jar = WebEngineCookieStoreJar(self.profile, self.cookie_txt_path, parent=self)

        # Adblock
        self.adblock = AdBlockInterceptor(enabled=bool(self.data.get("adblock_enabled", True)), parent=self)
        self.profile.setUrlRequestInterceptor(self.adblock)

        # user-agent cache
        self._webengine_user_agent = None
        self._refresh_user_agent()

        self.add_new_tab(QUrl('https://www.google.com'), 'Startseite')
        self.download_manager_dialog = None

        self.loaded_plugin_modules = {}
        self.load_plugins()

    def _refresh_user_agent(self):
        try:
            self._webengine_user_agent = self.profile.httpUserAgent()
        except Exception:
            self._webengine_user_agent = None

    def get_user_agent_for_ytdlp(self):
        return self._webengine_user_agent

    # --- WebView Factory ---
    def create_configured_webview(self) -> CustomWebEngineView:
        view = CustomWebEngineView(self, self.profile)

        view.loadStarted.connect(self.on_load_started)
        view.loadProgress.connect(self.on_load_progress)
        view.loadFinished.connect(lambda _, b=view: self.on_load_finished(b))

        view.urlChanged.connect(lambda new_url, b=view: self.update_url_bar(new_url, b))
        view.titleChanged.connect(lambda title, b=view: self.on_title_changed(title, b))
        view.iconChanged.connect(lambda icon, b=view: self.on_icon_changed(icon, b))
        return view

    def on_load_started(self):
        self.glow_bar.setVisible(True)
        self.glow_bar.setValue(5)
        self.glow_bar.startGlow()

    def on_load_progress(self, p: int):
        self.glow_bar.setVisible(True)
        self.glow_bar.setValue(max(1, p))
        if p >= 100:
            QTimer.singleShot(250, self._hide_glow)

    def _hide_glow(self):
        self.glow_bar.stopGlow()
        self.glow_bar.setVisible(False)

    def on_load_finished(self, browser: CustomWebEngineView):
        idx = self.tabs.indexOf(browser)
        if idx >= 0:
            self.tabs.setTabText(idx, browser.page().title() or "Neue Seite")
        if browser == self.tabs.currentWidget():
            self.update_url_bar()
        self.check_credentials(browser)

    def on_title_changed(self, title: str, browser: CustomWebEngineView):
        idx = self.tabs.indexOf(browser)
        if idx >= 0:
            self.tabs.setTabText(idx, title if title else "Neue Seite")

    def on_icon_changed(self, icon: QIcon, browser: CustomWebEngineView):
        idx = self.tabs.indexOf(browser)
        if idx >= 0 and not icon.isNull():
            self.tabs.setTabIcon(idx, icon)

    # --- Tabs ---
    def add_new_tab(self, qurl=None, label="Neue Seite"):
        if not qurl:
            qurl = QUrl("https://www.google.com")
        browser = self.create_configured_webview()
        browser.setUrl(qurl)
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)
        self.update_url_bar()

    def close_current_tab(self, index):
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.close()

    def update_url_bar(self, qurl=None, browser=None):
        current = self.tabs.currentWidget()
        if current is None:
            return
        if browser is not None and browser != current:
            return
        if qurl is None:
            qurl = current.url()

        self.url_bar.setText(qurl.toString())
        self.url_bar.setCursorPosition(0)

        title = current.page().title()
        url_str = qurl.toString()
        if url_str and url_str != "about:blank":
            self.add_to_history(title, url_str)

    # --- Navigation ---
    def navigate_to_url_or_search(self):
        text = self.url_bar.text().strip()
        if not text:
            return
        q = normalize_to_url(text) if looks_like_url(text) else google_search_url(text)
        self.tabs.currentWidget().setUrl(q)

    def navigate_home(self):
        self.tabs.currentWidget().setUrl(QUrl("https://www.google.com"))

    def navigate_to_url_string(self, url_string):
        if not url_string:
            return
        q = normalize_to_url(url_string) if looks_like_url(url_string) else google_search_url(url_string)
        self.tabs.currentWidget().setUrl(q)

    # --- Reader Mode ---
    def open_reader_mode(self):
        browser = self.tabs.currentWidget()
        if not browser:
            return
        js = r"""
        (function() {
            function textOf(el){
                if(!el) return "";
                return (el.innerText || el.textContent || "").trim();
            }
            var candidates = [
                document.querySelector('article'),
                document.querySelector('main'),
                document.querySelector('[role="main"]'),
                document.querySelector('.post'),
                document.querySelector('.article'),
                document.querySelector('#content')
            ].filter(Boolean);

            var best = null;
            var bestLen = 0;

            function score(node){
                var t = textOf(node);
                return t.length;
            }

            for (var i=0;i<candidates.length;i++){
                var s = score(candidates[i]);
                if (s > bestLen){
                    bestLen = s;
                    best = candidates[i];
                }
            }

            if(!best){
                var nodes = document.querySelectorAll('div, section');
                for (var j=0;j<nodes.length;j++){
                    var s2 = score(nodes[j]);
                    if (s2 > bestLen){
                        bestLen = s2;
                        best = nodes[j];
                    }
                }
            }

            var title = document.title || "";
            var url = location.href || "";
            var body = best ? textOf(best) : textOf(document.body);
            body = body.replace(/\n{3,}/g, "\n\n");

            return {title: title, url: url, text: body};
        })();
        """
        browser.page().runJavaScript(js, self._show_reader_dialog)

    def _show_reader_dialog(self, result):
        if not result or not isinstance(result, dict):
            QMessageBox.warning(self, "Reader Mode", "Konnte den Inhalt nicht extrahieren.")
            return
        title = result.get("title", "")
        url = result.get("url", "")
        text = result.get("text", "")

        if not text or len(text.strip()) < 50:
            QMessageBox.information(self, "Reader Mode", "Zu wenig Text gefunden (oder Seite blockiert).")
            return

        dlg = ReaderDialog(title, text, url, self)
        dlg.exec()

    # --- Adblock ---
    def toggle_adblock(self, checked: bool):
        self.data["adblock_enabled"] = bool(checked)
        self.save_data()
        self.adblock.setEnabled(bool(checked))
        self.status.showMessage(f"Adblock: {'AN' if checked else 'AUS'} (Reload empfohlen)", 4000)

    # --- Download Manager ---
    def open_download_manager(self):
        if not self.download_manager_dialog:
            self.download_manager_dialog = DownloadManagerDialog(self)
        self.download_manager_dialog.show()
        self.download_manager_dialog.raise_()
        self.download_manager_dialog.activateWindow()

    def on_downloadRequested(self, download):
        url = download.url().toString()
        if url.endswith('.m3u8'):
            self.download_video_url(url)
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Speichern unter", download.downloadFileName() or "", "Alle Dateien (*)"
        )
        if not file_path:
            return

        directory = os.path.dirname(file_path)
        filename_only = os.path.basename(file_path)
        download.setDownloadDirectory(directory)
        download.setDownloadFileName(filename_only)
        download.accept()

        download_info = {
            "type": "web",
            "download_obj": download,
            "filename": filename_only,
            "target_path": file_path,
            "progress_percent": 0,
            "status": "Läuft",
            "timer": None
        }
        self.active_downloads_info.append(download_info)
        self.all_downloads_info.append(download_info)

        timer = QTimer(self)
        timer.setInterval(500)
        timer.timeout.connect(partial(self.poll_webengine_download, download_info))
        timer.start()
        download_info["timer"] = timer

        download.stateChanged.connect(partial(self.handle_webengine_download_state_changed, download_info))

        self.download_progress_bar.setVisible(True)
        self.status.showMessage(f"Download gestartet: {filename_only}")

    def poll_webengine_download(self, download_info):
        d = download_info.get("download_obj")
        if not d:
            return
        received = d.receivedBytes()
        total = d.totalBytes()
        if total > 0:
            percent = int(received / total * 100)
            download_info["progress_percent"] = max(0, min(100, percent))
            self.download_progress_bar.setRange(0, 100)
            self.download_progress_bar.setValue(download_info["progress_percent"])
        else:
            self.download_progress_bar.setRange(0, 0)

        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def handle_webengine_download_state_changed(self, download_info, state):
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            download_info["status"] = "Fertig"
            download_info["progress_percent"] = 100
        elif state in (
            QWebEngineDownloadRequest.DownloadState.DownloadCancelled,
            QWebEngineDownloadRequest.DownloadState.DownloadInterrupted
        ):
            download_info["status"] = "Fehlgeschlagen"

        if download_info.get("timer"):
            download_info["timer"].stop()

        if download_info in self.active_downloads_info:
            self.active_downloads_info.remove(download_info)

        self._recompute_global_download_bar()

        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def _recompute_global_download_bar(self):
        if not self.active_downloads_info:
            self.download_progress_bar.setVisible(False)
            self.download_progress_bar.setRange(0, 100)
            self.status.clearMessage()
            return
        self.download_progress_bar.setVisible(True)
        self.download_progress_bar.setRange(0, 100)
        max_progress = max(dl.get("progress_percent", 0) for dl in self.active_downloads_info)
        self.download_progress_bar.setValue(max_progress)

    # --- yt-dlp download queue ---
    def _ytdlp_base_opts(self):
        opts = {'quiet': True, 'no_warnings': True}
        ua = self.get_user_agent_for_ytdlp()
        if ua:
            opts["user_agent"] = ua
        if os.path.exists(self.cookie_txt_path):
            opts["cookiefile"] = self.cookie_txt_path
        opts["http_headers"] = {"Accept-Language": "de-DE,de;q=0.9,en;q=0.8"}
        return opts

    def download_video_url(self, url):
        # Hinweis für Stories ohne ID
        if "instagram.com/stories/" in url and url.rstrip("/").count("/") <= 4:
            QMessageBox.information(
                self,
                "Instagram Stories Hinweis",
                "Diese URL ist eine Stories-Übersichts-URL.\n"
                "yt-dlp braucht oft eine konkrete Story-URL mit ID.\n\n"
                "Tipp: Öffne eine Story, bis du eine URL mit einer Zahlen-ID siehst, und nutze dann den Video-Button."
            )

        ydl_opts = self._ytdlp_base_opts()
        ydl_opts["skip_download"] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                ext = info.get('ext', 'mp4')
                title = info.get('title', 'downloaded_video')
                title = re.sub(r'[\\/*?:"<>|]', "", title)
                default_filename = f"{title}.{ext}"
        except Exception as e:
            QMessageBox.warning(self, "Download-Fehler", f"Fehler beim Abrufen der Videoinformationen:\n{e}")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Video speichern unter", default_filename,
            f"Video Dateien (*.{ext});;Alle Dateien (*)"
        )
        if not save_path:
            return

        download_info = {
            "type": "ytdlp",
            "url": url,
            "filename": os.path.basename(save_path),
            "target_path": save_path,
            "progress_percent": 0,
            "status": "Wartet",
            "worker": None,
            "thread": None
        }
        self.all_downloads_info.append(download_info)
        self.active_downloads_info.append(download_info)
        self.ytdlp_queue.append(download_info)

        self._recompute_global_download_bar()
        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

        self._try_start_next_ytdlp()

    def _try_start_next_ytdlp(self):
        while self.ytdlp_running < self.MAX_PARALLEL_YTDLP and self.ytdlp_queue:
            info = self.ytdlp_queue.popleft()
            if info.get("status") != "Wartet":
                continue
            self._start_ytdlp_download(info)

    def _start_ytdlp_download(self, download_info):
        url = download_info["url"]
        save_path = download_info["target_path"]

        thread = QThread()
        worker = DownloadWorker(
            url,
            save_path,
            cookiefile=self.cookie_txt_path,
            user_agent=self.get_user_agent_for_ytdlp(),
            referer="https://www.instagram.com/" if "instagram.com" in url else None
        )
        worker.moveToThread(thread)

        self.ytdlp_running += 1
        download_info["status"] = "Läuft"
        download_info["worker"] = worker
        download_info["thread"] = thread

        thread.started.connect(worker.run)
        worker.progress.connect(lambda p, di=download_info: self._ytdlp_progress(di, p))
        worker.status.connect(lambda s, di=download_info: self._ytdlp_status(di, s))
        worker.error.connect(lambda e, di=download_info: self._ytdlp_error(di, e))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda di=download_info: self._ytdlp_finished(di))
        thread.finished.connect(thread.deleteLater)

        thread.start()
        self.status.showMessage(f"yt-dlp Download gestartet: {download_info['filename']}")
        self._recompute_global_download_bar()

        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def _ytdlp_progress(self, download_info, percent):
        download_info["progress_percent"] = percent
        self._recompute_global_download_bar()
        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def _ytdlp_status(self, download_info, status):
        download_info["status"] = status
        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def _ytdlp_error(self, download_info, error_message):
        msg = str(error_message)

        if "Unsupported URL" in msg:
            QMessageBox.warning(
                self,
                "yt-dlp: Unsupported URL",
                "yt-dlp unterstützt diese Instagram-URL-Form aktuell nicht.\n\n"
                "Tipp: Öffne eine konkrete Story (mit Zahlen-ID in der URL) oder nutze Reels/Post-URLs.\n\n"
                f"Fehler:\n{msg}"
            )
            return

        if "You need to log in" in msg or "need to log in" in msg.lower():
            QMessageBox.warning(
                self,
                "Instagram Login nötig",
                "Instagram verlangt Login für diesen Inhalt.\n\n"
                "Du bist zwar im eingebauten Browser eingeloggt, aber yt-dlp braucht die Session-Cookies.\n"
                "Wir exportieren Cookies automatisch aus dem QtWebEngine-Profil nach:\n"
                f"{self.cookie_txt_path}\n\n"
                "Wenn es trotzdem nicht klappt, liegt es meist daran, dass die Cookies in der Chromium-DB verschlüsselt sind "
                "(encrypted_value) und lokal nicht ohne Keychain-Entschlüsselung exportiert werden können.\n\n"
                f"Fehler:\n{msg}"
            )
            return

        QMessageBox.warning(self, "Download-Fehler", f"Fehler bei {download_info['filename']}:\n{msg}")

    def _ytdlp_finished(self, download_info):
        self.ytdlp_running = max(0, self.ytdlp_running - 1)
        if download_info in self.active_downloads_info:
            self.active_downloads_info.remove(download_info)
        self._recompute_global_download_bar()
        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()
        self._try_start_next_ytdlp()

    def cancel_download(self, download_info):
        typ = download_info.get("type", "web")
        status = download_info.get("status")
        if typ == "ytdlp":
            if status == "Wartet":
                download_info["status"] = "Abgebrochen"
                try:
                    self.ytdlp_queue.remove(download_info)
                except ValueError:
                    pass
                if download_info in self.active_downloads_info:
                    self.active_downloads_info.remove(download_info)
                self._recompute_global_download_bar()
                return
            worker = download_info.get("worker")
            if worker and status in ("Läuft", "Wartet"):
                worker.cancel()
                download_info["status"] = "Abgebrochen"
        else:
            d = download_info.get("download_obj")
            if d and status == "Läuft":
                d.cancel()
                download_info["status"] = "Abgebrochen"

        self._recompute_global_download_bar()
        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def delete_download(self, download_info):
        self.cancel_download(download_info)
        if download_info in self.active_downloads_info:
            self.active_downloads_info.remove(download_info)
        if download_info in self.all_downloads_info:
            self.all_downloads_info.remove(download_info)
        self._recompute_global_download_bar()
        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    # --- Favoriten / Passwörter / Chronik / Plugins / Whois / yt-dlp scan/play ---
    # Diese Teile sind aus Platzgründen identisch zu deiner Version und wurden hier nicht erneut geändert,
    # außer dass download_video_url/yt-dlp jetzt Cookies/Headers nutzt.
    #
    # Damit der Code lauffähig bleibt, folgen die restlichen Methoden in kompakter Form:

    def add_favorite(self):
        current_url = self.tabs.currentWidget().url().toString()
        current_title = self.tabs.currentWidget().page().title()
        if any(fav["url"] == current_url for fav in self.data["favorites"]):
            QMessageBox.information(self, "Info", "Diese Seite ist bereits als Favorit gespeichert.")
            return
        self.data["favorites"].append({"title": current_title, "url": current_url})
        self.save_data()
        self.update_favorites_menu()
        QMessageBox.information(self, "Erfolg", "Favorit hinzugefügt.")

    def update_favorites_menu(self):
        actions = self.fav_menu.actions()
        while len(actions) > 3:
            self.fav_menu.removeAction(actions[-1])
            actions = self.fav_menu.actions()

        for fav in sorted(self.data["favorites"], key=lambda x: x["title"]):
            submenu = QMenu(fav["title"], self)
            open_action = QAction("Öffnen", self)
            open_action.setData(fav["url"])
            open_action.triggered.connect(self.navigate_to_favorite)
            submenu.addAction(open_action)
            delete_action = QAction("Löschen ❌", self)
            delete_action.triggered.connect(lambda checked, f=fav: self.delete_favorite_directly(f))
            submenu.addAction(delete_action)
            self.fav_menu.addMenu(submenu)

    def delete_favorite_directly(self, fav):
        if QMessageBox.question(self, "Löschen", f"Favorit '{fav['title']}' löschen?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.data["favorites"] = [x for x in self.data["favorites"] if x != fav]
            self.save_data()
            self.update_favorites_menu()

    def navigate_to_favorite(self):
        action = self.sender()
        if action:
            self.navigate_to_url_string(action.data())

    def manage_favorites(self):
        if not self.data["favorites"]:
            QMessageBox.information(self, "Info", "Keine Favoriten vorhanden.")
            return
        dlg = FavoritesManagerDialog(self, favorites_list=self.data["favorites"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.data["favorites"] = dlg.favorites
            self.save_data()
            self.update_favorites_menu()

    def save_credentials_for_current_page(self):
        current_url = self.tabs.currentWidget().url().toString()
        domain = QUrl(current_url).host()
        dlg = LoginDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            username, password = dlg.get_credentials()
            if username and password:
                self.data["credentials"][domain] = {"username": username, "password": password}
                self.save_data()
                QMessageBox.information(self, "Erfolg", f"Zugangsdaten für {domain} gespeichert.")
            else:
                QMessageBox.warning(self, "Warnung", "Benutzername und Passwort dürfen nicht leer sein.")

    def view_credentials(self):
        if not self.data["credentials"]:
            QMessageBox.information(self, "Info", "Keine Zugangsdaten vorhanden.")
            return
        creds_text = ""
        for domain, creds in sorted(self.data["credentials"].items()):
            creds_text += f"Domain: {domain}\nBenutzername: {creds['username']}\nPasswort: {creds['password']}\n\n"
        dlg = QDialog(self)
        dlg.setWindowTitle("Gespeicherte Zugangsdaten")
        dlg.resize(520, 360)
        layout = QVBoxLayout(dlg)
        label = QLabel(creds_text)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.exec()

    def manage_credentials(self):
        if not self.data["credentials"]:
            QMessageBox.information(self, "Info", "Keine Zugangsdaten vorhanden.")
            return
        dlg = CredentialsManagerDialog(self, credentials_dict=self.data["credentials"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.data["credentials"] = dlg.credentials
            self.save_data()

    def view_history(self):
        dlg = HistoryDialog(self, history_list=self.data.get("history", []))
        dlg.exec()

    def get_credentials_for_url(self, url):
        domain = QUrl(url).host()
        return self.data["credentials"].get(domain, None)

    def check_credentials(self, browser):
        url = browser.url().toString()
        credentials = self.get_credentials_for_url(url)
        if not credentials:
            return
        js_code = """
        (function() {
            var inputs = document.getElementsByTagName('input');
            for(var i=0; i<inputs.length; i++) {
                if(inputs[i].type && inputs[i].type.toLowerCase() === 'password') return true;
            }
            return false;
        })();
        """
        browser.page().runJavaScript(js_code, lambda result: self._handle_password_field(result, credentials, browser))

    def _handle_password_field(self, has_password_field, credentials, browser):
        if not has_password_field:
            return
        if QMessageBox.question(self, "Zugangsdaten verfügbar", "Einfügen?",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            username = credentials['username'].replace('"', '\\"')
            password = credentials['password'].replace('"', '\\"')
            js_code = f"""
            (function() {{
                var inputs = document.getElementsByTagName('input');
                for(var i=0; i<inputs.length; i++) {{
                    var t = (inputs[i].type || "").toLowerCase();
                    if(t === 'text' || t === 'email') inputs[i].value = "{username}";
                    if(t === 'password') inputs[i].value = "{password}";
                }}
            }})();
            """
            browser.page().runJavaScript(js_code)

    def handle_youtube_via_yt_dlp(self, youtube_url):
        # Für "Play in VLC" nutzt du weiterhin direct URLs. Cookies/Headers wären analog möglich.
        ydl_opts = self._ytdlp_base_opts()
        ydl_opts["format"] = "best"
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                formats = info.get('formats', [])
                if not formats:
                    QMessageBox.warning(self, "Fehler", "Keine abspielbaren Formate gefunden.")
                    return
                variant_list = []
                for f in formats:
                    resolution = f.get('resolution') or f"{f.get('width','?')}x{f.get('height','?')}"
                    label = f"{resolution} ({f.get('ext','?')}, {f.get('format_id','?')}, {f.get('fps','?')}fps)"
                    direct_url = f.get('url')
                    if direct_url:
                        variant_list.append((label, direct_url))

                if not variant_list:
                    QMessageBox.warning(self, "Fehler", "Keine Direct-URLs gefunden.")
                    return

                if len(variant_list) == 1:
                    self.play_video_in_vlc(variant_list[0][1])
                    return

                dlg = QDialog(self)
                dlg.setWindowTitle("Stream auswählen")
                dlg.resize(560, 420)
                layout = QVBoxLayout(dlg)
                layout.addWidget(QLabel(f"Formate für: {info.get('title', youtube_url)}"))

                list_widget = QListWidget()
                for label_text, u in variant_list:
                    item = QListWidgetItem(label_text)
                    item.setData(Qt.ItemDataRole.UserRole, u)
                    list_widget.addItem(item)
                layout.addWidget(list_widget)

                btns = QHBoxLayout()
                ok_btn = QPushButton("Abspielen")
                cancel_btn = QPushButton("Abbrechen")
                btns.addWidget(ok_btn)
                btns.addWidget(cancel_btn)
                layout.addLayout(btns)

                def on_ok():
                    it = list_widget.currentItem()
                    if it:
                        self.play_video_in_vlc(it.data(Qt.ItemDataRole.UserRole))
                    dlg.accept()

                ok_btn.clicked.connect(on_ok)
                cancel_btn.clicked.connect(dlg.reject)
                dlg.exec()

        except Exception as e:
            QMessageBox.warning(self, "yt-dlp Fehler", f"Fehler:\n{e}")

    def scan_and_play_videos(self):
        current_url = self.tabs.currentWidget().url().toString()
        self.handle_youtube_via_yt_dlp(current_url)

    def play_video_in_vlc(self, video_url):
        VLCPlayerDialog(video_url, self).exec()

    def show_whois_info(self):
        current_url = self.tabs.currentWidget().url().toString()
        domain = QUrl(current_url).host()
        if not domain:
            QMessageBox.warning(self, "Fehler", "Keine gültige Domain gefunden.")
            return
        try:
            whois_info = whois.whois(domain)
            whois_str = ""
            for key, value in whois_info.items():
                whois_str += f"{key}: {value}\n"
            ip = socket.gethostbyname(domain)
            ip_info = f"IP-Adresse: {ip}"
            WhoisDialog(whois_str, ip_info, self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"WHOIS Fehler:\n{e}")

    def load_plugins(self):
        for plugin_info in self.data["plugins"]:
            path = plugin_info["path"]
            try:
                spec = importlib.util.spec_from_file_location("temp_plugin", path)
                plugin_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(plugin_module)
                if hasattr(plugin_module, "initialize_plugin"):
                    plugin_module.initialize_plugin(self)
                self.loaded_plugin_modules[path] = plugin_module
            except Exception as e:
                print(f"Fehler beim Laden des Plugins '{path}': {e}")

    def add_plugin(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Plugin hinzufügen", "", "Python-Dateien (*.py);;Alle Dateien (*)")
        if not file_path:
            return
        self.data["plugins"].append({"path": file_path})
        self.save_data()
        QMessageBox.information(self, "Neustart", "Plugin hinzugefügt. App wird neu gestartet.")
        self.restart_application()

    def manage_plugins(self):
        old = self.data["plugins"][:]
        dlg = PluginManagerDialog(self, plugins_list=self.data["plugins"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.data["plugins"] = dlg.plugins
            self.save_data()
            if self.data["plugins"] != old:
                QMessageBox.information(self, "Neustart", "Plugin-Liste geändert. Neustart.")
                self.restart_application()

    def restart_application(self):
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                QMessageBox.warning(self, "Fehler", f"Die Datei {DATA_FILE} ist beschädigt.")
                self.data = {"favorites": [], "credentials": {}, "history": [], "plugins": [], "adblock_enabled": True}
        else:
            self.data = {"favorites": [], "credentials": {}, "history": [], "plugins": [], "adblock_enabled": True}

    def save_data(self):
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.make_serializable(self.data), f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Beim Speichern der Daten ist ein Fehler aufgetreten:\n{e}")

    def make_serializable(self, obj):
        if isinstance(obj, dict):
            return {k: self.make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.make_serializable(x) for x in obj]
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return obj

    def add_to_history(self, title, url):
        self.data["history"].append({"title": title or "Ohne Titel", "url": url})
        self.save_data()


if __name__ == "__main__":
    for k in (
        "http_proxy", "https_proxy", "all_proxy", "no_proxy",
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"
    ):
        os.environ.pop(k, None)

    extra_flags = "--no-proxy-server --proxy-auto-detect=false"
    existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (existing_flags + " " + extra_flags).strip() if existing_flags else extra_flags

    QNetworkProxyFactory.setUseSystemConfiguration(False)
    QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))

    app = QApplication(sys.argv)
    app.setStyleSheet(EPIC_QSS)

    window = Browser()
    window.show()
    sys.exit(app.exec())
