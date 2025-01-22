#!/usr/bin/env python3
# TMP-Networks-Browser-Mini.py

import sys
import json
import os
import re
import requests
import vlc
import socket
import whois
import m3u8  # Wichtig für das Parsen von M3U8
from datetime import datetime
from functools import partial
import importlib
import importlib.util

from urllib.parse import urljoin

# PyQt6
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QLineEdit, QWidget,
    QTabWidget, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QDialog, QPushButton, QLabel, QMenu, QListWidget, QListWidgetItem, QHBoxLayout,
    QSizePolicy, QFrame, QSlider, QTextEdit, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar
)
from PyQt6.QtGui import QAction, QFont, QDesktopServices
from PyQt6.QtCore import QUrl, QSize, Qt, QTimer, QThread
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineDownloadRequest, QWebEngineProfile

# AppDirs für plattformübergreifende Pfadverwaltung
from appdirs import AppDirs

import yt_dlp  # Achte darauf, dass du yt-dlp installiert hast

# Verzeichnisse für Daten
dirs = AppDirs("TMPNetworksBrowserMini", "DeinName")
json_dir = dirs.user_data_dir
json_path = os.path.join(json_dir, "favoriten_und_passwoerter.json")
os.makedirs(json_dir, exist_ok=True)
DATA_FILE = json_path


def get_emoji_font():
    """ 
    Vereinfachtes Fallback: Liefert z.B. 'Noto Color Emoji' mit Größe 16
    """
    return QFont("Noto Color Emoji", 16)


class DownloadWorker(QWidget):
    """
    Worker-Objekt für den Download via yt_dlp in einem separaten QThread.
    """
    from PyQt6.QtCore import pyqtSignal
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, url, output_path):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self._is_cancelled = False

    def run(self):
        import yt_dlp

        def progress_hook(d):
            if self._is_cancelled:
                raise yt_dlp.utils.DownloadError('Download cancelled by user.')
            if d['status'] == 'downloading':
                if d.get('total_bytes'):
                    percent = int(d['downloaded_bytes'] / d['total_bytes'] * 100)
                    self.progress.emit(percent)
            elif d['status'] == 'finished':
                self.progress.emit(100)
                self.status.emit('Fertig')

        ydl_opts = {
            'outtmpl': self.output_path,
            'progress_hooks': [progress_hook],
            'quiet': True,
            'no_warnings': True,
            'format': 'best'
        }
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


class VLCPlayerDialog(QDialog):
    """
    Dialog zum Abspielen eines Videos mit VLC und Steuerelementen.
    """
    def __init__(self, video_url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video abspielen mit VLC")
        self.resize(800, 600)
        self.video_url = video_url

        self.is_seeking = False  # Zum Unterscheiden, ob gerade Slider bedient wird

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
        new_position = self.position_slider.value()
        self.media_player.set_time(new_position)

    def download_video(self):
        # Statt direktes Herunterladen, rufe die Browser-Methode auf
        parent_browser = self.parent()
        from PyQt6.QtWidgets import QMessageBox
        if not parent_browser or not isinstance(parent_browser, Browser):
            QMessageBox.warning(self, "Fehler", "Der Browser ist nicht verfügbar.")
            return

        parent_browser.download_video_url(self.video_url)
        QMessageBox.information(self, "Download", "Download wurde gestartet und wird im Download-Manager angezeigt.")

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


class MyWebEnginePage(QWebEnginePage):
    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)
        
        # Damit JavaScript auf die Zwischenablage zugreifen darf:
        self.settings().setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard,
            True
        )
        
        # Falls du noch andere Features (z.B. Geolocation usw.) manuell erlauben willst,
        # kannst du das Signal hier abfangen:
        self.featurePermissionRequested.connect(self.onFeaturePermissionRequested)

    def onFeaturePermissionRequested(self, security_origin, feature):
        """
        Hier kannst du - wenn nötig - andere Features erlauben oder ablehnen,
        z.B. Notifications, Geolocation, Kamera, Mikrofon etc.
        """
        # Beispiel: Alle Feature-Anfragen ablehnen, außer Geolocation
        if feature == QWebEnginePage.Feature.Geolocation:
            self.setFeaturePermission(security_origin, feature,
                                      QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)
        else:
            self.setFeaturePermission(security_origin, feature,
                                      QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)


