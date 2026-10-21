"""資源限制設定點（spec P7 限制參數初值；ADR-0004「P1 先預留設定點」）。

這些是產品政策待實測值，不是程式庫保證。P1 只在開檔時檢查檔案大小與頁數，
並對每個請求設逾時；記憶體、解壓與巢狀深度的完整限制於 P7 加上。
"""

MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_PAGES = 500
REQUEST_TIMEOUT_S = 30.0
MAX_FORM_DEPTH = 8
MAX_RENDER_DPI = 300
