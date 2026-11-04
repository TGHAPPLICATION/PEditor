"""資源限制設定點（spec P7 限制參數初值；ADR-0004「P1 先預留設定點」）。

這些是產品政策待實測值，不是程式庫保證。P1 先限制檔案大小、頁數、逾時，
以及 P1 安全掃描（reports/P1/security/TRIAGE.md）確認會被惡意 PDF 放大的解析工作量；
P7 加上 worker 記憶體上限與解壓前的大小限制（ADR-0024）。
"""

MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_PAGES = 500
REQUEST_TIMEOUT_S = 30.0
MAX_FORM_DEPTH = 8
MAX_RENDER_DPI = 300
WORKER_MEMORY_BYTES = 2 * 1024 * 1024 * 1024  # spec P7「worker 2 GB」；Windows 由 Job Object 強制
MAX_STREAM_BYTES = 64 * 1024 * 1024  # 單一內容／字型串流解壓後大小；解壓前先檢查（P2 triage f024）

# P1 安全掃描（f001、f004、f005、f009、f012、f016）後加入
MAX_RENDER_PIXELS = 50_000_000  # spec P7「單張影像 50 MP」
MAX_CONTENT_OPERATORS = 1_000_000  # 每頁執行的運算子總數（含 Form）
MAX_FORM_INVOCATIONS = 10_000  # 每頁 Form XObject 呼叫次數
MAX_GSTATE_DEPTH = 256  # q 巢狀深度
MAX_CLIPS = 64  # 同一圖形狀態累積的 clip 數
MAX_CMAP_BYTES = 4 * 1024 * 1024  # 單一 ToUnicode CMap 解壓後大小
MAX_CODE_EXPANSION = 4 * 65536  # 單一字型 /W 或 ToUnicode 展開的字碼總數
MAX_OBJECT_WALK = 10_000  # 走訪表單欄位樹、書籤樹的節點數

# P5 圖片替換（ADR-0022）：使用者提供的圖片檔
MAX_IMAGE_BYTES = 32 * 1024 * 1024  # 以 base64 經 IPC 傳送，須在 MAX_MESSAGE_BYTES 之內
MAX_IMAGE_PIXELS = 50_000_000  # spec P7「單張影像 50 MP」；含補透明邊後的尺寸

# P6 表格格線偵測（ADR-0023）
MAX_RULE_PATHS = 20_000  # 每頁記錄的直線段＋填色矩形；超過即不做表格偵測
MAX_TABLE_CELLS = 10_000  # 單一表格的格線網格格數上限
MAX_PAINTED_POINTS = (
    100_000  # 每頁記錄的已繪製路徑點數（障礙線用，含曲線控制點）；超過即不做表格偵測
)
MAX_RULE_PAIRS = 1_000_000  # 水平線數×垂直線數（交會判定的工作量）；超過即不做表格偵測


class LimitExceeded(Exception):
    """解析工作量超過上限；呼叫端應回報 RESOURCE_LIMIT，不得繼續以部分結果判定可編輯。"""
