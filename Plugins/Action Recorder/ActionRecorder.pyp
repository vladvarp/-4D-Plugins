# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ACTION RECORDER  —  Cinema 4D  R20+                                 ║
║          Аналог экшонов Photoshop для Cinema 4D                              ║
║                                                                              ║
║  3 кнопки в меню плагинов:                                                   ║
║   1. «Лог событий»  — плавающее окно с записью всех команд в виде кода       ║
║   2. «Менеджер экшонов» — создание, удаление, запуск, коллекции              ║
║   3. «Воспроизвести последний» — быстрый запуск последнего экшона            ║
║                                                                              ║
║  Экшоны хранятся в:                                                          ║
║    ~/Documents/ActionRecorder/<Коллекция>/<action>.py                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import c4d  # type: ignore
from c4d import gui  # type: ignore
import os
import sys
import json
import base64
import tempfile
import datetime
import traceback

# ─── ID плагинов ──────────────────────────────────────────────────────────────
PLUGIN_ID_MANAGER   = 1069095   # Менеджер экшонов
PLUGIN_ID_PLAYBACK  = 1069096   # Воспроизвести последний
PLUGIN_ID_LOG       = 1069097   # Лог событий

# ─── ID элементов GUI ─────────────────────────────────────────────────────────
# Лог-диалог
ID_LOG_TEXT         = 10001
ID_LOG_BTN_CLEAR    = 10002
ID_LOG_BTN_SAVE     = 10003
ID_LOG_BTN_RECORD   = 10004
ID_LOG_STATUS       = 10005
ID_LOG_SCROLL       = 10006
ID_LOG_GROUP        = 10007

# Менеджер
ID_MGR_COLLECTION   = 11001
ID_MGR_BTN_NEW_COL  = 11002
ID_MGR_BTN_DEL_COL  = 11003
ID_MGR_ACTION_LIST  = 11010
ID_MGR_BTN_NEW_ACT  = 11011
ID_MGR_BTN_DEL_ACT  = 11012
ID_MGR_BTN_RUN_ACT  = 11013
ID_MGR_BTN_RENAME   = 11014
ID_MGR_BTN_IMPORT   = 11015
ID_MGR_BTN_RECORD   = 11016   # Кнопка старт/стоп записи в менеджере
ID_MGR_NAME_FIELD   = 11020
ID_MGR_STATUS       = 11030
ID_MGR_SCROLL       = 11040
ID_MGR_LIST_GROUP   = 11041
ID_MGR_CODE_SCROLL  = 11050
ID_MGR_CODE_TEXT    = 11051

ROW_STRIDE          = 10
ACTION_ROW_BASE     = 12000

# ─── Иконки Base64 ────────────────────────────────────────────────────────────
ICON_LOG_B64      = "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"
ICON_MANAGER_B64  = "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"
ICON_PLAY_B64     = "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"

# ─── Хранилище событий ────────────────────────────────────────────────────────
DEFAULT_COLLECTION = "Коллекция"
ROOT_DIR_NAME      = "ActionRecorder"

_event_log = []          # список кортежей (время_строка, строка_кода)
_is_recording = False    # режим записи


def _get_root_dir():
    """Возвращает путь к корневой папке ~/Documents/ActionRecorder."""
    home = os.path.expanduser("~")
    docs_candidates = [
        os.path.join(home, "Documents"),
        os.path.join(home, "Документы"),
        home,
    ]
    for d in docs_candidates:
        if os.path.isdir(d):
            root = os.path.join(d, ROOT_DIR_NAME)
            break
    else:
        root = os.path.join(home, ROOT_DIR_NAME)
    os.makedirs(root, exist_ok=True)
    return root


def _get_collection_dir(collection_name):
    path = os.path.join(_get_root_dir(), collection_name)
    os.makedirs(path, exist_ok=True)
    return path


def _list_collections():
    root = _get_root_dir()
    cols = [d for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))]
    if not cols:
        _get_collection_dir(DEFAULT_COLLECTION)
        cols = [DEFAULT_COLLECTION]
    return sorted(cols)


