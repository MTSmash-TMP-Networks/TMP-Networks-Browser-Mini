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
from datetime import datetime

from urllib.parse import urljoin

# PyQt6
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QLineEdit, QWidget,
    QTabWidget, QToolBar, QStatusBar, QFileDialog, QMessageBox,
    QDialog, QPushButton, QLabel, QMenu, QListWidget, QListWidgetItem, QHBoxLayout,
    QSizePolicy, QFrame, QSlider, QTextEdit, QScrollArea
)
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtCore import QUrl, QSize, QObject, pyqtSlot, Qt, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

# AppDirs für plattformübergreifende Pfadverwaltung
from appdirs import AppDirs

# Initialisiere AppDirs
dirs = AppDirs("TMPNetworksBrowserMini", "DeinName")

# Bestimme den Pfad zur JSON-Datei im Application Support-Verzeichnis
json_dir = dirs.user_data_dir
json_path = os.path.join(json_dir, "favoriten_und_passwoerter.json")

# Stelle sicher, dass das Verzeichnis existiert
os.makedirs(json_dir, exist_ok=True)

# Setze DATA_FILE auf den neuen Pfad
DATA_FILE = json_path

def get_emoji_font():
    """ 
    Vereinfachtes Fallback: Liefert 'Arial' mit Größe 16 zurück,
    um Probleme mit QFontDatabase zu vermeiden.
    """
    return QFont("Arial", 16)

class WebChannelInterface(QObject):
    def __init__(self, browser):
        super().__init__()
        self.browser = browser

    @pyqtSlot(str, str)
    def submit_form(self, username, password):
        self.browser.handle_form_submission(username, password)

class VLCPlayerDialog(QDialog):
    """
    Dialog zum Abspielen eines Videos mit VLC und Steuerelementen:
    - Play/Pause, Stop
    - Lauter/Leiser
    - Download
    - Positions-Slider (zum Spulen)
    """
    def __init__(self, video_url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video abspielen mit VLC")
        self.resize(800, 600)
        self.video_url = video_url

        # Variable, um zu wissen, ob gerade per Slider gesprungen wird
        self.is_seeking = False

        # Hauptlayout
        layout = QVBoxLayout(self)

        # -----------------------------------
        # 1) Video-Frame
        self.videoframe = QFrame(self)
        self.videoframe.setFrameShape(QFrame.Shape.Box)
        self.videoframe.setLineWidth(2)
        layout.addWidget(self.videoframe)

        # 2) Slider für die Position im Video
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)  # Start: Dummy-Wert
        self.position_slider.setValue(0)
        layout.addWidget(self.position_slider)

        # Events für den Slider
        self.position_slider.sliderPressed.connect(self.slider_pressed)
        self.position_slider.sliderReleased.connect(self.slider_released)

        # -----------------------------------
        # 3) Steuer-Buttons (Play/Pause, Stop)
        playback_layout = QHBoxLayout()
        self.play_button = QPushButton("Play/Pause")
        self.play_button.clicked.connect(self.toggle_play)
        playback_layout.addWidget(self.play_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_playback)
        playback_layout.addWidget(self.stop_button)

        layout.addLayout(playback_layout)

        # -----------------------------------
        # 4) Lautstärke und Download
        volume_layout = QHBoxLayout()

        self.volume = 100  # Standard-Lautstärke
        # Buttons: Leiser / Lauter
        self.vol_down_button = QPushButton("Leiser")
        self.vol_down_button.clicked.connect(self.volume_down)
        volume_layout.addWidget(self.vol_down_button)

        self.vol_up_button = QPushButton("Lauter")
        self.vol_up_button.clicked.connect(self.volume_up)
        volume_layout.addWidget(self.vol_up_button)

        # Download-Button
        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.download_video)
        volume_layout.addWidget(self.download_button)

        layout.addLayout(volume_layout)

        # -----------------------------------
        # VLC-Setup
        self.instance = vlc.Instance()
        self.media_player = self.instance.media_player_new()
        media = self.instance.media_new(self.video_url)
        self.media_player.set_media(media)
        self.media_player.audio_set_volume(self.volume)

        # Timer, um den Player zu aktualisieren (Position etc.)
        self.timer = QTimer(self)
        self.timer.setInterval(200)  # alle 200 ms
        self.timer.timeout.connect(self.update_frame)
        self.timer.start()

        # Beim Öffnen direkt abspielen
        self.media_player.play()

        # Widget für Video
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
        new_position = self.position_slider.value()  # in ms
        self.media_player.set_time(new_position)

    def download_video(self):
        save_path, _ = QFileDialog.getSaveFileName(self, "Video speichern unter",
                                                   os.path.basename(self.video_url))
        if not save_path:
            return  # Abbruch

        try:
            r = requests.get(self.video_url, stream=True)
            r.raise_for_status()

            total_size = int(r.headers.get('content-length', 0))
            chunk_size = 8192
            downloaded = 0

            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int(downloaded / total_size * 100)
                            self.setWindowTitle(f"Download: {percent}%")
                        QApplication.processEvents()

            QMessageBox.information(self, "Download", "Download abgeschlossen.")
        except requests.RequestException as e:
            QMessageBox.warning(self, "Download-Fehler", f"Fehler beim Herunterladen: {e}")

        self.setWindowTitle("Video abspielen mit VLC")

    def update_frame(self):
        if not self.is_seeking:
            current_time = self.media_player.get_time()  # in ms
            total_length = self.media_player.get_length()
            if total_length > 0:
                self.position_slider.setRange(0, total_length)
                self.position_slider.setValue(current_time)

    def closeEvent(self, event):
        self.timer.stop()
        self.media_player.stop()
        super().closeEvent(event)

