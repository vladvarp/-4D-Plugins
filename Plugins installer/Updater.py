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
from urllib.parse import unquote

import ctypes

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
    "https://raw.githubusercontent.com/vladvarp/-4D-Plugins/main/update_data/list.json"
)
CONFIG_FILE = Path(os.getenv("APPDATA")) / "C4D_PluginInstaller" / "config.json"
GIT_INSTALLER_URL = (
    "https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe"
)

# ── Иконка приложения (PNG 256×256, base64) ───────────────────────────────────

ICON_B64 = (
    "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"
)

# ── Парсинг list.json ─────────────────────────────────────────────────────────

def parse_list(raw: str) -> list[dict]:
    """
    Парсит строки вида:
      https://github.com/.../tree/main/PluginName%20X v1.0 {INFO}
    repo_path — декодированный путь (пробелы вместо %20)
    """
    plugins = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # Извлекаем текст из фигурных скобок {INFO} перед удалением
        info_match = re.search(r"\{([^}]+)\}", line)
        info_text = info_match.group(1).strip() if info_match else ""

        # Вычленяем url: из info_text, если есть
        info_url = ""
        if info_text:
            url_match = re.search(r"(?:^|[\s,;]*)url:\s*(https?://\S+)", info_text)
            if url_match:
                info_url = url_match.group(1).strip()
                # Убираем «url: <адрес>» из текста, оставляем остальное
                info_text = re.sub(r"(?:^|[\s,;]*)url:\s*https?://\S+", "", info_text).strip().strip(",;.")

        line = re.sub(r"\{[^}]+\}", "", line).strip()
        m = re.search(r"\s+(v[\d.]+)\s*$", line)
        if not m:
            continue
        version = m.group(1)
        url = line[: m.start()].strip()

        # Имя папки — последний сегмент URL, декодированный
        name = unquote(url.rstrip("/").split("/")[-1])

        # Разбираем: https://github.com/user/repo/tree/branch/path/to/folder
        parts = url.split("/tree/", 1)
        if len(parts) < 2:
            continue
        repo_url = parts[0] + ".git"
        # parts[1] = "main/path/to/folder" → убираем ветку
        after_branch = parts[1].split("/", 1)
        # repo_path ДЕКОДИРУЕМ — git sparse-checkout требует реальные имена
        repo_path = unquote(after_branch[1]) if len(after_branch) > 1 else unquote(after_branch[0])

        plugins.append({
            "name": name,
            "version": version,
            "url": url,
            "repo_url": repo_url,
            "repo_path": repo_path,   # «VAr Tools», не «VAr%20Tools»
            "info": info_text,         # текст из {}, например «Пакет VAr Tools»
            "info_url": info_url,      # url: из {}, если указан
        })
    return plugins

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

def install_git(progress_cb, done_cb):
    def worker():
        try:
            progress_cb("Скачиваю Git for Windows…")
            tmp = tempfile.mktemp(suffix=".exe")
            urllib.request.urlretrieve(GIT_INSTALLER_URL, tmp)
            progress_cb("Устанавливаю Git (подождите)…")
            _run(
                [tmp, "/VERYSILENT", "/NORESTART",
                 "/COMPONENTS=icons,ext\\reg\\shellhere,assoc,assoc_sh"],
                check=True
            )
            os.remove(tmp)
            done_cb(True, "Git установлен")
        except Exception as e:
            done_cb(False, str(e))
    threading.Thread(target=worker, daemon=True).start()

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
                    f"Папка «{folder_path}» не найдена в репозитории. "
                    f"Проверьте правильность пути в list.json."
                )

        target = Path(dest) / src.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
        return str(target)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

def read_plugin_ver(install_dir: str, name: str) -> str:
    """Читает версию плагина из файла 'ver' (без расширения) внутри папки плагина."""
    ver_file = Path(install_dir) / name / "ver"
    if ver_file.exists():
        return ver_file.read_text(encoding="utf-8").strip()
    return ""

