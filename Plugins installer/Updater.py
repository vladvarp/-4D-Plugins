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

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QFrame, QMessageBox,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QFont, QColor, QIcon, QPalette, QPixmap

# ── Конфигурация ──────────────────────────────────────────────────────────────

LIST_JSON_URL = (
    "https://raw.githubusercontent.com/vladvarp/-4D-Plugins/main/update_data/list.json"
)
CONFIG_FILE = Path(os.getenv("APPDATA")) / "C4D_PluginInstaller" / "config.json"
GIT_INSTALLER_URL = "https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe"

# ── Парсинг list.json ─────────────────────────────────────────────────────────

def parse_list(raw: str) -> list[dict]:
    """
    Парсит строки вида:
      https://github.com/.../tree/main/PluginName v1.0 {INFO}
    Возвращает список словарей: name, url, version, repo_path
    """
    plugins = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        # убираем {INFO} и подобные теги
        line = re.sub(r"\{[^}]+\}", "", line).strip()
        # последний токен вида vX.Y — версия
        m = re.search(r"\s+(v[\d.]+)\s*$", line)
        if not m:
            continue
        version = m.group(1)
        url = line[: m.start()].strip()
        # имя папки — последний сегмент URL (декодируем %20 → пробел)
        from urllib.parse import unquote
        name = unquote(url.rstrip("/").split("/")[-1])
        # путь внутри репо для sparse-checkout
        # URL вида: https://github.com/user/repo/tree/branch/path/to/folder
        parts = url.split("/tree/", 1)
        repo_url = parts[0] + ".git"
        repo_path = parts[1].split("/", 1)[1] if "/" in parts[1] else ""  # без ветки
        plugins.append(
            {"name": name, "version": version, "url": url,
             "repo_url": repo_url, "repo_path": repo_path}
        )
    return plugins

# ── Хранение конфига и состояния ──────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"install_dir": "", "installed": {}}


