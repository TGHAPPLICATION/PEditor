"""PyInstaller 進入點（避免以套件內 __main__.py 直接凍結造成相對匯入問題）。"""

import sys

from peditor.__main__ import main

sys.exit(main())
