# Plugin-System für TMP-Networks-Browser-Mini

Das **Plugin-System** ermöglicht es, den Funktionsumfang des TMP-Networks-Browser-Mini durch eigene Python-Dateien zu erweitern. Plugins können zum Beispiel neue Menüs, Toolbar-Buttons oder Hintergrundprozesse hinzufügen und mit allen Funktionen des Browsers interagieren.

## Inhalt

1. [Grundprinzip](#grundprinzip)  
2. [Plugin-Struktur](#plugin-struktur)  
3. [Beispiel-Plugin](#beispiel-plugin)  
4. [Mögliche Szenarien](#mögliche-szenarien)  
5. [Tipps & Tricks](#tipps--tricks)  
6. [FAQ](#faq)

---

## Grundprinzip

- Du erstellst eine **Python-Datei** (Endung `.py`) – z.B. `my_plugin.py`.  
- Diese wird über den Dialog **"Plugins verwalten"** in den Browser geladen (Hinzufügen).  
- Bei jeder **Änderung** (Hinzufügen oder Entfernen) wird der Browser **neu gestartet**, damit nur die tatsächlich eingetragenen Plugins im Speicher liegen.  
- Beim Laden führt der Browser dein Plugin aus und ruft – falls definiert – die Funktion `initialize_plugin(browser)` auf. Darin hast du Zugriff auf das Browser-Hauptfenster (`browser`) und kannst beliebige PyQt-Funktionen nutzen.  
- Optional kannst du in deinem Plugin eine Funktion `finalize_plugin(browser)` bereitstellen, um z.B. Timer oder GUI-Elemente gezielt aufzuräumen, wenn der Browser das Plugin entlädt (aktuell geschieht das nur beim „Alles entladen“ oder falls du es manuell aufrufst).

---

## Plugin-Struktur

Ein Plugin ist eine einfache **Python-Datei** mit folgenden Empfehlungen:

1. **Docstring**: Kurze Beschreibung, was das Plugin tut.  
2. **Import**-Statements: Alles, was dein Plugin braucht (z.B. `from PyQt6.QtWidgets import QAction, QMessageBox`).  
3. (Optional) **Globale Variablen** oder Hilfsfunktionen.  
4. **`initialize_plugin(browser)`** (empfohlen):  
   - Wird vom Browser beim Laden des Plugins aufgerufen.  
   - `browser` ist das QMainWindow-Objekt deines Browsers, so hast du Zugriff auf Menüs, Toolbars, Tabs usw.  
5. (Optional) **`finalize_plugin(browser)`**:  
   - Wird aufgerufen, bevor das Plugin entladen wird (sofern der Code das explizit unterstützt).  
   - Entferne hier Timer, Signale und GUI-Elemente, die dein Plugin hinzugefügt hat.

---

## Beispiel-Plugin

```python
"""
MyExamplePlugin.py
Dieses Plugin zeigt eine einfache Info-Message an und fügt dem 'Plugins'-Menü
einen zusätzlichen Menüeintrag hinzu.
"""

from PyQt6.QtWidgets import QAction, QMessageBox

def initialize_plugin(browser):
    """
    Wird automatisch aufgerufen, wenn das Plugin geladen wird.
    browser: Referenz auf das Hauptfenster (QMainWindow).
    """

    # Beispiel: Eine neue Aktion hinzufügen
    action = QAction("Hallo vom Example-Plugin", browser)
    action.triggered.connect(lambda: QMessageBox.information(
        browser,
        "Info vom Plugin",
        "Hallo! Ich bin das MyExamplePlugin."
    ))
    
    # Füge die Aktion ins 'Plugins'-Menü ein (falls existiert)
    if hasattr(browser, "plugin_menu"):
        browser.plugin_menu.addAction(action)
    
    # Optional merken wir uns die Action am Browser, um sie später entfernen zu können
    browser.my_example_plugin_action = action
    
    print("[MyExamplePlugin] initialize_plugin() wurde ausgeführt.")

def finalize_plugin(browser):
    """
    Wird aufgerufen, wenn das Plugin entladen wird (z.B. bei manuellem Unload).
    """
    # Entferne die Aktion aus dem 'Plugins'-Menü, wenn vorhanden
    if hasattr(browser, "my_example_plugin_action"):
        action = browser.my_example_plugin_action
        if action in browser.plugin_menu.actions():
            browser.plugin_menu.removeAction(action)
        del browser.my_example_plugin_action
    
    print("[MyExamplePlugin] finalize_plugin() wurde ausgeführt.")
```

---

## Mögliche Szenarien

- **GUI-Erweiterungen**: Füge eigene Menüeinträge, Toolbar-Buttons oder Kontextmenüs hinzu.  
- **Automatisierungen**: Starte im Hintergrund Timer, die regelmäßig etwas prüfen (z.B. neue Nachrichten).  
- **Datenverarbeitung**: Greife auf Browser-Daten wie `browser.data`, `browser.all_downloads_info` oder die History zu.  
- **Sicherheitstools**: Prüfe Webseiten, protokolliere bestimmte Events oder manipulieren den DOM via JS (über `browser.tabs.currentWidget().page().runJavaScript(...)`).  

---

## Tipps & Tricks

- **Speichere Referenzen**, wenn du Objekte hinzufügst (z.B. Aktionen, Timer), damit du sie in `finalize_plugin` entfernen kannst.  
- Du kannst bei Bedarf in `initialize_plugin` auf **jedes** Attribut und jede Methode von `browser` zugreifen. Dort findest du:  
  - `browser.tabs` (QTabWidget)  
  - `browser.menuBar()` (QMenuBar)  
  - `browser.download_manager_dialog`, falls du Downloads manipulieren willst.  
- **Fehler melden**: Schreibe Fehlermeldungen per `print(...)` in die Konsole oder nutze `QMessageBox`, um sie sichtbar anzuzeigen.  
- Denk daran, dass **alle Python-Abhängigkeiten** deines Plugins (z.B. zusätzliche Bibliotheken) auf dem System installiert sein müssen, damit das Plugin funktioniert.

---

## FAQ

### 1. Wie installiere ich mein Plugin?  
- Gehe ins Menü **"Plugins" → "Plugins verwalten"**.  
- Klicke auf **"Hinzufügen"** und wähle deine `.py`-Datei.  
- Schließe den Dialog – der Browser wird automatisch **neu gestartet**, und dein Plugin ist geladen.

### 2. Wie entferne ich ein Plugin?  
- Ebenfalls in **"Plugins verwalten"**: Wähle das Plugin in der Liste aus und klicke auf **"Entfernen"**.  
- Nach Schließen des Dialogs wird der Browser **neu gestartet** und das Plugin ist weg.

### 3. Wird `finalize_plugin` beim Neustart aufgerufen?  
- Standardmäßig wird beim `unload_all_plugins()`-Prozess `finalize_plugin` für jedes Plugin aufgerufen, **bevor** der Browser neu startet.  
- Falls du nur via OS-Neustart arbeitest (also `os.execl`), kann es passieren, dass dein Code keinen expliziten `finalize_plugin`-Aufruf mehr bekommt. Plane daher bitte entsprechend.

### 4. Kann ich Plugins direkt bearbeiten, ohne den Browser neu zu starten?  
- Momentan nicht. Jede Änderung an der Plugin-Datei (oder an der Liste im Dialog) erfordert einen Browser-Neustart, damit der Code neu geladen wird.

---

Damit bist du startklar, um eigene Plugins zu entwickeln! Solltest du weitere Fragen haben, findest du Hilfe in den Quelltexten oder du nimmst Kontakt mit uns auf.  
