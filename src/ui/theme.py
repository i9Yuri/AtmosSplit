"""Paleta neutra e tipografia da estação (Escuro AMOLED ou Claro de Estúdio)."""

from PySide6.QtGui import QColor

THEMES = {
    "amoled": {
        "CANVAS": "#000000",
        "PANEL": "#0B0B0D",
        "PANEL_ALT": "#141417",
        "RAISED": "#1E1E22",
        "LINE": "#28282D",
        "GRID": "#161619",
        "INK": "#FFFFFF",
        "SECONDARY": "#A1A1AA",
        "MUTED": "#71717A",
        "ACCENT": "#FFFFFF",
        "ACCENT_INK": "#000000",
        "ACCENT_HOVER": "#E4E4E7",
        "ACCENT_PRESSED": "#D4D4D8",
        "WARM": "#F59E0B",
        "COOL": "#60A5FA",
        "FAULT": "#EF4444",
        "SUCCESS": "#10B981",
        "DARK_TEXT": "#000000",
    },
    "light": {
        "CANVAS": "#F4F4F6",
        "PANEL": "#FFFFFF",
        "PANEL_ALT": "#E5E5E8",
        "RAISED": "#D4D4D8",
        "LINE": "#D1D5DB",
        "GRID": "#E5E7EB",
        "INK": "#09090B",
        "SECONDARY": "#52525B",
        "MUTED": "#8E8E93",
        "ACCENT": "#09090B",
        "ACCENT_INK": "#FFFFFF",
        "ACCENT_HOVER": "#27272A",
        "ACCENT_PRESSED": "#3F3F46",
        "WARM": "#D97706",
        "COOL": "#2563EB",
        "FAULT": "#DC2626",
        "SUCCESS": "#059669",
        "DARK_TEXT": "#09090B",
    },
}

DEFAULT_THEME = "amoled"
CURRENT_THEME = "amoled"

CANVAS = THEMES[DEFAULT_THEME]["CANVAS"]
PANEL = THEMES[DEFAULT_THEME]["PANEL"]
PANEL_ALT = THEMES[DEFAULT_THEME]["PANEL_ALT"]
RAISED = THEMES[DEFAULT_THEME]["RAISED"]
LINE = THEMES[DEFAULT_THEME]["LINE"]
GRID = THEMES[DEFAULT_THEME]["GRID"]
INK = THEMES[DEFAULT_THEME]["INK"]
SECONDARY = THEMES[DEFAULT_THEME]["SECONDARY"]
MUTED = THEMES[DEFAULT_THEME]["MUTED"]
ACCENT = THEMES[DEFAULT_THEME]["ACCENT"]
ACCENT_INK = THEMES[DEFAULT_THEME]["ACCENT_INK"]
ACCENT_HOVER = THEMES[DEFAULT_THEME]["ACCENT_HOVER"]
ACCENT_PRESSED = THEMES[DEFAULT_THEME]["ACCENT_PRESSED"]
WARM = THEMES[DEFAULT_THEME]["WARM"]
COOL = THEMES[DEFAULT_THEME]["COOL"]
FAULT = THEMES[DEFAULT_THEME]["FAULT"]
SUCCESS = THEMES[DEFAULT_THEME]["SUCCESS"]
DARK_TEXT = THEMES[DEFAULT_THEME]["DARK_TEXT"]
BODY = "Roboto"
MONO = "Noto Sans Mono"


def set_active_theme(name: str) -> None:
    global CURRENT_THEME, CANVAS, PANEL, PANEL_ALT, RAISED, LINE, GRID, INK, SECONDARY, MUTED, ACCENT, ACCENT_INK, ACCENT_HOVER, ACCENT_PRESSED, WARM, COOL, FAULT, SUCCESS, DARK_TEXT
    if name not in THEMES:
        name = DEFAULT_THEME
    CURRENT_THEME = name
    p = THEMES[name]
    CANVAS = p["CANVAS"]
    PANEL = p["PANEL"]
    PANEL_ALT = p["PANEL_ALT"]
    RAISED = p["RAISED"]
    LINE = p["LINE"]
    GRID = p["GRID"]
    INK = p["INK"]
    SECONDARY = p["SECONDARY"]
    MUTED = p["MUTED"]
    ACCENT = p["ACCENT"]
    ACCENT_INK = p["ACCENT_INK"]
    ACCENT_HOVER = p["ACCENT_HOVER"]
    ACCENT_PRESSED = p["ACCENT_PRESSED"]
    WARM = p["WARM"]
    COOL = p["COOL"]
    FAULT = p["FAULT"]
    SUCCESS = p["SUCCESS"]
    DARK_TEXT = p["DARK_TEXT"]


