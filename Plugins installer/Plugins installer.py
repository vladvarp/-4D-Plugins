import sys
import os
import json
import re
import shutil
import subprocess
import tempfile
import threading
import urllib.request
import winreg
import base64
from pathlib import Path
from urllib.parse import unquote, quote

import ctypes

PROGRAM_NAME = "4D Plugin Installer"
PROGRAM_VER  = "v1.4"

# Скрываем консольное окно для всех дочерних процессов на Windows
CREATE_NO_WINDOW = 0x08000000

def _run(cmd, **kwargs):
    """subprocess.run с флагом скрытия консоли."""
    kwargs.setdefault("creationflags", CREATE_NO_WINDOW)
    return subprocess.run(cmd, **kwargs)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QFrame, QMessageBox,
    QAbstractItemView
)
from PyQt6.QtGui import QColor, QPalette, QCursor, QDesktopServices, QIcon, QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl

# ── Конфигурация ──────────────────────────────────────────────────────────────

LIST_JSON_URL = (
    "https://raw.githubusercontent.com/vladvarp/-4D-Plugins/main/update_data/uplist.json"
)
CONFIG_FILE = Path(os.getenv("APPDATA")) / "C4D_PluginInstaller" / "config.json"
GIT_RELEASES_PAGE = "https://github.com/git-for-windows/git/releases"
# Кэш list.json в папке temp Windows (доступен при отсутствии сети)
LIST_JSON_CACHE = Path(tempfile.gettempdir()) / "c4d_installer_list_cache.json"
# URL логотипа в шапке
HEADER_LOGO_URL = (
    "https://raw.githubusercontent.com/vladvarp/-4D-Plugins/refs/heads/main/Plugins%20installer/icon.png"
)

# ── Иконка приложения (PNG 256×256, base64) ───────────────────────────────────

ICON_B64 = (
    "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"
)

# ── Парсинг list.json ─────────────────────────────────────────────────────────

def parse_list_json(raw: str) -> tuple[list[dict], dict]:
    """
    Парсит новый JSON-формат uplist.json.

    Формат файла:
    {
      "app": {
        "about_label": "О плагинах",
        "about_url": "https://..."
      },
      "authors": [
        {
          "name": "Автор",
          "expanded": true,
          "plugins": [
            {
              "url": "https://github.com/.../tree/main/Plugins/PluginName",
              "info": "Описание плагина",
              "info_url": "https://..."
            }
          ]
        }
      ]
    }

    Возвращает (authors_list, app_meta):
      authors_list — список авторов, каждый содержит "name", "expanded", "plugins"
      app_meta     — словарь {"about_label": ..., "about_url": ...}

    Каждый плагин после разбора содержит:
      name, url, repo_url, repo_path, info, info_url, author
    (version НЕ хранится — берётся из файла ver внутри папки)
    """
    data = json.loads(raw)

    app_meta = data.get("app", {})

    authors_out = []
    for author_entry in data.get("authors", []):
        author_name = author_entry.get("name", "Неизвестный автор")
        expanded = author_entry.get("expanded", True)
        plugins_out = []

        for p in author_entry.get("plugins", []):
            url = p.get("url", "").strip().rstrip("/")
            if not url:
                continue

            info_text = p.get("info", "")
            info_url  = p.get("info_url", "")

            # Разбираем github-url: https://github.com/user/repo/tree/branch/path
            parts = url.split("/tree/", 1)
            if len(parts) < 2:
                continue
            repo_url = parts[0] + ".git"
            after_branch = parts[1].split("/", 1)
            # repo_path декодируем — git sparse-checkout требует реальные имена
            repo_path = unquote(after_branch[1]) if len(after_branch) > 1 else unquote(after_branch[0])

            # Имя папки — последний сегмент repo_path
            name = repo_path.rstrip("/").split("/")[-1]

            # Raw URL для файла ver (читается как обычный текст без авторизации)
            # Пример: https://raw.githubusercontent.com/user/repo/main/Plugins/Name/ver
            # repo_path декодирован (пробелы) — для URL нужно закодировать обратно
            branch = after_branch[0]
            raw_base = parts[0].replace("github.com", "raw.githubusercontent.com")
            raw_ver_url = f"{raw_base}/{branch}/{quote(repo_path, safe='/')}/ver"

            plugins_out.append({
                "name":        name,
                "url":         url,
                "repo_url":    repo_url,
                "repo_path":   repo_path,  # декодированный путь, напр. «Plugins/VAr Tools»
                "info":        info_text,
                "info_url":    info_url,
                "author":      author_name,
                "raw_ver_url": raw_ver_url,  # URL для чтения актуальной версии с GitHub
            })

        authors_out.append({
            "name":     author_name,
            "expanded": expanded,
            "plugins":  plugins_out,
        })

    return authors_out, app_meta

# ── Конфиг ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"install_dir": "", "installed": {}}

def save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ── Git ───────────────────────────────────────────────────────────────────────