def _list_actions(collection_name):
    col_dir = _get_collection_dir(collection_name)
    return sorted([
        f[:-3] for f in os.listdir(col_dir) if f.endswith(".py")
    ])


def _action_path(collection_name, action_name):
    return os.path.join(_get_collection_dir(collection_name),
                        action_name + ".py")


def _save_action(collection_name, action_name, code):
    path = _action_path(collection_name, action_name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path


def _load_action(collection_name, action_name):
    path = _action_path(collection_name, action_name)
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _delete_action(collection_name, action_name):
    path = _action_path(collection_name, action_name)
    if os.path.isfile(path):
        os.remove(path)


def _run_action_code(code):
    """Выполняет строку кода Python с доступом к c4d и активному документу."""
    doc = c4d.documents.GetActiveDocument()
    ctx = {
        "c4d": c4d,
        "doc": doc,
        "__name__": "__action__",
    }
    try:
        exec(compile(code, "<action>", "exec"), ctx)  # noqa: S102
        c4d.EventAdd()
        return True, ""
    except Exception:
        return False, traceback.format_exc()


def _get_last_action_path():
    """Возвращает путь к последнему записанному экшону (info-файл)."""
    return os.path.join(_get_root_dir(), "_last_action.json")


def _save_last_info(collection, action):
    info = {"collection": collection, "action": action}
    with open(_get_last_action_path(), "w", encoding="utf-8") as f:
        json.dump(info, f)


def _load_last_info():
    path = _get_last_action_path()
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d.get("collection"), d.get("action")
    except Exception:
        return None, None


# ─── Перехват команд Cinema 4D через MessageData ───────────────────────────────

def _scene_snapshot(doc):
    """
    Возвращает строку-«отпечаток» текущего состояния сцены.
    Используется для определения факта изменения без GetUndoName().
    Собирает: имена, типы, позиции всех объектов + число материалов + число тегов.
    """
    parts = []
    try:
        # Рекурсивный обход объектов
        def _walk(obj):
            while obj:
                try:
                    pos = obj.GetAbsPos()
                    parts.append("{}|{}|{:.2f},{:.2f},{:.2f}".format(
                        obj.GetName(), obj.GetType(), pos.x, pos.y, pos.z))
                    # Теги
                    tag = obj.GetFirstTag()
                    while tag:
                        parts.append("T:{}:{}".format(tag.GetType(), tag.GetName()))
                        tag = tag.GetNext()
                except Exception:
                    pass
                child = obj.GetDown()
                if child:
                    _walk(child)
                obj = obj.GetNext()
        _walk(doc.GetFirstObject())
        # Материалы
        mat = doc.GetFirstMaterial()
        while mat:
            parts.append("M:{}".format(mat.GetName()))
            mat = mat.GetNext()
        # Активный рендер (разрешение)
        rd = doc.GetActiveRenderData()
        if rd:
            parts.append("R:{}x{}".format(
                int(rd[c4d.RDATA_XRES]), int(rd[c4d.RDATA_YRES])))
    except Exception:
        pass
    return "|".join(parts)


def _describe_change(old_snap, new_snap, doc):
    """
    Сравнивает два снимка и возвращает человекочитаемое описание изменения.
    Если описать не удаётся — возвращает универсальное «Изменение сцены».
    """
    try:
        old_set = set(old_snap.split("|")) if old_snap else set()
        new_set = set(new_snap.split("|")) if new_snap else set()
        added   = new_set - old_set
        removed = old_set - new_set

        # Объекты добавлены
        obj_added = [x for x in added if not x.startswith(("T:", "M:", "R:"))]
        obj_removed = [x for x in removed if not x.startswith(("T:", "M:", "R:"))]
        mat_added = [x[2:] for x in added if x.startswith("M:")]
        mat_removed = [x[2:] for x in removed if x.startswith("M:")]

        lines = []
        if obj_added and not obj_removed:
            names = [x.split("|")[0] for x in obj_added]
            lines.append("# Добавлен объект: {}".format(", ".join(names[:3])))
        elif obj_removed and not obj_added:
            names = [x.split("|")[0] for x in obj_removed]
            lines.append("# Удалён объект: {}".format(", ".join(names[:3])))
        elif obj_added and obj_removed:
            lines.append("# Изменение объектов в сцене")
        if mat_added:
            lines.append("# Добавлен материал: {}".format(", ".join(mat_added[:3])))
        if mat_removed:
            lines.append("# Удалён материал: {}".format(", ".join(mat_removed[:3])))

        # Позиции/трансформации
        if not lines:
            moved = []
            for token in obj_added:
                parts = token.split("|")
                if len(parts) == 3:
                    name = parts[0]
                    # Ищем тот же объект в old_set с другой позицией
                    for old_token in old_set:
                        old_parts = old_token.split("|")
                        if len(old_parts) == 3 and old_parts[0] == name and old_parts[2] != parts[2]:
                            moved.append(name)
                            break
            if moved:
                lines.append("# Перемещён объект: {}".format(", ".join(moved[:3])))

        if not lines:
            lines.append("# Изменение сцены")

        return "\n".join(lines)
    except Exception:
        return "# Изменение сцены"


class ActionMessageData(c4d.plugins.MessageData):
    """
    Перехватывает глобальные события C4D через EVMSG_CHANGE.
    Сравнивает снимки состояния сцены до/после для определения что изменилось.
    Запись ведётся всегда, пока открыт лог-диалог.
    """

    def __init__(self):
        super(ActionMessageData, self).__init__()
        self._last_snapshot = ""   # снимок сцены после предыдущего события
        self._last_doc_name = ""   # имя документа для сброса снимка при смене проекта

    def CoreMessage(self, kind, msg):
        global _event_log

        # Лог пишется только пока открыт лог-диалог ИЛИ включена запись в менеджере
        log_open = (_log_command and _log_command._dialog
                    and _log_command._dialog.IsOpen())
        if not log_open and not _is_recording:
            return True

        if kind != c4d.EVMSG_CHANGE:
            return True

        try:
            doc = c4d.documents.GetActiveDocument()
            if doc is None:
                return True

            # Сбрасываем снимок при смене документа
            doc_name = doc.GetDocumentName()
            if doc_name != self._last_doc_name:
                self._last_doc_name = doc_name
                self._last_snapshot = _scene_snapshot(doc)
                return True

            # Делаем новый снимок и сравниваем
            new_snap = _scene_snapshot(doc)
            if new_snap == self._last_snapshot:
                return True  # ничего не изменилось

            description = _describe_change(self._last_snapshot, new_snap, doc)
            self._last_snapshot = new_snap

            ts = datetime.datetime.now().strftime("%H:%M:%S")
            for line in description.split("\n"):
                _event_log.append((ts, line))

            # Обновляем лог-диалог если открыт
            if log_open:
                _log_command._dialog._refresh_log()

        except Exception:
            pass

        return True


_message_data_instance = None


# ─── Иконка ───────────────────────────────────────────────────────────────────

def _make_icon(b64):
    """Создаёт BaseBitmap из base64 PNG. Возвращает None если иконка == '000'."""
    if b64 == "000" or not b64:
        return None
    try:
        data = base64.b64decode(b64)
        bmp = c4d.bitmaps.BaseBitmap()
        fd, tmp = tempfile.mkstemp(suffix=".png")
        try:
            os.write(fd, data)
            os.close(fd)
            fd = -1
            bmp.InitWith(tmp)
        finally:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return bmp
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  ДИАЛОГ 1: ЛОГ СОБЫТИЙ
# ═══════════════════════════════════════════════════════════════════════════════

class LogDialog(gui.GeDialog):

    def CreateLayout(self):
        self.SetTitle("Action Recorder — Лог событий")

        # Статус лога и кнопка очистки
        self.GroupBegin(0, c4d.BFH_SCALEFIT, cols=2, rows=1)
        self.GroupBorderSpace(6, 4, 6, 4)
        self.AddStaticText(ID_LOG_STATUS, c4d.BFH_SCALEFIT, name="● Лог активен — записываются все изменения сцены")
        self.AddButton(ID_LOG_BTN_CLEAR, c4d.BFH_RIGHT, initw=80, name="Очистить")
        self.GroupEnd()

        self.AddSeparatorH(0)

        # Прокручиваемый текст лога
        self.ScrollGroupBegin(
            ID_LOG_SCROLL,
            c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            c4d.SCROLLGROUP_VERT | c4d.SCROLLGROUP_HORIZ |
            c4d.SCROLLGROUP_AUTOVERT | c4d.SCROLLGROUP_AUTOHORIZ,
            initw=0, inith=300,
        )
        self.GroupBegin(ID_LOG_GROUP, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1, rows=1)
        self.GroupBorderSpace(4, 4, 4, 4)
        self.AddMultiLineEditText(
            ID_LOG_TEXT,
            c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=560, inith=280,
            style=c4d.DR_MULTILINE_MONOSPACED | c4d.DR_MULTILINE_READONLY,
        )
        self.GroupEnd()
        self.GroupEnd()

        self.AddSeparatorH(0)

        self.GroupBegin(0, c4d.BFH_SCALEFIT, cols=2, rows=1)
        self.GroupBorderSpace(6, 4, 6, 4)
        self.AddButton(ID_LOG_BTN_SAVE, c4d.BFH_LEFT, initw=180, name="Сохранить как экшон…")
        self.AddStaticText(0, c4d.BFH_SCALEFIT, name="")
        self.GroupEnd()

        return True

    def InitValues(self):
        self._refresh_log()
        return True

    def _refresh_log(self):
        if _event_log:
            text = "\n".join("[{}] {}".format(ts, line) for ts, line in _event_log)
        else:
            text = "# Лог пуст. Выполните любое действие в сцене."
        self.SetString(ID_LOG_TEXT, text)

    def _refresh_record_btn(self):
        if _is_recording:
            self.SetString(ID_LOG_BTN_RECORD, "■ Остановить запись")
            self.SetString(ID_LOG_STATUS, "● Запись идёт…")
        else:
            self.SetString(ID_LOG_BTN_RECORD, "● Начать запись")
            self.SetString(ID_LOG_STATUS, "Запись остановлена")

    def Command(self, widget_id, msg):
        global _event_log

        if widget_id == ID_LOG_BTN_CLEAR:
            _event_log = []
            self._refresh_log()
            return True

        if widget_id == ID_LOG_BTN_SAVE:
            self._save_as_action()
            return True

        return True

    def _save_as_action(self):
        if not _event_log:
            gui.MessageDialog("Лог пуст — нечего сохранять.")
            return

        # Диалог выбора имени
        result = gui.InputDialog("Сохранить экшон", "Введите имя экшона:")
        if not result:
            return
        action_name = result.strip()
        if not action_name:
            return

        # Выбор коллекции
        cols = _list_collections()
        col_menu = "\n".join(
            "{}:{}".format(i, c) for i, c in enumerate(cols)
        )
        # Простейший выбор — через InputDialog с нумерованным списком
        hint = "Введите номер коллекции:\n" + "\n".join(
            "{} — {}".format(i, c) for i, c in enumerate(cols)
        )
        col_idx_str = gui.InputDialog("Выбор коллекции", hint)
        try:
            col_idx = int(col_idx_str)
            if col_idx < 0 or col_idx >= len(cols):
                raise ValueError
            col_name = cols[col_idx]
        except (ValueError, TypeError):
            col_name = cols[0]

        code = "# Action: {}\n# Recorded: {}\nimport c4d\n\n{}\n".format(
            action_name,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "\n".join(line for _, line in _event_log),
        )
        _save_action(col_name, action_name, code)
        _save_last_info(col_name, action_name)
        gui.MessageDialog("Экшон «{}» сохранён в коллекцию «{}».".format(action_name, col_name))

    def CoreMessage(self, kind, msg):
        if kind == c4d.EVMSG_CHANGE:
            self._refresh_log()
        return True


# ═══════════════════════════════════════════════════════════════════════════════
#  ДИАЛОГ 2: МЕНЕДЖЕР ЭКШОНОВ
# ═══════════════════════════════════════════════════════════════════════════════

class ManagerDialog(gui.GeDialog):

    def __init__(self):
        super(ManagerDialog, self).__init__()
        self._collections = []
        self._actions = []
        self._selected_action_idx = -1

    def CreateLayout(self):
        self.SetTitle("Action Recorder — Менеджер экшонов")

        # ── Строка коллекций ──────────────────────────────────────────────────
        self.GroupBegin(0, c4d.BFH_SCALEFIT, cols=4, rows=1)
        self.GroupBorderSpace(6, 6, 6, 4)
        self.AddStaticText(0, c4d.BFH_LEFT, initw=80, name="Коллекция:")
        self.AddComboBox(ID_MGR_COLLECTION, c4d.BFH_SCALEFIT, initw=200, inith=0)
        self.AddButton(ID_MGR_BTN_NEW_COL, c4d.BFH_LEFT, initw=110, name="+ Новая")
        self.AddButton(ID_MGR_BTN_DEL_COL, c4d.BFH_LEFT, initw=90, name="✕ Удалить")
        self.GroupEnd()

        self.AddSeparatorH(0)

        # ── Список экшонов ────────────────────────────────────────────────────
        self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=2, rows=1)
        self.GroupBorderSpace(6, 4, 6, 4)

        # Левая панель — список
        self.GroupBegin(0, c4d.BFH_LEFT | c4d.BFV_SCALEFIT, cols=1, rows=0)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Экшоны:")

        self.ScrollGroupBegin(
            ID_MGR_SCROLL,
            c4d.BFH_FIT | c4d.BFV_SCALEFIT,
            c4d.SCROLLGROUP_VERT | c4d.SCROLLGROUP_AUTOVERT,
            initw=200, inith=260,
        )
        self.GroupBegin(ID_MGR_LIST_GROUP,
                        c4d.BFH_SCALEFIT | c4d.BFV_TOP,
                        cols=1, rows=0)
        self.GroupBorderSpace(2, 2, 2, 2)
        self.GroupEnd()
        self.GroupEnd()

        # Кнопки управления
        self.GroupBegin(0, c4d.BFH_SCALEFIT, cols=2, rows=0)
        self.GroupBorderSpace(0, 6, 0, 0)
        self.AddButton(ID_MGR_BTN_NEW_ACT, c4d.BFH_SCALEFIT, name="+ Новый")
        self.AddButton(ID_MGR_BTN_DEL_ACT, c4d.BFH_SCALEFIT, name="✕ Удалить")
        self.AddButton(ID_MGR_BTN_RUN_ACT, c4d.BFH_SCALEFIT, name="▶ Запустить")
        self.AddButton(ID_MGR_BTN_RENAME,  c4d.BFH_SCALEFIT, name="✎ Переименовать")
        self.AddButton(ID_MGR_BTN_RECORD,  c4d.BFH_SCALEFIT, name="● Начать запись")
        self.GroupEnd()

        self.GroupEnd()  # левая панель

        # Правая панель — код
        self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1, rows=0)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Код экшона:")
        self.ScrollGroupBegin(
            ID_MGR_CODE_SCROLL,
            c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            c4d.SCROLLGROUP_VERT | c4d.SCROLLGROUP_HORIZ |
            c4d.SCROLLGROUP_AUTOVERT | c4d.SCROLLGROUP_AUTOHORIZ,
            initw=340, inith=280,
        )
        self.GroupBegin(0, c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT, cols=1, rows=1)
        self.GroupBorderSpace(4, 4, 4, 4)
        self.AddMultiLineEditText(
            ID_MGR_CODE_TEXT,
            c4d.BFH_SCALEFIT | c4d.BFV_SCALEFIT,
            initw=320, inith=260,
            style=c4d.DR_MULTILINE_MONOSPACED,
        )
        self.GroupEnd()
        self.GroupEnd()

        # Кнопка сохранить код
        self.GroupBegin(0, c4d.BFH_SCALEFIT, cols=2, rows=1)
        self.GroupBorderSpace(0, 4, 0, 0)
        self.AddButton(ID_MGR_BTN_IMPORT, c4d.BFH_LEFT, initw=150, name="💾 Сохранить код")
        self.AddStaticText(0, c4d.BFH_SCALEFIT, name="")
        self.GroupEnd()

        self.GroupEnd()  # правая панель

        self.GroupEnd()  # двухколоночная

        self.AddSeparatorH(0)
        self.GroupBegin(0, c4d.BFH_SCALEFIT, cols=1, rows=1)
        self.GroupBorderSpace(6, 2, 6, 4)
        self.AddStaticText(ID_MGR_STATUS, c4d.BFH_SCALEFIT, name="")
        self.GroupEnd()

        return True

    def InitValues(self):
        self._reload_collections()
        return True

    # ── Коллекции ──────────────────────────────────────────────────────────────

    def _reload_collections(self):
        self._collections = _list_collections()
        self.FreeChildren(ID_MGR_COLLECTION)
        for i, c in enumerate(self._collections):
            self.AddChild(ID_MGR_COLLECTION, i, c)
        if self._collections:
            self.SetInt32(ID_MGR_COLLECTION, 0)
        self._reload_actions()

    def _current_collection(self):
        idx = self.GetInt32(ID_MGR_COLLECTION)
        if 0 <= idx < len(self._collections):
            return self._collections[idx]
        return DEFAULT_COLLECTION

    # ── Экшоны ─────────────────────────────────────────────────────────────────

    def _reload_actions(self):
        col = self._current_collection()
        self._actions = _list_actions(col)
        self._selected_action_idx = -1
        self._rebuild_action_list()
        self.SetString(ID_MGR_CODE_TEXT, "")
        self.SetString(ID_MGR_STATUS, "Коллекция: {}  |  Экшонов: {}".format(col, len(self._actions)))

    def _rebuild_action_list(self):
        self.LayoutFlushGroup(ID_MGR_LIST_GROUP)
        if not self._actions:
            self.AddStaticText(0, c4d.BFH_SCALEFIT, name="— нет экшонов —")
        else:
            for idx, name in enumerate(self._actions):
                btn_id = ACTION_ROW_BASE + idx * ROW_STRIDE
                label = ("▶ " if idx == self._selected_action_idx else "   ") + name
                self.AddButton(btn_id, c4d.BFH_SCALEFIT, name=label)
        self.LayoutChanged(ID_MGR_LIST_GROUP)

    def _select_action(self, idx):
        self._selected_action_idx = idx
        col = self._current_collection()
        name = self._actions[idx]
        code = _load_action(col, name)
        self.SetString(ID_MGR_CODE_TEXT, code)
        self._rebuild_action_list()
        self.SetString(ID_MGR_STATUS, "Выбран: {}".format(name))

    # ── Команды ────────────────────────────────────────────────────────────────

    def Command(self, widget_id, msg):

        # Выбор коллекции
        if widget_id == ID_MGR_COLLECTION:
            self._reload_actions()
            return True

        # Новая коллекция
        if widget_id == ID_MGR_BTN_NEW_COL:
            name = gui.InputDialog("Новая коллекция", "Введите имя коллекции:")
            if name and name.strip():
                _get_collection_dir(name.strip())
                self._reload_collections()
                # Выбрать новую
                if name.strip() in self._collections:
                    self.SetInt32(ID_MGR_COLLECTION, self._collections.index(name.strip()))
                    self._reload_actions()
            return True

        # Удалить коллекцию
        if widget_id == ID_MGR_BTN_DEL_COL:
            col = self._current_collection()
            confirm = gui.QuestionDialog(
                "Удалить коллекцию «{}» и все её экшоны?".format(col))
            if confirm:
                import shutil
                shutil.rmtree(_get_collection_dir(col), ignore_errors=True)
                self._reload_collections()
            return True

        # Новый экшон
        if widget_id == ID_MGR_BTN_NEW_ACT:
            name = gui.InputDialog("Новый экшон", "Введите имя нового экшона:")
            if name and name.strip():
                col = self._current_collection()
                template = (
                    "# Action: {}\n"
                    "# Created: {}\n"
                    "import c4d\n\n"
                    "doc = c4d.documents.GetActiveDocument()\n"
                    "# --- ваш код ---\n"
                ).format(name.strip(), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                _save_action(col, name.strip(), template)
                _save_last_info(col, name.strip())
                self._reload_actions()
                if name.strip() in self._actions:
                    self._select_action(self._actions.index(name.strip()))
            return True

        # Удалить экшон
        if widget_id == ID_MGR_BTN_DEL_ACT:
            if self._selected_action_idx < 0:
                gui.MessageDialog("Выберите экшон для удаления.")
                return True
            name = self._actions[self._selected_action_idx]
            if gui.QuestionDialog("Удалить экшон «{}»?".format(name)):
                _delete_action(self._current_collection(), name)
                self._reload_actions()
            return True

        # Запустить экшон
        if widget_id == ID_MGR_BTN_RUN_ACT:
            self._run_selected()
            return True

        # Переименовать экшон
        if widget_id == ID_MGR_BTN_RENAME:
            if self._selected_action_idx < 0:
                gui.MessageDialog("Выберите экшон для переименования.")
                return True
            old_name = self._actions[self._selected_action_idx]
            new_name = gui.InputDialog("Переименовать «{}»".format(old_name), "Введите новое имя:")
            if new_name and new_name.strip() and new_name.strip() != old_name:
                col = self._current_collection()
                code = _load_action(col, old_name)
                _save_action(col, new_name.strip(), code)
                _delete_action(col, old_name)
                self._reload_actions()
                if new_name.strip() in self._actions:
                    self._select_action(self._actions.index(new_name.strip()))
            return True

        # Сохранить код из редактора
        if widget_id == ID_MGR_BTN_IMPORT:
            if self._selected_action_idx < 0:
                gui.MessageDialog("Выберите экшон для сохранения.")
                return True
            code = self.GetString(ID_MGR_CODE_TEXT)
            name = self._actions[self._selected_action_idx]
            _save_action(self._current_collection(), name, code)
            _save_last_info(self._current_collection(), name)
            self.SetString(ID_MGR_STATUS, "Сохранено: {}".format(name))
            return True

        # Кнопка записи — старт/стоп
        if widget_id == ID_MGR_BTN_RECORD:
            global _is_recording
            _is_recording = not _is_recording
            if _is_recording:
                self.SetString(ID_MGR_BTN_RECORD, "■ Остановить запись")
                self.SetString(ID_MGR_STATUS, "● Запись идёт…")
            else:
                self.SetString(ID_MGR_BTN_RECORD, "● Начать запись")
                self.SetString(ID_MGR_STATUS, "Запись остановлена")
            return True

        # Клик по кнопке экшона в списке
        for idx in range(len(self._actions)):
            btn_id = ACTION_ROW_BASE + idx * ROW_STRIDE
            if widget_id == btn_id:
                if self._selected_action_idx == idx:
                    # Двойной клик — запуск
                    self._run_selected()
                else:
                    self._select_action(idx)
                return True

        return True

    def _run_selected(self):
        if self._selected_action_idx < 0:
            gui.MessageDialog("Выберите экшон для запуска.")
            return
        col = self._current_collection()
        name = self._actions[self._selected_action_idx]
        code = _load_action(col, name)
        if not code.strip():
            gui.MessageDialog("Экшон «{}» пуст.".format(name))
            return
        ok, err = _run_action_code(code)
        if ok:
            _save_last_info(col, name)
            self.SetString(ID_MGR_STATUS, "✓ Выполнен: {}".format(name))
        else:
            self.SetString(ID_MGR_STATUS, "✕ Ошибка в: {}".format(name))
            gui.MessageDialog("Ошибка при выполнении «{}»:\n\n{}".format(name, err))


# ═══════════════════════════════════════════════════════════════════════════════
#  CommandData-обёртки для трёх кнопок меню
# ═══════════════════════════════════════════════════════════════════════════════

class LogCommand(c4d.plugins.CommandData):
    """Кнопка 1 — Лог событий."""

    def __init__(self):
        super(LogCommand, self).__init__()
        self._dialog = None

    def Execute(self, doc):
        if self._dialog is None:
            self._dialog = LogDialog()
        if self._dialog.IsOpen():
            self._dialog.Close()
        else:
            self._dialog.Open(
                dlgtype=c4d.DLG_TYPE_ASYNC,
                pluginid=PLUGIN_ID_LOG,
                defaultw=620,
                defaulth=420,
            )
        return True

    def RestoreLayout(self, secret):
        if self._dialog is None:
            self._dialog = LogDialog()
        return self._dialog.Restore(PLUGIN_ID_LOG, secret)

    def GetState(self, doc):
        return c4d.CMD_ENABLED


class ManagerCommand(c4d.plugins.CommandData):
    """Кнопка 2 — Менеджер экшонов."""

    def __init__(self):
        super(ManagerCommand, self).__init__()
        self._dialog = None

    def Execute(self, doc):
        if self._dialog is None:
            self._dialog = ManagerDialog()
        if self._dialog.IsOpen():
            self._dialog.Close()
        else:
            self._dialog.Open(
                dlgtype=c4d.DLG_TYPE_ASYNC,
                pluginid=PLUGIN_ID_MANAGER,
                defaultw=600,
                defaulth=480,
            )
        return True

    def RestoreLayout(self, secret):
        if self._dialog is None:
            self._dialog = ManagerDialog()
        return self._dialog.Restore(PLUGIN_ID_MANAGER, secret)

    def GetState(self, doc):
        return c4d.CMD_ENABLED


class PlaybackCommand(c4d.plugins.CommandData):
    """Кнопка 3 — Воспроизвести последний экшон."""

    def Execute(self, doc):
        col, name = _load_last_info()
        if not col or not name:
            gui.MessageDialog(
                "Нет последнего экшона.\n"
                "Запишите или выберите экшон в Менеджере.")
            return True
        code = _load_action(col, name)
        if not code.strip():
            gui.MessageDialog("Экшон «{}» пуст.".format(name))
            return True
        ok, err = _run_action_code(code)
        if not ok:
            gui.MessageDialog(
                "Ошибка при выполнении «{}»:\n\n{}".format(name, err))
        return True

    def GetState(self, doc):
        col, name = _load_last_info()
        if col and name:
            return c4d.CMD_ENABLED
        return c4d.CMD_ENABLED  # всегда активна, но выдаст диалог если нет экшона


# ─── Глобальные экземпляры (нужны для доступа из MessageData) ─────────────────
_log_command = None


# ═══════════════════════════════════════════════════════════════════════════════
#  Регистрация
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Создаём дефолтную папку при первом запуске
    _get_collection_dir(DEFAULT_COLLECTION)

    # Глобальный перехватчик событий
    _message_data_instance = ActionMessageData()
    c4d.plugins.RegisterMessagePlugin(
        id=PLUGIN_ID_LOG + 100,
        str="Action Recorder Message Hook",
        info=0,
        dat=_message_data_instance,
    )

    # Кнопка 1 — Лог событий
    _log_command = LogCommand()
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_LOG,
        str="AR: Лог событий",
        info=0,
        icon=_make_icon(ICON_LOG_B64),
        help="Action Recorder — просмотр лога команд в виде кода",
        dat=_log_command,
    )

    # Кнопка 2 — Менеджер экшонов
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_MANAGER,
        str="AR: Менеджер экшонов",
        info=0,
        icon=_make_icon(ICON_MANAGER_B64),
        help="Action Recorder — создание, удаление, запуск экшонов",
        dat=ManagerCommand(),
    )

    # Кнопка 3 — Воспроизвести последний
    c4d.plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_PLAYBACK,
        str="AR: Воспроизвести последний",
        info=0,
        icon=_make_icon(ICON_PLAY_B64),
        help="Action Recorder — запустить последний использованный экшон",
        dat=PlaybackCommand(),
    )
