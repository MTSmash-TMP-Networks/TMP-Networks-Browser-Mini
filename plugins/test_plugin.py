# test_plugin.py

def initialize_plugin(browser):
    """
    Wird vom Browser aufgerufen, wenn das Plugin geladen wird.
    """
    from PyQt6.QtWidgets import QMessageBox, QToolBar
    from PyQt6.QtGui import QAction, QFont
    from PyQt6.QtCore import Qt

    # Navigation-Toolbar finden:
    navigation_bar = None
    for tb in browser.findChildren(QToolBar):
        if tb.windowTitle() == "Navigation":
            navigation_bar = tb
            break

    if navigation_bar is not None:
        # Hier einen emoji-fähigen Font definieren
        emoji_font = QFont("Noto Color Emoji", 16)

        new_action = QAction("🧪", browser)
        new_action.setToolTip("Test-Plugin")
        # Den Font explizit setzen
        new_action.setFont(emoji_font)

        # Bei Klick eine Meldung zeigen
        new_action.triggered.connect(
            lambda: QMessageBox.information(
                browser,
                "Test-Plugin",
                "Hallo! Dies ist ein Test-Plugin, das Emojis nutzt."
            )
        )
        navigation_bar.addAction(new_action)
