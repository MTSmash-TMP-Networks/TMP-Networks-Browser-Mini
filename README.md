# TMP-Networks-Browser-Mini

## Überblick

**TMP-Networks-Browser-Mini-** ist ein leichter Webbrowser, entwickelt mit Python und PyQt5. Der Browser bietet grundlegende Funktionen wie Tab-Unterstützung, Favoritenverwaltung und ein sicheres Passwortmanagement. Mit der Integration von GitHub Actions wird automatisch eine ausführbare `.exe`-Datei erstellt, die einfach verteilt werden kann.

## Features

- **Tab-Unterstützung**: Öffnen und Verwalten mehrerer Tabs gleichzeitig.
- **Favoritenverwaltung**: Webseiten als Favoriten speichern und einfach darauf zugreifen.
- **Passwortmanagement**:
  - **Speichern**: Benutzername und Passwort pro Domain speichern.
  - **Automatisches Ausfüllen**: Gespeicherte Zugangsdaten automatisch in Login-Felder einfügen.
  - **Bearbeiten und Löschen**: Gespeicherte Zugangsdaten verwalten.
- **Manuelles Scannen von Eingabefeldern**: Benutzer können manuell nach Login-Feldern suchen und Zugangsdaten speichern.
- **Download-Management**: Downloads direkt im Browser verwalten.
- **Pop-up-Verwaltung**: Steuerung von Pop-up-Fenstern durch den Benutzer.

## Installation

### Voraussetzungen

- **Python 3.6+**
- **pip** (Python Package Installer)

### Schritte

1. **Repository klonen**

   ```bash
   git clone https://github.com/MTSmash-TMP-Networks/TMP-Networks-Browser-Mini-.git
   cd TMP-Networks-Browser-Mini-
   ```

2. **Virtuelle Umgebung erstellen (optional, aber empfohlen)**

   ```bash
   python -m venv venv
   # Aktivieren der virtuellen Umgebung
   # Auf Windows:
   venv\Scripts\activate
   # Auf macOS/Linux:
   source venv/bin/activate
   ```

3. **Abhängigkeiten installieren**

   ```bash
   pip install -r requirements.txt
   ```

4. **Browser starten**

   ```bash
   python TMP-Networks-Browser-Mini.py
   ```

## Nutzung

### Favoriten Hinzufügen

1. Besuchen Sie die gewünschte Webseite.
2. Klicken Sie im Menü auf **"Favorit hinzufügen"**.
3. Der Favorit wird gespeichert und kann über das **"Favoriten"**-Menü aufgerufen werden.

### Passwörter Speichern

1. Besuchen Sie eine Login-Seite.
2. Geben Sie Ihren Benutzernamen und Ihr Passwort ein.
3. Klicken Sie auf den **"Eingabefelder scannen"**-Button in der Toolbar.
4. Wenn die Eingabefelder erkannt werden, werden Sie gefragt, ob Sie die Zugangsdaten speichern möchten.

### Passwörter Verwalten

1. Öffnen Sie das **"Passwörter"**-Menü.
2. Wählen Sie **"Passwörter verwalten"**.
3. In dem sich öffnenden Dialog können Sie gespeicherte Zugangsdaten bearbeiten oder löschen.

### Automatisches Ausfüllen

Beim erneuten Besuch einer Webseite, für die Zugangsdaten gespeichert sind, werden Sie gefragt, ob diese automatisch eingefügt werden sollen.

### Downloads Verwalten

Beim Starten eines Downloads wird dieser direkt im Browser verwaltet. Fortschritte und Abschlussstatus werden in der Statusleiste angezeigt.

## Erstellung einer ausführbaren `.exe`-Datei

Das Projekt verwendet **GitHub Actions**, um automatisch eine ausführbare `.exe`-Datei zu erstellen, die Sie direkt von GitHub herunterladen können.

### GitHub Actions Workflow

Der Workflow befindet sich in `.github/workflows/build.yml` und wird bei jedem Push zum `main`-Branch ausgelöst. Er verwendet `PyInstaller`, um die `.exe` zu erstellen und als Artifact hochzuladen.

### Schritte zum Herunterladen der `.exe`

1. Navigieren Sie zu Ihrem Repository auf GitHub: [TMP-Networks-Browser-Mini-](https://github.com/MTSmash-TMP-Networks/TMP-Networks-Browser-Mini-/)
2. Klicken Sie auf den Reiter **"Actions"**.
3. Wählen Sie den neuesten **Build-Job** aus.
4. Nach erfolgreichem Abschluss finden Sie die erstellte `.exe` unter den **Artifacts**.
5. Laden Sie die `.exe` herunter und führen Sie sie aus.

## Beitrag leisten

Beiträge sind willkommen! Folgen Sie diesen Schritten, um zum Projekt beizutragen:

1. Forken Sie das Repository.
2. Erstellen Sie einen neuen Branch für Ihre Änderungen:

   ```bash
   git checkout -b feature/NeuesFeature
   ```

3. Nehmen Sie Ihre Änderungen vor und committen Sie sie:

   ```bash
   git commit -m "Add neues Feature"
   ```

4. Pushen Sie den Branch zu Ihrem Fork:

   ```bash
   git push origin feature/NeuesFeature
   ```

5. Öffnen Sie einen Pull Request in diesem Repository.

## Lizenz

Dieses Projekt ist lizenziert unter der [MIT License](LICENSE).

## Sicherheitshinweis

**Wichtig:** Die gespeicherten Passwörter werden gespeichert, jedoch sollten Sie sicherstellen, dass die Passwort-Datei sicher aufbewahrt wird und nicht in das Repository aufgenommen wird. Fügen Sie die Passwort-Datei zur `.gitignore`-Datei hinzu, um eine versehentliche Veröffentlichung zu verhindern.

## Kontakt

Bei Fragen oder Vorschlägen kontaktieren Sie mich gerne unter [marek.templin@tmp-system-service.de](mailto:marek.templin@tmp-system-service.de).
