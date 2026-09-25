import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox
from biliscribe.ui import MainWindow

def test_all_dropdowns_ignore_wheel_but_keyboard_and_click_work(tmp_path, monkeypatch):
    monkeypatch.setenv("BILISCRIBE_DATA_DIR", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    win = MainWindow(); win.show(); win.advanced.show(); app.processEvents()
    boxes = win.findChildren(QComboBox)
    assert len(boxes) >= 6
    for box in boxes:
        box.setCurrentIndex(1); box.setFocus(); app.processEvents()
        for delta in (120, -120, 480, -480):
            event = QWheelEvent(QPointF(10,10), QPointF(box.mapToGlobal(QPoint(10,10))), QPoint(), QPoint(0,delta), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
            app.sendEvent(box, event)
            assert box.currentIndex() == 1
        QTest.keyClick(box, Qt.Key.Key_Down)
        assert box.currentIndex() == min(2, box.count()-1)
        box.showPopup(); app.processEvents()
        idx = box.model().index(0, 0)
        QTest.mouseClick(box.view().viewport(), Qt.MouseButton.LeftButton, pos=box.view().visualRect(idx).center())
        assert box.currentIndex() == 0
    assert win.srt_btn.text() == "Mở SRT"
    win.close()