def save_config(cfg: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ── Git helpers ───────────────────────────────────────────────────────────────

def git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def git_install_path() -> str:
    """Ищет git.exe в реестре Windows."""
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\GitForWindows")
        path, _ = winreg.QueryValueEx(key, "InstallPath")
        return str(Path(path) / "bin" / "git.exe")
    except Exception:
        return "git"


def install_git(progress_cb, done_cb):
    """Скачивает и тихо устанавливает Git for Windows."""
    def worker():
        try:
            progress_cb("Скачиваю Git for Windows…")
            tmp = tempfile.mktemp(suffix=".exe")
            urllib.request.urlretrieve(GIT_INSTALLER_URL, tmp)
            progress_cb("Устанавливаю Git (это займёт минуту)…")
            subprocess.run(
                [tmp, "/VERYSILENT", "/NORESTART",
                 "/COMPONENTS=icons,ext\\reg\\shellhere,assoc,assoc_sh"],
                check=True
            )
            os.remove(tmp)
            done_cb(True, "Git успешно установлен")
        except Exception as e:
            done_cb(False, str(e))
    threading.Thread(target=worker, daemon=True).start()


def sparse_clone_folder(repo_url: str, folder_path: str,
                         dest: str, progress_cb) -> str:
    """
    Клонирует только нужную папку из репозитория через sparse-checkout.
    dest — куда положить итоговую папку.
    Возвращает путь к установленной папке.
    """
    git = git_install_path()
    tmp_dir = tempfile.mkdtemp()
    try:
        progress_cb(f"Инициализирую репозиторий…")
        subprocess.run([git, "init", tmp_dir], check=True, capture_output=True)
        subprocess.run([git, "-C", tmp_dir, "remote", "add", "origin", repo_url],
                       check=True, capture_output=True)
        subprocess.run([git, "-C", tmp_dir, "config",
                        "core.sparseCheckout", "true"],
                       check=True, capture_output=True)

        sparse_file = Path(tmp_dir) / ".git" / "info" / "sparse-checkout"
        sparse_file.write_text(folder_path + "/\n", encoding="utf-8")

        progress_cb(f"Скачиваю папку {folder_path}…")
        subprocess.run([git, "-C", tmp_dir, "pull", "--depth=1",
                        "origin", "main"],
                       check=True, capture_output=True)

        src = Path(tmp_dir) / folder_path
        if not src.exists():
            raise FileNotFoundError(f"Папка {folder_path} не найдена в репозитории")

        target = Path(dest) / src.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
        return str(target)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# ── Worker-поток ──────────────────────────────────────────────────────────────

class InstallWorker(QThread):
    progress = pyqtSignal(str, int)   # (сообщение, % или -1 для индетерминации)
    plugin_done = pyqtSignal(str, bool, str)   # (name, ok, message)
    finished = pyqtSignal()

    def __init__(self, plugins: list[dict], install_dir: str, config: dict):
        super().__init__()
        self.plugins = plugins
        self.install_dir = install_dir
        self.config = config

    def run(self):
        for i, p in enumerate(self.plugins):
            name = p["name"]
            self.progress.emit(f"Устанавливаю {name}…", -1)
            try:
                sparse_clone_folder(
                    p["repo_url"], p["repo_path"],
                    self.install_dir,
                    lambda msg: self.progress.emit(msg, -1)
                )
                self.config["installed"][name] = {"version": p["version"]}
                save_config(self.config)
                self.plugin_done.emit(name, True, p["version"])
            except Exception as e:
                self.plugin_done.emit(name, False, str(e))
        self.finished.emit()

# ── Главное окно ──────────────────────────────────────────────────────────────

DARK_BG   = "#141414"
PANEL_BG  = "#1e1e1e"
BORDER    = "#2d2d2d"
ACCENT    = "#e8622a"        # оранжевый как C4D
TEXT      = "#e8e8e8"
TEXT_DIM  = "#888888"
GREEN     = "#4caf6e"
RED       = "#e05c5c"
YELLOW    = "#e0a94e"

STYLE = f"""
QMainWindow, QWidget#root {{
    background: {DARK_BG};
}}
QLabel {{
    color: {TEXT};
    background: transparent;
}}
QLabel#dim {{
    color: {TEXT_DIM};
    font-size: 11px;
}}
QLabel#title {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT};
    letter-spacing: 1px;
}}
QLabel#subtitle {{
    font-size: 11px;
    color: {TEXT_DIM};
    letter-spacing: 2px;
    text-transform: uppercase;
}}
QLabel#accent {{
    color: {ACCENT};
    font-size: 22px;
    font-weight: 700;
}}
QPushButton {{
    background: {PANEL_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
}}
QPushButton:hover {{
    background: #2a2a2a;
    border-color: #444;
}}
QPushButton:pressed {{
    background: #111;
}}
QPushButton#primary {{
    background: {ACCENT};
    color: white;
    border: none;
    font-weight: 600;
    font-size: 13px;
    padding: 10px 24px;
}}
QPushButton#primary:hover {{
    background: #f07040;
}}
QPushButton#primary:disabled {{
    background: #5a3020;
    color: #aa7060;
}}
QPushButton#small {{
    padding: 5px 12px;
    font-size: 11px;
    border-radius: 4px;
}}
QLineEdit {{
    background: {PANEL_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 10px;
    font-size: 12px;
    font-family: Consolas;
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QTableWidget {{
    background: {PANEL_BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    gridline-color: {BORDER};
    font-size: 12px;
    outline: none;
}}
QTableWidget::item {{
    padding: 8px 10px;
    border: none;
}}
QTableWidget::item:selected {{
    background: #2a2a2a;
    color: {TEXT};
}}
QHeaderView::section {{
    background: #181818;
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QProgressBar {{
    background: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}
QFrame#divider {{
    background: {BORDER};
    max-height: 1px;
}}
QScrollBar:vertical {{
    background: {PANEL_BG};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: #444;
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("4D Plugin Installer")
        self.setMinimumSize(780, 580)
        self.resize(860, 620)

        self.config = load_config()
        self.remote_plugins: list[dict] = []
        self.worker: InstallWorker | None = None

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_path_bar())

        divider = QFrame()
        divider.setObjectName("divider")
        layout.addWidget(divider)

        layout.addWidget(self._build_table_area(), stretch=1)
        layout.addWidget(self._build_bottom_bar())

        self.setStyleSheet(STYLE)

        # Если путь уже сохранён — сразу проверяем
        if self.config.get("install_dir"):
            self.path_edit.setText(self.config["install_dir"])
            QTimer.singleShot(300, self._check_updates)

    # ── Секции UI ──────────────────────────────────────────────────────────────

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(64)
        w.setStyleSheet(f"background: #1a1a1a; border-bottom: 1px solid {BORDER};")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 0, 24, 0)

        badge = QLabel("4D")
        badge.setStyleSheet(
            f"background: {ACCENT}; color: white; font-size: 14px; font-weight: 800;"
            "padding: 4px 10px; border-radius: 5px; letter-spacing: 1px;"
        )
        h.addWidget(badge)
        h.addSpacing(12)

        title = QLabel("Plugin Installer")
        title.setObjectName("title")
        title.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {TEXT};")
        h.addWidget(title)

        h.addStretch()

        self.status_label = QLabel("Готов к работе")
        self.status_label.setObjectName("dim")
        h.addWidget(self.status_label)

        return w

    def _build_path_bar(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(62)
        w.setStyleSheet(f"background: {DARK_BG};")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 10, 24, 10)
        h.setSpacing(10)

        lbl = QLabel("Папка плагинов C4D:")
        lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; min-width: 140px;")
        h.addWidget(lbl)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(
            r"Например: C:\Users\...\AppData\Roaming\Maxon\...\plugins"
        )
        if self.config.get("install_dir"):
            self.path_edit.setText(self.config["install_dir"])
        h.addWidget(self.path_edit, stretch=1)

        browse_btn = QPushButton("Обзор…")
        browse_btn.setObjectName("small")
        browse_btn.clicked.connect(self._browse_dir)
        h.addWidget(browse_btn)

        return w

    def _build_table_area(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {DARK_BG};")
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 16, 24, 0)
        v.setSpacing(10)

        # Заголовок + кнопка
        row = QHBoxLayout()
        sec_label = QLabel("ПЛАГИНЫ")
        sec_label.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; font-weight: 700; letter-spacing: 2px;"
        )
        row.addWidget(sec_label)
        row.addStretch()

        self.refresh_btn = QPushButton("↻  Проверить обновления")
        self.refresh_btn.setObjectName("small")
        self.refresh_btn.clicked.connect(self._check_updates)
        row.addWidget(self.refresh_btn)

        v.addLayout(row)

        # Таблица
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Плагин", "Установлено", "На GitHub", "Статус"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 160)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        v.addWidget(self.table)

        return w

    def _build_bottom_bar(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(70)
        w.setStyleSheet(f"background: #181818; border-top: 1px solid {BORDER};")
        h = QHBoxLayout(w)
        h.setContentsMargins(24, 0, 24, 0)
        h.setSpacing(16)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(5)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")

        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(self.progress_label)
        left.addWidget(self.progress_bar)
        h.addLayout(left, stretch=1)

        self.install_btn = QPushButton("⬇  Установить / обновить")
        self.install_btn.setObjectName("primary")
        self.install_btn.setFixedHeight(42)
        self.install_btn.setEnabled(False)
        self.install_btn.clicked.connect(self._start_install)
        h.addWidget(self.install_btn)

        return w

    # ── Логика ─────────────────────────────────────────────────────────────────

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Выберите папку плагинов Cinema 4D",
            self.path_edit.text() or "C:\\"
        )
        if d:
            self.path_edit.setText(d)
            self.config["install_dir"] = d
            save_config(self.config)

    def _set_status(self, msg: str):
        self.status_label.setText(msg)

    def _check_updates(self):
        # Сохраняем путь
        install_dir = self.path_edit.text().strip()
        if install_dir:
            self.config["install_dir"] = install_dir
            save_config(self.config)

        self.refresh_btn.setEnabled(False)
        self.install_btn.setEnabled(False)
        self._set_status("Загружаю список плагинов…")
        self.progress_bar.setVisible(True)
        self.progress_label.setText("Подключаюсь к GitHub…")

        def worker():
            try:
                req = urllib.request.Request(
                    LIST_JSON_URL, headers={"User-Agent": "C4D-Installer/1.0"}
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    raw = r.read().decode("utf-8")
                plugins = parse_list(raw)
                # передаём в главный поток
                self._on_list_loaded(plugins, None)
            except Exception as e:
                self._on_list_loaded([], str(e))

        # Запускаем в отдельном потоке, результат через QTimer (простой способ)
        self._pending_result = None
        t = threading.Thread(target=worker, daemon=True)
        t.start()

        def poll():
            if t.is_alive():
                QTimer.singleShot(100, poll)
            # _on_list_loaded уже вызван из worker через безопасный костыль ниже
        # Безопасный вызов из потока — используем атрибут
        QTimer.singleShot(100, poll)

    def _on_list_loaded(self, plugins: list, error: str | None):
        # Вызывается из потока — откладываем на main loop
        self._pending_plugins = plugins
        self._pending_error = error
        QTimer.singleShot(0, self._apply_list)

    def _apply_list(self):
        self.progress_bar.setVisible(False)
        self.refresh_btn.setEnabled(True)

        if self._pending_error:
            self._set_status(f"Ошибка: {self._pending_error}")
            self.progress_label.setText(f"Не удалось загрузить список: {self._pending_error}")
            return

        self.remote_plugins = self._pending_plugins
        self._populate_table()

    def _populate_table(self):
        installed = self.config.get("installed", {})
        self.table.setRowCount(0)
        needs_update = 0

        for p in self.remote_plugins:
            name = p["name"]
            remote_ver = p["version"]
            local_info = installed.get(name, {})
            local_ver = local_info.get("version", "")

            row = self.table.rowCount()
            self.table.insertRow(row)

            # Имя
            self.table.setItem(row, 0, QTableWidgetItem(name))

            # Локальная версия
            loc_item = QTableWidgetItem(local_ver or "не установлен")
            loc_item.setForeground(QColor(TEXT_DIM if not local_ver else TEXT))
            self.table.setItem(row, 1, loc_item)

            # Remote версия
            rem_item = QTableWidgetItem(remote_ver)
            self.table.setItem(row, 2, rem_item)

            # Статус
            outdated = not local_ver or local_ver != remote_ver
            if outdated:
                needs_update += 1
                status = "⬆ Нужно обновить" if local_ver else "✦ Не установлен"
                color = YELLOW if local_ver else ACCENT
            else:
                status = "✓ Актуально"
                color = GREEN

            st_item = QTableWidgetItem(status)
            st_item.setForeground(QColor(color))
            self.table.setItem(row, 3, st_item)

            self.table.setRowHeight(row, 44)

        if needs_update:
            self.install_btn.setEnabled(True)
            self._set_status(f"Найдено: {len(self.remote_plugins)} плагинов, требуют обновления: {needs_update}")
            self.progress_label.setText(f"Готово к установке: {needs_update} плагин(ов)")
        else:
            self._set_status("Все плагины актуальны")
            self.progress_label.setText("Всё актуально")

    def _start_install(self):
        install_dir = self.path_edit.text().strip()
        if not install_dir:
            QMessageBox.warning(self, "Укажите папку",
                                "Выберите папку плагинов Cinema 4D перед установкой.")
            return

        if not os.path.exists(install_dir):
            try:
                os.makedirs(install_dir)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось создать папку:\n{e}")
                return

        # Проверяем Git
        if not git_available():
            reply = QMessageBox.question(
                self, "Git не найден",
                "Git не установлен на этом компьютере.\n"
                "Установить Git for Windows автоматически?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.install_btn.setEnabled(False)
                self.progress_bar.setVisible(True)

                def on_git_done(ok, msg):
                    if ok:
                        self.progress_label.setText("Git установлен. Запускаю установку плагинов…")
                        QTimer.singleShot(500, self._run_install_worker)
                    else:
                        self.progress_label.setText(f"Ошибка установки Git: {msg}")
                        self.install_btn.setEnabled(True)

                install_git(
                    lambda msg: QTimer.singleShot(0, lambda m=msg:
                                                  self.progress_label.setText(m)),
                    lambda ok, msg: QTimer.singleShot(0, lambda: on_git_done(ok, msg))
                )
            return

        self._run_install_worker()

    def _run_install_worker(self):
        install_dir = self.path_edit.text().strip()
        installed = self.config.get("installed", {})
        to_install = [
            p for p in self.remote_plugins
            if installed.get(p["name"], {}).get("version", "") != p["version"]
        ]

        if not to_install:
            return

        self.install_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.worker = InstallWorker(to_install, install_dir, self.config)
        self.worker.progress.connect(
            lambda msg, _: self.progress_label.setText(msg)
        )
        self.worker.plugin_done.connect(self._on_plugin_done)
        self.worker.finished.connect(self._on_install_finished)
        self.worker.start()

    def _on_plugin_done(self, name: str, ok: bool, info: str):
        installed = self.config.get("installed", {})
        # Обновляем строку в таблице
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).text() == name:
                if ok:
                    self.table.item(row, 1).setText(info)
                    self.table.item(row, 1).setForeground(QColor(TEXT))
                    self.table.item(row, 3).setText("✓ Актуально")
                    self.table.item(row, 3).setForeground(QColor(GREEN))
                else:
                    self.table.item(row, 3).setText("✗ Ошибка")
                    self.table.item(row, 3).setForeground(QColor(RED))
                    self.table.item(row, 3).setToolTip(info)
                break

    def _on_install_finished(self):
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.progress_label.setText("Установка завершена")
        self._set_status("Готово")
        self.install_btn.setEnabled(False)
        self.refresh_btn.setEnabled(True)
        QMessageBox.information(self, "Готово", "Плагины успешно установлены!")


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