def git_available() -> bool:
    # return False  # <- временно для теста отсутствия GIT
    try:
        _run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def git_exe() -> str:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GitForWindows")
        path, _ = winreg.QueryValueEx(key, "InstallPath")
        return str(Path(path) / "bin" / "git.exe")
    except Exception:
        return "git"

def sparse_clone_folder(repo_url: str, folder_path: str, dest: str, progress_cb):
    """
    Клонирует только папку folder_path из репозитория.
    folder_path должен быть уже декодирован (пробелы, не %20).
    """
    git = git_exe()
    tmp_dir = tempfile.mkdtemp()
    try:
        progress_cb(f"Инициализирую репозиторий…")
        _run([git, "init", tmp_dir], check=True, capture_output=True)
        _run([git, "-C", tmp_dir, "remote", "add", "origin", repo_url],
                       check=True, capture_output=True)
        _run([git, "-C", tmp_dir, "config", "core.sparseCheckout", "true"],
                       check=True, capture_output=True)

        sparse_file = Path(tmp_dir) / ".git" / "info" / "sparse-checkout"
        # Записываем декодированный путь — git понимает пробелы
        sparse_file.write_text(folder_path + "/\n", encoding="utf-8")

        progress_cb(f"Скачиваю «{folder_path}»…")
        result = _run(
            [git, "-C", tmp_dir, "pull", "--depth=1", "origin", "main"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"git pull вернул ошибку:\n{result.stderr}")

        src = Path(tmp_dir) / folder_path
        if not src.exists():
            # Попробуем найти папку case-insensitive
            parent = src.parent
            if parent.exists():
                found = [d for d in parent.iterdir()
                         if d.name.lower() == src.name.lower()]
                if found:
                    src = found[0]
                else:
                    listing = [d.name for d in parent.iterdir()]
                    raise FileNotFoundError(
                        f"Папка «{folder_path}» не найдена. "
                        f"Содержимое: {listing}"
                    )
            else:
                raise FileNotFoundError(
                    f"Папка «{folder_path}» не найдена в репозитории."
                )

        target = Path(dest) / src.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
        return str(target)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def read_plugin_ver(install_dir: str, folder_name: str) -> tuple[str, str]:
    """
    Читает файл 'ver' (без расширения) внутри папки плагина.
    Первая строка — версия, вторая (необязательная) — отображаемое имя.
    Возвращает (version, display_name). Если файла нет — ("", "").
    """
    ver_file = Path(install_dir) / folder_name / "ver"
    if ver_file.exists():
        lines = ver_file.read_text(encoding="utf-8").splitlines()
        version = lines[0].strip() if lines else ""
        display_name = lines[1].strip() if len(lines) > 1 else ""
        return version, display_name
    return "", ""

def write_plugin_ver(install_dir: str, name: str, version: str):
    """Записывает версию в файл 'ver' внутри папки плагина."""
    ver_file = Path(install_dir) / name / "ver"
    ver_file.write_text(version, encoding="utf-8")

def remove_plugin_folder(install_dir: str, name: str):
    target = Path(install_dir) / name
    if target.exists():
        shutil.rmtree(target)

def fetch_remote_ver(raw_ver_url: str) -> str:
    """
    Скачивает файл ver с GitHub (raw) и возвращает первую строку — версию.
    При любой ошибке возвращает пустую строку.
    """
    try:
        req = urllib.request.Request(
            raw_ver_url, headers={"User-Agent": "C4D-Installer/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            text = r.read().decode("utf-8")
        lines = text.splitlines()
        return lines[0].strip() if lines else ""
    except Exception:
        return ""

# ── Worker ────────────────────────────────────────────────────────────────────

class InstallWorker(QThread):
    progress   = pyqtSignal(str)
    plugin_done = pyqtSignal(str, bool, str)   # name, ok, info
    finished_all = pyqtSignal()

    def __init__(self, plugins, install_dir, config):
        super().__init__()
        self.plugins = plugins
        self.install_dir = install_dir
        self.config = config

    def run(self):
        for p in self.plugins:
            name = p["name"]
            self.progress.emit(f"Устанавливаю «{name}»…")
            try:
                sparse_clone_folder(
                    p["repo_url"], p["repo_path"], self.install_dir,
                    lambda msg: self.progress.emit(msg)
                )
                # Если репозиторий не содержит файл ver — создаём его с "?"
                installed_ver, _ = read_plugin_ver(self.install_dir, name)
                if not installed_ver:
                    write_plugin_ver(self.install_dir, name, "Не указан")
                    installed_ver = "Не указан"
                self.config["installed"][name] = {"version": installed_ver}
                save_config(self.config)
                self.plugin_done.emit(name, True, installed_ver)
            except Exception as e:
                self.plugin_done.emit(name, False, str(e))
        self.finished_all.emit()

# ── Цвета / стиль ─────────────────────────────────────────────────────────────

DARK_BG  = "#141414"
PANEL_BG = "#1e1e1e"
BORDER   = "#2d2d2d"
ACCENT   = "#e8622a"
TEXT     = "#e8e8e8"
DIM      = "#777777"
GREEN    = "#4caf6e"
RED      = "#e05c5c"
YELLOW   = "#e0a94e"

STYLE = f"""
QMainWindow, QWidget#root {{ background: {DARK_BG}; }}
QWidget {{ background: transparent; color: {TEXT}; }}
QLabel {{ color: {TEXT}; background: transparent; }}
QPushButton {{
    background: {PANEL_BG}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 6px;
    padding: 7px 16px; font-size: 12px;
}}
QPushButton:hover {{ background: #282828; border-color: #444; }}
QPushButton:pressed {{ background: #111; }}
QPushButton:disabled {{ color: #555; border-color: #252525; }}
QPushButton#primary {{
    background: {ACCENT}; color: white; border: 2px solid #ff8050;
    font-weight: 600; font-size: 13px; padding: 9px 22px;
}}
QPushButton#primary:hover {{ background: #f07040; }}
QPushButton#primary:disabled {{ background: #5a3020; color: #996050; }}
QPushButton#danger {{
    background: transparent; color: {RED};
    border: 1px solid #4a2020; border-radius: 6px;
    padding: 5px 12px; font-size: 11px;
}}
QPushButton#danger:hover {{ background: #2a1212; }}
QPushButton#danger:disabled {{ color: #554040; border-color: #2a1818; }}
QPushButton#readme {{
    background: transparent; color: {DIM};
    border: 1px solid {BORDER}; border-radius: 6px;
    padding: 5px 14px; font-size: 11px;
}}
QPushButton#readme:hover {{ color: {TEXT}; border-color: #555; background: #252525; }}
QPushButton#install {{
    background: transparent; color: #5b9bd5;
    border: 1px solid #2a4a70; border-radius: 6px;
    padding: 5px 12px; font-size: 11px;
}}
QPushButton#install:hover {{ background: #152030; }}
QPushButton#update {{
    background: transparent; color: {GREEN};
    border: 1px solid #1e4a2e; border-radius: 6px;
    padding: 5px 12px; font-size: 11px;
}}
QPushButton#update:hover {{ background: #122018; }}
QLineEdit {{
    background: {PANEL_BG}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 6px;
    padding: 7px 10px; font-size: 12px; font-family: Consolas;
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QTableWidget {{
    background: {PANEL_BG}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 8px;
    gridline-color: transparent; outline: none; font-size: 12px;
}}
QTableWidget::item {{ padding: 0 10px; border: none; }}
QTableWidget::item:selected {{ background: #252525; color: {TEXT}; }}
QHeaderView::section {{
    background: #181818; color: {DIM};
    border: none; border-bottom: 1px solid {BORDER};
    padding: 7px 10px; font-size: 10px; font-weight: 700;
    letter-spacing: 1px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid #555; border-radius: 3px;
    background: {PANEL_BG};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT}; border-color: {ACCENT};
    image: none;
}}
QProgressBar {{
    background: {PANEL_BG}; border: 1px solid {BORDER};
    border-radius: 3px; height: 5px;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QScrollBar:vertical {{
    background: {PANEL_BG}; width: 5px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: #444; border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QFrame#divider {{ background: {BORDER}; max-height: 1px; }}
QTableWidget::item[groupHeader="true"] {{ background: #202020; }}
"""

# ── Главное окно ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(PROGRAM_NAME + " " + PROGRAM_VER)
        self.setMinimumSize(820, 560)
        self.resize(900, 620)

        self.config = load_config()
        self.remote_authors: list[dict] = []   # список авторов из list.json
        self.app_meta: dict = {}               # app-секция из list.json (кнопка «О плагинах»)
        self.offline_mode: bool = False        # флаг: нет подключения к сети
        self.third_party_expanded: bool = False  # блок «Сторонние» свёрнут по умолчанию
        self.worker: InstallWorker | None = None

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._mk_header())
        lay.addWidget(self._mk_path_bar())
        div = QFrame(); div.setObjectName("divider"); lay.addWidget(div)
        lay.addWidget(self._mk_table_area(), stretch=1)
        lay.addWidget(self._mk_bottom())

        self.setStyleSheet(STYLE)

        # При клике в любом месте окна фокус уходит с поля ввода
        root.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        if self.config.get("install_dir"):
            self.path_edit.setText(self.config["install_dir"])
            QTimer.singleShot(400, self._check_updates)

        # Загружаем логотип заголовка из GitHub
        QTimer.singleShot(100, self._load_header_logo)

        # Проверяем наличие Git при запуске и устанавливаем если нужно
        if not git_available():
            QTimer.singleShot(500, self._ensure_git_installed)

    # ── Построение UI ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        """Снимает фокус с поля ввода при клике в любом месте окна."""
        focused = QApplication.focusWidget()
        if focused and focused is self.path_edit:
            self.path_edit.clearFocus()
        super().mousePressEvent(event)

    def _mk_header(self):
        w = QWidget()
        w.setFixedHeight(62)
        w.setStyleSheet(f"background:#1a1a1a; border-bottom:1px solid {BORDER};")
        h = QHBoxLayout(w)
        h.setContentsMargins(22, 0, 22, 0)

        # Логотип: загружается из GitHub, пока грузится — заглушка-текст
        self.logo_lbl = QLabel("4D")
        self.logo_lbl.setFixedSize(40, 40)
        self.logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_lbl.setStyleSheet(
            f"background:{ACCENT}; color:white; font-size:14px; font-weight:800;"
            "padding:4px 10px; border-radius:5px; letter-spacing:1px;"
        )
        h.addWidget(self.logo_lbl)
        h.addSpacing(12)

        title = QLabel(PROGRAM_NAME)
        title.setStyleSheet(f"font-size:18px; font-weight:700; color:{TEXT};")
        h.addWidget(title)
        h.addStretch()

        # Индикатор оффлайн-режима (скрыт по умолчанию)
        self.offline_lbl = QLabel("⚠ Нет подключения")
        self.offline_lbl.setStyleSheet(f"font-size:11px; color:{YELLOW}; background:transparent;")
        self.offline_lbl.setVisible(False)
        h.addWidget(self.offline_lbl)
        h.addSpacing(8)

        self.status_lbl = QLabel("Готов к работе")
        self.status_lbl.setStyleSheet(f"font-size:11px; color:{DIM};")
        h.addWidget(self.status_lbl)

        h.addSpacing(12)
        # Кнопка «О плагинах»: метка и URL берутся из app_meta (заполняется после загрузки JSON)
        self.readme_btn = QPushButton("О плагинах")
        self.readme_btn.setFixedHeight(30)
        self.readme_btn.setObjectName("readme")
        self.readme_btn.clicked.connect(self._open_about_url)
        h.addWidget(self.readme_btn)
        return w

    def _open_about_url(self):
        """Открывает ссылку из app_meta, либо дефолтную."""
        url = self.app_meta.get(
            "about_url",
            "https://github.com/vladvarp/-4D-Plugins?tab=readme-ov-file#readme"
        )
        QDesktopServices.openUrl(QUrl(url))

    def _load_header_logo(self):
        """Скачивает логотип из GitHub и устанавливает в self.logo_lbl."""
        def worker():
            try:
                req = urllib.request.Request(
                    HEADER_LOGO_URL, headers={"User-Agent": "C4D-Installer/1.0"}
                )
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = r.read()
                self._pending_logo = data
            except Exception:
                self._pending_logo = b""

        self._pending_logo = None
        threading.Thread(target=worker, daemon=True).start()

        def poll():
            if self._pending_logo is None:
                QTimer.singleShot(80, poll)
            else:
                if self._pending_logo:
                    pix = QPixmap()
                    pix.loadFromData(self._pending_logo)
                    pix = pix.scaled(
                        40, 40,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.logo_lbl.setPixmap(pix)
                    self.logo_lbl.setStyleSheet("background:transparent; border-radius:5px;")
        QTimer.singleShot(80, poll)

    def _mk_path_bar(self):
        w = QWidget()
        w.setFixedHeight(58)
        w.setStyleSheet(f"background:{DARK_BG};")
        h = QHBoxLayout(w)
        h.setContentsMargins(22, 8, 22, 8)
        h.setSpacing(10)

        lbl = QLabel("Папка плагинов C4D:")
        lbl.setStyleSheet(f"font-size:11px; color:{DIM}; min-width:140px;")
        h.addWidget(lbl)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(
            r"Например: C:\Users\...\AppData\Roaming\Maxon\Cinema 4D\plugins"
        )
        # При ручном вводе — обновляем таблицу когда фокус уходит с поля
        self.path_edit.editingFinished.connect(self._on_path_edited)
        h.addWidget(self.path_edit, stretch=1)

        browse = QPushButton("Обзор…")
        browse.setFixedHeight(34)
        browse.clicked.connect(self._browse_dir)
        h.addWidget(browse)
        return w

    def _mk_table_area(self):
        w = QWidget()
        w.setStyleSheet(f"background:{DARK_BG};")
        v = QVBoxLayout(w)
        v.setContentsMargins(22, 14, 22, 0)
        v.setSpacing(10)

        # Заголовок секции + кнопки управления
        row = QHBoxLayout()
        sec = QLabel("ПЛАГИНЫ")
        sec.setStyleSheet(f"font-size:10px; font-weight:700; color:{DIM}; letter-spacing:2px;")
        row.addWidget(sec)
        row.addStretch()

        # Строка поиска по именам плагинов (динамический, без учёта регистра)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по плагинам…")
        self.search_edit.setFixedHeight(28)
        self.search_edit.setMaximumWidth(220)
        self.search_edit.textChanged.connect(self._on_search_changed)
        row.addWidget(self.search_edit)
        row.addSpacing(8)

        self.refresh_btn = QPushButton("↻  Проверить")
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.clicked.connect(self._check_updates)
        row.addWidget(self.refresh_btn)
        v.addLayout(row)

        # Таблица: Плагин | Установлено | На GitHub | Статус | Действие | Удалить
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Плагин", "Текущая", "Актуальная", "Статус", "", ""])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 90)  # Текущая
        self.table.setColumnWidth(2, 90)  # Актуальная
        self.table.setColumnWidth(3, 125)  # Статус
        self.table.setColumnWidth(4, 120)  # Установить / Обновить
        self.table.setColumnWidth(5, 115)  # Удалить
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        v.addWidget(self.table)
        return w

    def _mk_bottom(self):
        w = QWidget()
        w.setFixedHeight(68)
        w.setStyleSheet(f"background:#181818; border-top:1px solid {BORDER};")
        h = QHBoxLayout(w)
        h.setContentsMargins(22, 0, 22, 0)
        h.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(5)
        self.progress_lbl = QLabel("Введите путь и нажмите «Проверить»")
        self.progress_lbl.setStyleSheet(f"font-size:11px; color:{DIM};")
        left.addWidget(self.progress_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        left.addWidget(self.progress_bar)
        h.addLayout(left, stretch=1)
        return w

    # ── Логика ────────────────────────────────────────────────────────────────

    def _on_search_changed(self, text: str):
        """Динамически фильтрует таблицу по тексту поиска (без учёта регистра)."""
        self._populate_table()

    def _on_path_edited(self):
        """Вызывается когда пользователь вручную ввёл путь и убрал фокус с поля."""
        d = self.path_edit.text().strip()
        if d:
            self.config["install_dir"] = d
            save_config(self.config)
            # Перечитываем таблицу с новой папкой (версии из файлов 'ver')
            if self.remote_authors:
                self._populate_table()

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Папка плагинов Cinema 4D",
            self.path_edit.text() or "C:\\"
        )
        if d:
            self.path_edit.setText(d)
            self.config["install_dir"] = d
            save_config(self.config)
            # Перечитываем таблицу с новой папкой (версии из файлов 'ver')
            if self.remote_authors:
                self._populate_table()

    def _check_updates(self):
        d = self.path_edit.text().strip()
        if d:
            self.config["install_dir"] = d
            save_config(self.config)

        self.refresh_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_lbl.setText("Подключаюсь к GitHub…")
        self.status_lbl.setText("Загружаю список…")

        def worker():
            raw = None
            is_offline = False
            error_msg = None
            try:
                req = urllib.request.Request(
                    LIST_JSON_URL, headers={"User-Agent": "C4D-Installer/1.0"}
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    raw = r.read().decode("utf-8")
                # Сохраняем актуальный кэш в temp Windows
                try:
                    LIST_JSON_CACHE.write_text(raw, encoding="utf-8")
                except Exception:
                    pass
            except Exception as e:
                is_offline = True
                error_msg = str(e)
                # Пробуем прочитать кэш из temp
                if LIST_JSON_CACHE.exists():
                    try:
                        raw = LIST_JSON_CACHE.read_text(encoding="utf-8")
                    except Exception:
                        raw = None

            if raw:
                try:
                    authors, app_meta = parse_list_json(raw)
                    # Скачиваем актуальную версию с GitHub для каждого плагина (файл ver)
                    if not is_offline:
                        threads = []
                        for author_entry in authors:
                            for p in author_entry["plugins"]:
                                p["remote_ver"] = ""  # инициализируем
                                def _fetch(plugin=p):
                                    plugin["remote_ver"] = fetch_remote_ver(
                                        plugin.get("raw_ver_url", "")
                                    )
                                t = threading.Thread(target=_fetch, daemon=True)
                                t.start()
                                threads.append(t)
                        for t in threads:
                            t.join(timeout=10)
                    self._pending = (authors, app_meta, is_offline, None)
                except Exception as parse_err:
                    self._pending = ([], {}, is_offline, str(parse_err))
            else:
                self._pending = ([], {}, is_offline, error_msg)

        self._pending = None
        t = threading.Thread(target=worker, daemon=True)
        t.start()

        def poll():
            if self._pending is None:
                QTimer.singleShot(80, poll)
            else:
                authors, app_meta, is_offline, err = self._pending
                self.progress_bar.setVisible(False)
                self.refresh_btn.setEnabled(True)
                self.offline_mode = is_offline
                self.offline_lbl.setVisible(is_offline)

                if err and not authors:
                    self.status_lbl.setText("Ошибка")
                    self.progress_lbl.setText(f"Не удалось загрузить список: {err}")
                else:
                    if is_offline:
                        self.status_lbl.setText("Оффлайн — данные из кэша")
                    self.remote_authors = authors
                    self.app_meta = app_meta
                    # Обновляем кнопку «О плагинах» согласно данным из JSON
                    about_label = app_meta.get("about_label", "О плагинах")
                    self.readme_btn.setText(about_label)
                    self._populate_table()
        QTimer.singleShot(80, poll)

    def _populate_table(self):
        self.table.setRowCount(0)
        install_dir = self.path_edit.text().strip()
        needs = 0
        search_query = self.search_edit.text().strip().lower()

        # ── Собираем все известные имена папок из remote_authors ──────────────
        known_plugin_names: set[str] = set()
        for author_entry in self.remote_authors:
            for p in author_entry["plugins"]:
                known_plugin_names.add(p["name"])

        # ── Определяем установленные «сторонние» плагины ──────────────────────
        # Сторонний плагин — папка в install_dir с файлом ver, которой нет в JSON
        third_party: list[dict] = []
        if install_dir and Path(install_dir).exists():
            for entry in sorted(Path(install_dir).iterdir()):
                if not entry.is_dir():
                    continue
                folder_name = entry.name
                if folder_name in known_plugin_names:
                    continue
                ver_file = entry / "ver"
                if not ver_file.exists():
                    continue
                local_ver, display_name = read_plugin_ver(install_dir, folder_name)
                if not local_ver:
                    continue
                third_party.append({
                    "folder_name":   folder_name,
                    "display_name":  display_name or folder_name,
                    "local_ver":     local_ver,
                })

        # ── Вспомогательная функция добавления строки ─────────────────────────
        def add_row(name: str, display_name: str, local_ver: str,
                    remote_ver: str, p: dict | None):
            """
            Добавляет строку в таблицу.
            p — словарь плагина из JSON (None для сторонних).
            """
            nonlocal needs

            # Фильтр поиска по отображаемому имени
            if search_query and search_query not in display_name.lower():
                return

            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 46)

            # Имя + info/ссылка
            if p and (p.get("info") or p.get("info_url")):
                name_widget = QWidget()
                name_widget.setStyleSheet("background:transparent;")
                nw_lay = QVBoxLayout(name_widget)
                nw_lay.setContentsMargins(10, 4, 6, 4)
                nw_lay.setSpacing(2)
                lbl_name = QLabel(display_name)
                lbl_name.setStyleSheet(f"color:{TEXT}; font-size:12px; background:transparent;")
                nw_lay.addWidget(lbl_name)
                if p.get("info"):
                    lbl_info = QLabel(p["info"])
                    lbl_info.setStyleSheet(f"color:{DIM}; font-size:10px; background:transparent;")
                    lbl_info.setWordWrap(True)
                    nw_lay.addWidget(lbl_info)
                if p.get("info_url"):
                    lbl_link = QLabel(
                        f'<a href="{p["info_url"]}" style="color:#5b9bd5; font-size:10px;">Подробнее...</a>'
                    )
                    lbl_link.setOpenExternalLinks(True)
                    lbl_link.setStyleSheet("background:transparent;")
                    nw_lay.addWidget(lbl_link)
                self.table.setCellWidget(row, 0, name_widget)
                # Сбрасываем фиксированную высоту — строка растянется по контенту
                self.table.setRowHeight(row, 0)
                self.table.resizeRowToContents(row)
            else:
                name_item = QTableWidgetItem(display_name)
                if p and p.get("info"):
                    name_item.setToolTip(p["info"])
                self.table.setItem(row, 0, name_item)

            # Локальная версия
            loc = QTableWidgetItem(local_ver or " ")
            loc.setForeground(QColor(DIM if not local_ver else TEXT))
            self.table.setItem(row, 1, loc)

            # Актуальная версия (из JSON или прочерк для сторонних)
            self.table.setItem(row, 2, QTableWidgetItem(remote_ver or "—"))

            # Статус
            if p is None:
                # Сторонний плагин — только показываем, действий нет
                st = QTableWidgetItem("Сторонний")
                st.setForeground(QColor(DIM))
                self.table.setItem(row, 3, st)
            elif self.offline_mode:
                # Нет подключения — статус неизвестен
                st = QTableWidgetItem("Нет подключения")
                st.setForeground(QColor(DIM))
                self.table.setItem(row, 3, st)
            elif not local_ver:
                # Не установлен — не входит в счётчик обновлений
                st = QTableWidgetItem("")
                st.setForeground(QColor(ACCENT))
                self.table.setItem(row, 3, st)
            elif local_ver != remote_ver:
                needs += 1  # считаем только установленные с устаревшей версией
                st = QTableWidgetItem("Есть обновление")
                st.setForeground(QColor(YELLOW))
                self.table.setItem(row, 3, st)
            else:
                st = QTableWidgetItem("✓ Актуально")
                st.setForeground(QColor(GREEN))
                self.table.setItem(row, 3, st)

            # Кнопка «Установить» / «Обновить» (только для плагинов из JSON и при наличии сети)
            if p is not None and not self.offline_mode and (not local_ver or local_ver != remote_ver):
                action_label = "Обновить" if local_ver else "Установить"
                act_btn = QPushButton(action_label)
                act_btn.setObjectName("update" if local_ver else "install")
                act_btn.setFixedHeight(28)
                captured_plugin = dict(p)
                act_btn.clicked.connect(lambda _, pl=captured_plugin: self._install_single(pl))
                aw = QWidget()
                aw.setStyleSheet("background:transparent;")
                al = QHBoxLayout(aw)
                al.setContentsMargins(6, 0, 6, 0)
                al.addWidget(act_btn)
                self.table.setCellWidget(row, 4, aw)

            # Кнопка «Удалить» (только если установлен)
            if local_ver:
                del_btn = QPushButton("Удалить")
                del_btn.setObjectName("danger")
                del_btn.setFixedHeight(28)
                captured_name = name
                del_btn.clicked.connect(lambda _, n=captured_name: self._delete_plugin(n))
                dw = QWidget()
                dw.setStyleSheet("background:transparent;")
                dl = QHBoxLayout(dw)
                dl.setContentsMargins(6, 0, 6, 0)
                dl.addWidget(del_btn)
                self.table.setCellWidget(row, 5, dw)

        # ── Вспомогательная: строка-заголовок группы автора ───────────────────
        def add_author_header(author_name: str, expanded: bool):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 34)

            arrow = "▼" if expanded else "▶"
            header_widget = QWidget()
            header_widget.setStyleSheet(f"background:#202020; border-radius:4px;")
            hl = QHBoxLayout(header_widget)
            hl.setContentsMargins(10, 0, 10, 0)
            hl.setSpacing(8)

            arrow_lbl = QLabel(arrow)
            arrow_lbl.setStyleSheet(f"color:{DIM}; font-size:10px; background:transparent;")
            hl.addWidget(arrow_lbl)

            name_lbl = QLabel(author_name.upper())
            name_lbl.setStyleSheet(
                f"color:{DIM}; font-size:10px; font-weight:700; "
                f"letter-spacing:1px; background:transparent;"
            )
            hl.addWidget(name_lbl)
            hl.addStretch()

            self.table.setCellWidget(row, 0, header_widget)
            self.table.setSpan(row, 0, 1, 6)

            # Клик по строке-заголовку переключает состояние expanded
            captured_author = author_name
            header_widget.mousePressEvent = lambda e, a=captured_author: self._toggle_author(a)
            header_widget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        # ── Сторонние плагины (блок выше всех, свёрнут по умолчанию) ─────────
        if third_party:
            filtered_third = [
                tp for tp in third_party
                if not search_query or search_query in tp["display_name"].lower()
            ]
            if filtered_third:
                tp_expanded = self.third_party_expanded if not search_query else True
                add_author_header("Сторонние", tp_expanded)
                if tp_expanded:
                    for tp in filtered_third:
                        add_row(
                            tp["folder_name"],
                            tp["display_name"],
                            tp["local_ver"],
                            "",    # remote_ver неизвестен
                            None   # нет записи в JSON
                        )

        # ── Рендерим плагины по авторам ───────────────────────────────────────
        for author_entry in self.remote_authors:
            author_name = author_entry["name"]
            expanded = author_entry.get("expanded", True)

            # При активном поиске — показываем группу только если есть совпадения
            if search_query:
                matched = [
                    p for p in author_entry["plugins"]
                    if search_query in (
                        (p.get("display_name") or p["name"]).lower()
                    ) or search_query in p["name"].lower()
                ]
                if not matched:
                    continue
                add_author_header(author_name, True)
                for p in matched:
                    local_ver, display_name = read_plugin_ver(install_dir, p["name"]) if install_dir else ("", "")
                    dn = display_name or p["name"]
                    # remote_ver берётся из скачанного файла ver репозитория
                    add_row(p["name"], dn, local_ver, p.get("remote_ver", ""), p)
            else:
                add_author_header(author_name, expanded)
                if expanded:
                    for p in author_entry["plugins"]:
                        local_ver, display_name = read_plugin_ver(install_dir, p["name"]) if install_dir else ("", "")
                        dn = display_name or p["name"]
                        # remote_ver берётся из скачанного файла ver репозитория
                        add_row(p["name"], dn, local_ver, p.get("remote_ver", ""), p)

        if needs:
            self.status_lbl.setText(f"Требуют обновления: {needs}")
            self.progress_lbl.setText("Нажмите «Установить» или «Обновить» напротив нужного плагина")
        else:
            self.status_lbl.setText("Всё актуально")
            self.progress_lbl.setText("Все плагины актуальны")

    def _toggle_author(self, author_name: str):
        """Переключает состояние expanded для группы автора и перерисовывает таблицу."""
        if author_name == "Сторонние":
            self.third_party_expanded = not self.third_party_expanded
        else:
            for author_entry in self.remote_authors:
                if author_entry["name"] == author_name:
                    author_entry["expanded"] = not author_entry.get("expanded", True)
                    break
        self._populate_table()

    def _ensure_git_installed(self):
        """Вызывается при запуске: если Git не найден — показывает предупреждение."""
        self.status_lbl.setText("Git не найден")
        self.progress_lbl.setText("Для работы программы необходим Git")

        msg = QMessageBox(self)
        msg.setWindowTitle("Требуется Git")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(
            "<b>Для работы программы необходим Git.</b><br><br>"
            "Git не обнаружен на вашем компьютере.<br>"
            "Пожалуйста, скачайте и установите Git, затем перезапустите программу."
        )
        download_btn = msg.addButton("Скачать Git", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("Закрыть", QMessageBox.ButtonRole.RejectRole)
        msg.exec()

        if msg.clickedButton() == download_btn:
            QDesktopServices.openUrl(QUrl(GIT_RELEASES_PAGE))

    def _install_single(self, plugin: dict):
        """Устанавливает/обновляет один плагин по кнопке в строке таблицы."""
        install_dir = self.path_edit.text().strip()
        if not install_dir:
            QMessageBox.warning(self, "Укажите папку", "Выберите папку плагинов Cinema 4D.")
            return
        os.makedirs(install_dir, exist_ok=True)

        if not git_available():
            msg = QMessageBox(self)
            msg.setWindowTitle("Требуется Git")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText(
                "<b>Для работы программы необходим Git.</b><br><br>"
                "Git не обнаружен на вашем компьютере.<br>"
                "Пожалуйста, скачайте и установите Git, затем перезапустите программу."
            )
            download_btn = msg.addButton("Скачать Git", QMessageBox.ButtonRole.ActionRole)
            msg.addButton("Закрыть", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == download_btn:
                QDesktopServices.openUrl(QUrl(GIT_RELEASES_PAGE))
            return

        # Немедленно блокируем UI и показываем прогресс ДО запуска воркера
        self.refresh_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.progress_lbl.setText(f"Подготовка к установке «{plugin['name']}»…")
        QApplication.processEvents()

        self._run_worker([plugin], install_dir)

    def _delete_plugin(self, name: str):
        install_dir = self.path_edit.text().strip()
        if not install_dir:
            QMessageBox.warning(self, "Ошибка", "Не указана папка плагинов.")
            return
        reply = QMessageBox.question(
            self, "Удалить плагин",
            f"Удалить папку «{name}» из папки плагинов?\nДействие необратимо.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            remove_plugin_folder(install_dir, name)
            # Убираем из конфига
            self.config["installed"].pop(name, None)
            save_config(self.config)
            self._populate_table()
            self.progress_lbl.setText(f"«{name}» удалён")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка удаления", str(e))

    def _run_worker(self, to_install, install_dir):
        self.refresh_btn.setEnabled(False)
        if not self.progress_bar.isVisible():
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setVisible(True)

        self.worker = InstallWorker(to_install, install_dir, self.config)
        self.worker.progress.connect(self.progress_lbl.setText)
        self.worker.plugin_done.connect(self._on_plugin_done)
        self.worker.finished_all.connect(self._on_finished)
        self.worker.start()

    def _on_plugin_done(self, name: str, ok: bool, info: str):
        for row in range(self.table.rowCount()):
            # Имя может быть QTableWidgetItem или виджетом (когда есть info-текст)
            item = self.table.item(row, 0)
            widget = self.table.cellWidget(row, 0)
            row_name = ""
            if item:
                row_name = item.text()
            elif widget:
                labels = widget.findChildren(QLabel)
                if labels:
                    row_name = labels[0].text()
            # Сравниваем по folder_name (name) и по display_name
            install_dir = self.path_edit.text().strip()
            _, display_name = read_plugin_ver(install_dir, name) if install_dir else ("", "")
            if row_name not in (name, display_name or name):
                continue
            if ok:
                self.table.item(row, 1).setText(info)
                self.table.item(row, 1).setForeground(QColor(TEXT))
                self.table.item(row, 3).setText("✓ Актуально")
                self.table.item(row, 3).setForeground(QColor(GREEN))
                # Убрать кнопку «Установить»/«Обновить» — плагин теперь актуален
                self.table.removeCellWidget(row, 4)
                # Поставить кнопку «Удалить» (если её ещё нет)
                captured_name = name
                del_btn = QPushButton("Удалить")
                del_btn.setObjectName("danger")
                del_btn.setFixedHeight(28)
                del_btn.clicked.connect(lambda _, n=captured_name: self._delete_plugin(n))
                dw = QWidget()
                dw.setStyleSheet("background:transparent;")
                dl = QHBoxLayout(dw)
                dl.setContentsMargins(6, 0, 6, 0)
                dl.addWidget(del_btn)
                self.table.setCellWidget(row, 5, dw)
            else:
                self.table.item(row, 3).setText("✗ Ошибка")
                self.table.item(row, 3).setForeground(QColor(RED))
                self.table.item(row, 3).setToolTip(info)
            break

    def _on_finished(self):
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_lbl.setText("Установка завершена")
        self.status_lbl.setText("Готово")
        self.refresh_btn.setEnabled(True)

# ── Точка входа ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Иконка из встроенного base64
    import tempfile, os
    _ico_tmp = os.path.join(tempfile.gettempdir(), "c4d_installer_icon.png")
    with open(_ico_tmp, "wb") as _f:
        _f.write(base64.b64decode(ICON_B64))
    app.setWindowIcon(QIcon(_ico_tmp))

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(DARK_BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    app.setPalette(palette)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())