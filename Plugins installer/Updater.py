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
from pathlib import Path
from urllib.parse import unquote

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QFrame, QMessageBox,
    QCheckBox, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPalette, QCursor

# ── Конфигурация ──────────────────────────────────────────────────────────────

LIST_JSON_URL = (
    "https://raw.githubusercontent.com/vladvarp/-4D-Plugins/main/update_data/list.json"
)
CONFIG_FILE = Path(os.getenv("APPDATA")) / "C4D_PluginInstaller" / "config.json"
GIT_INSTALLER_URL = (
    "https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe"
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
        subprocess.run(["git", "--version"], capture_output=True, check=True)
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
            subprocess.run(
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
        subprocess.run([git, "init", tmp_dir], check=True, capture_output=True)
        subprocess.run([git, "-C", tmp_dir, "remote", "add", "origin", repo_url],
                       check=True, capture_output=True)
        subprocess.run([git, "-C", tmp_dir, "config", "core.sparseCheckout", "true"],
                       check=True, capture_output=True)

        sparse_file = Path(tmp_dir) / ".git" / "info" / "sparse-checkout"
        # Записываем декодированный путь — git понимает пробелы
        sparse_file.write_text(folder_path + "/\n", encoding="utf-8")

        progress_cb(f"Скачиваю «{folder_path}»…")
        result = subprocess.run(
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
        self._row_checks: list[QCheckBox] = []   # чекбоксы строк

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

        self.select_all_btn = QPushButton("Выбрать все")
        self.select_all_btn.setFixedHeight(30)
        self.select_all_btn.clicked.connect(self._select_all)
        row.addWidget(self.select_all_btn)

        self.deselect_btn = QPushButton("Снять все")
        self.deselect_btn.setFixedHeight(30)
        self.deselect_btn.clicked.connect(self._deselect_all)
        row.addWidget(self.deselect_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background:{BORDER}; max-width:1px; margin:4px 4px;")
        row.addWidget(sep)

        self.refresh_btn = QPushButton("↻  Проверить")
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.clicked.connect(self._check_updates)
        row.addWidget(self.refresh_btn)
        v.addLayout(row)

        # Таблица: чекбокс | Плагин | Установлено | На GitHub | Статус | Действие | Удалить
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["", "Плагин", "Установлено", "На GitHub", "Статус", "", ""])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 44)
        self.table.setColumnWidth(2, 115)
        self.table.setColumnWidth(3, 115)
        self.table.setColumnWidth(4, 155)
        self.table.setColumnWidth(5, 130)  # Установить / Обновить
        self.table.setColumnWidth(6, 120)  # Удалить
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

        self.install_btn = QPushButton("⬇  Установить выбранные")
        self.install_btn.setObjectName("primary")
        self.install_btn.setFixedHeight(40)
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.connect(self._start_install)
        h.addWidget(self.install_btn)
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

    def _select_all(self):
        for cb in self._row_checks:
            cb.setChecked(True)
        self._update_install_btn()

    def _deselect_all(self):
        for cb in self._row_checks:
            cb.setChecked(False)
        self._update_install_btn()

    def _update_install_btn(self):
        any_checked = any(cb.isChecked() for cb in self._row_checks)
        self.install_btn.setEnabled(any_checked)

    def _check_updates(self):
        d = self.path_edit.text().strip()
        if d:
            self.config["install_dir"] = d
            save_config(self.config)

        self.refresh_btn.setEnabled(False)
        self.install_btn.setEnabled(False)
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
        self._row_checks.clear()
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

            # Чекбокс
            cb_widget = QWidget()
            cb_widget.setStyleSheet("background:transparent;")
            cb_lay = QHBoxLayout(cb_widget)
            cb_lay.setContentsMargins(0, 0, 0, 0)
            cb_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb = QCheckBox()
            cb.setChecked(False)  # галочки сняты по умолчанию
            cb.stateChanged.connect(self._update_install_btn)
            cb_lay.addWidget(cb)
            self._row_checks.append(cb)
            self.table.setCellWidget(row, 0, cb_widget)

            # Имя + info из {}
            name_item = QTableWidgetItem(name)
            if p.get("info"):
                name_item.setToolTip(p["info"])
                # Показываем info как подсказку прямо в ячейке через виджет
                name_widget = QWidget()
                name_widget.setStyleSheet("background:transparent;")
                nw_lay = QVBoxLayout(name_widget)
                nw_lay.setContentsMargins(10, 2, 6, 2)
                nw_lay.setSpacing(1)
                lbl_name = QLabel(name)
                lbl_name.setStyleSheet(f"color:{TEXT}; font-size:12px; background:transparent;")
                lbl_info = QLabel(p["info"])
                lbl_info.setStyleSheet(f"color:{DIM}; font-size:10px; background:transparent;")
                nw_lay.addWidget(lbl_name)
                nw_lay.addWidget(lbl_info)
                self.table.setCellWidget(row, 1, name_widget)
            else:
                self.table.setItem(row, 1, name_item)

            # Локальная версия
            loc = QTableWidgetItem(local_ver or "не установлен")
            loc.setForeground(QColor(DIM if not local_ver else TEXT))
            self.table.setItem(row, 2, loc)

            # Remote версия
            self.table.setItem(row, 3, QTableWidgetItem(remote_ver))

            # Статус
            if outdated:
                needs += 1
                status_text = "⬆ Нужно обновить" if local_ver else "✦ Не установлен"
                status_color = YELLOW if local_ver else ACCENT
            else:
                status_text = "✓ Актуально"
                status_color = GREEN
            st = QTableWidgetItem(status_text)
            st.setForeground(QColor(status_color))
            self.table.setItem(row, 4, st)

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
                self.table.setCellWidget(row, 5, aw)

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
                self.table.setCellWidget(row, 6, dw)

        if needs:
            self.status_lbl.setText(f"Требуют обновления: {needs}")
            self.progress_lbl.setText(f"Отметьте нужные плагины и нажмите «Установить выбранные»")
        else:
            self.status_lbl.setText("Всё актуально")
            self.progress_lbl.setText("Все плагины актуальны")

        self._update_install_btn()

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

    def _start_install(self):
        install_dir = self.path_edit.text().strip()
        if not install_dir:
            QMessageBox.warning(self, "Укажите папку", "Выберите папку плагинов Cinema 4D.")
            return
        os.makedirs(install_dir, exist_ok=True)

        # Собираем только отмеченные
        to_install = []
        for i, cb in enumerate(self._row_checks):
            if cb.isChecked() and i < len(self.remote_plugins):
                to_install.append(self.remote_plugins[i])

        if not to_install:
            return

        if not git_available():
            reply = QMessageBox.question(
                self, "Git не найден",
                "Git не установлен. Установить Git for Windows автоматически?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.install_btn.setEnabled(False)
                self.progress_bar.setVisible(True)

                def on_git_done(ok, msg):
                    if ok:
                        self.progress_lbl.setText("Git установлен. Запускаю установку…")
                        QTimer.singleShot(300, lambda: self._run_worker(to_install, install_dir))
                    else:
                        self.progress_lbl.setText(f"Ошибка установки Git: {msg}")
                        self.install_btn.setEnabled(True)

                install_git(
                    lambda msg: QTimer.singleShot(0, lambda m=msg: self.progress_lbl.setText(m)),
                    lambda ok, msg: QTimer.singleShot(0, lambda: on_git_done(ok, msg))
                )
            return

        self._run_worker(to_install, install_dir)

    def _run_worker(self, to_install, install_dir):
        self.install_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
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
            item = self.table.item(row, 1)
            widget = self.table.cellWidget(row, 1)
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
                self.table.item(row, 2).setText(info)
                self.table.item(row, 2).setForeground(QColor(TEXT))
                self.table.item(row, 4).setText("✓ Актуально")
                self.table.item(row, 4).setForeground(QColor(GREEN))
                # Снять чекбокс
                cw = self.table.cellWidget(row, 0)
                if cw:
                    for ch in cw.findChildren(QCheckBox):
                        ch.setChecked(False)
                # Убрать кнопку «Установить»/«Обновить» — плагин теперь актуален
                self.table.removeCellWidget(row, 5)
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
                self.table.setCellWidget(row, 6, dw)
            else:
                self.table.item(row, 4).setText("✗ Ошибка")
                self.table.item(row, 4).setForeground(QColor(RED))
                self.table.item(row, 4).setToolTip(info)
            break

    def _on_finished(self):
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_lbl.setText("Установка завершена")
        self.status_lbl.setText("Готово")
        self.refresh_btn.setEnabled(True)
        self._update_install_btn()
        QMessageBox.information(self, "Готово", "Выбранные плагины установлены!")

# ── Точка входа ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(DARK_BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    app.setPalette(palette)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())