class CustomWebEngineView(QWebEngineView):
    def __init__(self, browser, profile):
        super().__init__()
        self.browser = browser
        
        # Unsere eigene Page-Klasse verwenden mit dem angegebenen Profil:
        custom_page = MyWebEnginePage(profile, self)
        self.setPage(custom_page)

    def createWindow(self, requested_window_type):
        reply = QMessageBox.question(
            self.browser,
            "Pop-up anfordern",
            "Eine Webseite möchte ein Pop-up öffnen. Möchten Sie es erlauben?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            popup_browser = CustomWebEngineView(self.browser, self.browser.profile)
            i = self.browser.tabs.addTab(popup_browser, "Neues Fenster")
            self.browser.tabs.setCurrentIndex(i)
            return popup_browser
        else:
            return None


class LoginDialog(QDialog):
    def __init__(self, parent=None, username="", password=""):
        super().__init__(parent)
        self.setWindowTitle("Zugangsdaten speichern")
        layout = QVBoxLayout()

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

        self.setLayout(layout)

    def get_credentials(self):
        return self.username_edit.text(), self.password_edit.text()


class CredentialsManagerDialog(QDialog):
    def __init__(self, parent=None, credentials_dict=None):
        super().__init__(parent)
        self.setWindowTitle("Passwörter verwalten")
        self.resize(400, 300)
        self.credentials = credentials_dict.copy() if credentials_dict else {}
        layout = QVBoxLayout()

        self.list_widget = QListWidget()
        for domain in sorted(self.credentials.keys()):
            item = QListWidgetItem(domain)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("Bearbeiten")
        self.delete_btn = QPushButton("Löschen")
        self.edit_btn.clicked.connect(self.edit_credentials)
        self.delete_btn.clicked.connect(self.delete_credentials)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        layout.addLayout(btn_layout)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def edit_credentials(self):
        selected_item = self.list_widget.currentItem()
        if not selected_item:
            QMessageBox.information(self, "Info", "Bitte wählen Sie einen Eintrag aus.")
            return
        domain = selected_item.text()
        creds = self.credentials[domain]
        dlg = LoginDialog(self, username=creds["username"], password=creds["password"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            username, password = dlg.get_credentials()
            if username and password:
                self.credentials[domain] = {"username": username, "password": password}
                QMessageBox.information(self, "Erfolg", f"Zugangsdaten für {domain} geändert.")
            else:
                QMessageBox.warning(
                    self,
                    "Warnung",
                    "Benutzername und Passwort dürfen nicht leer sein."
                )

    def delete_credentials(self):
        selected_item = self.list_widget.currentItem()
        if not selected_item:
            QMessageBox.information(self, "Info", "Bitte wählen Sie einen Eintrag aus.")
            return
        domain = selected_item.text()
        reply = QMessageBox.question(
            self,
            "Löschen bestätigen",
            f"Sollen die Zugangsdaten für {domain} wirklich gelöscht werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            del self.credentials[domain]
            self.list_widget.takeItem(self.list_widget.row(selected_item))
            QMessageBox.information(self, "Erfolg", f"Zugangsdaten für {domain} gelöscht.")

    def refresh_list(self):
        self.list_widget.clear()
        for domain, creds in sorted(self.credentials.items()):
            item = QListWidgetItem(domain)
            self.list_widget.addItem(item)


class EditFavoriteDialog(QDialog):
    """
    Dialog zum Bearbeiten eines einzelnen Favoriten (Titel/URL).
    """
    def __init__(self, parent=None, title="", url=""):
        super().__init__(parent)
        self.setWindowTitle("Favorit bearbeiten")
        layout = QVBoxLayout()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Titel")
        self.title_edit.setText(title)
        layout.addWidget(QLabel("Titel:"))
        layout.addWidget(self.title_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("URL")
        self.url_edit.setText(url)
        layout.addWidget(QLabel("URL:"))
        layout.addWidget(self.url_edit)

        save_btn = QPushButton("Speichern")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)

        self.setLayout(layout)

    def get_values(self):
        return self.title_edit.text(), self.url_edit.text()


class FavoritesManagerDialog(QDialog):
    """
    Verwaltung für Favoriten (Bearbeiten / Löschen).
    """
    def __init__(self, parent=None, favorites_list=None):
        super().__init__(parent)
        self.setWindowTitle("Favoriten verwalten")
        self.resize(400, 300)
        
        self.favorites = favorites_list.copy() if favorites_list else []
        
        layout = QVBoxLayout()

        self.list_widget = QListWidget()
        for fav in sorted(self.favorites, key=lambda x: x["title"]):
            item_text = f"{fav['title']}\n{fav['url']}"
            item = QListWidgetItem(item_text)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("Bearbeiten")
        self.delete_btn = QPushButton("Löschen")
        self.edit_btn.clicked.connect(self.edit_favorite)
        self.delete_btn.clicked.connect(self.delete_favorite)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        layout.addLayout(btn_layout)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def edit_favorite(self):
        selected_item = self.list_widget.currentItem()
        if not selected_item:
            QMessageBox.information(self, "Info", "Bitte wählen Sie einen Favoriten aus.")
            return
        lines = selected_item.text().split("\n")
        if len(lines) < 2:
            return
        old_title = lines[0]
        old_url = lines[1]
        
        edit_dlg = EditFavoriteDialog(self, old_title, old_url)
        if edit_dlg.exec() == QDialog.DialogCode.Accepted:
            new_title, new_url = edit_dlg.get_values()
            if new_title and new_url:
                for fav in self.favorites:
                    if fav["title"] == old_title and fav["url"] == old_url:
                        fav["title"] = new_title
                        fav["url"] = new_url
                        break
                self.refresh_list()
                QMessageBox.information(self, "Erfolg", f"Favorit '{new_title}' bearbeitet.")
            else:
                QMessageBox.warning(
                    self,
                    "Warnung",
                    "Titel und URL dürfen nicht leer sein."
                )

    def delete_favorite(self):
        selected_item = self.list_widget.currentItem()
        if not selected_item:
            QMessageBox.information(self, "Info", "Bitte wählen Sie einen Favoriten aus.")
            return
        
        lines = selected_item.text().split("\n")
        if len(lines) < 2:
            return
        fav_title = lines[0]
        fav_url = lines[1]
        
        reply = QMessageBox.question(
            self,
            "Löschen bestätigen",
            f"Sollen der Favorit '{fav_title}' wirklich gelöscht werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.favorites = [
                f for f in self.favorites
                if not (f["title"] == fav_title and f["url"] == fav_url)
            ]
            self.refresh_list()
            QMessageBox.information(self, "Erfolg", f"Favorit '{fav_title}' gelöscht.")

    def refresh_list(self):
        self.list_widget.clear()
        for fav in sorted(self.favorites, key=lambda x: x["title"]):
            item_text = f"{fav['title']}\n{fav['url']}"
            item = QListWidgetItem(item_text)
            self.list_widget.addItem(item)


class HistoryDialog(QDialog):
    """
    Einfache Dialogklasse, um die Chronik anzuzeigen.
    """
    def __init__(self, parent=None, history_list=None):
        super().__init__(parent)
        self.setWindowTitle("Chronik anzeigen")
        self.resize(400, 300)
        self.history = history_list if history_list else []

        layout = QVBoxLayout()

        self.list_widget = QListWidget()
        for entry in self.history:
            title = entry.get("title", "Ohne Titel")
            url = entry.get("url", "")
            item_text = f"{title}\n{url}"
            item = QListWidgetItem(item_text)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        self.list_widget.itemDoubleClicked.connect(self.navigate_from_history)

        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def navigate_from_history(self, item):
        text = item.text()
        lines = text.split("\n")
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
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        
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
        
        self.setLayout(layout)


class DownloadManagerDialog(QDialog):
    """
    Zeigt eine Tabelle aller Downloads an.
    Ermöglicht das Abbrechen, Löschen von Downloads sowie das Öffnen der heruntergeladenen Dateien.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download-Manager")
        self.resize(700, 400)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Dateiname", "Fortschritt", "Status", "Zielpfad"])
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

        self.setLayout(layout)

        self.browser = parent

        self.cancel_btn.clicked.connect(self.cancel_download)
        self.delete_btn.clicked.connect(self.delete_download)
        self.close_btn.clicked.connect(self.accept)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(500)  # alle 0,5 Sek
        self.refresh_timer.timeout.connect(self.refresh_table)
        self.refresh_timer.start()

        self.table.itemDoubleClicked.connect(self.open_download)

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

            self.table.setItem(row, 0, filename_item)
            self.table.setCellWidget(row, 1, progress_bar)
            self.table.setItem(row, 2, status_item)
            self.table.setItem(row, 3, path_item)

    def get_selected_download_info(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Info", "Bitte wählen Sie einen Download aus.")
            return None
        download_info = selected_items[0].data(Qt.ItemDataRole.UserRole)
        return download_info

    def cancel_download(self):
        download_info = self.get_selected_download_info()
        if not download_info:
            return

        if download_info["status"] not in ["Läuft", "Wartet"]:
            QMessageBox.warning(self, "Warnung", "Nur laufende oder wartende Downloads können abgebrochen werden.")
            return

        reply = QMessageBox.question(
            self,
            "Abbrechen bestätigen",
            f"Sollen der Download '{download_info['filename']}' wirklich abgebrochen werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.browser.cancel_download(download_info)
            QMessageBox.information(self, "Abgebrochen", f"Download '{download_info['filename']}' wurde abgebrochen.")

    def delete_download(self):
        download_info = self.get_selected_download_info()
        if not download_info:
            return

        reply = QMessageBox.question(
            self,
            "Enfernen bestätigen",
            f"Sollen der Download '{download_info['filename']}' wirklich enfernt werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.browser.delete_download(download_info)
            self.refresh_table()
            QMessageBox.information(self, "Entfernt", f"Download '{download_info['filename']}' wurde entfernt.")

    def open_download(self, item):
        download_info = item.data(Qt.ItemDataRole.UserRole)
        target_path = download_info.get("target_path")

        if target_path and os.path.exists(target_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(target_path))
        else:
            QMessageBox.warning(self, "Fehler", f"Die Datei '{target_path}' wurde nicht gefunden.")


# --- NEU: Plugins verwalten ---
class PluginManagerDialog(QDialog):
    """
    Dialog zur Verwaltung der Plugins.
    Zeigt eine Tabelle mit Plugin-Pfad und ob es aktiv ist oder nicht.
    Ermöglicht das Hinzufügen, Entfernen und Aktivieren/Deaktivieren.
    """
    def __init__(self, parent=None, plugins_list=None):
        super().__init__(parent)
        self.setWindowTitle("Plugins verwalten")
        self.resize(600, 400)

        self.plugins = plugins_list.copy() if plugins_list else []

        layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Plugin-Pfad", "Aktiv?"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.refresh_table()

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Hinzufügen")
        self.remove_btn = QPushButton("Entfernen")
        self.toggle_btn = QPushButton("Aktivieren/Deaktivieren")
        self.close_btn = QPushButton("Schließen")

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.toggle_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.add_btn.clicked.connect(self.add_plugin)
        self.remove_btn.clicked.connect(self.remove_plugin)
        self.toggle_btn.clicked.connect(self.toggle_plugin)
        self.close_btn.clicked.connect(self.accept)

        self.setLayout(layout)

    def refresh_table(self):
        self.table.setRowCount(len(self.plugins))
        for row, plugin in enumerate(self.plugins):
            path_item = QTableWidgetItem(plugin["path"])
            active_text = "Ja" if plugin["active"] else "Nein"
            active_item = QTableWidgetItem(active_text)

            self.table.setItem(row, 0, path_item)
            self.table.setItem(row, 1, active_item)

    def add_plugin(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Plugin hinzufügen",
            "",
            "Python-Dateien (*.py);;Alle Dateien (*)"
        )
        if not file_path:
            return
        # Plugin an Liste anhängen, standardmäßig aktivieren oder deaktiviert (deine Wahl)
        self.plugins.append({"path": file_path, "active": True})
        self.refresh_table()

    def remove_plugin(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Info", "Bitte wähle ein Plugin aus.")
            return
        reply = QMessageBox.question(
            self,
            "Plugin entfernen",
            "Möchtest du dieses Plugin wirklich entfernen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.plugins.pop(row)
            self.refresh_table()

    def toggle_plugin(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Info", "Bitte wähle ein Plugin aus.")
            return
        plugin = self.plugins[row]
        plugin["active"] = not plugin["active"]
        self.refresh_table()


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TMP-Networks Browser Mini")
        self.setGeometry(100, 100, 1200, 800)
        self.load_data()

        # Sicherstellen, dass die nötigen Keys existieren
        if "history" not in self.data:
            self.data["history"] = []
        if "plugins" not in self.data:
            self.data["plugins"] = []  # Liste von dicts mit {"path":..., "active":...}

        # Listen für Downloads
        self.active_downloads_info = []
        self.all_downloads_info = []

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_current_tab)
        self.tabs.currentChanged.connect(self.update_url_bar)
        self.setCentralWidget(self.tabs)

        menu_bar = self.menuBar()

        # Favoriten-Menü
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

        # Passwörter-Menü
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

        # Chronik-Menü
        self.history_menu = QMenu("Chronik", self)
        menu_bar.addMenu(self.history_menu)
        show_history_action = QAction("Chronik anzeigen", self)
        show_history_action.triggered.connect(self.view_history)
        self.history_menu.addAction(show_history_action)

        # Download-Manager-Menü
        self.download_menu = QMenu("Downloads", self)
        menu_bar.addMenu(self.download_menu)
        show_download_mgr_action = QAction("Download-Manager öffnen", self)
        show_download_mgr_action.triggered.connect(self.open_download_manager)
        self.download_menu.addAction(show_download_mgr_action)

        # --- NEU: Plugins-Menü ---
        self.plugin_menu = QMenu("Plugins", self)
        menu_bar.addMenu(self.plugin_menu)

        add_plugin_action = QAction("Plugin hinzufügen", self)
        add_plugin_action.triggered.connect(self.add_plugin)
        self.plugin_menu.addAction(add_plugin_action)

        manage_plugins_action = QAction("Plugins verwalten", self)
        manage_plugins_action.triggered.connect(self.manage_plugins)
        self.plugin_menu.addAction(manage_plugins_action)
        # --- Ende Plugins-Menü ---

        # Navigation Bar
        navigation_bar = QToolBar("Navigation")
        navigation_bar.setIconSize(QSize(24, 24))
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
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        navigation_bar.addWidget(self.url_bar)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        navigation_bar.addWidget(spacer)

        video_scan_button = QAction("🎥", self)
        video_scan_button.setToolTip("Videos scannen und abspielen (höchste Auflösung)")
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

        # QWebEngineProfile mit persistentem Speicherpfad
        self.profile = QWebEngineProfile("TMPNetworksBrowserProfile", self)
        self.profile.setPersistentStoragePath(json_dir)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.downloadRequested.connect(self.on_downloadRequested)

        self.add_new_tab(QUrl('https://www.google.com'), 'Startseite')
        self.download_manager_dialog = None

        # Plugins laden
        self.loaded_plugin_modules = {}
        self.load_plugins()

    # --- Plugin-Handling ---
    def load_plugins(self):
        """
        Lädt alle aktiven Plugins (falls in self.data["plugins"] eingetragen).
        Wenn das Plugin eine Funktion 'initialize_plugin(browser)' definiert, wird sie aufgerufen.
        """
        for plugin_info in self.data["plugins"]:
            if plugin_info.get("active", False):
                path = plugin_info["path"]
                try:
                    spec = importlib.util.spec_from_file_location("temp_plugin", path)
                    plugin_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(plugin_module)

                    # Falls das Plugin eine spezielle Init-Funktion hat
                    if hasattr(plugin_module, "initialize_plugin"):
                        plugin_module.initialize_plugin(self)

                    self.loaded_plugin_modules[path] = plugin_module
                except Exception as e:
                    print(f"Fehler beim Laden des Plugins '{path}': {e}")

    def add_plugin(self):
        """
        Fügt ein Plugin (Pfad) direkt hinzu.
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Plugin hinzufügen",
            "",
            "Python-Dateien (*.py);;Alle Dateien (*)"
        )
        if not file_path:
            return
        # Plugin in self.data ablegen und aktivieren
        self.data["plugins"].append({"path": file_path, "active": True})
        self.save_data()
        QMessageBox.information(self, "Plugin", f"Plugin hinzugefügt: {file_path}")
        # Optional: direkt laden
        self.load_plugins()

    def manage_plugins(self):
        """
        Öffnet den Dialog zur Plugin-Verwaltung.
        """
        dlg = PluginManagerDialog(self, plugins_list=self.data["plugins"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Liste aktualisieren
            self.data["plugins"] = dlg.plugins
            self.save_data()

            # Ggf. neu laden (einfachste Variante: Alles neu laden)
            self.loaded_plugin_modules = {}
            self.load_plugins()

    # --- Ende Plugin-Handling ---

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                QMessageBox.warning(self, "Fehler", f"Die Datei {DATA_FILE} ist beschädigt.")
                self.data = {"favorites": [], "credentials": {}, "history": [], "plugins": []}
        else:
            self.data = {"favorites": [], "credentials": {}, "history": [], "plugins": []}

    def save_data(self):
        try:
            serializable_data = self.make_serializable(self.data)
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Beim Speichern der Daten ist ein Fehler aufgetreten:\n{e}")

    def make_serializable(self, obj):
        if isinstance(obj, dict):
            return {k: self.make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.make_serializable(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        else:
            return obj

    def add_to_history(self, title, url):
        if not title:
            title = "Ohne Titel"
        self.data["history"].append({"title": title, "url": url})
        self.save_data()

    def add_new_tab(self, qurl=None, label="Neue Seite"):
        if not qurl:
            qurl = QUrl("https://www.google.com")
        browser = CustomWebEngineView(self, self.profile)
        browser.setUrl(qurl)
        browser.loadFinished.connect(lambda _, b=browser: self.check_credentials(b))
        browser.loadFinished.connect(lambda _, b=browser: self.tabs.setTabText(self.tabs.indexOf(b), b.page().title()))
        browser.urlChanged.connect(lambda new_url, b=browser: self.update_url_bar(new_url, b))
        i = self.tabs.addTab(browser, label)
        self.tabs.setCurrentIndex(i)

    def close_current_tab(self, index):
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.close()

    def update_url_bar(self, qurl=None, browser=None):
        if browser != self.tabs.currentWidget():
            return
        if qurl is None:
            qurl = self.tabs.currentWidget().url()
        self.url_bar.setText(qurl.toString())
        self.url_bar.setCursorPosition(0)

        current_title = self.tabs.currentWidget().page().title()
        current_url = qurl.toString()
        if current_url and current_url != "about:blank":
            self.add_to_history(current_title, current_url)

    def navigate_to_url(self):
        q = QUrl(self.url_bar.text())
        if q.scheme() == "":
            q.setScheme("http")
        self.tabs.currentWidget().setUrl(q)

    def navigate_home(self):
        self.tabs.currentWidget().setUrl(QUrl("https://www.google.com"))

    def navigate_to_url_string(self, url_string):
        if not url_string:
            return
        q = QUrl(url_string)
        if q.scheme() == "":
            q.setScheme("http")
        self.tabs.currentWidget().setUrl(q)

    def open_download_manager(self):
        if not self.download_manager_dialog:
            self.download_manager_dialog = DownloadManagerDialog(self)
        self.download_manager_dialog.show()
        self.download_manager_dialog.raise_()
        self.download_manager_dialog.activateWindow()

    def on_downloadRequested(self, download):
        url = download.url().toString()
        # Prüfe, ob es sich um eine .m3u8 URL handelt
        if url.endswith('.m3u8'):
            # Verwende download_video_url, um den Download zu verwalten
            self.download_video_url(url)
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Speichern unter",
                download.downloadFileName() or "",
                "Alle Dateien (*)"
            )
            if file_path:
                directory = os.path.dirname(file_path)
                filename_only = os.path.basename(file_path)
                download.setDownloadDirectory(directory)
                download.setDownloadFileName(filename_only)
                download.accept()

                download_info = {
                    "download_obj": download,
                    "filename": filename_only,
                    "target_path": file_path,
                    "progress_percent": 0,
                    "status": "Läuft",
                    "timer": None
                }
                self.active_downloads_info.append(download_info)
                self.all_downloads_info.append(download_info)
                print(f"Download gestartet: {filename_only}")

                timer = QTimer(self)
                timer.setInterval(500)
                timer.timeout.connect(partial(self.poll_download, download_info))
                timer.start()
                download_info["timer"] = timer

                download.stateChanged.connect(
                    partial(self.handle_download_state_changed, download_info)
                )

                self.download_progress_bar.setVisible(True)
                self.status.showMessage(f"Download gestartet: {filename_only}")

    def poll_download(self, download_info):
        if "download_obj" in download_info:
            download = download_info["download_obj"]
            received = download.receivedBytes()
            total = download.totalBytes()

            if total > 0:
                percent = int(received / total * 100)
                percent = min(percent, 100)
                download_info["progress_percent"] = percent
                self.download_progress_bar.setValue(percent)
                print(f"Download Fortschritt: {percent}% - {download_info['filename']}")
            else:
                self.download_progress_bar.setRange(0, 0)
                print(f"Download Fortschritt: Unbestimmt - {download_info['filename']}")

    def handle_download_state_changed(self, download_info, state):
        if state == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            download_info["status"] = "Fertig"
            download_info["progress_percent"] = 100
            self.status.showMessage(f"Download abgeschlossen: {download_info['target_path']}")
            print(f"Download abgeschlossen: {download_info['filename']}")
            if download_info["timer"]:
                download_info["timer"].stop()
            self.download_progress_bar.setValue(100)
            if download_info in self.active_downloads_info:
                self.active_downloads_info.remove(download_info)
            if not self.active_downloads_info:
                self.download_progress_bar.setVisible(False)
                self.status.clearMessage()
            else:
                max_progress = max(dl["progress_percent"] for dl in self.active_downloads_info)
                self.download_progress_bar.setValue(max_progress)

        elif state in (
            QWebEngineDownloadRequest.DownloadState.DownloadCancelled,
            QWebEngineDownloadRequest.DownloadState.DownloadInterrupted
        ):
            download_info["status"] = "Fehlgeschlagen"
            self.status.showMessage(f"Download fehlgeschlagen oder abgebrochen: {download_info['target_path']}")
            print(f"Download fehlgeschlagen oder abgebrochen: {download_info['filename']}")
            if download_info["timer"]:
                download_info["timer"].stop()
            self.download_progress_bar.setValue(0)
            if download_info in self.active_downloads_info:
                self.active_downloads_info.remove(download_info)
            if not self.active_downloads_info:
                self.download_progress_bar.setVisible(False)
                self.status.clearMessage()
            else:
                max_progress = max(dl["progress_percent"] for dl in self.active_downloads_info)
                self.download_progress_bar.setValue(max_progress)

        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    # ---- Favoriten ----
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
        # Die ersten Einträge: 0=Favorit hinzufügen, 1=Separator, 2=Favoriten verwalten
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
        reply = QMessageBox.question(
            self,
            "Löschen bestätigen",
            f"Sollen der Favorit '{fav['title']}' gelöscht werden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.data["favorites"] = [x for x in self.data["favorites"] if x != fav]
            self.save_data()
            self.update_favorites_menu()
            QMessageBox.information(self, "Erfolg", f"Favorit '{fav['title']}' gelöscht.")

    def navigate_to_favorite(self):
        action = self.sender()
        if action:
            url = action.data()
            self.tabs.currentWidget().setUrl(QUrl(url))

    def manage_favorites(self):
        if not self.data["favorites"]:
            QMessageBox.information(self, "Info", "Keine gespeicherten Favoriten vorhanden.")
            return
        dlg = FavoritesManagerDialog(self, favorites_list=self.data["favorites"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.data["favorites"] = dlg.favorites
            self.save_data()
            self.update_favorites_menu()

    # ---- Passwörter ----
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
            QMessageBox.information(self, "Info", "Keine gespeicherten Zugangsdaten vorhanden.")
            return
        creds_text = ""
        for domain, creds in sorted(self.data["credentials"].items()):
            creds_text += (
                f"Domain: {domain}\n"
                f"Benutzername: {creds['username']}\n"
                f"Passwort: {creds['password']}\n\n"
            )
        creds_dialog = QDialog(self)
        creds_dialog.setWindowTitle("Gespeicherte Zugangsdaten")
        creds_dialog.resize(400, 300)
        layout = QVBoxLayout()
        creds_label = QLabel(creds_text)
        creds_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(creds_label)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(creds_dialog.accept)
        layout.addWidget(close_btn)
        creds_dialog.setLayout(layout)
        creds_dialog.exec()

    def manage_credentials(self):
        if not self.data["credentials"]:
            QMessageBox.information(self, "Info", "Keine gespeicherten Zugangsdaten vorhanden.")
            return
        dlg = CredentialsManagerDialog(self, credentials_dict=self.data["credentials"])
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.data["credentials"] = dlg.credentials
            self.save_data()

    # ---- Chronik ----
    def view_history(self):
        history_list = self.data.get("history", [])
        dlg = HistoryDialog(self, history_list=history_list)
        dlg.exec()

    # ---- Credential Checking ----
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
            var hasPasswordField = false;
            for(var i=0; i<inputs.length; i++) {
                if(inputs[i].type.toLowerCase() === 'password') {
                    hasPasswordField = true;
                    break;
                }
            }
            return hasPasswordField;
        })();
        """
        browser.page().runJavaScript(
            js_code, lambda result: self.handle_check_password_field(result, credentials, browser)
        )

    def handle_check_password_field(self, has_password_field, credentials, browser):
        if not has_password_field:
            return
        reply = QMessageBox.question(
            self,
            "Zugangsdaten verfügbar",
            "Zugangsdaten für diese Domain sind gespeichert. Möchten Sie diese einfügen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            username = credentials['username'].replace('"', '\\"')
            password = credentials['password'].replace('"', '\\"')
            js_code = f"""
            (function() {{
                var inputs = document.getElementsByTagName('input');
                for(var i=0; i<inputs.length; i++) {{
                    if(inputs[i].type.toLowerCase() === 'text' || inputs[i].type.toLowerCase() === 'email') {{
                        inputs[i].value = "{username}";
                    }} else if(inputs[i].type.toLowerCase() === 'password') {{
                        inputs[i].value = "{password}";
                    }}
                }}
            }})();
            """
            browser.page().runJavaScript(js_code)
            QMessageBox.information(self, "Info", "Zugangsdaten wurden eingefügt.")

    # ---- Video/Media-Handling via yt_dlp ----
    def download_video_url(self, url):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
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
            self,
            "Video speichern unter",
            default_filename,
            f"Video Dateien (*.{ext});;Alle Dateien (*)"
        )
        if not save_path:
            return

        download_info = {
            "filename": os.path.basename(save_path),
            "target_path": save_path,
            "progress_percent": 0,
            "status": "Wartet",
            "timer": None,
            "worker": None,
            "thread": None
        }
        self.all_downloads_info.append(download_info)
        self.active_downloads_info.append(download_info)

        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

        thread = QThread()
        worker = DownloadWorker(url, save_path)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(lambda p: self.update_download_progress(download_info, p))
        worker.status.connect(lambda s: self.update_download_status(download_info, s))
        worker.error.connect(lambda e: self.handle_download_error(download_info, e))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: self.on_download_finished(download_info))
        thread.finished.connect(thread.deleteLater)

        thread.start()

        download_info["worker"] = worker
        download_info["thread"] = thread

        self.download_progress_bar.setVisible(True)
        self.status.showMessage(f"Download gestartet: {download_info['filename']}")

    def update_download_progress(self, download_info, percent):
        download_info["progress_percent"] = percent
        self.download_progress_bar.setValue(percent)
        self.download_progress_bar.setVisible(True)
        print(f"Download Fortschritt: {percent}% - {download_info['filename']}")
        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def update_download_status(self, download_info, status):
        download_info["status"] = status
        self.status.showMessage(f"Download Status: {status} - {download_info['target_path']}")
        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def handle_download_error(self, download_info, error_message):
        QMessageBox.warning(self, "Download-Fehler", f"Fehler beim Herunterladen von {download_info['filename']}:\n{error_message}")

    def on_download_finished(self, download_info):
        if download_info["status"] == "Fertig":
            self.status.showMessage(f"Download abgeschlossen: {download_info['target_path']}")
        elif download_info["status"] == "Abgebrochen":
            self.status.showMessage(f"Download abgebrochen: {download_info['target_path']}")
        elif download_info["status"] == "Fehlgeschlagen":
            self.status.showMessage(f"Download fehlgeschlagen: {download_info['target_path']}")

        if download_info in self.active_downloads_info:
            self.active_downloads_info.remove(download_info)

        if not self.active_downloads_info:
            self.download_progress_bar.setVisible(False)
            self.status.clearMessage()
        else:
            max_progress = max(dl["progress_percent"] for dl in self.active_downloads_info)
            self.download_progress_bar.setValue(max_progress)

        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def cancel_download(self, download_info):
        if download_info["status"] in ["Läuft", "Wartet"]:
            if "worker" in download_info and download_info["worker"]:
                worker = download_info["worker"]
                worker.cancel()
                print(f"Download abgebrochen: {download_info['filename']}")
            elif "download_obj" in download_info and download_info["download_obj"]:
                download_obj = download_info["download_obj"]
                download_obj.cancel()
                print(f"Download abgebrochen: {download_info['filename']}")
        elif download_info["status"] == "Wartet":
            if download_info in self.active_downloads_info:
                self.active_downloads_info.remove(download_info)
            print(f"Download entfernt: {download_info['filename']}")

        if not self.active_downloads_info:
            self.download_progress_bar.setVisible(False)
            self.status.clearMessage()
        else:
            max_progress = max(dl["progress_percent"] for dl in self.active_downloads_info)
            self.download_progress_bar.setValue(max_progress)

        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def delete_download(self, download_info):
        if download_info["status"] in ["Läuft", "Wartet"]:
            if "worker" in download_info and download_info["worker"]:
                worker = download_info["worker"]
                worker.cancel()
                print(f"Download abgebrochen und gelöscht: {download_info['filename']}")
            elif "download_obj" in download_info and download_info["download_obj"]:
                download_obj = download_info["download_obj"]
                download_obj.cancel()
                print(f"Download abgebrochen und gelöscht: {download_info['filename']}")

        if download_info in self.active_downloads_info:
            self.active_downloads_info.remove(download_info)
        if download_info in self.all_downloads_info:
            self.all_downloads_info.remove(download_info)
        print(f"Download gelöscht: {download_info['filename']}")

        if not self.active_downloads_info:
            self.download_progress_bar.setVisible(False)
            self.status.clearMessage()
        else:
            max_progress = max(dl["progress_percent"] for dl in self.active_downloads_info)
            self.download_progress_bar.setValue(max_progress)

        if self.download_manager_dialog and self.download_manager_dialog.isVisible():
            self.download_manager_dialog.refresh_table()

    def handle_youtube_via_yt_dlp(self, youtube_url):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best'
        }
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
                    QMessageBox.warning(self, "Fehler", "Keine abspielbaren Direct-URLs gefunden.")
                    return

                if len(variant_list) == 1:
                    self.play_video_in_vlc(variant_list[0][1])
                    return

                dlg = QDialog(self)
                dlg.setWindowTitle("Stream auswählen")
                dlg.resize(400, 300)
                layout = QVBoxLayout(dlg)

                info_label = QLabel(f"Formate für: {info.get('title', youtube_url)}")
                layout.addWidget(info_label)

                list_widget = QListWidget()
                for label_text, url in variant_list:
                    item = QListWidgetItem(label_text)
                    item.setData(Qt.ItemDataRole.UserRole, url)
                    list_widget.addItem(item)
                layout.addWidget(list_widget)

                btn_layout = QHBoxLayout()
                ok_btn = QPushButton("Abspielen")
                cancel_btn = QPushButton("Abbrechen")
                btn_layout.addWidget(ok_btn)
                btn_layout.addWidget(cancel_btn)
                layout.addLayout(btn_layout)

                def on_ok():
                    item = list_widget.currentItem()
                    if item:
                        chosen_url = item.data(Qt.ItemDataRole.UserRole)
                        self.play_video_in_vlc(chosen_url)
                    dlg.accept()

                def on_cancel():
                    dlg.reject()

                ok_btn.clicked.connect(on_ok)
                cancel_btn.clicked.connect(on_cancel)

                dlg.exec()

        except Exception as e:
            QMessageBox.warning(self, "YouTube-Fehler", f"Fehler beim Abrufen der Streams:\n{e}")

    def scan_and_play_videos(self):
        current_url = self.tabs.currentWidget().url().toString()
        self.handle_youtube_via_yt_dlp(current_url)

    def play_video_in_vlc(self, video_url):
        dlg = VLCPlayerDialog(video_url, self)
        dlg.exec()

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

            dlg = WhoisDialog(whois_str, ip_info, self)
            dlg.exec()

        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Fehler beim Abrufen der WHOIS-Informationen:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Browser()
    window.show()
    sys.exit(app.exec())