def write_plugin_ver(install_dir: str, name: str, version: str):
    """Записывает версию плагина в файл 'ver' (без расширения) внутри папки плагина."""
    ver_file = Path(install_dir) / name / "ver"
    ver_file.write_text(version, encoding="utf-8")

def remove_plugin_folder(install_dir: str, name: str):
    target = Path(install_dir) / name
    if target.exists():
        shutil.rmtree(target)

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
                # Записываем файл 'ver' в папку плагина
                write_plugin_ver(self.install_dir, name, p["version"])
                self.config["installed"][name] = {"version": p["version"]}
                save_config(self.config)
                self.plugin_done.emit(name, True, p["version"])
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
"""

# ── Главное окно ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("4D Plugin Installer")
        self.setMinimumSize(820, 560)
        self.resize(900, 620)

        self.config = load_config()
        self.remote_plugins: list[dict] = []
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

        badge = QLabel("4D")
        badge.setStyleSheet(
            f"background:{ACCENT}; color:white; font-size:14px; font-weight:800;"
            "padding:4px 10px; border-radius:5px; letter-spacing:1px;"
        )
        h.addWidget(badge)
        h.addSpacing(12)

        title = QLabel("Plugin Installer")
        title.setStyleSheet(f"font-size:18px; font-weight:700; color:{TEXT};")
        h.addWidget(title)
        h.addStretch()

        self.status_lbl = QLabel("Готов к работе")
        self.status_lbl.setStyleSheet(f"font-size:11px; color:{DIM};")
        h.addWidget(self.status_lbl)

        h.addSpacing(12)
        readme_btn = QPushButton("О плагинах")
        readme_btn.setFixedHeight(30)
        readme_btn.setObjectName("readme")
        readme_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/vladvarp/-4D-Plugins?tab=readme-ov-file#readme")
        ))
        h.addWidget(readme_btn)
        return w

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

        self.refresh_btn = QPushButton("↻  Проверить")
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.clicked.connect(self._check_updates)
        row.addWidget(self.refresh_btn)
        v.addLayout(row)

        # Таблица: Плагин | Установлено | На GitHub | Статус | Действие | Удалить
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Плагин", "Текущая версия", "Актуальная версия", "Статус", "", ""])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 115)
        self.table.setColumnWidth(2, 135)
        self.table.setColumnWidth(3, 125)
        self.table.setColumnWidth(4, 120)  # Установить / Обновить
        self.table.setColumnWidth(5, 115)  # Удалить
        self.table.verticalHeader().setVisible(False)
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

    def _on_path_edited(self):
        """Вызывается когда пользователь вручную ввёл путь и убрал фокус с поля."""
        d = self.path_edit.text().strip()
        if d:
            self.config["install_dir"] = d
            save_config(self.config)
            # Перечитываем таблицу с новой папкой (версии из файлов 'ver')
            if self.remote_plugins:
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
            if self.remote_plugins:
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
            try:
                req = urllib.request.Request(
                    LIST_JSON_URL, headers={"User-Agent": "C4D-Installer/1.0"}
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    raw = r.read().decode("utf-8")
                plugins = parse_list(raw)
                self._pending = (plugins, None)
            except Exception as e:
                self._pending = ([], str(e))

        self._pending = None
        t = threading.Thread(target=worker, daemon=True)
        t.start()

        def poll():
            if self._pending is None:
                QTimer.singleShot(80, poll)
            else:
                plugins, err = self._pending
                self.progress_bar.setVisible(False)
                self.refresh_btn.setEnabled(True)
                if err:
                    self.status_lbl.setText("Ошибка")
                    self.progress_lbl.setText(f"Не удалось загрузить список: {err}")
                else:
                    self.remote_plugins = plugins
                    self._populate_table()
        QTimer.singleShot(80, poll)

    def _populate_table(self):
        self.table.setRowCount(0)
        install_dir = self.path_edit.text().strip()
        needs = 0

        for p in self.remote_plugins:
            name = p["name"]
            remote_ver = p["version"]
            # Версию читаем из файла 'ver' в папке плагина (актуально при смене папки)
            local_ver = read_plugin_ver(install_dir, name) if install_dir else ""
            outdated = not local_ver or local_ver != remote_ver

            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 46)

            # Имя + info из {}
            name_item = QTableWidgetItem(name)
            if p.get("info") or p.get("info_url"):
                name_item.setToolTip(p.get("info", "") or p.get("info_url", ""))
                # Показываем info как подсказку прямо в ячейке через виджет
                name_widget = QWidget()
                name_widget.setStyleSheet("background:transparent;")
                nw_lay = QVBoxLayout(name_widget)
                nw_lay.setContentsMargins(10, 2, 6, 2)
                nw_lay.setSpacing(1)
                lbl_name = QLabel(name)
                lbl_name.setStyleSheet(f"color:{TEXT}; font-size:12px; background:transparent;")
                nw_lay.addWidget(lbl_name)
                # Строка под именем: текст (если есть) + ссылка «Подробнее» (если есть url)
                if p.get("info") or p.get("info_url"):
                    sub_lay = QHBoxLayout()
                    sub_lay.setContentsMargins(0, 0, 0, 0)
                    sub_lay.setSpacing(4)
                    if p.get("info"):
                        lbl_info = QLabel(p["info"])
                        lbl_info.setStyleSheet(f"color:{DIM}; font-size:10px; background:transparent;")
                        sub_lay.addWidget(lbl_info)
                    if p.get("info_url"):
                        lbl_link = QLabel(f'<a href="{p["info_url"]}" style="color:#5b9bd5; font-size:10px;">Подробнее...</a>')
                        lbl_link.setOpenExternalLinks(True)
                        lbl_link.setStyleSheet("background:transparent;")
                        sub_lay.addWidget(lbl_link)
                    sub_lay.addStretch()
                    nw_lay.addLayout(sub_lay)
                self.table.setCellWidget(row, 0, name_widget)
            else:
                self.table.setItem(row, 0, name_item)

            # Локальная версия
            loc = QTableWidgetItem(local_ver or "не установлен")
            loc.setForeground(QColor(DIM if not local_ver else TEXT))
            self.table.setItem(row, 1, loc)

            # Remote версия
            self.table.setItem(row, 2, QTableWidgetItem(remote_ver))

            # Статус
            if outdated:
                needs += 1
                status_text = "Есть обновление" if local_ver else ""
                status_color = YELLOW if local_ver else ACCENT
            else:
                status_text = "✓ Актуально"
                status_color = GREEN
            st = QTableWidgetItem(status_text)
            st.setForeground(QColor(status_color))
            self.table.setItem(row, 3, st)

            # Кнопка «Установить» или «Обновить» для одиночной установки
            if outdated:
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

            # Кнопка удалить (только если установлен)
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

        if needs:
            self.status_lbl.setText(f"Требуют обновления: {needs}")
            self.progress_lbl.setText("Нажмите «Установить» или «Обновить» напротив нужного плагина")
        else:
            self.status_lbl.setText("Всё актуально")
            self.progress_lbl.setText("Все плагины актуальны")

    def _install_single(self, plugin: dict):
        """Устанавливает/обновляет один плагин по кнопке в строке таблицы."""
        install_dir = self.path_edit.text().strip()
        if not install_dir:
            QMessageBox.warning(self, "Укажите папку", "Выберите папку плагинов Cinema 4D.")
            return
        os.makedirs(install_dir, exist_ok=True)

        if not git_available():
            QMessageBox.warning(self, "Git не найден",
                                "Git не установлен. Нажмите «Установить выбранные» для автоустановки Git.")
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
            if row_name != name:
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