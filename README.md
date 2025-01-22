# TMP-Networks-Browser-Mini

<img width="1194" alt="grafik" src="https://github.com/user-attachments/assets/5eaf3395-4aed-4e52-8776-1b0fdf380e49" />

**TMP-Networks-Browser-Mini** ist ein leichter Webbrowser, entwickelt mit Python und PyQt6. Der Browser bietet grundlegende Funktionen wie Tab-Unterstützung, Favoritenverwaltung, Passwortmanagement und lässt sich über ein **Plugin-System** erweitern. Ein automatischer Build-Prozess via GitHub Actions kann aus dem Code eine `.exe`-Datei erstellen, die sich einfach verteilen lässt.

## Überblick / Features

- **Tab-Unterstützung**  
  Öffne und verwalte mehrere Tabs gleichzeitig.

- **Favoritenverwaltung**  
  - Webseiten als Favoriten speichern und über ein Menü schnell darauf zugreifen  
  - Favoriten bearbeiten oder löschen

- **Passwortmanagement**  
  - **Speichern** von Benutzername und Passwort pro Domain  
  - **Automatisches Einfügen** der Zugangsdaten bei erneutem Besuch  
  - **Bearbeiten und Löschen** gespeicherter Zugangsdaten

- **Pop-up-Verwaltung**  
  Der Browser erkennt Pop-up-Anfragen und fragt den Nutzer, ob sie erlaubt werden sollen.

- **Download-Management**  
  Lade Dateien bequem im Browser herunter und verwalte den Fortschritt im Download-Manager.

- **Video & Stream-Handling (YT-DLP)**  
  - Auf Knopfdruck („Videos scannen“) analysiert der Browser YouTube- oder ähnliche Video-Links  
  - Direkte Wiedergabe über VLC  
  - Downloads von Video-/Audio-Streams via [yt-dlp](https://github.com/yt-dlp/yt-dlp)

- **WHOIS-Abfrage**  
  - Per Klick lässt sich für die aktuelle Domain eine WHOIS- und IP-Information anzeigen

- **Plugin-System**  
  - Einfaches **Hinzufügen** eigener Python-Plugins (z.B. `my_plugin.py`)  
  - Plugins können neue Menüs oder Buttons hinzufügen, automatisch Code ausführen usw.  
  - Bei **Änderung** an der Plugin-Liste (Hinzufügen/Entfernen) wird der Browser automatisch **neu gestartet**, sodass nur die tatsächlich vorhandenen Plugins geladen werden.

## Installation

### Voraussetzungen

- **Python 3.6+**  
- **pip** (Python Package Installer)

### Schritte

1. **Repository klonen**:

   ```bash
   git clone https://github.com/MTSmash-TMP-Networks/TMP-Networks-Browser-Mini.git
   cd TMP-Networks-Browser-Mini
   ```

2. **Virtuelle Umgebung erstellen (optional, empfohlen)**:

   ```bash
   python -m venv venv
   # Aktivieren der virtuellen Umgebung
   # Auf Windows:
   venv\Scripts\activate
   # Auf macOS/Linux:
   source venv/bin/activate
   ```

3. **Abhängigkeiten installieren**:

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

   **Hinweis**: `requirements.txt` enthält z.B.:

   ```text
   PyQt6>=6.0.0
   PyQt6-WebEngine>=6.0.0
   requests
   vlc
   appdirs
   whois
   yt-dlp
   ```

4. **Browser starten**:

   ```bash
   python TMP-Networks-Browser-Mini.py
   ```

## Nutzung

### Favoriten hinzufügen

1. Besuche die gewünschte Webseite.  
2. Klicke im Menü auf **"Favorit hinzufügen"**.  
3. Der Favorit wird gespeichert und kann über das **"Favoriten"**-Menü aufgerufen oder verwaltet werden.

### Passwörter speichern und verwalten

1. Besuche eine Login-Seite.  
2. Klicke auf **"Zugangsdaten speichern"** (im Menü **Passwörter**).  
3. Gib Benutzername und Passwort ein.  
4. Bei erneutem Aufruf der Domain wird vorgeschlagen, die Loginfelder automatisch zu befüllen.  
5. Unter **"Passwörter verwalten"** können Einträge bearbeitet oder gelöscht werden.

### Downloads verwalten

- Beim Starten eines Downloads wirst du nach einem Speicherort gefragt.  
- Fortschritt und Status kannst du über **"Downloads" → "Download-Manager öffnen"** verfolgen.  
- Abbrechen, Löschen und Öffnen der heruntergeladenen Dateien sind möglich.

### Plugins hinzufügen oder entfernen

1. Öffne das Menü **"Plugins"** → **"Plugins verwalten"**.  
2. **Hinzufügen**: Wähle eine Python-Datei (`.py`) aus, die dein Plugin-Code enthält.  
3. **Entfernen**: Wähle einen Eintrag in der Liste aus und klicke auf **"Entfernen"**.  
4. Sobald du das Dialogfenster schließt und eine Änderung stattfand, wird der Browser **neu gestartet**.  

**Tipp**: Lies die [README_PLUGIN.md](https://github.com/MTSmash-TMP-Networks/TMP-Networks-Browser-Mini/blob/qt6/plugins/README.md) (oder ein entsprechendes Dokument), um zu erfahren, wie du eigene Plugins schreiben kannst.

### WHOIS und IP-Abfragen

- Über die **ℹ️-Schaltfläche** in der Toolbar kannst du eine WHOIS-Abfrage für die aktuelle Domain starten und IP-Infos anzeigen.

### Video-Scan (YouTube etc.)

- Mit dem **"🎥"-Button** scannt der Browser die aktuelle URL.  
- Wird ein YouTube-Link oder ein ähnlicher Stream erkannt, kannst du das Video in verschiedenen Auflösungen auswählen und direkt per VLC abspielen.

## Erstellung einer ausführbaren `.exe`-Datei

Das Projekt verwendet **GitHub Actions**, um automatisch eine ausführbare `.exe`-Datei zu erstellen, die Du direkt von GitHub herunterladen kannst.

### GitHub Actions Workflow

- Der Workflow liegt in `.github/workflows/build.yml` und wird bei jedem Push in den entsprechenden Branch ausgelöst.  
- Er verwendet **PyInstaller**, um die `.exe` zu erstellen und anschließend als Artifact hochzuladen.

### Schritte zum Herunterladen der `.exe`

1. Gehe zum Repository auf GitHub:  
   [TMP-Networks-Browser-Mini](https://github.com/MTSmash-TMP-Networks/TMP-Networks-Browser-Mini/)
2. Klicke auf den Reiter **"Actions"**.  
3. Wähle den neuesten **Build-Job** aus.  
4. Nach erfolgreichem Abschluss findest du die `.exe` unter **Artifacts**.  
5. Lade die `.exe` herunter und führe sie aus.

## Beitrag leisten

1. **Forke** das Repository.  
2. Erstelle einen neuen **Branch** für Deine Änderungen:

   ```bash
   git checkout -b feature/NeuesFeature
   ```

3. Nimm Deine Änderungen vor und **committe** sie:

   ```bash
   git commit -m "Add neues Feature"
   ```

4. **Pushe** den Branch zu Deinem Fork:

   ```bash
   git push origin feature/NeuesFeature
   ```

5. Erstelle einen **Pull Request** in diesem Repository.

## Lizenz

Dieses Projekt ist lizenziert unter der [MIT License](LICENSE).

## Kontakt

Bei Fragen oder Vorschlägen kontaktiere uns gerne unter  
[marek.templin@tmp-system-service.de](mailto:marek.templin@tmp-system-service.de).
