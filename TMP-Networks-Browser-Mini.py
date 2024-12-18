import json
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QLineEdit, QWidget,
    QTabWidget, QToolBar, QAction, QStatusBar, QFileDialog, QMessageBox,
    QDialog, QPushButton, QLabel, QMenu, QListWidget, QListWidgetItem, QHBoxLayout
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QSize, QObject, pyqtSlot, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWebChannel import QWebChannel


DATA_FILE = "favoriten_und_passwoerter.json"


class WebChannelInterface(QObject):
    def __init__(self, browser):
        super().__init__()
        self.browser = browser

    @pyqtSlot(str, str)
    def submit_form(self, username, password):
        self.browser.handle_form_submission(username, password)


class CustomWebEngineView(QWebEngineView):
    def __init__(self, browser):
        super().__init__()
        self.browser = browser

    def createWindow(self, requested_window_type):
        reply = QMessageBox.question(
            self.browser,
            "Pop-up anfordern",
            "Eine Webseite möchte ein Pop-up öffnen. Möchten Sie es erlauben?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
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
        self.password_edit.setEchoMode(QLineEdit.Password)
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
        self.selected_domain = None

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
        if dlg.exec_() == QDialog.Accepted:
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
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self.credentials[domain]
            self.list_widget.takeItem(self.list_widget.row(selected_item))
            QMessageBox.information(self, "Erfolg", f"Zugangsdaten für {domain} gelöscht.")


class Browser(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TMP-Networks Browser")
        self.setGeometry(100, 100, 1200, 800)

        self.load_data()

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

        navigation_bar = QToolBar("Navigation")
        navigation_bar.setIconSize(QSize(16, 16))
        self.addToolBar(navigation_bar)

        back_button = QAction(QIcon('icons/back.png'), "Zurück", self)
        back_button.triggered.connect(lambda: self.tabs.currentWidget().back())
        navigation_bar.addAction(back_button)

        forward_button = QAction(QIcon('icons/forward.png'), "Vorwärts", self)
        forward_button.triggered.connect(lambda: self.tabs.currentWidget().forward())
        navigation_bar.addAction(forward_button)

        reload_button = QAction(QIcon('icons/reload.png'), "Neu laden", self)
        reload_button.triggered.connect(lambda: self.tabs.currentWidget().reload())
        navigation_bar.addAction(reload_button)

        home_button = QAction(QIcon('icons/home.png'), "Startseite", self)
        home_button.triggered.connect(self.navigate_home)
        navigation_bar.addAction(home_button)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        navigation_bar.addWidget(self.url_bar)

        new_tab_button = QAction(QIcon('icons/new_tab.png'), "Neuer Tab", self)
        new_tab_button.triggered.connect(lambda: self.add_new_tab())
        navigation_bar.addAction(new_tab_button)

        # Button: Eingabefelder scannen
        scan_button = QAction(QIcon('icons/search.png'), "Eingabefelder scannen", self)
        scan_button.triggered.connect(self.scan_for_login_fields)
        navigation_bar.addAction(scan_button)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.add_new_tab(QUrl('https://www.google.com'), 'Startseite')

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                QMessageBox.warning(self, "Fehler", f"Die Datei {DATA_FILE} ist beschädigt.")
                self.data = {"favorites": [], "credentials": {}}
        else:
            self.data = {"favorites": [], "credentials": {}}

    def save_data(self):
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Beim Speichern der Daten ist ein Fehler aufgetreten:\n{e}")

    def add_new_tab(self, qurl=None, label="Neue Seite"):
        if qurl is None or qurl == '':
            qurl = QUrl('https://www.google.com')

        browser = CustomWebEngineView(self)
        browser.setUrl(qurl)

        browser.page().profile().downloadRequested.connect(self.on_downloadRequested)

        # Beim Laden der Seite prüfen wir später, ob Credentials vorhanden sind.
        browser.loadFinished.connect(lambda _, b=browser: self.check_credentials(b))
        browser.loadFinished.connect(lambda _, i=self.tabs.count(), browser=browser: self.tabs.setTabText(i, browser.page().title()))
        browser.urlChanged.connect(lambda qurl, browser=browser: self.update_url_bar(qurl, browser))

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

    def navigate_to_url(self):
        q = QUrl(self.url_bar.text())
        if q.scheme() == "":
            q.setScheme("http")
        self.tabs.currentWidget().setUrl(q)

    def navigate_home(self):
        self.tabs.currentWidget().setUrl(QUrl("https://www.google.com"))

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

    # Favoriten-Methoden
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
        for action in actions[2:]:
            self.fav_menu.removeAction(action)

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

    # Passwort-Methoden
    def save_credentials_for_current_page(self):
        current_url = self.tabs.currentWidget().url().toString()
        domain = QUrl(current_url).host()
        dlg = LoginDialog(self)
        if dlg.exec_() == QDialog.Accepted:
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
            creds_text += f"Domain: {domain}\nBenutzername: {creds['username']}\nPasswort: {creds['password']}\n\n"

        creds_dialog = QDialog(self)
        creds_dialog.setWindowTitle("Gespeicherte Zugangsdaten")
        creds_dialog.resize(400, 300)
        layout = QVBoxLayout()
        creds_label = QLabel(creds_text)
        creds_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(creds_label)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(creds_dialog.accept)
        layout.addWidget(close_btn)
        creds_dialog.setLayout(layout)
        creds_dialog.exec_()

    def manage_credentials(self):
        if not self.data["credentials"]:
            QMessageBox.information(self, "Info", "Keine gespeicherten Zugangsdaten vorhanden.")
            return
        dlg = CredentialsManagerDialog(self, credentials_dict=self.data["credentials"])
        if dlg.exec_() == QDialog.Accepted:
            # Änderungen übernehmen
            self.data["credentials"] = dlg.credentials
            self.save_data()

    def get_credentials_for_url(self, url):
        domain = QUrl(url).host()
        return self.data["credentials"].get(domain, None)

    def check_credentials(self, browser):
        # Beim Laden der Seite prüfen, ob Credentials vorhanden sind
        url = browser.url().toString()
        credentials = self.get_credentials_for_url(url)
        if not credentials:
            return

        # Erst prüfen, ob Passwortfelder vorhanden sind
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

        browser.page().runJavaScript(js_code, lambda result: self.handle_check_password_field(result, credentials, browser))

    def handle_check_password_field(self, has_password_field, credentials, browser):
        if not has_password_field:
            # Keine Passwortfelder vorhanden, also nicht nach Einfügen fragen
            return

        # Passwortfelder vorhanden, jetzt nachfragen
        reply = QMessageBox.question(
            self,
            "Zugangsdaten verfügbar",
            "Zugangsdaten für diese Domain sind gespeichert. Möchten Sie diese einfügen?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
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

    def scan_for_login_fields(self):
        # Diese Funktion liest die aktuellen Eingabefelder aus
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
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                current_url = self.tabs.currentWidget().url().toString()
                domain = QUrl(current_url).host()
                if username and password:
                    self.data["credentials"][domain] = {"username": username, "password": password}
                    self.save_data()
                    QMessageBox.information(self, "Erfolg", f"Zugangsdaten für {domain} gespeichert.")
                else:
                    QMessageBox.warning(self, "Warnung", "Es wurden nicht beide Felder (Benutzername und Passwort) gefunden oder sind leer.")
        else:
            QMessageBox.information(self, "Info", "Keine geeigneten Eingabefelder gefunden.")


if __name__ == "__main__":
    app = QApplication([])
    window = Browser()
    window.show()
    app.exec_()
