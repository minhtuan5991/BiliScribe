from __future__ import annotations

import json
import os
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt, QUrl, QPoint
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

from . import __version__
from .config import MODELS, PROFILES, Settings, atomic_text, data_dir, load_settings, normalize_url, resource_path, save_settings
from .windows import ProcessJob
from .history import load_history
from .output_files import transcript_file

STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 13px; color: #203E40; }
QMainWindow, QWidget#page { background: #F5F7F6; }
QFrame#sidebar { background: #112F31; border: none; }
QFrame#sidebar QLabel { color: #E8F1F0; }
QLabel#brand { font-size: 23px; font-weight: 700; }
QLabel#eyebrow { font-size: 11px; font-weight: 700; color: #55706F; }
QLabel#heading { font-size: 28px; font-weight: 700; color: #112F31; }
QLabel#subheading { color: #57716F; font-size: 13px; }
QLabel#cardTitle { font-size: 15px; font-weight: 600; }
QLabel#muted { color: #57716F; }
QLabel#status { font-size: 13px; font-weight: 600; }
QLabel#error { color: #AE2736; }
QFrame#card { background: #FFFFFF; border: 1px solid #DDE7E3; border-radius: 12px; }
QFrame#card QLabel { background: transparent; border: none; }
QLineEdit, QPlainTextEdit, QComboBox { background: #FFFFFF; border: 1px solid #B8C9C3; border-radius: 7px; padding: 8px; selection-background-color: #0B756B; selection-color: white; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 2px solid #0B756B; }
QLineEdit:disabled, QComboBox:disabled { background: #EBF0ED; color: #738781; }
QComboBox { min-height: 20px; padding-right: 26px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: white; color: #203E40; selection-background-color: #DFF2EB; selection-color: #173B34; }
QPushButton { background: #FFFFFF; border: 1px solid #B8C9C3; border-radius: 7px; padding: 9px 13px; font-weight: 600; min-height: 18px; }
QPushButton:hover { background: #EFF7F3; border-color: #658F82; }
QPushButton:pressed { background: #D9ECE3; }
QPushButton:focus { border: 2px solid #0B756B; }
QPushButton:disabled { background: #EEF2EF; border-color: #DEE5E0; color: #83918C; }
QPushButton#primary { background: #0B756B; color: white; border: 1px solid #0B756B; padding: 11px 20px; }
QPushButton#primary:hover { background: #095E57; }
QPushButton#primary:disabled { background: #A6BBB2; border-color: #A6BBB2; color: #FFFFFF; }
QPushButton#nav { background: transparent; border: 1px solid transparent; color: #D5E4DF; text-align: left; padding: 12px; }
QPushButton#nav:hover { background: #254345; }
QPushButton#nav:checked { background: #2C514C; color: #FFFFFF; border-color: #527F6F; }
QPushButton#link { border: none; background: transparent; color: #0B756B; padding: 3px 0; text-align: left; }
QCheckBox { spacing: 8px; min-height: 25px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QProgressBar { background: #E4EDE8; border: none; border-radius: 4px; height: 7px; text-align: center; }
QProgressBar::chunk { background: #0B756B; border-radius: 4px; }
QTableWidget { background: #FFFFFF; border: none; gridline-color: #ECF0ED; selection-background-color: #E0F2EA; selection-color: #173B34; }
QTableWidget::item { padding: 8px; border-bottom: 1px solid #ECF0ED; }
QHeaderView::section { background: #F4F7F5; border: none; padding: 9px; color: #57716F; font-size: 11px; font-weight: 600; text-align: left; }
QTextBrowser { border: none; background: #FFFFFF; padding: 12px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #F0F4F1; width: 9px; }
QScrollBar::handle:vertical { background: #B9CCC2; border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QSplitter::handle { background: transparent; width: 14px; }
"""


def app_icon():
    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256):
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#0B756B"))
        painter.drawRoundedRect(0, 0, size, size, size * .24, size * .24)
        painter.setPen(QPen(QColor("#FFFFFF"), max(1.6, size * .055), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for x, height in ((.24, .22), (.38, .42), (.52, .58), (.66, .34), (.80, .16)):
            painter.drawLine(int(size*x), int(size*(.5-height/2)), int(size*x), int(size*(.5+height/2)))
        painter.end()
        icon.addPixmap(pix)
    return icon


def label(text, name="", wrap=False):
    obj = QLabel(text)
    if name:
        obj.setObjectName(name)
    obj.setWordWrap(wrap)
    return obj


def button(text, slot, name=""):
    obj = QPushButton(text)
    obj.setCursor(Qt.CursorShape.PointingHandCursor)
    if name:
        obj.setObjectName(name)
    obj.clicked.connect(slot)
    return obj


class DropDown(QComboBox):
    def wheelEvent(self, event):
        # Let the surrounding page scroll without changing the selected option.
        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#52736A"))
        x, y = self.width() - 16, self.height() // 2
        painter.drawPolygon(QPolygon([QPoint(x - 4, y - 2), QPoint(x + 4, y - 2), QPoint(x, y + 3)]))
        painter.end()


def combo(items):
    obj = DropDown()
    for text, value in items:
        obj.addItem(text, value)
    return obj


def card():
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    return frame, layout


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_settings()
        self.setWindowTitle(f"BiliScribe · {__version__}")
        self.setWindowIcon(app_icon())
        self.resize(1280, 860)
        self.setMinimumSize(960, 690)
        self.proc = None
        self.job = None
        self.buffer = b""
        self.request_file = None
        self.local_files = []
        self.last_folder = None
        self.summaries = {}
        self.terminal_event = False
        self.cancelling = False
        self.started_at = None
        self.mode = "transcribe"
        self.row_progress = {}
        self.active_index = None
        self.update_check = None
        self.update_url = None
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._poll_update)
        self._build()
        self._restore()
        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.timeout.connect(self._tick)
        self.elapsed_timer.start(1000)

    def _build(self):
        root = QWidget()
        horizontal = QHBoxLayout(root)
        horizontal.setContentsMargins(0, 0, 0, 0)
        horizontal.setSpacing(0)
        self.setCentralWidget(root)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20, 28, 20, 23)
        brand_icon = QLabel()
        brand_icon.setPixmap(app_icon().pixmap(42, 42))
        side.addWidget(brand_icon)
        side.addWidget(label("BiliScribe", "brand"))
        side.addWidget(label("VIDEO → TIẾNG TRUNG", wrap=True))
        side.addSpacing(32)
        self.nav_buttons = []
        for number, text in enumerate(("Tạo transcript", "Lịch sử xử lý", "Hướng dẫn")):
            item = button(text, lambda checked=False, n=number: self._navigate(n), "nav")
            item.setCheckable(True)
            side.addWidget(item)
            self.nav_buttons.append(item)
        side.addStretch()
        self.processing_title = label("CHẠY TRÊN MÁY CỦA BẠN")
        self.processing_note = label("Âm thanh được nhận dạng\nngay trên máy tính.", wrap=True)
        side.addWidget(self.processing_title)
        side.addWidget(self.processing_note)
        side.addSpacing(12)
        side.addWidget(label("Windows 10 / 11 · 64-bit\nPhiên bản " + __version__))
        self.update_btn = button("", self._open_update)
        self.update_btn.setAccessibleName("Mở trang tải bản cập nhật BiliScribe")
        self.update_btn.hide()
        side.addWidget(self.update_btn)
        horizontal.addWidget(sidebar)
        self.pages = QStackedWidget()
        horizontal.addWidget(self.pages, 1)
        self._build_work_page()
        self._build_history()
        self._build_help()
        self._navigate(0)

    def _build_work_page(self):
        page = QWidget()
        page.setObjectName("page")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(28, 25, 28, 22)
        outer.setSpacing(16)
        outer.addWidget(label("BILIBILI  /  AUDIO  /  TRANSCRIPT", "eyebrow"))
        outer.addWidget(label("Từ video đến chữ.", "heading"))
        outer.addWidget(label("Dán link, chọn chế độ và nhận bản chép lời tiếng Trung có mốc thời gian.", "subheading", True))
        split = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(split, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(430)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left = QWidget()
        layout = QVBoxLayout(left)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(14)
        scroll.setWidget(left)
        split.addWidget(scroll)
        source_card, source_layout = card()
        source_layout.addWidget(label("01   Nguồn video", "cardTitle"))
        self.urls = QPlainTextEdit()
        self.urls.setAccessibleName("Link video Bilibili, mỗi link một dòng")
        self.urls.setPlaceholderText("https://www.bilibili.com/video/BV…\nMỗi link một dòng · Giữ đúng phần p= trong link")
        self.urls.setFixedHeight(80)
        source_layout.addWidget(self.urls)
        source_actions = QHBoxLayout()
        self.add_file_btn = button("Thêm audio / video", self._add_files)
        source_actions.addWidget(self.add_file_btn)
        self.clear_btn = button("Xóa nguồn", self._clear_sources, "link")
        source_actions.addWidget(self.clear_btn)
        source_actions.addStretch()
        source_layout.addLayout(source_actions)
        self.file_count = label("Hỗ trợ link Bilibili, b23.tv và file trên máy.", "muted", True)
        source_layout.addWidget(self.file_count)
        self.input_error = label("", "error", True)
        self.input_error.hide()
        source_layout.addWidget(self.input_error)
        layout.addWidget(source_card)
        self.settings_card, options = card()
        options.addWidget(label("02   Cách xử lý", "cardTitle"))
        self.profile = combo([(v, k) for k, v in PROFILES.items()])
        options.addWidget(label("Chế độ"))
        options.addWidget(self.profile)
        self.profile_help = label("", "muted", True)
        options.addWidget(self.profile_help)
        self.api_options = QWidget()
        api_layout = QVBoxLayout(self.api_options)
        api_layout.setContentsMargins(0, 0, 0, 0)
        api_layout.addWidget(label("Pixazo API key"))
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setAccessibleName("Pixazo API key")
        self.api_key.setPlaceholderText("Nhập API key của bạn")
        api_layout.addWidget(self.api_key)
        self.remember_api = QCheckBox("Nhớ API key · mã hóa bằng tài khoản Windows")
        self.remember_api.toggled.connect(self._remember_api_changed)
        api_layout.addWidget(self.remember_api)
        api_layout.addWidget(label("Số đoạn xử lý song song"))
        self.pixazo_workers = combo([("1 luồng · ít kết nối",1),("2 luồng",2),("3 luồng · mặc định",3),("4 luồng · mạng ổn định",4)])
        api_layout.addWidget(self.pixazo_workers)
        api_layout.addWidget(label("Âm thanh sẽ được gửi tới Pixazo. Cần Internet và tài khoản còn credit. Chỉ phần chưa hoàn tất mới được gửi khi chạy tiếp.", "muted", True))
        options.addWidget(self.api_options)
        self.profile.currentIndexChanged.connect(self._profile_hint)
        options.addWidget(label("Thư mục kết quả"))
        outrow = QHBoxLayout()
        self.output = QLineEdit()
        self.output.setAccessibleName("Thư mục lưu kết quả")
        outrow.addWidget(self.output, 1)
        outrow.addWidget(button("Chọn…", self._choose_output))
        options.addLayout(outrow)
        self.advanced_toggle = button("Cài đặt nâng cao  +", self._toggle_advanced, "link")
        options.addWidget(self.advanced_toggle)
        self.advanced = QWidget()
        advanced = QGridLayout(self.advanced)
        advanced.setContentsMargins(0, 2, 0, 0)
        advanced.setHorizontalSpacing(10)
        advanced.setVerticalSpacing(7)
        self.device = combo([("Tự động CPU / GPU", "auto"), ("CPU · INT8", "cpu"), ("NVIDIA GPU", "cuda")])
        self.model = combo([("Theo chế độ đã chọn", "auto")] + [(f"{k} · {v[1]}", k) for k, v in MODELS.items() if k != "tiny"])
        self.script = combo([("Tiếng Trung giản thể", "simplified"), ("Tiếng Trung phồn thể", "traditional"), ("Giữ chữ mô hình trả về", "original")])
        self.cookies = combo([("Không dùng cookie", "none"), ("File cookies.txt", "file"), ("Firefox", "firefox"), ("Chrome", "chrome"), ("Edge", "edge")])
        for col, (text, obj) in enumerate((("Thiết bị", self.device), ("Mô hình", self.model))):
            advanced.addWidget(label(text), 0, col)
            advanced.addWidget(obj, 1, col)
        advanced.addWidget(label("Kiểu chữ"), 2, 0)
        advanced.addWidget(label("Cookie đăng nhập Bilibili"), 2, 1)
        advanced.addWidget(self.script, 3, 0)
        advanced.addWidget(self.cookies, 3, 1)
        self.cookie_path = QLineEdit()
        self.cookie_path.setPlaceholderText("Chọn file cookies.txt khi video cần đăng nhập")
        self.cookie_path.setAccessibleName("File cookie Bilibili")
        advanced.addWidget(self.cookie_path, 4, 0)
        advanced.addWidget(button("Chọn cookies.txt…", self._choose_cookie), 4, 1)
        advanced.addWidget(label("Tên riêng / thuật ngữ tiếng Trung (không bắt buộc)"), 5, 0, 1, 2)
        self.glossary = QLineEdit()
        self.glossary.setPlaceholderText("Ví dụ: tên nhân vật, địa danh, thuật ngữ trong video")
        self.glossary.setMaxLength(600)
        self.glossary.setAccessibleName("Từ vựng gợi ý tiếng Trung")
        advanced.addWidget(self.glossary, 6, 0, 1, 2)
        self.vad = QCheckBox("Bỏ khoảng lặng (VAD)")
        self.vad.setToolTip("Tắt nếu âm thanh nhỏ hoặc có đoạn lời nói bị bỏ sót.")
        self.force = QCheckBox("Nhận dạng lại từ đầu")
        advanced.addWidget(self.vad, 7, 0)
        advanced.addWidget(self.force, 8, 1)
        advanced.addWidget(label("Tải đồng thời"), 9, 0)
        self.download_workers = combo([("1 video · tiết kiệm mạng", 1), ("2 video · tải trước", 2)])
        advanced.addWidget(self.download_workers, 9, 1)
        self.gpu_button = button("Chuẩn bị GPU NVIDIA (~1 GB)", self._prepare_gpu)
        advanced.addWidget(self.gpu_button, 10, 0, 1, 2)
        self.cache_path = QLineEdit()
        self.cache_path.setAccessibleName("Thư mục mô hình AI")
        advanced.addWidget(label("Thư mục mô hình AI"), 11, 0, 1, 2)
        advanced.addWidget(self.cache_path, 12, 0)
        advanced.addWidget(button("Chọn thư mục…", self._choose_cache), 12, 1)
        options.addWidget(self.advanced)
        self.advanced.hide()
        layout.addWidget(self.settings_card)
        queue_card, queue_layout = card()
        queue_layout.addWidget(label("03   Hàng đợi", "cardTitle"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["VIDEO / FILE", "TRẠNG THÁI", "%"])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(130)
        self.table.setMaximumHeight(220)
        self.table.itemSelectionChanged.connect(self._select_result)
        queue_layout.addWidget(self.table)
        self.queue_empty = label("Video sẽ xuất hiện ở đây khi bạn bắt đầu.", "muted", True)
        queue_layout.addWidget(self.queue_empty)
        layout.addWidget(queue_card)
        layout.addStretch()
        preview_card, preview_layout = card()
        preview_card.setMinimumWidth(280)
        head = QHBoxLayout()
        head.addWidget(label("Bản chép lời", "cardTitle"))
        head.addStretch()
        head.addWidget(label("中文", "muted"))
        preview_layout.addLayout(head)
        self.preview_title = label("Kết quả từ âm thanh gốc", "muted", True)
        preview_layout.addWidget(self.preview_title)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setStyleSheet("QPlainTextEdit { font-family: 'Microsoft YaHei UI'; font-size: 16px; padding: 12px; }")
        self.preview.setPlaceholderText("Bản chép lời tiếng Trung sẽ xuất hiện tại đây sau mỗi đoạn xử lý.\n\nTXT · SRT · Đối chiếu\n\nBạn có thể sao chép hoặc mở file để chỉnh sửa sau khi hoàn tất.")
        self.preview.setAccessibleName("Nội dung transcript tiếng Trung")
        preview_layout.addWidget(self.preview, 1)
        tools = QHBoxLayout()
        tools.addWidget(button("Sao chép", self._copy_preview))
        self.open_txt_btn = button("Mở TXT", self._open_txt)
        self.open_txt_btn.setEnabled(False)
        tools.addWidget(self.open_txt_btn)
        preview_layout.addLayout(tools)
        review_tools = QHBoxLayout()
        self.srt_btn = button("Mở SRT", lambda: self._open_transcript(".srt"))
        self.compare_btn = button("Đối chiếu", lambda: self._open_result_file("doi_chieu_zh.txt"))
        self.srt_btn.setEnabled(False)
        self.compare_btn.setEnabled(False)
        review_tools.addWidget(self.srt_btn)
        review_tools.addWidget(self.compare_btn)
        preview_layout.addLayout(review_tools)
        self.review_note = label("SenseVoice đã có sẵn cho CPU. Large v3 / Turbo chỉ cần tải ở lần đầu sử dụng.", "muted", True)
        preview_layout.addWidget(self.review_note)
        split.addWidget(preview_card)
        split.setSizes([610, 340])
        bottom, bottom_layout = card()
        progress_row = QHBoxLayout()
        self.status = label("Sẵn sàng", "status")
        self.status.setWordWrap(True)
        progress_row.addWidget(self.status, 1)
        self.elapsed = label("", "muted")
        progress_row.addWidget(self.elapsed)
        bottom_layout.addLayout(progress_row)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(7)
        self.progress.setValue(0)
        bottom_layout.addWidget(self.progress)
        actions = QHBoxLayout()
        self.start_btn = button("Bắt đầu tạo transcript", self._start, "primary")
        actions.addWidget(self.start_btn)
        self.stop_btn = button("Dừng", self._cancel)
        self.stop_btn.setEnabled(False)
        actions.addWidget(self.stop_btn)
        actions.addStretch()
        actions.addWidget(button("Nhật ký", self._show_log))
        actions.addWidget(button("Mở thư mục", self._open_output))
        bottom_layout.addLayout(actions)
        outer.addWidget(bottom)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setWindowTitle("BiliScribe · Nhật ký xử lý")
        self.log.resize(900, 460)
        self.log.document().setMaximumBlockCount(2000)
        self.pages.addWidget(page)

    def _build_history(self):
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 32, 30, 26)
        layout.addWidget(label("Lịch sử xử lý", "heading"))
        layout.addWidget(label("Nhấp đúp vào một kết quả để mở thư mục kết quả transcript.", "subheading", True))
        self.history = QTableWidget(0, 3)
        self.history.setHorizontalHeaderLabels(["VIDEO", "HOÀN TẤT", "SỐ CÂU"])
        self.history.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.history.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history.verticalHeader().hide()
        self.history.cellDoubleClicked.connect(self._open_history)
        layout.addWidget(self.history, 1)
        layout.addWidget(button("Làm mới lịch sử", self._refresh_history))
        self.pages.addWidget(page)

    def _build_help(self):
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 32, 30, 26)
        layout.addWidget(label("Bắt đầu với BiliScribe", "heading"))
        help_view = QTextBrowser()
        help_view.setOpenExternalLinks(True)
        help_view.setHtml("""<style>body {font-family: 'Segoe UI'; font-size:14px; color:#203e40;} p, li {line-height:1.6;} h2 {font-size:18px; margin-top:25px;}</style>
<h2>1. Dán link, chọn chế độ, bắt đầu</h2>
<p>Mỗi link một dòng. Hỗ trợ video Bilibili và b23.tv. Link có <b>?p=2</b> sẽ xử lý đúng phần 2. Hoặc chọn file MP3, M4A, WAV, MP4… trên máy.</p>
<h2>2. Chọn độ sát và tốc độ phù hợp</h2>
<ul><li><b>Tự động:</b> SenseVoice có sẵn trên CPU; Large v3 / Turbo khi GPU sẵn sàng.</li><li><b>Ưu tiên độ sát:</b> Large v3 đầy đủ, beam 5, thêm bản SenseVoice độc lập để đánh dấu sai khác cần nghe lại. Bản chính được giữ nguyên.</li><li><b>Cân bằng:</b> Large v3 Turbo, giảm thời gian xử lý nhưng có thể nhận sai khác Large v3.</li><li><b>Máy nhẹ / nhanh:</b> SenseVoice INT8, chạy CPU, có dấu câu; phù hợp máy ít RAM.</li></ul>
<p>SenseVoice có sẵn trong bộ cài. Các mô hình Whisper cần tải một lần (~75 MB đến ~3,1 GB), sau đó dùng lại. Tốc độ phụ thuộc máy, giọng đọc và âm thanh; không có mô hình nào bảo đảm đúng 100%.</p>
<h2>3. Kết quả</h2>
<p>Khi hoàn tất, mỗi video chỉ giữ <b>Tên Việt không dấu_zh.txt</b>, <b>Tên Việt không dấu_zh.srt</b> và <b>doi_chieu_zh.txt</b>. Âm thanh, JSON và dữ liệu tạm được xóa. Nếu dừng hoặc gặp lỗi, dữ liệu được giữ để tiếp tục. File nguồn bạn chọn trên máy không bị xóa.</p>
<p><b>doi_chieu_zh.txt:</b> chỗ Large v3 và SenseVoice khác nhau trong chế độ Ưu tiên độ sát; các chế độ khác ghi rõ chưa chạy đối chiếu hai mô hình. Sai khác không chứng minh mô hình nào đúng.</p>
<p>Chế độ <b>Pixazo API</b> gửi âm thanh tới Pixazo, cần API key và credit; tối đa 4 đoạn song song. API key chỉ được nhớ khi bạn chọn, mã hóa bằng tài khoản Windows. Dừng/lỗi giữ tiến độ các đoạn đã xong. Các chế độ khác tiếp tục chạy trên máy.</p><p>App nhận dạng trên âm thanh gốc trước khi nén MP3. Không thêm lời văn, tóm tắt hay dùng mô hình ngôn ngữ để viết lại. Với Whisper, bạn có thể điền tên riêng / thuật ngữ ngắn trong Nâng cao; tránh nhập chỉ dẫn hoặc đoạn văn dài.</p>
<h2>GPU, video dài và dừng / chạy lại</h2>
<p>NVIDIA cần driver phù hợp với CUDA 12. Bấm <b>Chuẩn bị GPU NVIDIA</b> để tải thư viện chính thức vào thư mục riêng của app. Không cần cài Python hay CUDA Toolkit. Nếu không dùng được GPU, app báo và chuyển sang CPU.</p>
<p>Whisper chia âm thanh thành đoạn 5 phút; SenseVoice dùng đoạn 28 giây. Mỗi đoạn có chồng lấn và ghép theo thời gian từ để giảm mất lời ở điểm nối. Khi dừng, phần đã hoàn tất được lưu. Chạy lại cùng cấu hình để tiếp tục; chọn <b>Nhận dạng lại từ đầu</b> nếu muốn làm lại. Sai khác sát ranh giới các đoạn vẫn có thể xảy ra.</p>
<h2>Khi video yêu cầu đăng nhập</h2>
<p>Chọn Firefox hoặc file cookies.txt của tài khoản có quyền xem. Chrome / Edge có thể chặn việc đọc cookie do cơ chế mã hóa. Cookie chỉ dùng để truy cập Bilibili, không gửi tới máy chủ riêng của app.</p>
<h2>Khi transcript bỏ sót / nghe nhầm</h2>
<p>Chọn Large v3, kiểm tra tên riêng, thử tắt VAD nếu giọng quá nhỏ. Với tiếng địa phương, nhạc nền lớn, nhiều người nói chồng nhau hoặc tiếng nói bị méo, cần đối chiếu bằng tai.</p>
<p>Có thể bật thêm dịch tiếng Anh (chậm hơn, dùng Large v3). App lưu bản dịch ở file riêng để bản tiếng Trung giữ nguyên mục tiêu.</p>
<h2>Dữ liệu &amp; dung lượng</h2>
<p>Cài đặt / lịch sử / thư viện GPU được lưu ở %LOCALAPPDATA%\\BiliScribe. Mô hình lưu ở thư mục bạn chọn. Âm thanh đã tải được giữ trong .biliscribe-cache bên trong thư mục kết quả để chạy lại nhanh; có thể xóa thư mục này khi app đã dừng và không cần chạy tiếp.</p>
<p><a href='https://github.com/SYSTRAN/faster-whisper'>faster-whisper</a> · <a href='https://github.com/yt-dlp/yt-dlp'>yt-dlp</a></p>""")
        layout.addWidget(help_view)
        self.pages.addWidget(page)

    def _navigate(self, index):
        self.pages.setCurrentIndex(index)
        for i, nav in enumerate(self.nav_buttons):
            nav.setChecked(i == index)
        if index == 1:
            self._refresh_history()

    def _restore(self):
        for name in ("profile", "device", "model", "script", "cookies", "download_workers", "pixazo_workers"):
            obj = getattr(self, name)
            obj.setCurrentIndex(max(0, obj.findData(getattr(self.cfg, name))))
        self.output.setText(self.cfg.output_dir)
        self.cache_path.setText(self.cfg.cache_dir)
        self.cookie_path.setText(self.cfg.cookie_file)
        self.glossary.setText(self.cfg.glossary)
        for name in ("vad", "force"):
            getattr(self, name).setChecked(getattr(self.cfg, name))
        from .credentials import load_key
        stored = load_key()
        self.api_key.setText(stored)
        self.remember_api.setChecked(bool(stored))
        self._profile_hint()

    def _remember_api_changed(self, checked):
        if not checked:
            from .credentials import save_key
            try: save_key("")
            except OSError: self.log.appendPlainText("Chưa xóa được API key đã nhớ. Hãy thử lại.")

    def _profile_hint(self):
        hints = {"auto": "CPU dùng SenseVoice có sẵn; GPU sẵn sàng dùng Large v3 / Turbo. Tên mô hình sẽ hiện trong nhật ký.", "quality": "Large v3 (~3,1 GB tải lần đầu), thêm SenseVoice để chỉ ra chỗ khác nhau cần nghe lại. Không tự sửa lời.", "balanced": "Large v3 Turbo · ~1,6 GB tải lần đầu. Cân bằng thời gian và chất lượng.", "fast": "SenseVoice CPU INT8 · đã có sẵn, có dấu câu. Phù hợp máy ít RAM; cần kiểm tra tên riêng và từ đồng âm."}
        hints["pixazo"] = "Qwen nhận dạng trên Pixazo; không cần tải mô hình hay dùng GPU. Tự chia đoạn và chạy song song, lưu tiến độ sau từng đoạn."
        api = self.profile.currentData() == "pixazo"
        self.profile_help.setText(hints.get(self.profile.currentData(), ""))
        self.api_options.setVisible(api)
        for control in (self.device, self.model, self.gpu_button, self.glossary, self.vad):
            control.setEnabled(not api)
        self.processing_title.setText("NHẬN DẠNG QUA PIXAZO" if api else "CHẠY TRÊN MÁY CỦA BẠN")
        self.processing_note.setText("Âm thanh gửi tới Pixazo\nbằng kết nối mã hóa." if api else "Âm thanh được nhận dạng\nngay trên máy tính.")

    def _toggle_advanced(self):
        visible = not self.advanced.isVisible()
        self.advanced.setVisible(visible)
        self.advanced_toggle.setText("Cài đặt nâng cao  −" if visible else "Cài đặt nâng cao  +")

    def _add_files(self):
        names, _ = QFileDialog.getOpenFileNames(self, "Thêm audio / video", "", "Audio / video (*.mp3 *.m4a *.wav *.flac *.aac *.ogg *.mp4 *.mkv *.mov *.webm);;Tất cả (*)")
        self.local_files = list(dict.fromkeys(self.local_files + names))
        self.file_count.setText(f"Đã thêm {len(self.local_files)} file trên máy." if self.local_files else "Hỗ trợ link Bilibili, b23.tv và file trên máy.")
        self.file_count.setToolTip("\n".join(self.local_files))

    def _clear_sources(self):
        self.urls.clear()
        self.local_files.clear()
        self.file_count.setText("Hỗ trợ link Bilibili, b23.tv và file trên máy.")

    def _choose_output(self):
        value = QFileDialog.getExistingDirectory(self, "Thư mục kết quả", self.output.text())
        if value:
            self.output.setText(value)

    def _choose_cache(self):
        value = QFileDialog.getExistingDirectory(self, "Thư mục mô hình AI", self.cache_path.text())
        if value:
            self.cache_path.setText(value)

    def _choose_cookie(self):
        value, _ = QFileDialog.getOpenFileName(self, "File cookie Netscape", "", "Cookie (*.txt);;Tất cả (*)")
        if value:
            self.cookie_path.setText(value)
            self.cookies.setCurrentIndex(self.cookies.findData("file"))

    def _settings(self):
        data = asdict(self.cfg)
        for name in ("profile", "device", "model", "script", "cookies", "download_workers", "pixazo_workers"):
            data[name] = getattr(self, name).currentData()
        for name in ("vad", "force"):
            data[name] = getattr(self, name).isChecked()
        data.update(english=False, keep_source=False, output_dir=self.output.text().strip(), cache_dir=self.cache_path.text().strip(), cookie_file=self.cookie_path.text().strip(), glossary=self.glossary.text(), preview_seconds=0)
        if data["profile"] == "pixazo" and not self.api_key.text().strip():
            raise ValueError("Hãy nhập Pixazo API key trước khi bắt đầu.")
        return Settings.from_dict(data)

    def _start(self):
        if self.proc:
            return
        try:
            urls = [normalize_url(line) for line in self.urls.toPlainText().splitlines() if line.strip()]
            sources = list(dict.fromkeys(urls + self.local_files))
            if not sources:
                raise ValueError("Hãy dán ít nhất một link video hoặc chọn file trên máy.")
            if len(sources) > 100:
                raise ValueError("Mỗi lượt hỗ trợ tối đa 100 video.")
            cfg = self._settings()
            if cfg.cookies == "file" and not Path(cfg.cookie_file).is_file():
                raise ValueError("Hãy chọn file cookies.txt trong Nâng cao.")
            Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)
            Path(cfg.cache_dir).mkdir(parents=True, exist_ok=True)
            save_settings(cfg)
            self.cfg = cfg
        except (ValueError, OSError) as exc:
            self.input_error.setText(str(exc))
            self.input_error.show()
            self.urls.setFocus()
            return
        self.input_error.hide()
        self.table.setRowCount(len(sources))
        self.summaries.clear()
        self.active_index = None
        self.row_progress = {i: 0 for i in range(len(sources))}
        for i, source in enumerate(sources):
            for col, text in enumerate((Path(source).name if not source.startswith("http") else source, "Chờ xử lý", "0")):
                item = QTableWidgetItem(str(text))
                item.setToolTip(source)
                self.table.setItem(i, col, item)
        self.queue_empty.hide()
        self.preview.clear()
        self.last_folder = None
        self.open_txt_btn.setEnabled(False)
        self.srt_btn.setEnabled(False)
        self.compare_btn.setEnabled(False)
        self.review_note.setText("Đang xử lý. Kết quả và các nút mở file / đối chiếu sẽ hiện khi hoàn tất.")
        if cfg.profile == "pixazo":
            from .credentials import save_key
            try:
                save_key(self.api_key.text().strip() if self.remember_api.isChecked() else "")
            except OSError:
                self.log.appendPlainText("Không nhớ được API key; khóa chỉ được dùng trong lượt chạy này.")
        self._launch({"settings": asdict(cfg), "sources": sources}, "transcribe")

    def _prepare_gpu(self):
        if self.proc:
            return
        self._launch({"action": "gpu"}, "gpu")

    def _launch(self, request, mode):
        self.mode = mode
        self.terminal_event = False
        self.cancelling = False
        self.buffer = b""
        self.request_file = data_dir() / ("job-" + uuid.uuid4().hex + ".json")
        atomic_text(self.request_file, json.dumps(request, ensure_ascii=False))
        self.proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.remove("BILISCRIBE_PIXAZO_KEY")
        if request.get("settings", {}).get("profile") == "pixazo":
            env.insert("BILISCRIBE_PIXAZO_KEY", self.api_key.text().strip())
        env.insert("PYTHONUTF8", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        self.proc.setProcessEnvironment(env)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.proc.readyReadStandardOutput.connect(self._read_output)
        self.proc.readyReadStandardError.connect(self._drain_stderr)
        self.proc.finished.connect(self._finished)
        self.proc.errorOccurred.connect(self._process_error)
        self.proc.started.connect(self._started)
        if getattr(sys, "frozen", False):
            program = str(Path(sys.executable).with_name("BiliScribeWorker.exe"))
            arguments = ["--worker", str(self.request_file)]
        else:
            program = sys.executable
            arguments = [str(resource_path("main.py")), "--worker", str(self.request_file)]
        self.started_at = time.monotonic()
        self.progress.setRange(0, 0)
        self.status.setText("Đang chuẩn bị thư viện GPU…" if mode == "gpu" else "Đang kiểm tra cấu hình máy…")
        self._set_busy(True)
        self.log.appendPlainText("\n" + time.strftime("%H:%M:%S") + " · Bắt đầu lượt xử lý")
        self.proc.start(program, arguments)

    def _started(self):
        self.job = ProcessJob(self.proc.processId())

    def _set_busy(self, busy):
        for widget in (self.urls, self.add_file_btn, self.clear_btn, self.settings_card, self.start_btn):
            widget.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)

    def _read_output(self):
        if not self.proc:
            return
        self.buffer += bytes(self.proc.readAllStandardOutput())
        while b"\n" in self.buffer:
            line, self.buffer = self.buffer.split(b"\n", 1)
            try:
                self._event(json.loads(line.decode("utf-8")))
            except (ValueError, KeyError, TypeError):
                pass

    def _drain_stderr(self):
        if self.proc:
            # Dependency warnings can contain signed URLs; structured worker errors are displayed instead.
            self.proc.readAllStandardError()

    def _event(self, data):
        kind = data.get("event")
        if kind == "hardware":
            self.log.appendPlainText(f"Máy: RAM {data['ram_gb']} GB (còn {data['available_gb']} GB), {data['physical_cores']} nhân CPU, GPU: {data.get('gpu_name') or 'không có NVIDIA'}")
        elif kind == "plan":
            self.log.appendPlainText(f"Mô hình: {data['model']} · {data['device'].upper()} · {data['compute_type']} · batch {data['batch_size']}")
            self.progress.setRange(0, 100)
            self.progress.setValue(int(sum(self.row_progress.values()) / max(1, len(self.row_progress))))
        elif kind == "log":
            self.log.appendPlainText(data["message"])
        elif kind == "model":
            self.status.setText(data["message"])
            if data.get("progress", -1) < 0:
                self.progress.setRange(0, 0)
            else:
                self.progress.setRange(0, 100)
                self.progress.setValue(int(data["progress"]))
        elif kind == "item":
            index = data["index"]
            if index >= self.table.rowCount():
                return
            if data.get("title"):
                self.table.item(index, 0).setText(data["title"])
            if data.get("active"):
                self.active_index = index
            if data.get("stage"):
                self.table.item(index, 1).setText(data["stage"])
                if self.active_index is None or self.active_index == index:
                    self.status.setText(f"Mục {index + 1}/{self.table.rowCount()} · {data['stage']}" + (" · " + data["detail"] if data.get("detail") else ""))
            if "progress" in data:
                self.row_progress[index] = data["progress"]
                self.table.item(index, 2).setText(str(round(data["progress"])))
                self.progress.setRange(0, 100)
                self.progress.setValue(int(sum(self.row_progress.values()) / max(1, len(self.row_progress))))
            self.table.item(index, 1).setToolTip(data.get("detail", ""))
        elif kind == "heartbeat":
            if not self.cancelling:
                self.status.setText(f"Đang nhận dạng · đã đọc {data['seconds']:.0f} giây trong đoạn hiện tại")
        elif kind == "preview":
            self.preview.setPlainText(data["text"])
        elif kind == "result":
            self.summaries[data["index"]] = data
            self.last_folder = Path(data["folder"])
            self.preview_title.setText(data["title"])
            self._result_note(data)
            self.open_txt_btn.setEnabled(True)
            self._load_preview(self.last_folder)
        elif kind in {"done", "cancelled", "fatal"}:
            self.terminal_event = True
            self.progress.setRange(0, 100)
            if kind == "done":
                self.progress.setValue(100 if not data["failed"] else self.progress.value())
                self.status.setText(data.get("message") or f"Xong · {data['completed']} thành công · {data['failed']} lỗi")
            elif kind == "cancelled":
                self.status.setText("Đã dừng · Chạy lại để tiếp tục các đoạn đã lưu")
            else:
                self.status.setText("Lỗi · " + data["message"])
                self.log.appendPlainText(data["message"])

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.status.setText("Không mở được bộ xử lý. Hãy cài lại ứng dụng.")
            self.terminal_event = True
            self._finished(-1, QProcess.ExitStatus.CrashExit)

    def _finished(self, code, exit_status):
        self._read_output()
        if not self.terminal_event:
            if self.cancelling:
                self.status.setText("Đã dừng · Các đoạn hoàn tất đã được lưu")
            else:
                self.status.setText("Bộ xử lý đã dừng bất thường. Chọn CPU / mô hình nhỏ hơn rồi chạy lại để tiếp tục.")
        self.progress.setRange(0, 100)
        self._set_busy(False)
        if self.job:
            self.job.close()
            self.job = None
        if self.proc:
            self.proc.deleteLater()
            self.proc = None
        if self.request_file:
            self.request_file.unlink(missing_ok=True)
            self.request_file = None
        self.started_at = None

    def _cancel(self):
        if self.proc:
            self.cancelling = True
            self.stop_btn.setEnabled(False)
            self.status.setText("Đang dừng và giữ lại những đoạn đã lưu…")
            self.proc.write(b"cancel\n")
            active = self.proc
            QTimer.singleShot(6000, lambda: self._force_stop(active))

    def _force_stop(self, expected):
        if self.proc is expected and self.proc.state() != QProcess.ProcessState.NotRunning:
            if self.job:
                self.job.terminate()
            self.proc.kill()

    def _tick(self):
        if self.started_at:
            seconds = int(time.monotonic() - self.started_at)
            self.elapsed.setText(f"{seconds // 60:02}:{seconds % 60:02}")

    def _result_note(self, data):
        count = data.get("comparison_differences")
        if count is not None:
            text = f"{data['segments']} đoạn · {count} chỗ hai mô hình khác nhau. Bấm Đối chiếu để xem chi tiết và kiểm tra trên video gốc."
        elif data.get("model") == "qwen3-asr-flash-realtime":
            text = f"{data['segments']} đoạn · Pixazo Qwen. Mốc SRT có thể là ước lượng; chưa đối chiếu với mô hình thứ hai."
        elif data.get("model") == "sensevoice-small":
            text = f"{data['segments']} đoạn · SenseVoice. Hãy nghe lại tên riêng và thuật ngữ; mô hình không cung cấp điểm độ tin cậy."
        else:
            text = f"{data['segments']} đoạn · {data['review']} đoạn cần nghe lại. Xem file Đối chiếu."
        self.review_note.setText(text)
        self.compare_btn.setEnabled(True)

    def _open_result_file(self, name):
        if self.last_folder and (self.last_folder / name).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_folder / name)))

    def _load_preview(self, folder):
        self.srt_btn.setEnabled(transcript_file(folder, ".srt") is not None)
        path = transcript_file(folder, ".txt")
        if path:
            text = path.read_text("utf-8-sig")
            self.preview.setPlainText(text[:150000])
            if len(text) > 150000:
                self.review_note.setText("Bản xem trước hiển thị 150.000 ký tự đầu. File TXT chứa toàn bộ nội dung.")

    def _select_result(self):
        data = self.summaries.get(self.table.currentRow())
        if data:
            self.last_folder = Path(data["folder"])
            self.preview_title.setText(data["title"])
            self._result_note(data)
            self._load_preview(self.last_folder)

    def _copy_preview(self):
        QApplication.clipboard().setText(self.preview.toPlainText())

    def _open_txt(self):
        self._open_transcript(".txt")

    def _open_transcript(self, suffix):
        path = transcript_file(self.last_folder, suffix) if self.last_folder else None
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_output(self):
        path = self.last_folder or Path(self.output.text())
        try:
            path.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        except OSError as exc:
            QMessageBox.warning(self, "Không mở được thư mục", str(exc))

    def _show_log(self):
        self.log.show()
        self.log.raise_()

    def _refresh_history(self):
        records = load_history()
        self.history.setRowCount(len(records))
        for i, rec in enumerate(records):
            for column, text in enumerate((rec.get("title", ""), rec.get("completed_at", ""), str(rec.get("segments", 0)))):
                item = QTableWidgetItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, rec.get("folder", ""))
                self.history.setItem(i, column, item)

    def _open_history(self, row, column):
        path = Path(self.history.item(row, 0).data(Qt.ItemDataRole.UserRole))
        if path.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(self, "Kết quả đã di chuyển", "Thư mục này đã được di chuyển hoặc xóa.")

    def start_update_check(self):
        if self.update_check is not None:
            return
        from .updates import StartupCheck
        self.update_check = StartupCheck()
        self.update_check.start()
        self.update_timer.start(150)

    def _poll_update(self):
        result = self.update_check.poll() if self.update_check else None
        if result is None:
            return
        self.update_timer.stop()
        status, update = result
        if status != "ok":
            self.log.appendPlainText("Chưa kiểm tra được bản cập nhật. App sẽ thử lại vào lần mở sau.")
        elif update is None:
            self.log.appendPlainText("BiliScribe đang ở phiên bản mới nhất.")
        else:
            self.update_url = update.url
            self.update_btn.setText(f"Có bản {update.version}\nMở trang tải")
            self.update_btn.setToolTip("Mở GitHub để tải bộ cài mới.")
            self.update_btn.show()
            self.log.appendPlainText(f"Có BiliScribe {update.version}. Bấm Mở trang tải ở thanh bên trái.")

    def _open_update(self):
        if self.update_url:
            QDesktopServices.openUrl(QUrl(self.update_url))

    def closeEvent(self, event):
        if self.proc:
            reply = QMessageBox.question(self, "Đóng BiliScribe", "Đang xử lý. Dừng công việc và đóng ứng dụng? Phần đã hoàn tất vẫn được giữ.")
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            if self.job:
                self.job.terminate()
            self.proc.kill()
            self.proc.waitForFinished(2000)
        self.update_timer.stop()
        if self.update_check:
            self.update_check.close()
        self.log.close()
        event.accept()


def run_gui():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("BiliScribe")
    app.setOrganizationName("BiliScribe")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    QTimer.singleShot(500, window.start_update_check)
    return app.exec()
