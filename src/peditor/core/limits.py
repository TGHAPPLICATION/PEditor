"""資源限制設定點（spec P7 限制參數初值；ADR-0004「P1 先預留設定點」）。

這些是產品政策待實測值，不是程式庫保證。P1 先限制檔案大小、頁數、逾時，
以及 P1 安全掃描（reports/P1/security/TRIAGE.md）確認會被惡意 PDF 放大的解析工作量；
記憶體與解壓的完整限制於 P7 加上。
"""

MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_PAGES = 500
REQUEST_TIMEOUT_S = 30.0
MAX_FORM_DEPTH = 8
MAX_RENDER_DPI = 300

# P1 安全掃描（f001、f004、f005、f009、f012、f016）後加入
MAX_RENDER_PIXELS = 50_000_000  # spec P7「單張影像 50 MP」
MAX_CONTENT_OPERATORS = 1_000_000  # 每頁執行的運算子總數（含 Form）
MAX_FORM_INVOCATIONS = 10_000  # 每頁 Form XObject 呼叫次數
MAX_GSTATE_DEPTH = 256  # q 巢狀深度
MAX_CLIPS = 64  # 同一圖形狀態累積的 clip 數
MAX_CMAP_BYTES = 4 * 1024 * 1024  # 單一 ToUnicode CMap 解壓後大小
MAX_CODE_EXPANSION = 4 * 65536  # 單一字型 /W 或 ToUnicode 展開的字碼總數
MAX_OBJECT_WALK = 10_000  # 走訪表單欄位樹、書籤樹的節點數


class LimitExceeded(Exception):
    """解析工作量超過上限；呼叫端應回報 RESOURCE_LIMIT，不得繼續以部分結果判定可編輯。"""
