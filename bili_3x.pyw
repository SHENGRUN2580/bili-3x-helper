# -*- coding: utf-8 -*-
"""
B站 3x 助手

原理：B站播放器里「长按 →」会临时进入 3 倍速，松开恢复。
本工具在 B站窗口处于前台时，替你虚拟按住右方向键；
切换到其它窗口会自动松开，避免影响其它软件。

按 F8 开关。只对哔哩哔哩进程生效。
"""

import atexit
import ctypes
import os
import queue
import sys
import threading
import time
import tkinter as tk
from ctypes import wintypes

# ---------------------------------------------------------------------------
# Win32
# ---------------------------------------------------------------------------

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
VK_RIGHT = 0x27
VK_F8 = 0x77
VK_F9 = 0x78
VK_LBUTTON = 0x01
WM_HOTKEY = 0x0312
WM_KEYUP = 0x0101
MOD_NOREPEAT = 0x4000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000

user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetWindowTextW.restype = ctypes.c_int
user32.IsWindow.argtypes = (wintypes.HWND,)
user32.IsWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
user32.ShowWindow.restype = wintypes.BOOL
user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
user32.AttachThreadInput.restype = wintypes.BOOL
user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = (ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
user32.GetMessageW.restype = wintypes.BOOL
user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.PostMessageW.restype = wintypes.BOOL
user32.GetParent.argtypes = (wintypes.HWND,)
user32.GetParent.restype = wintypes.HWND
user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
user32.GetWindowLongW.restype = wintypes.LONG
user32.SetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.LONG)
user32.SetWindowLongW.restype = wintypes.LONG
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = wintypes.SHORT
user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
user32.FindWindowW.restype = wintypes.HWND
user32.MessageBoxW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
user32.MessageBoxW.restype = ctypes.c_int

kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD),
)
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
kernel32.CreateMutexW.restype = wintypes.HANDLE
ERROR_ALREADY_EXISTS = 183


def _send_right(flags):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ki = KEYBDINPUT(VK_RIGHT, 0, flags, 0, 0)
    return user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def right_down():
    return _send_right(KEYEVENTF_EXTENDEDKEY)


def right_up():
    return _send_right(KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP)