class CustomWebEngineView(QWebEngineView):
    def __init__(self, browser):
        super().__init__()
        self.browser = browser

    def createWindow(self, requested_window_type):
        reply = QMessageBox.question(
            self.browser,
            "Pop-up anfordern",
            "Eine Webseite möchte ein Pop-up öffnen. Möchten Sie es erlauben?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            popup_browser = CustomWebEngineView(self.browser)
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
                QMessageBox.warning(self, "Warnung", "Benutzername und Passwort dürfen nicht leer sein.")

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
            item_text = domain
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

        # Navigation beim Doppelklick
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

        # Buttons: Bearbeiten, Löschen
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
        old_url   = lines[1]
        
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
        fav_url   = lines[1]
        
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

class WhoisDialog(QDialog):
    def __init__(self, domain_info, ip_info, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WHOIS Informationen")
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        
        # Scrollbereich für WHOIS-Daten
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll_layout = QVBoxLayout(content)
        
        # WHOIS Informationen
        whois_label = QLabel("WHOIS Daten:")
        whois_text = QTextEdit()
        whois_text.setReadOnly(True)
        whois_text.setText(domain_info)
        
        # IP Informationen
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
        
        # Schließen-Button
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)

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

        # Navigation beim Doppelklick
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

class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TMP-Networks Browser (PyQt6)")
        self.setGeometry(100, 100, 1200, 800)
        self.load_data()

        if "history" not in self.data:
            self.data["history"] = []

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
        
        # Menüpunkt "Favoriten verwalten"
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

        # Navigation Bar
        navigation_bar = QToolBar("Navigation")
        navigation_bar.setIconSize(QSize(24, 24))
        self.addToolBar(navigation_bar)

        # Emoji-Schriftart (vereinfachter Fallback)
        emoji_font = get_emoji_font()

        # Buttons
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

        # URL-Leiste
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        navigation_bar.addWidget(self.url_bar)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        navigation_bar.addWidget(spacer)

        scan_button = QAction("🕵️‍♂️", self)
        scan_button.setToolTip("Eingabefelder scannen")
        scan_button.setFont(emoji_font)
        scan_button.triggered.connect(self.scan_for_login_fields)
        navigation_bar.addAction(scan_button)

        video_scan_button = QAction("🎥", self)
        video_scan_button.setToolTip("Videos scannen und abspielen (höchste Auflösung)")
        video_scan_button.setFont(emoji_font)
        video_scan_button.triggered.connect(self.scan_and_play_videos)
        navigation_bar.addAction(video_scan_button)
        
        # Hinzufügen des WHOIS-Buttons
        whois_button = QAction("ℹ️", self)  # Sie können ein passendes Icon wählen
        whois_button.setToolTip("WHOIS Informationen anzeigen")
        whois_button.setFont(emoji_font)
        whois_button.triggered.connect(self.show_whois_info)
        navigation_bar.addAction(whois_button)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        # Start-Tab
        self.add_new_tab(QUrl('https://www.google.com'), 'Startseite')

    # --------------------------------------------------
    #  HLS PARSING: Um .m3u8 zu analysieren und höchste Auflösung zu wählen
    # --------------------------------------------------
    def parse_m3u8_for_highest_variant(self, manifest_url):
        """
        Lädt das (Top-Level-)HLS-Manifest von manifest_url.
        Sucht #EXT-X-STREAM-INF-Einträge samt RESOLUTION=WxH
        und gibt die Sub-Playlist-URL mit der höchsten Auflösung zurück.
        
        Falls nichts gefunden wird, liefern wir einfach manifest_url zurück.
        """
        try:
            r = requests.get(manifest_url, timeout=5)
            r.raise_for_status()
        except requests.RequestException as e:
            print("Fehler beim Laden des Manifests:", e)
            return manifest_url

        lines = r.text.splitlines()
        best_url = None
        best_resolution = 0  # wir speichern z. B. w*h

        for i, line in enumerate(lines):
            if line.strip().startswith('#EXT-X-STREAM-INF:'):
                # Bsp: #EXT-X-STREAM-INF:BANDWIDTH=...,RESOLUTION=1280x720, ...
                match = re.search(r'RESOLUTION\s*=\s*(\d+)x(\d+)', line, re.IGNORECASE)
                if match:
                    w = int(match.group(1))
                    h = int(match.group(2))
                    resolution = w * h
                    # Nächste Zeile = URL (Sub-Manifest)
                    if i+1 < len(lines):
                        sub_url = lines[i+1].strip()
                        # Falls relativer Pfad => absolute URL bauen
                        if not sub_url.startswith('http'):
                            sub_url = urljoin(manifest_url, sub_url)

                        if resolution > best_resolution:
                            best_resolution = resolution
                            best_url = sub_url

        # Falls wir was gefunden haben, nimm den "besten" Sub-Manifest-Link
        if best_url:
            return best_url

        # Sonst nimm einfach das Original
        return manifest_url

    # --------------------------------------------------
    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                QMessageBox.warning(self, "Fehler", f"Die Datei {DATA_FILE} ist beschädigt.")
                self.data = {"favorites": [], "credentials": {}, "history": []}
        else:
            self.data = {"favorites": [], "credentials": {}, "history": []}

    def save_data(self):
        try:
            # Stellen Sie sicher, dass alle datetime-Objekte in Strings umgewandelt werden
            serializable_data = self.make_serializable(self.data)
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Beim Speichern der Daten ist ein Fehler aufgetreten:\n{e}")

    def make_serializable(self, obj):
        """
        Rekursive Funktion zur Umwandlung von datetime-Objekten in Strings.
        """
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
        if qurl is None or qurl == '':
            qurl = QUrl('https://www.google.com')
        browser = CustomWebEngineView(self)
        browser.setUrl(qurl)
        browser.page().profile().downloadRequested.connect(self.on_downloadRequested)
        browser.loadFinished.connect(lambda _, b=browser: self.check_credentials(b))
        browser.loadFinished.connect(lambda _, i=self.tabs.count(), b=browser:
                                     self.tabs.setTabText(i, b.page().title()))
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

    def on_downloadRequested(self, download):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Speichern unter", download.path(), options=options)
        if file_path:
            download.setPath(file_path)
            download.accept()
            download.finished.connect(lambda: self.download_finished(download))
            download.downloadProgress.connect(self.download_progress)

    def download_progress(self, received, total):
        if total > 0:
            progress = int(received / total * 100)
            self.status.showMessage(f"Download läuft: {progress}%")
        else:
            self.status.showMessage("Download läuft...")

    def download_finished(self, download):
        self.status.showMessage(f"Download abgeschlossen: {download.path()}")

    # -------------- Favoriten -------------- #
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
        # Ab Index 2 entfernen (0=Favorit hinzufügen, 1=Separator)
        while len(actions) > 2:
            self.fav_menu.removeAction(actions[-1])
            actions = self.fav_menu.actions()

        for fav in sorted(self.data["favorites"], key=lambda x: x["title"]):
            action = QAction(fav["title"], self)
            action.setData(fav["url"])
            action.triggered.connect(self.navigate_to_favorite)
            self.fav_menu.addAction(action)

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

    # -------------- Passwörter -------------- #
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

    # -------------- History -------------- #
    def view_history(self):
        history_list = self.data.get("history", [])
        dlg = HistoryDialog(self, history_list=history_list)
        dlg.exec()

    # -------------- Credential Checking -------------- #
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

    # -------------- Login-Felder-Scan -------------- #
    def scan_for_login_fields(self):
        js_code = """
        (function() {
            var inputs = document.getElementsByTagName('input');
            var username = '';
            var password = '';
            for(var i=0; i<inputs.length; i++){
                var t = inputs[i].type.toLowerCase();
                if((t === 'text' || t==='email') && !username) {
                    username = inputs[i].value;
                } else if(t === 'password' && !password) {
                    password = inputs[i].value;
                }
            }
            return {username: username, password: password};
        })();
        """
        page = self.tabs.currentWidget().page()
        page.runJavaScript(js_code, self.handle_scan_result)

    def handle_scan_result(self, result):
        username = result.get("username", "")
        password = result.get("password", "")
        if username or password:
            reply = QMessageBox.question(
                self,
                "Zugangsdaten gefunden",
                "Es wurden Eingabefelder gefunden. Möchten Sie diese Zugangsdaten speichern?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                current_url = self.tabs.currentWidget().url().toString()
                domain = QUrl(current_url).host()
                if username and password:
                    self.data["credentials"][domain] = {"username": username, "password": password}
                    self.save_data()
                    QMessageBox.information(self, "Erfolg", f"Zugangsdaten für {domain} gespeichert.")
                else:
                    QMessageBox.warning(
                        self,
                        "Warnung",
                        "Es wurden nicht beide Felder (Benutzername und Passwort) gefunden oder sind leer."
                    )
        else:
            QMessageBox.information(self, "Info", "Keine geeigneten Eingabefelder gefunden.")

    # -------------- Video-Scan (mit bester Qualität, inkl. HLS) -------------- #
    def scan_and_play_videos(self):
        """
        1) Scannt die aktuelle Seite nach <video>-Elementen.
        2) Für jedes <source> werten wir das 'label' oder die URL aus
           - Bei .m3u8 parsen wir das Manifest, um die höchste Auflösung zu finden.
           - Bei .mp4 oder Ähnlichem suchen wir per Regex nach "(\d+)p" etc.
        3) Wählen pro <video> die (vermeintlich) beste URL aus.
        4) Bieten dem Nutzer an, das Video in VLC zu starten.
        """
        js_code = r"""
        (function() {
            var videos = document.getElementsByTagName('video');
            var chosenSources = [];
            
            for (var i = 0; i < videos.length; i++) {
                var bestSrc = null;
                var bestQuality = 0;
                
                var sourceTags = videos[i].getElementsByTagName('source');
                for (var j = 0; j < sourceTags.length; j++) {
                    var src = sourceTags[j].src;
                    
                    // label- oder data-res-Attribute
                    var labelAttr = sourceTags[j].getAttribute('label') ||
                                    sourceTags[j].getAttribute('data-res') || "";
                    
                    var foundQuality = 0;
                    // Versuche, z.B. "1080p" im label zu finden
                    var matchLabel = labelAttr.match(/(\d+)p/);
                    if (matchLabel) {
                        foundQuality = parseInt(matchLabel[1], 10);
                    } else {
                        // Versuch in der URL
                        var matchURL = src.match(/(\d+)p/);
                        if (matchURL) {
                            foundQuality = parseInt(matchURL[1], 10);
                        }
                    }
                    
                    if (foundQuality > bestQuality) {
                        bestQuality = foundQuality;
                        bestSrc = src;
                    }
                }
                
                if (bestSrc) {
                    chosenSources.push(bestSrc);
                } else {
                    // Fallback: currentSrc oder videos[i].src
                    var fallback = videos[i].currentSrc || videos[i].src;
                    if (fallback) {
                        chosenSources.push(fallback);
                    }
                }
            }
            
            return chosenSources;
        })();
        """
        page = self.tabs.currentWidget().page()
        page.runJavaScript(js_code, self.handle_video_scan_result)

    def handle_video_scan_result(self, video_sources):
        if not video_sources:
            QMessageBox.information(self, "Info", "Keine Videoelemente auf dieser Seite gefunden.")
            return

        # NEUER SCHRITT: .m3u8 parsen
        final_urls = []
        for vs in video_sources:
            if vs.endswith('.m3u8'):
                # Manifest parsen, um Highest Variant zu finden
                best_variant = self.parse_m3u8_for_highest_variant(vs)
                final_urls.append(best_variant)
            else:
                final_urls.append(vs)

        if len(final_urls) == 1:
            video_url = final_urls[0]
            self.play_video_in_vlc(video_url)
        else:
            dlg = QDialog(self)
            dlg.setWindowTitle("Videos auswählen (höchste Auflösung)")
            dlg.resize(400, 300)
            layout = QVBoxLayout()

            list_widget = QListWidget()
            for src in final_urls:
                item = QListWidgetItem(src)
                list_widget.addItem(item)
            layout.addWidget(list_widget)

            btn_layout = QHBoxLayout()
            play_btn = QPushButton("Abspielen")
            cancel_btn = QPushButton("Abbrechen")
            btn_layout.addWidget(play_btn)
            btn_layout.addWidget(cancel_btn)
            layout.addLayout(btn_layout)

            dlg.setLayout(layout)

            play_btn.clicked.connect(lambda: self.play_selected_video(list_widget, dlg))
            cancel_btn.clicked.connect(dlg.reject)

            dlg.exec()

    def play_selected_video(self, list_widget, dialog):
        selected_item = list_widget.currentItem()
        if selected_item:
            video_url = selected_item.text()
            self.play_video_in_vlc(video_url)
            dialog.accept()
        else:
            QMessageBox.warning(self, "Warnung", "Bitte wählen Sie ein Video aus.")

    def play_video_in_vlc(self, video_url):
        dlg = VLCPlayerDialog(video_url, self)
        dlg.exec()

    # -------------- WHOIS Funktion -------------- #
    def show_whois_info(self):
        current_url = self.tabs.currentWidget().url().toString()
        domain = QUrl(current_url).host()
        
        if not domain:
            QMessageBox.warning(self, "Warnung", "Keine gültige Domain gefunden.")
            return
        
        try:
            # Ermitteln der IP-Adresse
            ip_address = socket.gethostbyname(domain)
        except socket.gaierror:
            QMessageBox.warning(self, "Warnung", f"IP-Adresse für {domain} konnte nicht ermittelt werden.")
            ip_address = "Nicht verfügbar"
        
        try:
            # WHOIS-Abfrage
            w = whois.whois(domain)
            if hasattr(w, 'text') and w.text:
                whois_info = w.text
            else:
                # Manuelle Formatierung der WHOIS-Daten
                whois_info = ""
                for key, value in w.items():
                    if isinstance(value, list):
                        value = ', '.join([self.convert_datetime(v) for v in value])
                    else:
                        value = self.convert_datetime(value)
                    whois_info += f"{key}: {value}\n"
        except Exception as e:
            QMessageBox.warning(self, "Warnung", f"WHOIS-Abfrage fehlgeschlagen: {e}")
            whois_info = "Keine WHOIS-Informationen verfügbar."
        
        # IP-Informationen (hier nur die IP-Adresse)
        ip_info = f"IP-Adresse: {ip_address}"
        
        # Anzeige im Dialog
        dlg = WhoisDialog(whois_info, ip_info, self)
        dlg.exec()

    def convert_datetime(self, value):
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        return str(value)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Browser()
    window.show()
    sys.exit(app.exec())
