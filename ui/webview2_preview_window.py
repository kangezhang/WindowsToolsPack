"""
Edge WebView2 preview window.

This runs in a separate process so the WebView2 event loop does not conflict
with the Qt workbench window.
"""

from __future__ import annotations

import argparse
import sys


def run_webview2_preview(
    url: str,
    title: str = "WebView2 预览",
    width: int = 1280,
    height: int = 820,
    x: int | None = None,
    y: int | None = None,
    frameless: bool = False,
) -> int:
    try:
        import webview
    except ImportError:
        print("请安装 pywebview: pip install pywebview")
        return 1

    kwargs = {
        "title": title,
        "url": url,
        "width": max(240, int(width)),
        "height": max(180, int(height)),
        "resizable": True,
        "text_select": True,
        "frameless": frameless,
    }
    if x is not None:
        kwargs["x"] = int(x)
    if y is not None:
        kwargs["y"] = int(y)

    try:
        window = webview.create_window(**kwargs)
    except TypeError:
        kwargs.pop("frameless", None)
        kwargs.pop("x", None)
        kwargs.pop("y", None)
        window = webview.create_window(**kwargs)
    try:
        webview.start(gui="edgechromium", debug=False)
    except TypeError:
        webview.start(debug=False)
    return 0 if window else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open a URL in Edge WebView2 preview.")
    parser.add_argument("url", help="URL to open")
    parser.add_argument("--title", default="WebView2 预览", help="Window title")
    parser.add_argument("--x", type=int, default=None, help="Window left position")
    parser.add_argument("--y", type=int, default=None, help="Window top position")
    parser.add_argument("--width", type=int, default=1280, help="Window width")
    parser.add_argument("--height", type=int, default=820, help="Window height")
    parser.add_argument("--frameless", action="store_true", help="Use frameless window style")
    args = parser.parse_args(argv)
    return run_webview2_preview(
        args.url,
        args.title,
        width=args.width,
        height=args.height,
        x=args.x,
        y=args.y,
        frameless=args.frameless,
    )


if __name__ == "__main__":
    sys.exit(main())
