"""理由碼與提示碼 → 繁中說明（G4-05：不可編輯物件須顯示原因）。訊息不含文件原文或路徑。"""

from __future__ import annotations

REASONS = {
    "UNSUPPORTED_ENCODING": "字型編碼無法可靠對應文字（缺少或不一致的 ToUnicode），無法安全修改",
    "UNSUPPORTED_LAYOUT": "版面不支援（直排、旋轉、Form 內文字、換行顯示或跨段落等）",
    "UNSUPPORTED_FEATURE": "含不支援的功能（例如 /ActualText、XFA、PDF/A 或跨標記內容）",
    "GLYPH_MISSING": "原字型與內建字型（Noto Sans TC）都缺少部分新字",
    "TEXT_OVERFLOW": "新文字會超出可改動區域；不會自動縮小字級",
    "SHARED_RESOURCE_UNSAFE": "這段內容被多處共用，修改會連帶改動其他位置",
    "SIGNED_DOCUMENT": "文件含數位簽章，修改會使簽章失效，不提供編輯",
    "ENCRYPTED_DOCUMENT": "文件已加密，不提供編輯",
    "REVISION_CONFLICT": "檔案或文件版本已改變，請重新開啟後再試",
    "RESOURCE_LIMIT": "文件超過處理上限或處理逾時",
    "VALIDATION_FAILED": "修改後的驗證未通過，未寫入任何變更",
    "SAVE_FAILED": "無法另存",
    "CANCELLED": "已取消，未提交變更",
    "NO_TEXT_LAYER": "此頁沒有文字層（例如掃描或圖片頁），只能檢視",
    "MALFORMED_DOCUMENT": "檔案結構損壞或需修復，不提供編輯",
    "ACTIVE_CONTENT": "文件含主動內容（JavaScript、自動動作等），不提供編輯",
    "INVALID_REQUEST": "操作無法執行",
    "WORKER_FAILED": "處理程序異常結束，已重新啟動；未提交變更",
}

NOTICES = {
    "PREVIEW_UNRELIABLE": (
        "此頁字型不符 PDF 規範（CID 與字型程式不一致），預覽可能空白；另存不受影響"
    ),
}


def reason_text(code: str) -> str:
    return REASONS.get(code, f"不支援（{code}）")


def reasons_text(codes: list[str]) -> str:
    return "；".join(reason_text(c) for c in dict.fromkeys(codes))
