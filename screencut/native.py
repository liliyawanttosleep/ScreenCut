"""Small, explicit Win32 boundary. Never intercept arbitrary keystrokes."""
import ctypes
from ctypes import wintypes
from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtGui import QKeySequence

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = wintypes.HWND

def parse_hotkey(text):
    if not text:
        return None
    parts = text.split("+")
    modifiers = {"Ctrl": 2, "Alt": 1, "Shift": 4, "Meta": 8, "Win": 8}
    mod = 0
    for p in parts[:-1]:
        if p not in modifiers:
            raise ValueError(text)
        mod |= modifiers[p]
    key = parts[-1].upper()
    if len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key)
    elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 111 + int(key[1:])
    else:
        raise ValueError(text)
    if not mod or vk == 123:  # F12 is reserved for debuggers.
        raise ValueError(text)
    return mod, vk

class Hotkeys(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.ids = {}

    def clear(self):
        for ident in self.ids:
            user32.UnregisterHotKey(None, ident)
        self.ids.clear()

    def register(self, mapping):
        self.clear()
        status = {}
        for ident, (action, text) in enumerate(mapping.items(), 1):
            try:
                parsed = parse_hotkey(text)
                if parsed is None:
                    status[action] = "disabled"
                elif user32.RegisterHotKey(None, ident, parsed[0] | 0x4000, parsed[1]):
                    self.ids[ident] = action
                    status[action] = "active"
                else:
                    status[action] = "conflict"
            except ValueError:
                status[action] = "invalid"
        return status

    def nativeEventFilter(self, event_type, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == 0x312 and msg.wParam in self.ids:
            self.callback(self.ids[msg.wParam])
            return True, 0
        return False, 0

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("data", INPUTUNION)]

user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]

def modifiers_down():
    return any(user32.GetAsyncKeyState(k) & 0x8000 for k in (0x10, 0x11, 0x12, 0x5B, 0x5C))

def paste():
    events = (INPUT * 4)(*[INPUT(1, INPUTUNION(ki=KEYBDINPUT(vk, 0, flags, 0, 0)))
                         for vk, flags in ((0x11, 0), (0x56, 0), (0x56, 2), (0x11, 2))])
    return user32.SendInput(4, events, ctypes.sizeof(INPUT)) == 4

def monitor_rect(device, geometry=None, ratio=1.0):
    class INFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR * 32)]
    result = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                      ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(INFO)]
    @callback_type
    def callback(handle, dc, rect, data):
        info = INFO()
        info.cbSize = ctypes.sizeof(INFO)
        if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            r = info.rcMonitor
            result.append((info.szDevice, (r.left, r.top, r.right-r.left, r.bottom-r.top)))
        return True
    user32.EnumDisplayMonitors(None, None, callback, 0)
    for name, rect in result:
        if name == device:
            return rect
    # Qt 6 may expose the EDID friendly name instead of the Win32 device name.
    # On Windows Qt scales monitor sizes, but keeps native monitor origins.
    if geometry is not None:
        matches = [rect for name, rect in result
                   if rect[0:2] == (geometry.x(), geometry.y())
                   and abs(rect[2]-geometry.width()*ratio) < 3
                   and abs(rect[3]-geometry.height()*ratio) < 3]
        if len(matches) == 1:
            return matches[0]
    raise RuntimeError("Display no longer available: " + device)
