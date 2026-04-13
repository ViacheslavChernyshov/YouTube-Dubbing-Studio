"""
Premium dark theme for the application — QSS stylesheets.
"""

# ── Color palette ──────────────────────────────────────────────────────────
COLORS = {
    "bg_darkest": "#08080c",
    "bg_dark": "#0f0f13",
    "bg_card": "#16161e",
    "bg_card_hover": "#1c1c28",
    "bg_input": "#12121a",
    "border": "#2a2a3a",
    "border_focus": "#6366f1",
    "text_primary": "#e4e4ef",
    "text_secondary": "#8888a0",
    "text_muted": "#55556a",
    "accent": "#6366f1",
    "accent_light": "#8b5cf6",
    "accent_glow": "rgba(99, 102, 241, 0.3)",
    "success": "#22c55e",
    "success_bg": "rgba(34, 197, 94, 0.12)",
    "warning": "#f59e0b",
    "warning_bg": "rgba(245, 158, 11, 0.12)",
    "error": "#ef4444",
    "error_bg": "rgba(239, 68, 68, 0.12)",
    "pending": "#55556a",
    "running": "#6366f1",
}


FONT_FAMILY = "'Segoe UI', 'Inter', 'Roboto', sans-serif"


def get_main_stylesheet() -> str:
    """Return the complete application stylesheet."""
    return f"""
    /* ── Global ─────────────────────────────────────────── */
    QMainWindow {{
        background-color: {COLORS['bg_darkest']};
        color: {COLORS['text_primary']};
        font-family: {FONT_FAMILY};
        font-size: 13px;
    }}

    QWidget {{
        background-color: transparent;
        color: {COLORS['text_primary']};
        font-family: {FONT_FAMILY};
    }}

    /* ── Scroll Areas ───────────────────────────────────── */
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}
    QScrollBar:vertical {{
        background: {COLORS['bg_dark']};
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLORS['border']};
        border-radius: 4px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLORS['text_muted']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {COLORS['bg_dark']};
        height: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {COLORS['border']};
        border-radius: 4px;
        min-width: 30px;
    }}

    /* ── Buttons ─────────────────────────────────────────── */
    QPushButton {{
        background-color: {COLORS['accent']};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {COLORS['accent_light']};
    }}
    QPushButton:pressed {{
        background-color: #5558e6;
    }}
    QPushButton:disabled {{
        background-color: {COLORS['border']};
        color: {COLORS['text_muted']};
    }}
    QPushButton#btn_stop {{
        background-color: {COLORS['error']};
    }}
    QPushButton#btn_stop:hover {{
        background-color: #dc2626;
    }}
    QPushButton#btn_secondary {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        color: {COLORS['text_secondary']};
    }}
    QPushButton#btn_secondary:hover {{
        border-color: {COLORS['accent']};
        color: {COLORS['text_primary']};
    }}

    /* ── Line Edits ──────────────────────────────────────── */
    QLineEdit {{
        background-color: {COLORS['bg_input']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        padding: 10px 14px;
        color: {COLORS['text_primary']};
        font-size: 14px;
        selection-background-color: {COLORS['accent']};
    }}
    QLineEdit:focus {{
        border-color: {COLORS['accent']};
    }}
    QLineEdit:disabled {{
        background-color: {COLORS['bg_darkest']};
        color: {COLORS['text_muted']};
    }}

    /* ── Combo Boxes ─────────────────────────────────────── */
    QComboBox {{
        background-color: {COLORS['bg_input']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 6px 12px;
        color: {COLORS['text_primary']};
        min-width: 120px;
    }}
    QComboBox:focus {{
        border-color: {COLORS['accent']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        color: {COLORS['text_primary']};
        selection-background-color: {COLORS['accent']};
    }}

    /* ── Labels ───────────────────────────────────────────── */
    QLabel {{
        color: {COLORS['text_primary']};
    }}
    QLabel#label_secondary {{
        color: {COLORS['text_secondary']};
        font-size: 12px;
    }}
    QLabel#label_muted {{
        color: {COLORS['text_muted']};
        font-size: 11px;
    }}
    QLabel#label_title {{
        font-size: 20px;
        font-weight: 700;
        color: {COLORS['text_primary']};
    }}
    QLabel#label_hardware {{
        font-size: 11px;
        color: {COLORS['text_secondary']};
        padding: 4px 10px;
        background-color: {COLORS['bg_card']};
        border-radius: 4px;
    }}

    /* ── Progress Bars ────────────────────────────────────── */
    QProgressBar {{
        background-color: {COLORS['bg_input']};
        border: none;
        border-radius: 4px;
        height: 8px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {COLORS['accent']}, stop:1 {COLORS['accent_light']});
        border-radius: 4px;
    }}

    /* ── Group Boxes ──────────────────────────────────────── */
    QGroupBox {{
        background-color: transparent;
        border: none;
        margin-top: 18px;
        padding-top: 4px;
        font-weight: 700;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 0px;
        padding: 0;
        color: {COLORS['text_muted']};
        font-size: 11px;
        letter-spacing: 1px;
    }}

    /* ── Text Edit (log viewer) ───────────────────────────── */
    QTextEdit, QPlainTextEdit {{
        background-color: {COLORS['bg_input']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        padding: 8px;
        color: {COLORS['text_secondary']};
        font-family: 'Cascadia Code', 'Consolas', 'Fira Code', monospace;
        font-size: 12px;
        selection-background-color: {COLORS['accent']};
    }}

    /* ── Splitter ──────────────────────────────────────────── */
    QSplitter::handle {{
        background-color: {COLORS['border']};
        height: 2px;
    }}
    QSplitter::handle:hover {{
        background-color: {COLORS['accent']};
    }}

    /* ── Menu Bar ──────────────────────────────────────────── */
    QMenuBar {{
        background-color: {COLORS['bg_darkest']};
        color: {COLORS['text_secondary']};
        border-bottom: 1px solid {COLORS['border']};
        padding: 2px;
    }}
    QMenuBar::item:selected {{
        background-color: {COLORS['bg_card']};
        color: {COLORS['text_primary']};
    }}
    QMenu {{
        background-color: {COLORS['bg_card']};
        border: 1px solid {COLORS['border']};
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 24px;
        color: {COLORS['text_primary']};
    }}
    QMenu::item:selected {{
        background-color: {COLORS['accent']};
    }}

    /* ── Tooltips ──────────────────────────────────────────── */
    QToolTip {{
        background-color: {COLORS['bg_card']};
        color: {COLORS['text_primary']};
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 12px;
    }}

    /* ── Checkboxes (toggle style) ─────────────────────────── */
    QCheckBox {{
        color: {COLORS['text_primary']};
        spacing: 8px;
        font-size: 13px;
    }}
    QCheckBox::indicator {{
        width: 40px;
        height: 22px;
        border-radius: 11px;
        background-color: {COLORS['border']};
        border: none;
    }}
    QCheckBox::indicator:checked {{
        background-color: {COLORS['accent']};
    }}
    QCheckBox::indicator:hover {{
        background-color: {COLORS['bg_card_hover']};
    }}
    QCheckBox::indicator:checked:hover {{
        background-color: {COLORS['accent_light']};
    }}

    /* ── Sliders ───────────────────────────────────────────── */
    QSlider::groove:horizontal {{
        height: 6px;
        background: {COLORS['bg_input']};
        border-radius: 3px;
        border: 1px solid {COLORS['border']};
    }}
    QSlider::handle:horizontal {{
        background: {COLORS['accent']};
        width: 18px;
        height: 18px;
        margin: -7px 0;
        border-radius: 9px;
        border: 2px solid {COLORS['bg_darkest']};
    }}
    QSlider::handle:horizontal:hover {{
        background: {COLORS['accent_light']};
    }}
    QSlider::sub-page:horizontal {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {COLORS['accent']}, stop:1 {COLORS['accent_light']});
        border-radius: 3px;
    }}
    """