def tint(color: str | QColor, alpha: int) -> QColor:
    value = QColor(color)
    value.setAlpha(max(0, min(255, int(alpha))))
    return value


def style_sheet(theme_name: str | None = None) -> str:
    name = theme_name or CURRENT_THEME
    if name not in THEMES:
        name = DEFAULT_THEME
    p = THEMES[name]
    return f"""
    QMainWindow, QDialog, QWidget#Studio {{ background: {p['CANVAS']}; color: {p['INK']}; }}
    QWidget {{ color: {p['INK']}; font-family: "{BODY}", "Noto Sans", sans-serif; font-size: 13px; }}
    QWidget#SessionHeader, QWidget#Transport, QWidget#Timeline, QStatusBar {{ background: {p['PANEL']}; }}
    QWidget#SessionHeader, QWidget#Transport, QWidget#Timeline, QStatusBar {{ border-top: 1px solid {p['LINE']}; }}
    QFrame#Panel, QWidget#SourcePanel, QWidget#Inspector {{ background: {p['PANEL']}; }}
    QFrame#Line {{ background: {p['LINE']}; }}
    QLabel {{ background: transparent; border: none; }}
    QLabel#Brand {{ font-size: 22px; font-weight: 700; color: {p['INK']}; }}
    QLabel#Heading {{ font-size: 15px; font-weight: 700; color: {p['INK']}; }}
    QLabel#Subtle {{ color: {p['SECONDARY']}; }}
    QLabel#Clock, QLabel#Status, QProgressBar {{
        font-family: "{MONO}", monospace; color: {p['INK']};
    }}
    QLabel#Status {{ font-size: 12px; }}
    QLabel#Status[error="true"] {{ color: {p['FAULT']}; }}
    QLabel#Status[success="true"] {{ color: {p['SUCCESS']}; }}
    QLabel#SectionInfo {{ color: {p['INK']}; font-weight: 600; }}
    QLabel#SourceTitle {{ color: {p['INK']}; font-size: 16px; font-weight: 600; }}
    QPushButton, QToolButton, QComboBox, QLineEdit {{
        background: {p['PANEL_ALT']}; color: {p['INK']}; border: 1px solid {p['LINE']};
        border-radius: 7px; padding: 5px 12px; min-height: 28px;
    }}
    QPushButton#ThemeToggle {{
        background: {p['PANEL_ALT']}; color: {p['INK']}; border: 1px solid {p['LINE']};
        border-radius: 7px; padding: 4px 10px; font-size: 12px; font-weight: 500;
    }}
    QPushButton#ThemeToggle:hover {{
        background: {p['RAISED']}; border-color: {p['SECONDARY']};
    }}
    QComboBox, QToolButton[popupMode="1"] {{ padding-right: 24px; }}
    QComboBox::drop-down {{
        subcontrol-origin: padding; subcontrol-position: top right; width: 22px; border: none;
    }}
    QToolButton[popupMode="2"] {{ padding-right: 23px; }}
    QToolButton[popupMode="2"]::menu-indicator {{
        subcontrol-origin: padding; subcontrol-position: center right; right: 7px;
    }}
    QPushButton[compact="true"] {{ min-height: 20px; padding: 4px 9px; }}
    QPushButton:hover, QToolButton:hover, QComboBox:hover, QLineEdit:hover {{
        background: {p['RAISED']}; border-color: {p['SECONDARY']};
    }}
    QPushButton:pressed, QToolButton:pressed {{ background: {p['CANVAS']}; border-color: {p['INK']}; }}
    QPushButton:checked {{
        background: {p['RAISED']}; color: {p['INK']}; border-color: {p['INK']}; font-weight: 600;
    }}
    QPushButton:checked:hover {{ background: {p['PANEL_ALT']}; }}
    QPushButton:checked:pressed {{ background: {p['CANVAS']}; }}
    QPushButton#Primary {{
        background: {p['ACCENT']}; color: {p['ACCENT_INK']}; border-color: {p['ACCENT']}; font-weight: 650;
    }}
    QPushButton#Primary:hover {{ background: {p['ACCENT_HOVER']}; border-color: {p['ACCENT_HOVER']}; }}
    QPushButton#Primary:pressed {{ background: {p['ACCENT_PRESSED']}; border-color: {p['ACCENT_PRESSED']}; }}
    QPushButton:focus, QToolButton:focus, QComboBox:focus, QLineEdit:focus, QListWidget:focus {{
        border: 1px solid {p['INK']};
    }}
    QPushButton#Primary:focus {{ border: 2px solid {p['INK']}; }}
    QPushButton:disabled, QPushButton#Primary:disabled, QToolButton:disabled,
    QComboBox:disabled, QLineEdit:disabled {{
        color: {p['MUTED']}; background: {p['PANEL']}; border-color: {p['GRID']};
    }}
    QMenu, QComboBox QAbstractItemView, QTableWidget, QListWidget {{
        background: {p['PANEL']}; color: {p['INK']}; selection-background-color: {p['RAISED']}; selection-color: {p['INK']};
        border: 1px solid {p['LINE']}; border-radius: 8px;
    }}
    QMenu, QComboBox QAbstractItemView {{ background: {p['PANEL_ALT']}; padding: 4px; }}
    QMenu::item {{ padding: 6px 20px; border-radius: 5px; }}
    QMenu::item:selected {{ background: {p['RAISED']}; }}
    QMenu::item:disabled {{ color: {p['MUTED']}; }}
    QMenu::separator {{ height: 1px; background: {p['LINE']}; margin: 4px 6px; }}
    QHeaderView::section {{ background: {p['PANEL_ALT']}; color: {p['INK']}; padding: 6px; border: none; }}
    QListWidget {{ outline: none; padding: 4px; }}
    QListWidget::item {{ padding: 7px 6px; border-radius: 5px; }}
    QListWidget::item:selected {{ background: {p['RAISED']}; color: {p['INK']}; font-weight: 600; }}
    QListWidget::item:hover:!selected {{ background: {p['PANEL_ALT']}; }}
    QScrollArea {{ border: none; background: {p['PANEL']}; }}
    QScrollArea > QWidget > QWidget {{ background: {p['PANEL']}; }}
    QSplitter::handle {{ background: {p['LINE']}; }}
    QSplitter::handle:hover {{ background: {p['SECONDARY']}; }}
    QStatusBar::item {{ border: none; }}
    QProgressBar {{ background: {p['PANEL_ALT']}; border: 1px solid {p['LINE']}; border-radius: 6px; }}
    QProgressBar::chunk {{ background: {p['ACCENT']}; border-radius: 5px; }}
    QSlider {{ background: transparent; min-height: 20px; }}
    QSlider::groove:horizontal {{ background: {p['LINE']}; height: 5px; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {p['INK']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        background: {p['INK']}; border: 1px solid {p['CANVAS']}; width: 14px; margin: -5px 0; border-radius: 7px;
    }}
    QSlider::handle:horizontal:hover {{ background: {p['ACCENT_HOVER']}; }}
    QSlider::handle:horizontal:pressed {{ background: {p['ACCENT_PRESSED']}; }}
    QSlider::handle:horizontal:focus {{ border: 2px solid {p['INK']}; }}
    QSlider::handle:horizontal:disabled, QSlider::sub-page:horizontal:disabled {{ background: {p['MUTED']}; }}
    QToolTip {{ background: {p['RAISED']}; color: {p['INK']}; border: 1px solid {p['LINE']}; padding: 5px; border-radius: 4px; }}
    """
