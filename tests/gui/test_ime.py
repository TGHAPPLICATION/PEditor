"""G4-02：IME 組字中的 preedit 不送出規劃；確認（commit）後按 Enter 才規劃。

offscreen 沒有真正的輸入法，以 QInputMethodEvent 模擬組字與確認；
注音／倉頡等實機輸入法在 Windows、macOS 實機人工驗收（ADR-0021 §3）。
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QInputMethodEvent
from PySide6.QtWidgets import QApplication
from test_e2e import FILES, find, open_file, wait


def compose(box, preedit):
    QApplication.sendEvent(box, QInputMethodEvent(preedit, []))


def commit(box, text):
    event = QInputMethodEvent()
    event.setCommitString(text)
    QApplication.sendEvent(box, event)


def test_preedit_not_committed(qtbot, make_window, monkeypatch):
    window = make_window()
    open_file(qtbot, window, FILES / "T01.pdf")
    find(qtbot, window, "衛生局")
    planned = []
    original = window.service.plan_text_edit

    def spy(doc, target_id, new_text, *args):
        planned.append(new_text)
        return original(doc, target_id, new_text, *args)

    monkeypatch.setattr(window.service, "plan_text_edit", spy)
    box = window.panel.new_text
    box.clear()

    compose(box, "ㄘㄜˋ")
    assert box.text() == "" and planned == [] and not window.busy and window.plan is None
    commit(box, "測")
    compose(box, "ㄕˋ")
    assert box.text() == "測" and planned == []  # 確認字不觸發規劃；組字中的字不在內容裡

    commit(box, "試局")
    qtbot.keyClick(box, Qt.Key.Key_Return)
    wait(qtbot, window)
    assert planned == ["測試局"] and window.plan["ready"]
