"""
Canonical entry module for the video download/playback workbench window.
Keeps a stable generic name while reusing the existing implementation.
"""

import sys

from ui.bilibili_downloader_window import (  # noqa: F401
    VideoDownloadWorkbenchWindow,
    run_qt_app,
)


if __name__ == "__main__":
    sys.exit(run_qt_app())
