"""
YouTube Dubbing Studio — Entry Point
"""
import sys
import os

# Ensure the project root is on the path (one level up from system)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from PySide6.QtWidgets import QApplication, QSplashScreen
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QPixmap, QIcon

    from app.config import (
        APP_NAME,
        is_portable_setup_needed,
        migrate_legacy_runtime_data,
        save_portable_config,
        settings,
    )
    from app.i18n import get_layout_direction, set_language
    from app.gui.theme import get_main_stylesheet
    from app.gui.tooltip_utils import install_tooltip_style

    set_language(getattr(settings, "interface_language", "en"), emit=False)

    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    try:
        import ctypes
        myappid = 'youtubedubbingstudio.app.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.png")
    app.setWindowIcon(QIcon(icon_path))
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")  # Consistent cross-platform base
    install_tooltip_style(app, wake_up_delay_ms=1000)
    app.setLayoutDirection(get_layout_direction())

    # Apply dark theme
    app.setStyleSheet(get_main_stylesheet())

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    if is_portable_setup_needed():
        from app.config import DEFAULT_DATA_DIR, has_legacy_runtime_data
        
        save_portable_config(
            data_dir=str(DEFAULT_DATA_DIR),
            ffmpeg_path="",
            cookies_path="",
            apply_now=True,
        )
        if has_legacy_runtime_data(DEFAULT_DATA_DIR):
            migrate_legacy_runtime_data(str(DEFAULT_DATA_DIR))
        settings.load()
        set_language(getattr(settings, "interface_language", "en"), emit=False)
        app.setLayoutDirection(get_layout_direction())

    from app.gui.main_window import MainWindow

    splash_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "splash.png")
    splash_pixmap = QPixmap(splash_path)
    if not splash_pixmap.isNull():
        splash_pixmap = splash_pixmap.scaled(600, 600, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        splash = QSplashScreen(splash_pixmap, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint)
        splash.show()
        # Ensure it renders immediately
        app.processEvents()
    else:
        splash = None

    # Create and show main window
    window = MainWindow()
    
    if splash:
        splash.finish(window)
        
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    main()