def foreground_info():
    """返回 (hwnd, 进程名, 窗口标题)。"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, "", ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    name = ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if handle:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            name = os.path.basename(buf.value)
        kernel32.CloseHandle(handle)
    title_buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title_buf, 512)
    return hwnd, name, title_buf.value


def is_bilibili(name):
    name = (name or "").lower()
    return "哔哩哔哩" in name or "bilibili" in name


def focus_window(hwnd):
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    current_fg = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(current_fg, None) if current_fg else 0
    my_thread = kernel32.GetCurrentThreadId()
    attached = False
    if fg_thread and fg_thread != my_thread:
        attached = bool(user32.AttachThreadInput(my_thread, fg_thread, True))
    ok = bool(user32.SetForegroundWindow(hwnd))
    if attached:
        user32.AttachThreadInput(my_thread, fg_thread, False)
    return ok


def post_right_keyup(hwnd):
    """尽量让 B站窗口收到一次 keyup，避免它停留在 3x。"""
    if hwnd and user32.IsWindow(hwnd):
        # repeat=1, scan=0x4D, extended=1, previous=1, transition=1
        user32.PostMessageW(hwnd, WM_KEYUP, VK_RIGHT, 0xC14D0001)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

BG = "#15161b"
CARD = "#1e2028"
TEXT = "#f2f3f5"
MUTED = "#8b8f9a"
GREEN = "#22c55e"
GREEN_ACTIVE = "#16a34a"
AMBER = "#fbbf24"
RED = "#ef4444"
RED_ACTIVE = "#dc2626"

FONT = "Microsoft YaHei UI"

enabled = False
holding = False
last_bili_hwnd = None
last_title = ""
prev_bili = False
tick_count = 0
root = None
status_dot = None
status_dot_id = None
status_text = None
toggle_btn = None
ui_queue = queue.Queue()
tool_hwnd = None
hidden = False
last_refocus = 0.0
single_mutex = None
LOG_PATH = os.path.join(os.environ.get("TEMP", "."), "bili_3x.log")


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S") + " " + msg + "\n")
    except Exception:
        pass


def set_status(text, color):
    if status_text.cget("text") != text:
        status_text.config(text=text)
    status_dot.itemconfig(status_dot_id, fill=color)


def set_button():
    if enabled:
        toggle_btn.config(
            text="停止 3x  ·  F8",
            bg=RED,
            activebackground=RED_ACTIVE,
            fg="#1a0606",
        )
    else:
        toggle_btn.config(
            text="开启 3x  ·  F8",
            bg=GREEN,
            activebackground=GREEN_ACTIVE,
            fg="#08110d",
        )


def press():
    global holding
    if not enabled:
        return
    right_down()
    holding = True
    log("keydown")


def release():
    global holding
    if holding:
        right_up()
        holding = False
        log("keyup")


def rearm():
    """先 keyup 再 keydown，确保播放器的按键状态是干净的。"""
    global holding
    if not enabled:
        return
    set_status("正在开启…", AMBER)
    release()
    right_up()
    root.after(70, press)


def hide_window():
    global hidden
    hidden = True
    root.withdraw()
    log("hide window")


def show_window():
    global hidden
    hidden = False
    root.deiconify()
    root.lift()
    root.attributes("-topmost", True)
    log("show window")


def start_enabled():
    global enabled, last_bili_hwnd, last_title
    enabled = True
    set_button()
    log("enabled")
    hwnd, name, title = foreground_info()
    if is_bilibili(name):
        last_bili_hwnd = hwnd
        last_title = title
        rearm()
    else:
        if last_bili_hwnd and user32.IsWindow(last_bili_hwnd):
            set_status("正在切回 B站…", AMBER)
            focus_window(last_bili_hwnd)
            root.after(260, after_refocus)
        else:
            set_status("已开启 · 请切到 B站播放器", AMBER)


def after_refocus():
    global last_bili_hwnd, last_title
    if not enabled:
        return
    hwnd, name, title = foreground_info()
    if is_bilibili(name):
        last_bili_hwnd = hwnd
        last_title = title
        rearm()
    else:
        set_status("已开启 · 请切到 B站播放器", AMBER)


def _finish_force_release(prev_hwnd, restore):
    right_up()
    right_up()
    if last_bili_hwnd:
        post_right_keyup(last_bili_hwnd)
    if restore and prev_hwnd and user32.IsWindow(prev_hwnd) and prev_hwnd != tool_hwnd:
        focus_window(prev_hwnd)
    log("force release finished")


def force_release(restore_foreground=True):
    """确保 B站 收到 keyup，即使当前前台不是 B站。"""
    prev_hwnd = user32.GetForegroundWindow()
    release()
    hwnd, name, title = foreground_info()
    if is_bilibili(name):
        right_up()
        right_up()
        if last_bili_hwnd:
            post_right_keyup(last_bili_hwnd)
        log("force release (bilibili foreground)")
        return
    if last_bili_hwnd and user32.IsWindow(last_bili_hwnd):
        focus_window(last_bili_hwnd)
        root.after(120, lambda: _finish_force_release(prev_hwnd, restore_foreground))
    else:
        right_up()
        log("force release (no bilibili window)")


def stop_enabled():
    global enabled
    enabled = False
    set_button()
    set_status("未开启", MUTED)
    log("disabled")
    force_release(True)


def toggle():
    if enabled:
        stop_enabled()
    else:
        start_enabled()


def toggle_visible():
    if hidden:
        show_window()
    else:
        hide_window()


def tick():
    global tick_count, last_bili_hwnd, last_title, prev_bili, last_refocus
    tick_count += 1
    hwnd, name, title = foreground_info()
    bili = is_bilibili(name)

    # 兜底：如果工具窗口意外成了前台（比如拖动标题栏），
    # 鼠标松开后自动把焦点还给 B站，避免加速中断。
    if enabled and tool_hwnd and hwnd == tool_hwnd:
        if not (user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000):
            now = time.monotonic()
            if now - last_refocus > 0.8:
                last_refocus = now
                if last_bili_hwnd and user32.IsWindow(last_bili_hwnd):
                    focus_window(last_bili_hwnd)
                    log("refocus bilibili after tool interaction")
        set_status("3x 保持中", GREEN if holding else AMBER)
        root.after(200, tick)
        return

    if bili:
        last_bili_hwnd = hwnd
        if enabled:
            if not prev_bili:
                prev_bili = True
                last_title = title
                rearm()
                log("bilibili foreground -> rearm")
            elif title and last_title and title != last_title:
                last_title = title
                rearm()
                log("title changed -> rearm")
            elif not holding:
                press()
            elif tick_count % 3 == 0:
                # 周期性补一次 keydown：若播放器在换集后重置了按键状态，
                # 下一次 keydown 会重新触发 3x；若状态仍在，会被播放器忽略。
                right_down()
            if holding:
                set_status("3x 保持中", GREEN)
        else:
            set_status("未开启", MUTED)
    else:
        if prev_bili:
            prev_bili = False
            release()
            if last_bili_hwnd:
                post_right_keyup(last_bili_hwnd)
            log("bilibili lost foreground -> release")
        set_status("已开启 · 等待 B站窗口" if enabled else "未开启", AMBER if enabled else MUTED)

    root.after(200, tick)


def poll_ui_queue():
    try:
        while True:
            fn = ui_queue.get_nowait()
            fn()
    except queue.Empty:
        pass
    root.after(60, poll_ui_queue)


def hotkey_loop():
    ok_f8 = user32.RegisterHotKey(None, 1, MOD_NOREPEAT, VK_F8)
    ok_f9 = user32.RegisterHotKey(None, 2, MOD_NOREPEAT, VK_F9)
    if not ok_f8 and not ok_f9:
        return
    msg = MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                if msg.wParam == 1:
                    ui_queue.put(toggle)
                elif msg.wParam == 2:
                    ui_queue.put(toggle_visible)
    finally:
        if ok_f8:
            user32.UnregisterHotKey(None, 1)
        if ok_f9:
            user32.UnregisterHotKey(None, 2)


def on_close():
    global enabled
    enabled = False
    release()
    if last_bili_hwnd and user32.IsWindow(last_bili_hwnd):
        focus_window(last_bili_hwnd)
        right_up()
        right_up()
        post_right_keyup(last_bili_hwnd)
    root.destroy()


def start_move(event):
    root._drag_x = event.x_root - root.winfo_x()
    root._drag_y = event.y_root - root.winfo_y()


def do_move(event):
    root.geometry(f"+{event.x_root - root._drag_x}+{event.y_root - root._drag_y}")


def build_ui():
    global root, status_dot, status_dot_id, status_text, toggle_btn, tool_hwnd

    root = tk.Tk()
    root.title("B站 3x 助手")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.protocol("WM_DELETE_WINDOW", on_close)

    width, height = 372, 262
    screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{width}x{height}+{screen_w - width - 28}+{screen_h - height - 72}")

    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", padx=18, pady=(16, 0))
    header.bind("<ButtonPress-1>", start_move)
    header.bind("<B1-Motion>", do_move)

    title_label = tk.Label(
        header,
        text="B站 3x 助手",
        font=(FONT, 14, "bold"),
        fg=TEXT,
        bg=BG,
    )
    title_label.pack(side="left")
    title_label.bind("<ButtonPress-1>", start_move)
    title_label.bind("<B1-Motion>", do_move)

    hint_label = tk.Label(
        header,
        text="F8 开关 · F9 隐藏",
        font=(FONT, 8),
        fg=MUTED,
        bg=BG,
    )
    hint_label.pack(side="right", pady=(5, 0))
    hint_label.bind("<ButtonPress-1>", start_move)
    hint_label.bind("<B1-Motion>", do_move)

    tk.Label(
        root,
        text="虚拟按住 →，让播放器保持 3 倍速",
        font=(FONT, 9),
        fg=MUTED,
        bg=BG,
    ).pack(anchor="w", padx=18, pady=(2, 0))

    card = tk.Frame(root, bg=CARD)
    card.pack(fill="both", expand=True, padx=16, pady=12)

    status_row = tk.Frame(card, bg=CARD)
    status_row.pack(anchor="w", padx=16, pady=(14, 0))
    status_dot = tk.Canvas(status_row, width=10, height=10, bg=CARD, highlightthickness=0)
    status_dot.pack(side="left", pady=2)
    status_dot_id = status_dot.create_oval(1, 1, 9, 9, fill=MUTED, outline="")
    status_text = tk.Label(
        status_row,
        text="未开启",
        font=(FONT, 12, "bold"),
        fg=TEXT,
        bg=CARD,
    )
    status_text.pack(side="left", padx=(8, 0))

    toggle_btn = tk.Button(
        card,
        text="开启 3x  ·  F8",
        font=(FONT, 11, "bold"),
        fg="#08110d",
        bg=GREEN,
        activebackground=GREEN_ACTIVE,
        activeforeground="#08110d",
        relief="flat",
        bd=0,
        cursor="hand2",
        command=toggle,
    )
    toggle_btn.pack(fill="x", padx=16, pady=(14, 6), ipady=9)

    footer = tk.Frame(card, bg=CARD)
    footer.pack(fill="x", padx=16, pady=(0, 10))
    tk.Label(
        footer,
        text="只对哔哩哔哩窗口生效",
        font=(FONT, 8),
        fg=MUTED,
        bg=CARD,
    ).pack(side="left")
    tk.Button(
        footer,
        text="退出",
        font=(FONT, 8),
        fg=MUTED,
        bg=CARD,
        activebackground="#2a2d36",
        activeforeground=TEXT,
        relief="flat",
        bd=0,
        cursor="hand2",
        command=on_close,
    ).pack(side="right", padx=(0, 10))
    tk.Button(
        footer,
        text="隐藏 F9",
        font=(FONT, 8),
        fg=MUTED,
        bg=CARD,
        activebackground="#2a2d36",
        activeforeground=TEXT,
        relief="flat",
        bd=0,
        cursor="hand2",
        command=hide_window,
    ).pack(side="right")

    set_button()

    # 让工具窗口不抢焦点：拖动、点击都不会把 B站的键盘焦点夺走。
    root.update()
    child = root.winfo_id()
    parent = user32.GetParent(child)
    tool_hwnd = parent if parent else child
    style = user32.GetWindowLongW(tool_hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(tool_hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE)
    log("tool hwnd=" + str(tool_hwnd))


def main():
    global root, single_mutex
    if "--selftest" in sys.argv:
        hwnd, name, title = foreground_info()
        print("foreground:", hwnd, name, title)
        ok = user32.RegisterHotKey(None, 99, 0, VK_F8)
        print("hotkey F8 available:", bool(ok))
        if ok:
            user32.UnregisterHotKey(None, 99)
        test_root = tk.Tk()
        test_root.withdraw()
        test_root.update()
        test_root.destroy()
        print("selftest ok")
        return

    ctypes.set_last_error(0)
    single_mutex = kernel32.CreateMutexW(None, False, "Local\\Bili3xHelper_SingleInstance")
    already = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
    if already or user32.FindWindowW(None, "B站 3x 助手"):
        user32.MessageBoxW(
            None,
            "B站 3x 助手已经在运行了。\n请使用已经打开的窗口；\n如果找不到窗口，先在任务管理器里结束旧的 pythonw.exe。",
            "B站 3x 助手",
            0x40,
        )
        return

    atexit.register(right_up)
    try:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " start\n")
    except Exception:
        pass
    build_ui()
    threading.Thread(target=hotkey_loop, daemon=True).start()
    root.after(200, tick)
    root.after(60, poll_ui_queue)
    root.mainloop()


if __name__ == "__main__":
    main()
