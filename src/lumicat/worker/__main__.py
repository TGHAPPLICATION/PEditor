"""`python -m lumicat.worker`：啟動 PDF worker 子行程。"""

import sys

from lumicat.worker.server import main

if __name__ == "__main__":
    sys.exit(main())
