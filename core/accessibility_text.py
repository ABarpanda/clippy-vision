from __future__ import annotations

import re
from collections import deque

from core.platform_support import IS_MACOS, IS_WINDOWS, _run_command


MAX_TEXT_CHARS = 4000
MIN_USEFUL_CHARS = 40
MAX_UI_NODES = 250
MAX_UI_DEPTH = 8
_SPACE_RE = re.compile(r"[ \t\r\f\v]+")


def normalize_accessibility_text(*values: object) -> str:
    seen = set()
    lines = []
    for value in values:
        for raw_line in str(value or "").splitlines():
            line = _SPACE_RE.sub(" ", raw_line).strip()
            key = line.casefold()
            if len(line) >= 2 and key not in seen:
                seen.add(key)
                lines.append(line)
    return "\n".join(lines)[:MAX_TEXT_CHARS]


def is_useful_accessibility_text(text: str) -> bool:
    compact = "".join(character for character in text if character.isalnum())
    return len(compact) >= MIN_USEFUL_CHARS and len(text.split()) >= 4


def _windows_text() -> str:
    try:
        import uiautomation as auto
        import win32gui

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return ""
        root = auto.ControlFromHandle(hwnd)
        queue = deque([(root, 0)])
        values = []
        visited = 0
        while queue and visited < MAX_UI_NODES:
            control, depth = queue.popleft()
            visited += 1
            try:
                if bool(getattr(control, "IsPasswordProperty", False)):
                    continue
                values.append(getattr(control, "Name", ""))
                try:
                    values.append(control.GetValuePattern().Value)
                except Exception:
                    pass
                if depth < MAX_UI_DEPTH:
                    queue.extend((child, depth + 1) for child in control.GetChildren())
            except Exception:
                continue
            if sum(len(str(value or "")) for value in values) >= MAX_TEXT_CHARS * 2:
                break
        return normalize_accessibility_text(*values)
    except Exception:
        return ""


_MAC_ACCESSIBILITY_SCRIPT = r'''
tell application "System Events"
    set frontProc to first application process whose frontmost is true
    set outputText to ""
    try
        set uiItems to entire contents of front window of frontProc
        repeat with uiItem in uiItems
            try
                set itemRole to role of uiItem
                if itemRole is not "AXSecureTextField" then
                    set itemText to ""
                    try
                        set itemText to value of uiItem as text
                    end try
                    if itemText is "" or itemText is "missing value" then
                        try
                            set itemText to name of uiItem as text
                        end try
                    end if
                    if itemText is not "" and itemText is not "missing value" then
                        set outputText to outputText & itemText & linefeed
                    end if
                end if
            end try
            if length of outputText > 8000 then exit repeat
        end repeat
    end try
    return outputText
end tell
'''


def _mac_text() -> str:
    return normalize_accessibility_text(
        _run_command(["osascript", "-e", _MAC_ACCESSIBILITY_SCRIPT], timeout=2.0)
    )


def extract_accessibility_text() -> str:
    """Read bounded text from the foreground UI without taking a screenshot."""
    if IS_WINDOWS:
        return _windows_text()
    if IS_MACOS:
        return _mac_text()
    return ""
