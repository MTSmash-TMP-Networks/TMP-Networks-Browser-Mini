# Plugin-Entwicklung für TMP-Networks-Browser-Mini

## Allgemeine Informationen

- Plugins sind **einfache Python-Dateien** (`.py`), die beim Starten des Browsers mit Hilfe von `importlib` geladen werden.  
- Jedes Plugin hat **vollen Zugriff** auf das Python-Umfeld deiner Anwendung, kann also theoretisch beliebigen Code ausführen.  
- Damit du beim Laden und Entladen bestimmte Aktionen durchführen kannst, **empfiehlt** es sich, in deinem Plugin zwei spezielle Funktionen zu definieren:
  1. `initialize_plugin(browser)`: Wird aufgerufen, **sobald** das Plugin geladen wird.  
  2. *(optional)* `finalize_plugin(browser)`: Wird aufgerufen, wenn das Plugin entladen wird (aktuell erfolgt das in unserem Code nur bei einem kompletten Neustart oder wenn du es in deinem `unload_all_plugins`-Prozess explizit aufrufst).

## Voraussetzungen

1. Das Plugin muss eine **gültige Python-Datei** sein.  
2. Die Datei muss im Browser über das „Plugins verwalten“-Menü hinzugefügt werden (oder im JSON manuell eingetragen werden).  
3. Alle **externen Bibliotheken**, die das Plugin benötigt, sollten installiert sein (z.B. via `pip`), da der Browser sie sonst nicht finden kann.  

## Beispielaufbau eines Plugins

```python
"""
Plugin-Beispiel: MyExamplePlugin.py
Dieses Plugin zeigt zur Demonstration eine einfache Begrüßung an,
sobald es geladen wird. Außerdem legt es eine neue Menü-Aktion an.
"""

from PyQt6.QtWidgets import QAction, QMessageBox

def initialize_plugin(browser):
    """
    Diese Funktion wird vom Browser nach dem Import des Moduls aufgerufen.
    Parameter:
      browser: Das Browser-Hauptobjekt (QMainWindow), auf das du zugreifen kannst.
    """

    # Beispiel: Ein Menü-Eintrag hinzufügen:
    example_action = QAction("Beispiel-Plugin Info", browser)
    example_action.triggered.connect(lambda: QMessageBox.information(
        browser,
        "Info vom Plugin",
        "Hallo! Ich bin das Beispiel-Plugin."
    ))
    
    # Du kannst den Action zum Beispiel in ein bestehendes Menü einhängen:
    # Hier wird er im 'Plugins'-Menü ergänzt (falls es existiert):
    if hasattr(browser, "plugin_menu"):
        browser.plugin_menu.addAction(example_action)
    
    # Oder du erstellst eine eigene Toolbar etc.
    # Merke dir die Action in 'browser' oder global, damit du sie ggf. später entfernen kannst.
    # Beispiel: 
    browser.my_example_action = example_action
    
    print("MyExamplePlugin: initialize_plugin wurde aufgerufen.")

def finalize_plugin(browser):
    """
    Diese Funktion wird (falls implementiert) beim Entladen des Plugins aufgerufen.
    Momentan nur dann, wenn du 'unload_all_plugins' aufrufst oder einen harten Neustart machst
    und vorher manuell finalize_plugin ausführen lässt.
    """
    # Beispiel: Menüeintrag entfernen, Timer stoppen, Signale abklemmen etc.
    if hasattr(browser, "my_example_action"):
        if browser.my_example_action in browser.plugin_menu.actions():
            browser.plugin_menu.removeAction(browser.my_example_action)
        del browser.my_example_action
    
    print("MyExamplePlugin: finalize_plugin wurde aufgerufen.")
```

## Was kann ein Plugin machen?

- **GUI-Erweiterungen**:  
  - Neue Menüs, Buttons, Aktionen hinzufügen, z.B. in `browser.menuBar()`, in vorhandenen Menüs oder Toolbars.  
  - Eigene Dialoge oder Widgets erstellen und anzeigen.  
- **Daten verarbeiten**:  
  - Über den `browser`-Parameter hast du Zugriff auf sämtliche Methoden/Attribute, z.B. `browser.tabs`, `browser.load_data()`, `browser.save_data()`, usw.  
  - Eigene Datenstrukturen anlegen, in JSON speichern, etc.
- **Signal-Handling**:  
  - Du kannst an beliebige Qt-Signale andocken (z.B. `browser.tabs.currentChanged.connect(...)`), um auf Ereignisse im Browser zu reagieren.
- **Netzwerkzugriffe**:  
  - Python-Module wie `requests` oder `socket` verwenden, um Daten abzurufen, eigene Checks vorzunehmen usw.

## Typische Anwendungsfälle

1. **Spezielle Aktionen**: Ein Plugin könnte beispielsweise beim Laden einer Webseite bestimmte Inhalte scannen und eine Warnung ausgeben.  
2. **Automation**: Du könntest automatisch Bookmarks setzen, deine eigenen Scripte integrieren oder den Browser auf bestimmte Seiten lenken.  
3. **Sicherheitsprüfungen**: Plugins könnten etwa eigene WHOIS-Abfragen machen (zusätzlich zu denen im Browser), Logs anlegen oder Traffic mitprotokollieren.

## Tipps & Tricks

- Achte darauf, dass das Plugin beim **Beenden** (oder Neustart) des Browsers keine offenen Threads, Timer oder Netzwerkverbindungen mehr zurücklässt. Implementiere dazu ggf. eine **`finalize_plugin(browser)`**-Methode, in der du alles aufräumst.  
- Soll das Plugin **nur** bei Bedarf aktiv werden (z.B. bei Klick auf eine Menüaktion), so kannst du sämtliche Logik in `initialize_plugin` vorbereiten, aber erst auf **User-Interaktion** reagieren.  
- Die in `initialize_plugin` erstellten GUI-Elemente solltest du am besten **referenzieren** (z.B. in `browser.my_example_action = ...`), damit du sie in `finalize_plugin` auch wieder löschen kannst.  
- Fehler und Ausgaben kannst du einfach mit `print` in der Konsole anzeigen oder über `QMessageBox.warning(...)` im Browser.

---

## Weiterführendes

- Python-Dokumentation zu [importlib](https://docs.python.org/3/library/importlib.html) und [ModuleSpec](https://docs.python.org/3/library/importlib.html#importlib.machinery.ModuleSpec).  
- PyQt6-Dokumentation für [QAction](https://doc.qt.io/qtforpython/PySide6/QtWidgets/QAction.html), [QMessageBox](https://doc.qt.io/qtforpython/PySide6/QtWidgets/QMessageBox.html) und andere GUI-Klassen.  
- Eventuell eigenes Logging oder Exception-Handling einbauen, damit Plugin-Fehler im Browser gut erkennbar bleiben.
