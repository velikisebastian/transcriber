#!/usr/bin/env python3
"""Транскрибатор: видео/аудио -> Markdown через AssemblyAI."""
import sys
import webbrowser
from pathlib import Path

import core
from core import KEY_URL, LANGS, MEDIA_EXT
from PySide6.QtCore import QObject, QSettings, Qt, QThread, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

STYLE = """
* { font-family: 'Inter', 'Noto Sans', sans-serif; font-size: 13px; color: #e8e6e1; }
QMainWindow, #root { background: #17181a; }
#panel { background: #1f2124; border: 1px solid #2c2f33; border-radius: 12px; }
#title { font-size: 20px; font-weight: 600; }
#muted { color: #8d9096; }
#section { color: #8d9096; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
#drop { background: #1b1d1f; border: 1.5px dashed #3a3e43; border-radius: 12px; }
#drop[hover="true"] { border-color: #d9a441; background: #22211d; }
#dropTitle { font-size: 15px; font-weight: 500; }
QLineEdit, QComboBox {
    background: #17181a; border: 1px solid #2c2f33; border-radius: 8px;
    padding: 7px 10px; selection-background-color: #d9a441; selection-color: #17181a;
}
QLineEdit:focus, QComboBox:focus { border-color: #d9a441; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #1f2124; border: 1px solid #2c2f33; selection-background-color: #2c2f33; outline: 0; }
QPushButton { background: #2a2d31; border: 1px solid #353a3f; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { background: #32363b; }
QPushButton:disabled { color: #5d6066; background: #222426; border-color: #2a2d31; }
QPushButton#primary { background: #d9a441; border-color: #d9a441; color: #17181a; font-weight: 600; padding: 9px 20px; }
QPushButton#primary QLabel { color: #17181a; }
QPushButton#primary:hover { background: #e6b556; }
QPushButton#primary:disabled { background: #3a3629; border-color: #3a3629; color: #7a7360; }
QPushButton#link { background: transparent; border: none; color: #d9a441; padding: 0; text-align: left; }
QPushButton#link:hover { text-decoration: underline; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #4a4f55; background: #17181a; }
QCheckBox::indicator:checked { background: #d9a441; border-color: #d9a441; }
QListWidget { background: transparent; border: none; outline: 0; }
QListWidget::item { border-radius: 8px; padding: 0; margin: 0 0 4px 0; }
QProgressBar { background: #2c2f33; border: none; border-radius: 2px; max-height: 4px; }
QProgressBar::chunk { background: #d9a441; border-radius: 2px; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #3a3e43; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""


class Job(QObject):
    """Транскрибация одного файла (живёт в рабочем потоке)."""
    status = Signal(str, int)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, path, out_dir, key, lang, speakers, stamps):
        super().__init__()
        self.args = (path, out_dir, key, lang, speakers, stamps)
        self.cancel = False

    def run(self):
        try:
            out = core.transcribe(*self.args, self.status.emit, lambda: self.cancel)
            self.done.emit(out)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class DropZone(QFrame):
    files = Signal(list)

    def __init__(self):
        super().__init__()
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        t = QLabel("Перетащите видео или аудио сюда")
        t.setObjectName("dropTitle")
        t.setAlignment(Qt.AlignCenter)
        s = QLabel("mp4, mkv, mov, mp3, wav, m4a, ogg, flac…")
        s.setObjectName("muted")
        s.setAlignment(Qt.AlignCenter)
        b = QPushButton("Выбрать файлы")
        b.clicked.connect(self.pick)
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addSpacing(8)
        lay.addWidget(b, 0, Qt.AlignCenter)

    def _hover(self, on):
        self.setProperty("hover", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def pick(self):
        exts = " ".join(f"*{e}" for e in sorted(MEDIA_EXT))
        paths, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы", str(Path.home()),
                                                f"Медиа ({exts});;Все файлы (*)")
        if paths:
            self.files.emit(paths)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._hover(True)

    def dragLeaveEvent(self, e):
        self._hover(False)

    def dropEvent(self, e):
        self._hover(False)
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.files.emit(paths)


class Row(QWidget):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.result = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)
        top = QHBoxLayout()
        self.name = QLabel(Path(path).name)
        self.name.setStyleSheet("font-weight:500")
        self.state = QLabel("В очереди")
        self.state.setObjectName("muted")
        self.open_btn = QPushButton("Показать")
        self.open_btn.setVisible(False)
        self.open_btn.clicked.connect(self.reveal)
        top.addWidget(self.name, 1)
        top.addWidget(self.state)
        top.addWidget(self.open_btn)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 100)
        self.bar.setVisible(False)
        lay.addLayout(top)
        lay.addWidget(self.bar)
        self.setStyleSheet("Row { background: #1f2124; border: 1px solid #2c2f33; border-radius: 8px; }")
        self.setAttribute(Qt.WA_StyledBackground, True)

    def reveal(self):
        if self.result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.result).parent)))

    def progress(self, text, pct):
        self.state.setText(text)
        self.state.setStyleSheet("color:#d9a441")
        self.bar.setVisible(True)
        self.bar.setValue(pct)

    def finished(self, out):
        self.result = out
        self.state.setText("Готово")
        self.state.setStyleSheet("color:#7cc48a")
        self.bar.setVisible(False)
        self.open_btn.setVisible(True)

    def error(self, msg):
        self.state.setText(msg if len(msg) < 70 else msg[:67] + "…")
        self.state.setToolTip(msg)
        self.state.setStyleSheet("color:#e5736b")
        self.bar.setVisible(False)


class Main(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Транскрибатор")
        self.resize(760, 780)
        self.cfg = QSettings("transcriber", "transcriber")
        self.rows, self.queue, self.thread, self.job = [], [], None, None

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        title = QLabel("Транскрибатор")
        title.setObjectName("title")
        sub = QLabel("Видео и аудио → текст в Markdown · AssemblyAI")
        sub.setObjectName("muted")
        lay.addWidget(title)
        lay.addWidget(sub)

        self.drop = DropZone()
        self.drop.files.connect(self.add_files)
        lay.addWidget(self.drop)

        # настройки
        panel = QFrame()
        panel.setObjectName("panel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.setSpacing(10)

        pl.addWidget(self._sec("API-КЛЮЧ"))
        kr = QHBoxLayout()
        self.key = QLineEdit(self.cfg.value("key", ""))
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("Вставьте ключ AssemblyAI")
        self.key.textChanged.connect(lambda t: self.cfg.setValue("key", t.strip()))
        getk = QPushButton("Получить ключ")
        getk.clicked.connect(lambda: webbrowser.open(KEY_URL))
        kr.addWidget(self.key, 1)
        kr.addWidget(getk)
        pl.addLayout(kr)

        pl.addWidget(self._sec("ПАПКА ДЛЯ РЕЗУЛЬТАТОВ"))
        fr = QHBoxLayout()
        default = str(Path.home() / "Transcripts")
        self.folder = QLineEdit(self.cfg.value("folder", default))
        self.folder.textChanged.connect(lambda t: self.cfg.setValue("folder", t.strip()))
        chg = QPushButton("Изменить…")
        chg.clicked.connect(self.choose_folder)
        opn = QPushButton("Открыть")
        opn.clicked.connect(self.open_folder)
        fr.addWidget(self.folder, 1)
        fr.addWidget(chg)
        fr.addWidget(opn)
        pl.addLayout(fr)

        opts = QHBoxLayout()
        self.lang = QComboBox()
        for label, code in LANGS:
            self.lang.addItem(label, code)
        self.lang.setCurrentIndex(int(self.cfg.value("lang_idx", 0)))
        self.lang.currentIndexChanged.connect(lambda i: self.cfg.setValue("lang_idx", i))
        self.spk = QCheckBox("Разделять по спикерам")
        self.spk.setChecked(self.cfg.value("spk", "false") == "true")
        self.spk.toggled.connect(lambda v: self.cfg.setValue("spk", "true" if v else "false"))
        self.stamps = QCheckBox("Таймкоды")
        self.stamps.setChecked(self.cfg.value("stamps", "true") == "true")
        self.stamps.toggled.connect(lambda v: self.cfg.setValue("stamps", "true" if v else "false"))
        opts.addWidget(QLabel("Язык"))
        opts.addWidget(self.lang)
        opts.addSpacing(12)
        opts.addWidget(self.spk)
        opts.addWidget(self.stamps)
        opts.addStretch(1)
        pl.addLayout(opts)
        lay.addWidget(panel)

        # очередь
        hdr = QHBoxLayout()
        hdr.addWidget(self._sec("ОЧЕРЕДЬ"))
        hdr.addStretch(1)
        self.clear_btn = QPushButton("Очистить завершённые")
        self.clear_btn.clicked.connect(self.clear_done)
        hdr.addWidget(self.clear_btn)
        lay.addLayout(hdr)
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.NoSelection)
        lay.addWidget(self.list, 1)

        self.empty = QLabel("Файлы появятся здесь")
        self.empty.setObjectName("muted")
        self.empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.empty)

        self.start = QPushButton("Транскрибировать")
        self.start.setObjectName("primary")
        self.start.setEnabled(False)
        self.start.clicked.connect(self.go)
        lay.addWidget(self.start)

        if not self.key.text():
            self.key.setFocus()

    def _sec(self, t):
        l = QLabel(t)
        l.setObjectName("section")
        return l

    def choose_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Папка для результатов", self.folder.text() or str(Path.home()))
        if d:
            self.folder.setText(d)

    def open_folder(self):
        p = Path(self.folder.text()).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def add_files(self, paths):
        for p in paths:
            if Path(p).suffix.lower() not in MEDIA_EXT or not Path(p).is_file():
                continue
            row = Row(p)
            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, row)
            self.rows.append(row)
            self.queue.append(row)
        self.refresh()

    def clear_done(self):
        for i in reversed(range(self.list.count())):
            row = self.list.itemWidget(self.list.item(i))
            if row.result or row.state.text() not in ("В очереди",) and row not in self.queue and row is not getattr(self, "cur", None):
                self.list.takeItem(i)
                self.rows.remove(row)
        self.refresh()

    def refresh(self):
        self.empty.setVisible(self.list.count() == 0)
        busy = self.thread is not None
        self.start.setEnabled(bool(self.queue) and not busy)

    def go(self):
        key = self.key.text().strip()
        if not key:
            self.key.setFocus()
            self.key.setStyleSheet("border-color:#e5736b")
            return
        self.key.setStyleSheet("")
        self.next()

    def next(self):
        if not self.queue:
            self.thread = None
            self.start.setText("Транскрибировать")
            self.refresh()
            return
        self.cur = row = self.queue.pop(0)
        self.start.setText("Идёт обработка…")
        self.start.setEnabled(False)
        out = Path(self.folder.text()).expanduser()
        job = Job(row.path, out, self.key.text().strip(), self.lang.currentData(),
                  self.spk.isChecked(), self.stamps.isChecked())
        th = QThread()
        job.moveToThread(th)
        th.started.connect(job.run)
        job.status.connect(row.progress)
        job.done.connect(row.finished)
        job.failed.connect(row.error)
        for sig in (job.done, job.failed):
            sig.connect(th.quit)
        th.finished.connect(self.next)
        self.thread, self.job = th, job
        th.start()

    def closeEvent(self, e):
        if self.job:
            self.job.cancel = True
        if self.thread:
            self.thread.quit()
            self.thread.wait(3000)
        super().closeEvent(e)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    w = Main()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
