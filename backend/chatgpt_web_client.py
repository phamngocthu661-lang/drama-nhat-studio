import os
import re
import sys
import json
import time
import socket
import ctypes
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

import requests
from websockets.sync.client import connect as ws_connect
from .logger_service import log_info, log_warn, log_error

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Cấu hình 3 Tài khoản ChatGPT Web (Chuẩn Master Blueprint V6.0)
# QUAN TRỌNG: Luôn thoát khỏi thư mục con 'app/' để trỏ đúng về thư mục gốc chứa BROWSER_PROFILE,
# tránh tuyệt đối việc chạy từ app/ tạo ra profile trống làm văng tài khoản ChatGPT!
ROOT_DIR = Path(__file__).resolve().parent.parent
if ROOT_DIR.name.lower() == "app":
    ROOT_DIR = ROOT_DIR.parent
elif not (ROOT_DIR / "bin").exists() and (ROOT_DIR.parent / "bin").exists():
    ROOT_DIR = ROOT_DIR.parent

_APPDATA_STUDIO_DIR = Path(os.path.expandvars(r"%LOCALAPPDATA%\Drama_Nhat_Studio"))
_PROFILE_REGISTRY_FILE = _APPDATA_STUDIO_DIR / "chrome_profiles_registry.json"


def _has_existing_chrome_data(p: Path) -> bool:
    """Kiểm tra xem thư mục Profile đã có phiên đăng nhập / dữ liệu Chrome hay chưa."""
    if not p.exists():
        return False
    return (
        (p / "Default").exists()
        or (p / ".studio_account_info.json").exists()
        or (p / "Local State").exists()
    )


def _resolve_persistent_profile_dir(acc_id: str, folder_name: str) -> str:
    """
    Giữ cố định 100% phiên đăng nhập ChatGPT qua mọi bản cập nhật:
    1. Nếu thư mục gốc hiện tại (ROOT_DIR / folder_name) đã có dữ liệu đăng nhập -> Dùng ngay và lưu đường dẫn vào Registry máy.
    2. Nếu người dùng giải nén bản Update sang một thư mục mới (chưa có BROWSER_PROFILE), tự động đọc Registry
       trong %LOCALAPPDATA% để trỏ lại đúng thư mục BROWSER_PROFILE cũ đã đăng nhập trên máy tính này!
    """
    local_candidate = ROOT_DIR / folder_name
    registry_data: Dict[str, str] = {}
    try:
        _APPDATA_STUDIO_DIR.mkdir(parents=True, exist_ok=True)
        if _PROFILE_REGISTRY_FILE.exists():
            registry_data = json.loads(_PROFILE_REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        registry_data = {}

    if _has_existing_chrome_data(local_candidate):
        resolved = str(local_candidate.resolve())
        if registry_data.get(acc_id) != resolved:
            registry_data[acc_id] = resolved
            try:
                _PROFILE_REGISTRY_FILE.write_text(json.dumps(registry_data, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        return resolved

    # Kiểm tra xem trên máy đã từng đăng nhập ở thư mục trước khi update chưa
    prev_path_str = registry_data.get(acc_id, "")
    if prev_path_str:
        prev_p = Path(prev_path_str)
        if _has_existing_chrome_data(prev_p) and prev_p.name.lower() != "app":
            return str(prev_p.resolve())

    # Mặc định lưu ở ROOT_DIR / folder_name và ghi nhận vào Registry
    resolved_default = str(local_candidate.resolve())
    registry_data[acc_id] = resolved_default
    try:
        _PROFILE_REGISTRY_FILE.write_text(json.dumps(registry_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return resolved_default


ACCOUNTS_CONFIG: Dict[str, Dict[str, Any]] = {
    "acc_1": {
        "acc_id": "acc_1",
        "label": "Acc #1",
        "port": 9222,
        "profile_dir": _resolve_persistent_profile_dir("acc_1", "BROWSER_PROFILE"),
    },
    "acc_2": {
        "acc_id": "acc_2",
        "label": "Acc #2",
        "port": 9223,
        "profile_dir": _resolve_persistent_profile_dir("acc_2", "BROWSER_PROFILE_2"),
    },
    "acc_3": {
        "acc_id": "acc_3",
        "label": "Acc #3",
        "port": 9224,
        "profile_dir": _resolve_persistent_profile_dir("acc_3", "BROWSER_PROFILE_3"),
    },
}

_STATE_LOCK = threading.Lock()
_CHROME_HIDDEN_STATE: Dict[str, bool] = {
    "acc_1": False,
    "acc_2": False,
    "acc_3": False,
}
_ACTIVE_JOBS_BY_ACC: Dict[str, Dict[str, str]] = {
    "acc_1": {},  # tab_id -> project_id
    "acc_2": {},
    "acc_3": {},
}
_PENDING_PROJECTS_BY_ACC: Dict[str, set] = {
    "acc_1": set(),
    "acc_2": set(),
    "acc_3": set(),
}
CHATGPT_GUARD_URL = "https://chatgpt.com/?studio_login_guard=1#studio_login_guard"
_PROTECTED_WS_URLS: set = set()


def _fresh_guard_url() -> str:
    """Tạo URL trang chủ ChatGPT kèm timestamp query duy nhất để Page.navigate luôn tải trang mới thật sự (không bị Chrome coi là cuộn hash cùng trang)."""
    return f"https://chatgpt.com/?studio_login_guard={int(time.time() * 1000)}#studio_login_guard"


MAX_THREADS_PER_ACCOUNT = 3
COMPOSER_SELECTOR = (
    '#prompt-textarea, #mobile-composer-prompt, textarea[id*="prompt"], '
    'div.ProseMirror[contenteditable="true"], [data-composer-markdown], '
    'div[role="textbox"][contenteditable="true"], main textarea'
)
_STATUS_CACHE: Dict[str, Any] = {
    "ts": 0.0,
    "data": None,
}
_LAST_VERIFIED_LOGIN_BY_PORT: Dict[int, Dict[str, Any]] = {}
_LAST_BLANK_NAV_TS_BY_PORT: Dict[int, float] = {}
_KNOWN_EMAILS: Dict[str, str] = {}
_WS_LOCKS: Dict[str, threading.Lock] = {}
_ACC_TAB_LOCKS: Dict[str, threading.RLock] = {
    "acc_1": threading.RLock(),
    "acc_2": threading.RLock(),
    "acc_3": threading.RLock(),
}
_PORT_INJECT_LOCKS: Dict[int, threading.Lock] = {
    9222: threading.Lock(),
    9223: threading.Lock(),
    9224: threading.Lock(),
}
_ROUND_ROBIN_IDX = 0


def find_chrome_executable() -> str:
    """Tìm đường dẫn Google Chrome (hoặc Microsoft Edge Chromium dự phòng) trên Windows."""
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return "chrome.exe"


def _cdp_get_tabs(port: int, timeout: float = 2.5) -> Optional[List[Dict[str, Any]]]:
    """Lấy danh sách các tab đang mở từ cổng CDP của Chrome (kiểm tra nhanh socket 350ms trước, tự động thử lại nếu Chrome đang tải nặng)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.35)
            if s.connect_ex(("127.0.0.1", int(port))) != 0:
                return None
        for _attempt in range(2):
            try:
                resp = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=max(1.5, timeout))
                if resp.status_code == 200:
                    tabs = resp.json()
                    return [t for t in tabs if t.get("type") == "page"]
            except Exception:
                time.sleep(0.2)
    except Exception:
        pass
    return None


def _install_chatgpt_tab_protection_js(ws_url: str) -> None:
    """
    Gắn chốt bảo vệ '#studio_login_guard' trên Tab ChatGPT (thông qua Page.addScriptToEvaluateOnNewDocument,
    bọc History.pushState/replaceState và setInterval 250ms) để ngăn mọi tiến trình dọn tab bên ngoài
    đóng nhầm hoặc chuyển hướng các Tab đang viết kịch bản.
    """
    if not ws_url:
        return
    guard_script = r"""
    (() => {
        try {
            window.onbeforeunload = null;
            const ensureGuardHash = () => {
                try {
                    const host = (window.location.hostname || '').toLowerCase();
                    if ((host.includes('chatgpt.com') || host.includes('openai.com')) && !window.location.hash.includes('studio_login_guard')) {
                        const cleanUrl = window.location.pathname + window.location.search + '#studio_login_guard';
                        window.history.replaceState(window.history.state, '', cleanUrl);
                    }
                } catch (e) {}
            };
            if (!window.__studioHistoryPatched) {
                window.__studioHistoryPatched = true;
                const origPush = window.history.pushState;
                const origReplace = window.history.replaceState;
                const patchUrl = (u) => {
                    if (typeof u === 'string' && u.length > 0 && !u.includes('studio_login_guard')) {
                        return u.split('#')[0] + '#studio_login_guard';
                    }
                    return u;
                };
                if (typeof origPush === 'function') {
                    window.history.pushState = function(state, title, url) {
                        return origPush.call(this, state, title, patchUrl(url));
                    };
                }
                if (typeof origReplace === 'function') {
                    window.history.replaceState = function(state, title, url) {
                        return origReplace.call(this, state, title, patchUrl(url));
                    };
                }
            }
            ensureGuardHash();
            if (!window.__chatgptTabProtectionTimer) {
                window.__chatgptTabProtectionTimer = setInterval(ensureGuardHash, 250);
            }
        } catch (e) {}
        return true;
    })()
    """
    with _STATE_LOCK:
        ws_lock = _WS_LOCKS.setdefault(ws_url, threading.Lock())
    with ws_lock:
        try:
            with ws_connect(ws_url, open_timeout=2.5, close_timeout=1.2) as ws:
                ws.send(
                    json.dumps(
                        {
                            "id": 9103,
                            "method": "Runtime.evaluate",
                            "params": {"expression": guard_script, "returnByValue": True},
                        }
                    )
                )
                ws.recv(timeout=1.2)
        except Exception:
            pass


def _cdp_navigate(ws_url: str, url: str = CHATGPT_GUARD_URL, timeout: float = 3.0) -> bool:
    """Điều hướng tab tới URL bằng giao thức CDP Page.navigate (kèm cài sẵn chốt bảo vệ #studio_login_guard)."""
    if not ws_url:
        return False
    if url == CHATGPT_GUARD_URL or ("chatgpt.com" in url and "/c/" not in url):
        url = _fresh_guard_url()
    _install_chatgpt_tab_protection_js(ws_url)
    with _STATE_LOCK:
        ws_lock = _WS_LOCKS.setdefault(ws_url, threading.Lock())
    with ws_lock:
        try:
            with ws_connect(ws_url, open_timeout=3.0, close_timeout=1.5) as ws:
                msg_id = int(time.time() * 1000) % 1000000 + 7
                ws.send(json.dumps({"id": msg_id, "method": "Page.navigate", "params": {"url": url}}))
                ws.recv(timeout=timeout)
                return True
        except Exception:
            return False


def _cdp_eval_js(ws_url: str, expression: str, await_promise: bool = True, timeout: float = 15.0) -> Any:
    """Thực thi biểu thức JavaScript trực tiếp trong Tab Chrome thông qua CDP WebSocket (có khóa đồng bộ & chống ngủ nền mỗi tab)."""
    if not ws_url:
        return None
    with _STATE_LOCK:
        ws_lock = _WS_LOCKS.setdefault(ws_url, threading.Lock())
    with ws_lock:
        try:
            if await_promise:
                # Kích hoạt nhanh tab để Chrome không bao giờ làm chậm setTimeout bên trong Promise
                parts = str(ws_url).rstrip("/").split("/")
                tab_id = parts[-1] if parts else ""
                port_str = "9222"
                for seg in parts:
                    if ":" in seg:
                        port_str = seg.split(":")[-1]
                if tab_id and len(tab_id) >= 16:
                    try:
                        requests.get(f"http://127.0.0.1:{port_str}/json/activate/{tab_id}", timeout=1.2)
                        time.sleep(0.05)
                    except Exception:
                        pass
            with ws_connect(ws_url, open_timeout=4.0, close_timeout=2.0, max_size=32 * 1024 * 1024) as ws:
                msg_id = int(time.time() * 1000) % 1000000 + 1
                payload = {
                    "id": msg_id,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": expression,
                        "returnByValue": True,
                        "awaitPromise": await_promise,
                    },
                }
                ws.send(json.dumps(payload))
                deadline = time.time() + timeout
                while time.time() < deadline:
                    raw = ws.recv(timeout=max(0.5, deadline - time.time()))
                    data = json.loads(raw)
                    if data.get("id") == msg_id:
                        res = data.get("result", {}).get("result", {})
                        return res.get("value")
        except Exception:
            pass
    return None


def _get_pids_using_profile(profile_dir: str, port: int) -> List[int]:
    """Tìm các Process ID của cửa sổ Chrome thuộc về Profile/Port tương ứng."""
    pids: List[int] = []
    try:
        norm_prof = os.path.normpath(profile_dir).lower()
        ps_cmd = (
            "Get-CimInstance Win32_Process -Filter \"Name = 'chrome.exe' OR Name = 'msedge.exe'\" | "
            "Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress"
        )
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="ignore",
        )
        if res.stdout.strip():
            items = json.loads(res.stdout.strip())
            if isinstance(items, dict):
                items = [items]
            for it in items:
                cmd = str(it.get("CommandLine") or "").lower()
                pid = it.get("ProcessId")
                if pid and (f"--remote-debugging-port={port}" in cmd or norm_prof in cmd):
                    pids.append(int(pid))
    except Exception:
        pass
    return pids


def _move_chrome_windows_for_pids(pids: List[int], visible: bool, bring_to_front: bool = False) -> int:
    """Ẩn cửa sổ Chrome xuống tọa độ (-3200, -3200) hoặc đưa trở lại màn hình bằng Win32 API."""
    if os.name != "nt" or not pids:
        return 0
    pid_set = set(pids)
    moved_count = 0
    try:
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_long)

        SW_RESTORE = 9
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040

        def enum_cb(hwnd, _lparam):
            nonlocal moved_count
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pid_set:
                if visible:
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.SetWindowPos(hwnd, 0, 90, 50, 1280, 860, SWP_SHOWWINDOW)
                    if bring_to_front:
                        user32.SetForegroundWindow(hwnd)
                else:
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.SetWindowPos(hwnd, 0, -3200, -3200, 1280, 860, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
                moved_count += 1
            return True

        cb_func = WNDENUMPROC(enum_cb)
        user32.EnumWindows(cb_func, 0)
    except Exception:
        pass
    return moved_count


def _set_single_port_cdp_window_bounds(port: int, visible: bool = False, offset_idx: int = 0) -> int:
    """Dùng trực tiếp CDP Browser.getWindowForTarget + Browser.setWindowBounds để ẩn/hiện cửa sổ ở (-3200, -3200) với windowState='normal'."""
    changed = 0
    tabs = _cdp_get_tabs(port, timeout=1.5) or []
    for t in tabs:
        ws_url = t.get("webSocketDebuggerUrl")
        if not ws_url:
            continue
        try:
            with ws_connect(ws_url, open_timeout=2.5, close_timeout=1.5) as ws:
                ws.send(json.dumps({"id": 1, "method": "Browser.getWindowForTarget", "params": {}}))
                r = json.loads(ws.recv(timeout=2.0))
                wid = (r.get("result") or {}).get("windowId")
                if wid:
                    ws.send(
                        json.dumps(
                            {
                                "id": 2,
                                "method": "Browser.setWindowBounds",
                                "params": {"windowId": wid, "bounds": {"windowState": "normal"}},
                            }
                        )
                    )
                    ws.recv(timeout=2.0)
                    if visible:
                        left_pos = 50 + (offset_idx * 45)
                        top_pos = 35 + (offset_idx * 35)
                        ws.send(
                            json.dumps(
                                {
                                    "id": 3,
                                    "method": "Browser.setWindowBounds",
                                    "params": {
                                        "windowId": wid,
                                        "bounds": {
                                            "left": left_pos,
                                            "top": top_pos,
                                            "width": 1240,
                                            "height": 860,
                                        },
                                    },
                                }
                            )
                        )
                        ws.recv(timeout=2.0)
                        ws.send(json.dumps({"id": 4, "method": "Page.bringToFront", "params": {}}))
                        ws.recv(timeout=2.0)
                    else:
                        ws.send(
                            json.dumps(
                                {
                                    "id": 3,
                                    "method": "Browser.setWindowBounds",
                                    "params": {
                                        "windowId": wid,
                                        "bounds": {
                                            "left": -3200,
                                            "top": -3200,
                                            "width": 1100,
                                            "height": 850,
                                        },
                                    },
                                }
                            )
                        )
                        ws.recv(timeout=2.0)
                    changed += 1
                    break
        except Exception:
            pass
    return changed


def set_chrome_window_visibility(visible: bool = True, acc_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Ẩn toàn bộ cửa sổ Chrome xuống chạy ngầm (-3200, -3200) hoặc hiện lại lên màn hình.
    Chuẩn API #3 trong Master Blueprint V6.0 (kết hợp CDP Browser.setWindowBounds + Win32 API).
    """
    target_accs = [acc_id] if acc_id and acc_id in ACCOUNTS_CONFIG else list(ACCOUNTS_CONFIG.keys())
    total_moved = 0
    for idx, aid in enumerate(target_accs):
        cfg = ACCOUNTS_CONFIG[aid]
        with _STATE_LOCK:
            _CHROME_HIDDEN_STATE[aid] = not bool(visible)
        total_moved += _set_single_port_cdp_window_bounds(cfg["port"], visible=bool(visible), offset_idx=idx)
        pids = _get_pids_using_profile(cfg["profile_dir"], cfg["port"])
        total_moved += _move_chrome_windows_for_pids(pids, visible=bool(visible), bring_to_front=bool(visible))

    log_info(
        f"Đã {'hiện lại' if visible else 'ẩn ngầm (-3200, -3200)'} cửa sổ Chrome ({total_moved} cửa sổ bị tác động).",
        category="CHROME",
    )
    return {
        "success": True,
        "ok": True,
        "visible": bool(visible),
        "acc_id": acc_id,
        "windows_affected": total_moved,
        "hidden_state": dict(_CHROME_HIDDEN_STATE),
    }


def ensure_chrome_debug_browser_open(
    open_chatgpt_home: bool = True,
    force_bring_to_front: bool = True,
    run_hidden: bool = False,
    acc_id: str = "acc_1",
    fast_if_already_open: bool = False,
) -> Dict[str, Any]:
    """
    Đảm bảo trình duyệt Chrome của tài khoản (acc_1 | acc_2 | acc_3) đã mở với cổng CDP.
    Nếu chưa mở sẽ khởi chạy Chrome với Profile riêng biệt.
    Chuẩn API #2 trong Master Blueprint V6.0.
    """
    if acc_id not in ACCOUNTS_CONFIG:
        acc_id = "acc_1"
    cfg = ACCOUNTS_CONFIG[acc_id]
    port = cfg["port"]
    profile_dir = cfg["profile_dir"]
    os.makedirs(profile_dir, exist_ok=True)

    acc_lock = _ACC_TAB_LOCKS.setdefault(acc_id, threading.RLock())
    with acc_lock:
        tabs = _cdp_get_tabs(port)
        already_running = tabs is not None

        if already_running and fast_if_already_open:
            return {
                "success": True,
                "acc_id": acc_id,
                "label": cfg["label"],
                "port": port,
                "profile_dir": profile_dir,
                "browser_open": True,
                "open_tabs_count": len(tabs) if tabs else 0,
            }

        if tabs is None:
            chrome_exe = find_chrome_executable()
            start_url = CHATGPT_GUARD_URL if open_chatgpt_home else "about:blank"
            pos_arg = f"--window-position={'-3200,-3200' if run_hidden else '90,50'}"
            args = [
                chrome_exe,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile_dir}",
                "--remote-allow-origins=*",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-popup-blocking",
                pos_arg,
                "--window-size=1280,860",
                start_url,
            ]
            # Kiểm tra xem tiến trình Python hiện tại đã nằm trên Màn hình chính (WinSta0) của người dùng chưa.
            # Nếu đã ở trên WinSta0 -> gọi trực tiếp subprocess.Popen(args) để mở Chrome ngay trên màn hình chính và không bao giờ bị Task Scheduler đóng!
            is_interactive_winsta0 = True
            if os.name == "nt":
                try:
                    import ctypes
                    u32 = ctypes.windll.user32
                    h_winsta = u32.GetProcessWindowStation()
                    buf = ctypes.create_unicode_buffer(128)
                    needed = ctypes.c_ulong(0)
                    # UOI_NAME = 2
                    if u32.GetUserObjectInformationW(h_winsta, 2, buf, ctypes.sizeof(buf), ctypes.byref(needed)):
                        winsta_name = (buf.value or "").strip()
                        if winsta_name and "winsta0" not in winsta_name.lower():
                            is_interactive_winsta0 = False
                except Exception:
                    is_interactive_winsta0 = True

            launched_via_it = False
            if os.name == "nt" and not is_interactive_winsta0:
                try:
                    bat_dir = os.path.join(os.environ.get("LOCALAPPDATA") or str(ROOT_DIR), "Drama_Nhat_Studio")
                    os.makedirs(bat_dir, exist_ok=True)
                    bat_path = os.path.join(bat_dir, f"launch_chrome_{acc_id}.bat")
                    # Dùng explorer.exe hoặc giữ tiến trình sống để Task Scheduler không đóng Chrome khi .bat kết thúc
                    with open(bat_path, "w", encoding="utf-8") as bf:
                        bf.write(
                            f'@echo off\r\n"{chrome_exe}" '
                            f'--remote-debugging-port={port} --user-data-dir="{profile_dir}" '
                            f'--remote-allow-origins=* --no-first-run --no-default-browser-check '
                            f'--disable-blink-features=AutomationControlled '
                            f'--disable-background-timer-throttling --disable-backgrounding-occluded-windows '
                            f'--disable-renderer-backgrounding --disable-popup-blocking '
                            f'--new-window {pos_arg} --window-size=1280,860 "{start_url}"\r\n'
                        )
                    task_name = f"DramaNhatStudio_Chrome_{acc_id}"
                    subprocess.run(
                        ["schtasks", "/Create", "/TN", task_name, "/TR", bat_path, "/SC", "ONCE", "/ST", "00:00", "/IT", "/F"],
                        capture_output=True,
                        timeout=4,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    subprocess.run(
                        ["schtasks", "/Run", "/TN", task_name],
                        capture_output=True,
                        timeout=4,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    for _ in range(18):
                        time.sleep(0.35)
                        tabs = _cdp_get_tabs(port)
                        if tabs is not None:
                            launched_via_it = True
                            break
                except Exception:
                    launched_via_it = False

            if not launched_via_it and tabs is None:
                subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                )
                # Đợi cổng CDP sẵn sàng
                for _ in range(30):
                    time.sleep(0.35)
                    tabs = _cdp_get_tabs(port)
                    if tabs is not None:
                        break

    with _STATE_LOCK:
        _CHROME_HIDDEN_STATE[acc_id] = bool(run_hidden)

    if tabs is not None:
        has_chatgpt = any("chatgpt.com" in (t.get("url") or "") for t in tabs)
        if open_chatgpt_home and not has_chatgpt:
            # Nếu chỉ đang có 1 tab about:blank thì chuyển luôn tab đó sang CHATGPT_GUARD_URL
            blank_tab = next((t for t in tabs if (t.get("url") or "").startswith("about:blank")), None)
            if blank_tab and blank_tab.get("webSocketDebuggerUrl"):
                _cdp_navigate(blank_tab["webSocketDebuggerUrl"], CHATGPT_GUARD_URL, timeout=2.5)
                time.sleep(0.35)
                tabs = _cdp_get_tabs(port) or tabs
            else:
                try:
                    resp_new = requests.put(f"http://127.0.0.1:{port}/json/new?https://chatgpt.com/?studio_login_guard=1", timeout=3)
                    if resp_new.status_code == 200:
                        t_info = resp_new.json()
                        if t_info.get("webSocketDebuggerUrl"):
                            _install_chatgpt_tab_protection_js(t_info["webSocketDebuggerUrl"])
                    tabs = _cdp_get_tabs(port) or tabs
                except Exception:
                    pass
        for t in (tabs or []):
            t_url = t.get("url") or ""
            t_ws = t.get("webSocketDebuggerUrl")
            if t_ws and ("chatgpt.com" in t_url or "openai.com" in t_url):
                _install_chatgpt_tab_protection_js(t_ws)

    if not already_running or force_bring_to_front or run_hidden:
        _set_single_port_cdp_window_bounds(port, visible=not run_hidden)
        pids = _get_pids_using_profile(profile_dir, port)
        if run_hidden:
            _move_chrome_windows_for_pids(pids, visible=False, bring_to_front=False)
        elif force_bring_to_front:
            _move_chrome_windows_for_pids(pids, visible=True, bring_to_front=True)

    _STATUS_CACHE["ts"] = 0.0
    log_info(
        f"Đã mở trình duyệt {cfg['label']} (Cổng {port} | Profile: {profile_dir} | Số tab: {len(tabs) if tabs else 0})",
        category="CHROME",
    )
    return {
        "success": tabs is not None,
        "acc_id": acc_id,
        "label": cfg["label"],
        "port": port,
        "profile_dir": profile_dir,
        "browser_open": tabs is not None,
        "open_tabs_count": len(tabs) if tabs else 0,
    }


def _inspect_account_login_state(acc_id: str) -> Dict[str, Any]:
    """
    Kiểm tra trạng thái đăng nhập, email và danh sách tab của 1 tài khoản ChatGPT Web.
    Áp dụng cơ chế Non-Blocking Cache (_LAST_VERIFIED_LOGIN_BY_PORT + .studio_account_info.json)
    và fetch('/api/auth/session') chuẩn Master Blueprint V6.0.
    """
    cfg = ACCOUNTS_CONFIG[acc_id]
    port = cfg["port"]
    profile_dir = cfg["profile_dir"]
    tabs = _cdp_get_tabs(port, timeout=1.2)
    with _STATE_LOCK:
        active_map = dict(_ACTIVE_JOBS_BY_ACC.get(acc_id, {}))
        pending_set = set(_PENDING_PROJECTS_BY_ACC.get(acc_id, set()))
        is_hidden = bool(_CHROME_HIDDEN_STATE.get(acc_id, False))
    all_active_projects = list(dict.fromkeys(list(active_map.values()) + list(pending_set)))

    acc_info_file = os.path.join(profile_dir, ".studio_account_info.json")
    saved_disk_info: Dict[str, Any] = {}
    if os.path.exists(acc_info_file):
        try:
            with open(acc_info_file, "r", encoding="utf-8") as f:
                saved_disk_info = json.load(f)
        except Exception:
            pass

    if tabs is None:
        _LAST_VERIFIED_LOGIN_BY_PORT.pop(port, None)
        return {
            "acc_id": acc_id,
            "label": cfg["label"],
            "port": port,
            "browser_open": False,
            "browser_running": False,
            "logged_in": False,
            "email": "Chưa mở Chrome",
            "user_email": "",
            "open_tabs_count": 0,
            "chatgpt_tabs": 0,
            "active_threads": len(all_active_projects),
            "max_threads": MAX_THREADS_PER_ACCOUNT,
            "active_projects": all_active_projects,
            "hidden": is_hidden,
        }

    chatgpt_tabs = [t for t in tabs if "chatgpt.com" in (t.get("url") or "") or "openai.com" in (t.get("url") or "")]
    gemini_tabs = [t for t in tabs if "gemini.google.com" in (t.get("url") or "")]
    if not chatgpt_tabs and not gemini_tabs and tabs:
        # Nếu cửa sổ Chrome đang mở ở about:blank (sau khi dọn tab), tự động chuyển tab đầu tiên về CHATGPT_GUARD_URL
        # (Có khóa thời gian 25s để không bao giờ gọi lặp lại khi trang đang tải dở)
        first_ws = tabs[0].get("webSocketDebuggerUrl")
        now_nav = time.time()
        if (
            first_ws
            and (tabs[0].get("url") or "").startswith("about:blank")
            and (now_nav - _LAST_BLANK_NAV_TS_BY_PORT.get(port, 0.0)) > 25.0
        ):
            _LAST_BLANK_NAV_TS_BY_PORT[port] = now_nav
            _cdp_navigate(first_ws, CHATGPT_GUARD_URL, timeout=2.5)
            time.sleep(0.6)
            tabs = _cdp_get_tabs(port, timeout=1.2) or tabs
            chatgpt_tabs = [t for t in tabs if "chatgpt.com" in (t.get("url") or "") or "openai.com" in (t.get("url") or "")]

    for ct in chatgpt_tabs:
        ct_ws = ct.get("webSocketDebuggerUrl")
        ct_url = ct.get("url") or ""
        if ct_ws and "studio_login_guard" not in ct_url:
            _install_chatgpt_tab_protection_js(ct_ws)

    has_active_conv_url = any("/c/" in (t.get("url") or "") for t in chatgpt_tabs)
    logged_in = False
    email_or_user = "Chưa đăng nhập"

    if chatgpt_tabs:
        cached_login = _LAST_VERIFIED_LOGIN_BY_PORT.get(port)
        # Nếu đã xác thực trên cổng này trong vòng 25s (hoặc đang chạy dở dự án) -> trả về ngay từ bộ nhớ đệm (0ms)
        if cached_login and cached_login.get("logged_in") and (
            all_active_projects or has_active_conv_url or (time.time() - float(cached_login.get("ts") or 0)) < 25.0
        ):
            email_val = cached_login.get("user_email") or cached_login.get("email") or "Đã đăng nhập ChatGPT"
            return {
                "acc_id": acc_id,
                "label": cfg["label"],
                "port": port,
                "browser_open": True,
                "browser_running": True,
                "logged_in": True,
                "email": email_val,
                "user_email": email_val,
                "open_tabs_count": len(chatgpt_tabs) + len(gemini_tabs),
                "chatgpt_tabs": len(chatgpt_tabs),
                "total_tabs_count": len(tabs),
                "active_threads": len(all_active_projects),
                "max_threads": MAX_THREADS_PER_ACCOUNT,
                "active_projects": all_active_projects,
                "hidden": is_hidden,
            }

        target_tab = chatgpt_tabs[0]
        ws_url = target_tab.get("webSocketDebuggerUrl")
        _install_chatgpt_tab_protection_js(ws_url)
        js_check = r"""
        (async () => {
            try {
                const r = await fetch('/api/auth/session', { credentials: 'include' });
                if (r.ok) {
                    const d = await r.json();
                    const tok = (d && d.accessToken) ? d.accessToken : '';
                    if (tok) window.__studioAccessToken = tok;
                    const u = (d && d.user) ? d.user : {};
                    if (tok || u.email) {
                        return {
                            logged_in: true,
                            user: u.email || u.name || 'Đã đăng nhập ChatGPT',
                            plan: (d.account && d.account.planType) || ''
                        };
                    }
                    return { logged_in: false, user: 'Chưa đăng nhập ChatGPT' };
                }
            } catch (e) {}
            try {
                const url = location.href || "";
                if (url.includes("/auth/login") || url.includes("auth0.openai.com")) {
                    return { logged_in: false, user: "Đang ở trang Login" };
                }
                const loginBtn = document.querySelector('[data-testid="login-button"], [data-testid="mobile-login-button"]')
                    || Array.from(document.querySelectorAll('button, a')).find(el => /^(log in|sign up|sign up for free|đăng nhập)$/i.test((el.innerText || '').trim()));
                if (loginBtn) {
                    return { logged_in: false, user: "Chưa đăng nhập" };
                }
                const profileBtn = document.querySelector(
                    '[data-testid="profile-button"], button[aria-label*="profile" i], button[aria-label*="Open profile" i], img[alt*="User" i]'
                );
                let email = "";
                try {
                    const scripts = Array.from(document.querySelectorAll('script'));
                    for (const s of scripts) {
                        const txt = s.textContent || "";
                        const m = txt.match(/"email"\s*:\s*"([^"@]+@[^"]+)"/);
                        if (m && m[1]) { email = m[1]; break; }
                    }
                } catch (e) {}
                if (profileBtn || email) {
                    return { logged_in: true, user: email || "Đã đăng nhập ChatGPT" };
                }
                return { logged_in: false, user: "Đang tải trang..." };
            } catch (err) {
                return { logged_in: false, user: "Không rõ" };
            }
        })()
        """
        info = _cdp_eval_js(ws_url, js_check, await_promise=True, timeout=3.5)
        if isinstance(info, dict):
            logged_in = bool(info.get("logged_in") or has_active_conv_url)
            email_or_user = str(
                info.get("user")
                or (saved_disk_info.get("user_email") if logged_in else "")
                or ("Đã đăng nhập" if logged_in else "Chưa đăng nhập")
            )
            if logged_in:
                new_cache = {
                    "logged_in": True,
                    "user_email": email_or_user,
                    "plan_type": info.get("plan") or saved_disk_info.get("plan_type") or "",
                    "ts": time.time(),
                }
                _LAST_VERIFIED_LOGIN_BY_PORT[port] = new_cache
                try:
                    with open(acc_info_file, "w", encoding="utf-8") as f:
                        json.dump(new_cache, f, ensure_ascii=False)
                except Exception:
                    pass
            else:
                _LAST_VERIFIED_LOGIN_BY_PORT.pop(port, None)
        elif has_active_conv_url or (cached_login and cached_login.get("logged_in")):
            logged_in = True
            email_or_user = (cached_login or {}).get("user_email") or "Đã đăng nhập ChatGPT"
    elif gemini_tabs:
        gem_ws = gemini_tabs[0].get("webSocketDebuggerUrl")
        gem_info = _cdp_eval_js(
            gem_ws,
            r"""
            (() => {
                const signedOutEl = document.querySelector('[data-test-id="signed-out-disclaimer"], a[href*="ServiceLogin"]');
                const avatarEl = document.querySelector('a[aria-label*="Google Account" i], a[aria-label*="Tài khoản Google" i], a[aria-label*="@"]');
                const hint = avatarEl ? (avatarEl.getAttribute('aria-label') || '') : '';
                const m = hint.match(/([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/);
                const modeBtn = document.querySelector('[data-test-id="bard-mode-menu-button"], bard-mode-switcher button');
                const modeTxt = modeBtn ? (modeBtn.innerText || '').trim() : '';
                return {
                    logged_in: !signedOutEl && Boolean(avatarEl || modeBtn),
                    email: m ? m[1] : (modeTxt ? ('Gemini Pro (' + modeTxt + ')') : 'Đã đăng nhập Gemini')
                };
            })()
            """,
            await_promise=False,
            timeout=2.5,
        )
        if isinstance(gem_info, dict) and gem_info.get("logged_in"):
            logged_in = True
            email_or_user = str(gem_info.get("email") or "Đã đăng nhập Gemini Pro")
        else:
            email_or_user = "Đang mở Gemini Web"
    else:
        email_or_user = "Chưa mở tab ChatGPT/Gemini"

    return {
        "acc_id": acc_id,
        "label": cfg["label"],
        "port": port,
        "browser_open": True,
        "browser_running": True,
        "logged_in": logged_in,
        "email": email_or_user,
        "user_email": email_or_user if logged_in else "",
        "open_tabs_count": len(chatgpt_tabs) + len(gemini_tabs),
        "chatgpt_tabs": len(chatgpt_tabs),
        "total_tabs_count": len(tabs),
        "active_threads": len(all_active_projects),
        "max_threads": MAX_THREADS_PER_ACCOUNT,
        "active_projects": all_active_projects,
        "hidden": is_hidden,
    }


def _profile_has_saved_chatgpt_login(profile_dir: str) -> bool:
    """Kiểm tra nhanh trên ổ cứng xem Profile này đã từng đăng nhập tài khoản ChatGPT thật hay chưa."""
    try:
        info_path = os.path.join(profile_dir, ".studio_account_info.json")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            email_val = str(data.get("user_email") or data.get("email") or "")
            if data.get("logged_in") and "@" in email_val:
                return True
        cookie_path = os.path.join(profile_dir, "Default", "Network", "Cookies")
        if os.path.exists(cookie_path) and os.path.getsize(cookie_path) > 45000:
            return True
    except Exception:
        pass
    return False


def ensure_all_saved_chatgpt_accounts_open(run_hidden: bool = False) -> List[str]:
    """
    Tự động mở trình duyệt Chrome cho toàn bộ các tài khoản (Acc #1, Acc #2, Acc #3)
    đã có phiên đăng nhập ChatGPT lưu trên ổ cứng, sau đó xác thực và trả về danh sách acc_id đã đăng nhập.
    """
    for aid in ["acc_1", "acc_2", "acc_3"]:
        cfg = ACCOUNTS_CONFIG[aid]
        port = cfg["port"]
        prof = cfg["profile_dir"]
        tabs = _cdp_get_tabs(port, timeout=0.8)
        if tabs is None and _profile_has_saved_chatgpt_login(prof):
            ensure_chrome_debug_browser_open(
                open_chatgpt_home=True,
                force_bring_to_front=False,
                run_hidden=run_hidden,
                acc_id=aid,
                fast_if_already_open=True,
            )
            time.sleep(0.8)
        elif tabs is not None:
            has_cg = any("chatgpt.com" in (t.get("url") or "") for t in tabs)
            if not has_cg and _profile_has_saved_chatgpt_login(prof):
                ensure_chrome_debug_browser_open(
                    open_chatgpt_home=True,
                    force_bring_to_front=False,
                    run_hidden=run_hidden,
                    acc_id=aid,
                    fast_if_already_open=False,
                )

    st_all = check_all_web_accounts_status(force_refresh=True).get("accounts", {})
    logged = [aid for aid in ["acc_1", "acc_2", "acc_3"] if st_all.get(aid, {}).get("logged_in")]
    return logged


def check_all_web_accounts_status(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Kiểm tra trạng thái cả 3 tài khoản (Acc #1, Acc #2, Acc #3).
    Chuẩn API #1 trong Master Blueprint V6.0.
    """
    now = time.time()
    if not force_refresh and _STATUS_CACHE["data"] and (now - _STATUS_CACHE["ts"] < 2.5):
        return _STATUS_CACHE["data"]

    accounts = {}
    any_hidden = False
    any_open = False
    for aid in ["acc_1", "acc_2", "acc_3"]:
        st = _inspect_account_login_state(aid)
        accounts[aid] = st
        if st["browser_open"]:
            any_open = True
        if st["hidden"]:
            any_hidden = True

    result = {
        "success": True,
        "accounts": accounts,
        "any_browser_open": any_open,
        "chrome_hidden": any_hidden,
        "timestamp": int(now),
    }
    _STATUS_CACHE["ts"] = now
    _STATUS_CACHE["data"] = result
    return result


def _close_inactive_tabs_on_account(acc_id: str, keep_tab_id: Optional[str] = None) -> int:
    """
    Đóng ngay lập tức toàn bộ các Tab không hoạt động (inactive / đã xong bước trước / dư thừa)
    trên trình duyệt Chrome của tài khoản `acc_id`.
    Chỉ giữ lại các Tab đang thực sự chạy dự án (`_ACTIVE_JOBS_BY_ACC`) và `keep_tab_id` vừa mở.
    Nếu không có dự án nào đang chạy, giữ lại duy nhất 1 tab trang chủ để không làm tắt cửa sổ Chrome.
    """
    if acc_id not in ACCOUNTS_CONFIG:
        return 0
    port = ACCOUNTS_CONFIG[acc_id]["port"]
    tabs = _cdp_get_tabs(port, timeout=1.5)
    if not tabs:
        return 0

    existing_ids = {t.get("id") for t in tabs if t.get("id")}
    with _STATE_LOCK:
        acc_jobs = _ACTIVE_JOBS_BY_ACC.setdefault(acc_id, {})
        # Dọn các tab_id mồ côi không còn tồn tại trong trình duyệt
        for tid in list(acc_jobs.keys()):
            if tid not in existing_ids:
                acc_jobs.pop(tid, None)
        protected_ids = set(acc_jobs.keys())
        if keep_tab_id:
            protected_ids.add(keep_tab_id)

    # Luôn bảo vệ toàn bộ tab Gemini Pool & ChatGPT Pool có gắn studio_login_guard (tối đa MAX_THREADS_PER_ACCOUNT = 3 tab rảnh mỗi Acc)
    guarded_ids = [
        t.get("id")
        for t in tabs
        if ("gemini.google.com" in (t.get("url") or "") or "studio_login_guard" in (t.get("url") or "")) and t.get("id")
    ]
    for gid in guarded_ids[:MAX_THREADS_PER_ACCOUNT]:
        protected_ids.add(gid)

    # Nếu hoàn toàn không có tab nào đang hoạt động, giữ lại 1 tab đầu tiên để cửa sổ Chrome không bị đóng tắt
    if not protected_ids and tabs:
        first_chatgpt = next((t.get("id") for t in tabs if "chatgpt.com" in (t.get("url") or "")), None)
        protected_ids.add(first_chatgpt or tabs[0].get("id"))

    closed_count = 0
    for t in tabs:
        tid = t.get("id")
        if not tid or tid in protected_ids:
            continue
        # Chỉ giữ lại 1 tab duy nhất nếu tất cả các tab khác đều bị đóng
        if (len(tabs) - closed_count) <= 1:
            break
        try:
            ws = t.get("webSocketDebuggerUrl")
            if ws:
                _cdp_eval_js(
                    ws,
                    "window.onbeforeunload = null; true;",
                    await_promise=False,
                    timeout=0.8,
                )
            requests.get(f"http://127.0.0.1:{port}/json/close/{tid}", timeout=1.5)
            closed_count += 1
        except Exception:
            pass

    _STATUS_CACHE["ts"] = 0.0
    return closed_count


def sweep_completed_and_idle_tabs_across_all_accounts() -> Dict[str, Any]:
    """
    Đóng toàn bộ các Tab kịch bản đã hoàn thành / không hoạt động trên cả 3 tài khoản (giữ lại tab đang chạy hoặc bể 3 tab chính mỗi Acc).
    Chuẩn API #4 trong Master Blueprint V6.0.
    """
    closed_total = 0
    details: Dict[str, int] = {}

    for aid in ACCOUNTS_CONFIG.keys():
        closed_acc = _close_inactive_tabs_on_account(aid, keep_tab_id=None)
        details[aid] = closed_acc
        closed_total += closed_acc

    _STATUS_CACHE["ts"] = 0.0
    log_info(f"Đã dọn sạch {closed_total} tab không hoạt động trên 3 tài khoản Chrome ({details}).", category="CHROME")
    return {
        "success": True,
        "closed_tabs": closed_total,
        "by_account": details,
        "message": f"Đã dọn sạch {closed_total} tab không hoạt động trên 3 tài khoản!",
    }


def select_best_available_account(preferred_acc_id: Optional[str] = None, project_id: Optional[str] = None) -> str:
    """Chọn tài khoản ChatGPT đã đăng nhập và đang rảnh nhất (Load Balancing trực tiếp thời gian thực giữa các Acc)."""
    global _ROUND_ROBIN_IDX
    if preferred_acc_id and preferred_acc_id in ACCOUNTS_CONFIG:
        if project_id:
            with _STATE_LOCK:
                for aid in _PENDING_PROJECTS_BY_ACC:
                    _PENDING_PROJECTS_BY_ACC[aid].discard(project_id)
                _PENDING_PROJECTS_BY_ACC.setdefault(preferred_acc_id, set()).add(project_id)
        return preferred_acc_id

    status_all = check_all_web_accounts_status(force_refresh=False).get("accounts", {})
    logged_in_accs = [aid for aid in ["acc_1", "acc_2", "acc_3"] if status_all.get(aid, {}).get("logged_in")]
    if len(logged_in_accs) < 2:
        # Tự động kiểm tra và bật đủ các tài khoản ChatGPT đã lưu trên ổ cứng (ví dụ cả Acc #1 và Acc #2)
        logged_in_accs = ensure_all_saved_chatgpt_accounts_open(run_hidden=False)

    if logged_in_accs:
        with _STATE_LOCK:
            if project_id:
                for aid in _PENDING_PROJECTS_BY_ACC:
                    _PENDING_PROJECTS_BY_ACC[aid].discard(project_id)

            def _live_load(a: str) -> int:
                act_projs = set(_ACTIVE_JOBS_BY_ACC.get(a, {}).values())
                pend_projs = set(_PENDING_PROJECTS_BY_ACC.get(a, set()))
                return len(act_projs | pend_projs)

            loads = {a: _live_load(a) for a in logged_in_accs}
            min_load = min(loads.values())
            least_loaded = [a for a in logged_in_accs if loads[a] == min_load]
            chosen = least_loaded[_ROUND_ROBIN_IDX % len(least_loaded)]
            _ROUND_ROBIN_IDX += 1
            if project_id:
                _PENDING_PROJECTS_BY_ACC.setdefault(chosen, set()).add(project_id)
            return chosen

    # Nếu chưa tài khoản nào xác nhận đăng nhập, ưu tiên tài khoản đang mở trình duyệt hoặc mặc định acc_1
    open_accs = [aid for aid in ["acc_1", "acc_2", "acc_3"] if status_all.get(aid, {}).get("browser_open")]
    fallback = open_accs[0] if open_accs else "acc_1"
    ensure_chrome_debug_browser_open(
        open_chatgpt_home=True,
        force_bring_to_front=False,
        run_hidden=False,
        acc_id=fallback,
        fast_if_already_open=True,
    )
    if project_id:
        with _STATE_LOCK:
            _PENDING_PROJECTS_BY_ACC.setdefault(fallback, set()).add(project_id)
    return fallback


class ChatGPTWebSession:
    """
    Phiên làm việc trực tiếp trên 1 Tab ChatGPT Web thông qua Chrome DevTools Protocol (CDP).
    Hỗ trợ hội thoại nhiều bước liên tiếp (STEP 2 -> STEP 3 -> STEP 4 A/B/C -> STEP 5 -> STEP 6)
    trong cùng 1 đoạn chat để giữ trọn vẹn ngữ cảnh.
    """

    def __init__(self, project_id: str, acc_id: Optional[str] = None):
        self.project_id = project_id
        self.acc_id = select_best_available_account(acc_id, project_id=project_id)
        self.cfg = ACCOUNTS_CONFIG[self.acc_id]
        self.port = self.cfg["port"]
        self.tab_id: Optional[str] = None
        self.ws_url: Optional[str] = None
        self.resumed_existing_chat: bool = False

    def open_session_tab(self, force_new_chat: bool = True) -> bool:
        """
        Cấp phát 1 Tab độc lập 100% cho `self.project_id` trên trình duyệt của `self.acc_id`.
        Sử dụng khóa `_ACC_TAB_LOCKS[self.acc_id]` để đảm bảo khi chạy 3 luồng song song,
        3 luồng BẮT BUỘC nhận được 3 `tab_id` hoàn toàn khác nhau (Mở đủ 3 Tab trên Chrome),
        tuyệt đối không bao giờ tranh chấp chung 1 Tab hoặc đóng nhầm Tab của luồng khác!
        """
        with _STATE_LOCK:
            is_hidden = _CHROME_HIDDEN_STATE.get(self.acc_id, False)

        ensure_chrome_debug_browser_open(
            open_chatgpt_home=True,
            force_bring_to_front=False,
            run_hidden=is_hidden,
            acc_id=self.acc_id,
            fast_if_already_open=True,
        )

        acc_lock = _ACC_TAB_LOCKS.setdefault(self.acc_id, threading.RLock())
        with acc_lock:
            tabs = _cdp_get_tabs(self.port, timeout=3.0) or []
            existing_tab_ids = {t.get("id") for t in tabs if t.get("id")}

            with _STATE_LOCK:
                acc_jobs = _ACTIVE_JOBS_BY_ACC.setdefault(self.acc_id, {})
                # CHỈ dọn các tab_id mồ côi khi lấy được danh sách tab hợp lệ (existing_tab_ids không rỗng),
                # TUYỆT ĐỐI KHÔNG xóa acc_jobs nếu _cdp_get_tabs tạm thời timeout khi Chrome đang tải nặng!
                if existing_tab_ids:
                    for tid_old in list(acc_jobs.keys()):
                        if tid_old not in existing_tab_ids:
                            acc_jobs.pop(tid_old, None)
                # Nếu project_id này đã có tab đăng ký trước đó thì giải phóng để cấp mới
                for tid_old, pid_old in list(acc_jobs.items()):
                    if pid_old == self.project_id and tid_old != self.tab_id:
                        acc_jobs.pop(tid_old, None)
                busy_tabs = set(acc_jobs.keys())

            # 0. Nếu không ép mở chat mới và đã có tab hội thoại (/c/...) chứa đúng mã dự án -> nối tiếp
            if not force_new_chat and self.project_id:
                for t in tabs:
                    tid = t.get("id")
                    turl = (t.get("url") or "").strip()
                    ws = t.get("webSocketDebuggerUrl")
                    if tid and tid not in busy_tabs and ws and "/c/" in turl:
                        has_proj = _cdp_eval_js(
                            ws,
                            f"Boolean(document.body && (document.body.innerText || '').includes({json.dumps(self.project_id)}))",
                            await_promise=False,
                            timeout=2.0,
                        )
                        if has_proj:
                            self.tab_id = tid
                            self.ws_url = ws
                            self.resumed_existing_chat = True
                            break

            # 1. Tái sử dụng tab rảnh trong Bể 3 Tab (Pool) của tài khoản nếu chưa bị bất kỳ luồng nào giữ
            if not self.ws_url:
                for t in tabs:
                    tid = t.get("id")
                    turl = (t.get("url") or "").strip()
                    turl_base = turl.split("#")[0].split("?")[0].strip().rstrip("/")
                    ws = t.get("webSocketDebuggerUrl")
                    if tid and ws and tid not in busy_tabs:
                        if turl_base in ("https://chatgpt.com", "https://chat.openai.com"):
                            _install_chatgpt_tab_protection_js(ws)
                            self.tab_id = tid
                            self.ws_url = ws
                            break
                        elif turl.startswith("about:blank") or ("/c/" in turl and force_new_chat):
                            _cdp_navigate(ws, CHATGPT_GUARD_URL, timeout=2.5)
                            self.tab_id = tid
                            self.ws_url = ws
                            break

            # 2. Mở 1 Tab ChatGPT mới tinh riêng biệt cho luồng này (Đảm bảo 3 luồng = 3 Tab độc lập!)
            if not self.ws_url:
                for _attempt in range(3):
                    try:
                        resp = requests.put(
                            f"http://127.0.0.1:{self.port}/json/new?https://chatgpt.com/?studio_login_guard=1",
                            timeout=5,
                        )
                        if resp.status_code == 200:
                            tab_info = resp.json()
                            new_tid = tab_info.get("id")
                            new_ws = tab_info.get("webSocketDebuggerUrl")
                            new_url = (tab_info.get("url") or "").strip()
                            if new_tid and new_ws and new_tid not in busy_tabs:
                                _install_chatgpt_tab_protection_js(new_ws)
                                if not new_url or new_url.startswith("about:blank"):
                                    _cdp_navigate(new_ws, CHATGPT_GUARD_URL, timeout=2.5)
                                self.tab_id = new_tid
                                self.ws_url = new_ws
                                break
                    except Exception:
                        time.sleep(0.3)

            # 3. Đăng ký NGAY LẬP TỨC tab_id của luồng này vào _ACTIVE_JOBS_BY_ACC bên trong khóa acc_lock!
            if self.tab_id:
                _install_chatgpt_tab_protection_js(self.ws_url)
                with _STATE_LOCK:
                    _PENDING_PROJECTS_BY_ACC.setdefault(self.acc_id, set()).discard(self.project_id)
                    _ACTIVE_JOBS_BY_ACC.setdefault(self.acc_id, {})[self.tab_id] = self.project_id
                    active_now = dict(_ACTIVE_JOBS_BY_ACC.get(self.acc_id, {}))
                log_info(
                    f"[{self.project_id}] Đã mở & khóa Tab độc lập ({self.tab_id[:8]}) trên {self.cfg['label']} "
                    f"(Tổng {len(active_now)} luồng đang chạy song song trên {self.cfg['label']}: {list(active_now.values())})",
                    category="CHROME",
                    project_id=self.project_id,
                )

        if not self.ws_url or not self.tab_id:
            return False

        # Đợi ô nhập ChatGPT (ProseMirror / #prompt-textarea / #mobile-composer-prompt) xuất hiện trên Tab của luồng này
        composer_sel = COMPOSER_SELECTOR
        for tick in range(50):
            _install_chatgpt_tab_protection_js(self.ws_url)
            st = _cdp_eval_js(
                self.ws_url,
                f"""
                (() => {{
                    const href = window.location.href || '';
                    if (href.startsWith('about:blank') || (!href.includes('chatgpt.com') && !href.includes('openai.com'))) {{
                        return {{ blank: true, ready: false }};
                    }}
                    return {{ blank: false, ready: Boolean(document.querySelector('{composer_sel}')) }};
                }})()
                """,
                await_promise=False,
                timeout=3.0,
            )
            if isinstance(st, dict):
                if st.get("ready"):
                    time.sleep(0.4)
                    self.ensure_thinking_effort_medium()
                    return True
                if st.get("blank") and tick in (0, 3, 8, 16):
                    _cdp_navigate(self.ws_url, CHATGPT_GUARD_URL, timeout=2.5)
            time.sleep(0.5)
        return False

    def ensure_thinking_effort_medium(self) -> Dict[str, Any]:
        """
        BẮT BUỘC KHÓA MODEL VIẾT Ở CHẾ ĐỘ 'Thinking effort: Medium' (Mốc 1/2 trên thanh trượt Power Slider hoặc menu Medium),
        TUYỆT ĐỐI KHÔNG ĐỂ NGẪU NHIÊN (Instant / Low / High):
        1. Chờ nút 'Select ChatGPT model' (`button[aria-label="Select ChatGPT model"]` hoặc `form button[aria-haspopup="menu"]`)
           tải xong trên thanh công cụ dưới ô chat (tối đa 5 giây sau khi trang mở).
        2. Nếu nút đã hiện 'Medium' -> Giữ nguyên.
        3. Nếu đang ở 'Instant', 'High', 'Low', 'Auto'... -> Bấm mở menu bằng chuỗi sự kiện Radix UI (`pointerdown` + `mousedown` + `click`),
           sau đó điều khiển thanh trượt `[data-reasoning-slider="true"]` / `[role="slider"]` (hoặc menu item truyền thống)
           về đúng nấc **Medium** (`aria-valuenow="1"`) rồi đóng menu.
        """
        if not self.ws_url:
            return {"ok": False, "reason": "NO_WS_URL"}

        js_lock_medium = r"""
        (async () => {
            function dispatchMouseClickAt(el, x, y) {
                if (!el) return;
                const opts = {
                    bubbles: true,
                    cancelable: true,
                    view: window,
                    button: 0,
                    buttons: 1,
                    clientX: x,
                    clientY: y,
                    pointerId: 1,
                    pointerType: 'mouse',
                    isPrimary: true
                };
                el.dispatchEvent(new PointerEvent('pointerdown', opts));
                el.dispatchEvent(new MouseEvent('mousedown', opts));
                if (typeof el.focus === 'function') el.focus();
                el.dispatchEvent(new PointerEvent('pointerup', opts));
                el.dispatchEvent(new MouseEvent('mouseup', opts));
                el.dispatchEvent(new MouseEvent('click', opts));
            }

            function radixClick(el) {
                if (!el) return;
                const r = el.getBoundingClientRect();
                dispatchMouseClickAt(el, r.left + r.width / 2, r.top + r.height / 2);
            }

            function findModelEffortBtn() {
                return (
                    document.querySelector('button[aria-label="Select ChatGPT model"]')
                    || document.querySelector('button[aria-label*="Select ChatGPT model" i]')
                    || document.querySelector('button[aria-label*="Thinking effort" i]')
                    || Array.from(document.querySelectorAll('form button[aria-haspopup="menu"]')).find(
                        b => /thinking|effort|instant|medium|high|low|standard|extended|gpt/i.test((b.innerText || '') + ' ' + (b.getAttribute('aria-label') || ''))
                    )
                    || document.querySelector('form button[aria-haspopup="menu"]')
                );
            }

            // Nếu tab bị chuyển về about:blank thì điều hướng ngay lại https://chatgpt.com/
            if (!window.location.href || window.location.href.startsWith('about:blank')) {
                window.location.replace('https://chatgpt.com/');
                await new Promise(r => setTimeout(r, 2500));
            }

            // Chờ nút chọn Model / Thinking effort render xong (vì nút này tải sau #prompt-textarea khoảng 0.5s - 2.5s)
            let modelBtn = null;
            for (let w = 0; w < 25; w++) {
                modelBtn = findModelEffortBtn();
                if (modelBtn && (modelBtn.innerText || '').trim().length > 0) break;
                await new Promise(r => setTimeout(r, 220));
            }
            if (!modelBtn) {
                return { ok: false, reason: 'NO_MODEL_BTN' };
            }

            const initTxt = (modelBtn.innerText || '').trim();
            if (initTxt.toLowerCase().includes('medium')) {
                return { ok: true, before: initTxt, after: initTxt, alreadyMedium: true };
            }

            for (let attempt = 0; attempt < 3; attempt++) {
                const curBtn = findModelEffortBtn() || modelBtn;
                if ((curBtn.innerText || '').toLowerCase().includes('medium')) {
                    break;
                }

                // Mở menu: Gọi .click() trước, chỉ dùng pointerdown nếu menu vẫn chưa mở (tránh toggle đóng ngược!)
                let openMenuNow = document.querySelector('[role="menu"][data-state="open"], [data-reasoning-slider="true"], [role="slider"]');
                if (!openMenuNow) {
                    curBtn.click();
                    await new Promise(r => setTimeout(r, 280));
                    openMenuNow = document.querySelector('[role="menu"][data-state="open"], [data-reasoning-slider="true"], [role="slider"]');
                }
                if (!openMenuNow) {
                    const rect = curBtn.getBoundingClientRect();
                    curBtn.dispatchEvent(new PointerEvent('pointerdown', {
                        bubbles: true, cancelable: true, view: window, button: 0, buttons: 1,
                        clientX: rect.left + 10, clientY: rect.top + 10, pointerId: 1, pointerType: 'mouse', isPrimary: true
                    }));
                    await new Promise(r => setTimeout(r, 280));
                }

                const reasoningRow = document.querySelector('[data-reasoning-slider="true"], [aria-label="Power"]');
                const slider = document.querySelector('[role="slider"]');
                if (reasoningRow || slider) {
                    const keyTarget = reasoningRow || slider;
                    if (typeof keyTarget.focus === 'function') keyTarget.focus();

                    // Bước 1: Đưa thanh trượt về mốc 0 (Instant / trái cùng) trước
                    for (let i = 0; i < 4; i++) {
                        keyTarget.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', code: 'ArrowLeft', keyCode: 37, which: 37, bubbles: true, cancelable: true }));
                        keyTarget.dispatchEvent(new KeyboardEvent('keyup', { key: 'ArrowLeft', code: 'ArrowLeft', keyCode: 37, which: 37, bubbles: true, cancelable: true }));
                        await new Promise(r => setTimeout(r, 85));
                    }

                    // Bước 2: Dịch từng nấc sang phải cho đến khi chữ trên nút đạt đúng "Medium" (mốc 1/2)
                    for (let step = 0; step < 4; step++) {
                        const nowTxt = ((findModelEffortBtn() || curBtn).innerText || '').toLowerCase();
                        if (nowTxt.includes('medium')) break;
                        keyTarget.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', code: 'ArrowRight', keyCode: 39, which: 39, bubbles: true, cancelable: true }));
                        keyTarget.dispatchEvent(new KeyboardEvent('keyup', { key: 'ArrowRight', code: 'ArrowRight', keyCode: 39, which: 39, bubbles: true, cancelable: true }));
                        await new Promise(r => setTimeout(r, 120));
                        if (((findModelEffortBtn() || curBtn).innerText || '').toLowerCase().includes('medium')) break;
                    }

                    // Bước 3 (Dự phòng): Nếu chưa sang Medium, click thẳng vào chính giữa (50%) thanh trượt Power Slider
                    if (!((findModelEffortBtn() || curBtn).innerText || '').toLowerCase().includes('medium')) {
                        const track = document.querySelector('[data-model-picker-power-slider] [data-orientation="horizontal"]')
                            || document.querySelector('[data-model-picker-power-slider]')
                            || reasoningRow;
                        if (track) {
                            const tr = track.getBoundingClientRect();
                            if (tr.width > 10) {
                                dispatchMouseClickAt(track, tr.left + tr.width * 0.5, tr.top + tr.height * 0.5);
                                await new Promise(r => setTimeout(r, 180));
                            }
                        }
                    }
                } else {
                    // Giao diện menu danh sách truyền thống
                    const items = Array.from(document.querySelectorAll('[role="menuitem"], [role="menuitemradio"], [role="option"]'));
                    const medItem = items.find(x => (x.innerText || '').toLowerCase().includes('medium'));
                    if (medItem) {
                        medItem.click();
                        await new Promise(r => setTimeout(r, 180));
                    }
                }

                // Đóng menu bằng phím Escape để không che khung soạn thảo
                document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true }));
                await new Promise(r => setTimeout(r, 140));

                if (((findModelEffortBtn() || curBtn).innerText || '').toLowerCase().includes('medium')) {
                    break;
                }
            }

            const finalBtn = findModelEffortBtn() || modelBtn;
            const finalTxt = (finalBtn.innerText || '').trim();
            return {
                ok: finalTxt.toLowerCase().includes('medium'),
                before: initTxt,
                after: finalTxt
            };
        })()
        """
        port_lock = _PORT_INJECT_LOCKS.setdefault(self.port, threading.Lock())
        with port_lock:
            res = _cdp_eval_js(self.ws_url, js_lock_medium, await_promise=True, timeout=12.0)
        if isinstance(res, dict) and res.get("before") != res.get("after"):
            log_info(
                f"[{self.project_id}] 🎯 Đã tự động chuyển Model viết từ '{res.get('before', '').replace(chr(10), ' ')}' -> '{res.get('after', '').replace(chr(10), ' ')}' (Khóa cố định Medium)!",
                category="CHROME",
                project_id=self.project_id,
            )
        return res if isinstance(res, dict) else {"ok": False}

    def start_fresh_chat(self, step_name: str = "") -> bool:
        """
        Chuyển về ĐOẠN CHAT MỚI HOÀN TOÀN (New Chat) ngay trên Tab đang khóa của chính luồng này (`self.tab_id`),
        luôn duy trì chốt bảo vệ `#studio_login_guard` để không bao giờ bị tiến trình ngoài đóng Tab,
        đồng thời TUYỆT ĐỐI KHÔNG ĐỤNG CHẠM tới các Tab của các luồng khác đang chạy song song!
        """
        if not self.ws_url or not self.tab_id:
            return self.open_session_tab(force_new_chat=True)

        self.resumed_existing_chat = False

        # Kiểm tra xem tab hiện tại của luồng này còn sống trên trình duyệt hay không
        tabs_now = _cdp_get_tabs(self.port, timeout=1.5) or []
        if not any(t.get("id") == self.tab_id for t in tabs_now):
            self.tab_id = None
            self.ws_url = None
            return self.open_session_tab(force_new_chat=True)

        _install_chatgpt_tab_protection_js(self.ws_url)

        # Kiểm tra xem tab hiện tại của luồng này có đang ở sẵn trang chủ New Chat (chưa vào /c/...) hay không
        cur_path = _cdp_eval_js(
            self.ws_url,
            "window.location.pathname || '/'",
            await_promise=False,
            timeout=2.5,
        )
        if cur_path is None:
            # Nếu renderer của tab cũ bị treo sau khi render DOM lớn (ví dụ STEP 3 GenUI), đóng ngay tab đó và mở tab mới!
            try:
                requests.get(f"http://127.0.0.1:{self.port}/json/close/{self.tab_id}", timeout=2.0)
            except Exception:
                pass
            with _STATE_LOCK:
                _ACTIVE_JOBS_BY_ACC.get(self.acc_id, {}).pop(self.tab_id, None)
            self.tab_id = None
            self.ws_url = None
            return self.open_session_tab(force_new_chat=True)
        elif isinstance(cur_path, str) and not cur_path.startswith("/c/") and cur_path != "blank":
            # Tab hiện tại của luồng này đã là trang chủ sạch sẽ -> dùng luôn!
            pass
        else:
            # Điều hướng trực tiếp tab đã khóa của luồng này về trang chủ New Chat kèm chốt bảo vệ
            nav_ok = _cdp_navigate(self.ws_url, CHATGPT_GUARD_URL, timeout=3.0)
            if not nav_ok:
                self.tab_id = None
                self.ws_url = None
                return self.open_session_tab(force_new_chat=True)

        time.sleep(0.5)

        composer_sel = COMPOSER_SELECTOR
        none_nav_ticks = 0
        for tick in range(45):
            _install_chatgpt_tab_protection_js(self.ws_url)
            st = _cdp_eval_js(
                self.ws_url,
                f"""
                (() => {{
                    const path = window.location.pathname || '/';
                    const hasBox = Boolean(document.querySelector('{composer_sel}'));
                    const isFresh = !path.includes('/c/');
                    return {{ ready: Boolean(hasBox && isFresh), path: path, isFresh: isFresh }};
                }})()
                """,
                await_promise=False,
                timeout=3.0,
            )
            if isinstance(st, dict):
                none_nav_ticks = 0
                if st.get("ready"):
                    time.sleep(0.4)
                    self.ensure_thinking_effort_medium()
                    return True
                if not st.get("isFresh") and tick in (3, 10):
                    _cdp_navigate(self.ws_url, CHATGPT_GUARD_URL, timeout=2.5)
            else:
                none_nav_ticks += 1
                if none_nav_ticks >= 3:
                    try:
                        requests.get(f"http://127.0.0.1:{self.port}/json/close/{self.tab_id}", timeout=2.0)
                    except Exception:
                        pass
                    with _STATE_LOCK:
                        _ACTIVE_JOBS_BY_ACC.get(self.acc_id, {}).pop(self.tab_id, None)
                    self.tab_id = None
                    self.ws_url = None
                    return self.open_session_tab(force_new_chat=True)
            time.sleep(0.5)
        return False

    def close_session_tab(self, keep_open: bool = False):
        with _STATE_LOCK:
            _PENDING_PROJECTS_BY_ACC.setdefault(self.acc_id, set()).discard(self.project_id)
        if self.tab_id:
            acc_lock = _ACC_TAB_LOCKS.setdefault(self.acc_id, threading.RLock())
            with acc_lock:
                if not keep_open:
                    try:
                        tabs = _cdp_get_tabs(self.port, timeout=1.5) or []
                        if len(tabs) <= MAX_THREADS_PER_ACCOUNT and self.ws_url:
                            # Giữ lại tối đa 3 Tab ấm (Pool 3 Tab) mỗi tài khoản ở trang chủ có gắn #studio_login_guard
                            # để dự án kế tiếp tái sử dụng ngay lập tức mà không cần đóng/mở tab mới!
                            _cdp_navigate(self.ws_url, _fresh_guard_url(), timeout=2.5)
                            time.sleep(0.6)
                        else:
                            requests.get(f"http://127.0.0.1:{self.port}/json/close/{self.tab_id}", timeout=2.0)
                    except Exception:
                        pass
                with _STATE_LOCK:
                    _ACTIVE_JOBS_BY_ACC.get(self.acc_id, {}).pop(self.tab_id, None)

    def _harvest_latest_turn_from_backend_api(self) -> str:
        """
        Tầng 1 (Master Blueprint V6.0): Gọi fetch('/backend-api/conversation/' + convId)
        ngay bên trong Tab (kèm Bearer Token từ /api/auth/session) để thu hoạch 100% văn bản
        Markdown gốc của lượt trả lời cuối cùng mà không bị ảnh hưởng bởi DOM ảo hóa.
        """
        if not self.ws_url:
            return ""
        harvest_js = r"""
        (async () => {
            try {
                const mUrl = window.location.pathname.match(/\/c\/([0-9a-fA-F\-]{16,})/);
                if (!mUrl || !mUrl[1]) return "";
                const convId = mUrl[1];
                if (!window.__studioAccessToken) {
                    const sr = await fetch('/api/auth/session', { credentials: 'include' });
                    if (sr.ok) {
                        const sd = await sr.json();
                        if (sd && sd.accessToken) window.__studioAccessToken = sd.accessToken;
                    }
                }
                if (!window.__studioAccessToken) return "";
                const cr = await fetch('/backend-api/conversation/' + convId, {
                    credentials: 'include',
                    headers: {
                        'Authorization': 'Bearer ' + window.__studioAccessToken,
                        'Accept': 'application/json'
                    }
                });
                if (!cr.ok) return "";
                const conv = await cr.json();
                const mapping = conv.mapping || {};
                let cur = conv.current_node;
                const seen = new Set();
                const chain = [];
                while (cur && !seen.has(cur) && mapping[cur]) {
                    seen.add(cur);
                    chain.push(mapping[cur]);
                    cur = mapping[cur].parent;
                }
                chain.reverse();
                let lastUserIdx = -1;
                for (let i = 0; i < chain.length; i++) {
                    const msg = chain[i].message;
                    if (!msg) continue;
                    const role = (msg.author && msg.author.role) || "";
                    if (role === "user") lastUserIdx = i;
                }
                if (lastUserIdx < 0) return "";
                const asstParts = [];
                for (let i = lastUserIdx + 1; i < chain.length; i++) {
                    const msg = chain[i].message;
                    if (!msg || (msg.metadata && msg.metadata.is_visually_hidden_from_conversation)) continue;
                    const role = (msg.author && msg.author.role) || "";
                    const content = msg.content || {};
                    const ctype = content.content_type || "";
                    const rec = msg.recipient || "all";
                    const ch = msg.channel || "final";
                    if (role === "assistant" && (ctype === "text" || ctype === "multimodal_text") && (rec === "all" || !msg.recipient) && (ch === "final" || !msg.channel)) {
                        const parts = Array.isArray(content.parts) ? content.parts.filter(p => typeof p === "string") : [];
                        const txt = parts.join("\n").trim();
                        if (txt) asstParts.push(txt);
                    }
                }
                return asstParts.join("\n\n").trim();
            } catch (e) {
                return "";
            }
        })()
        """
        res = _cdp_eval_js(self.ws_url, harvest_js, await_promise=True, timeout=10.0)
        raw_md = str(res).strip() if isinstance(res, str) else ""
        if raw_md:
            # Làm sạch các thẻ GenUI nội bộ của ChatGPT (<box>, <title>, <text>, <badge>, <button>...) nếu có
            raw_md = re.sub(r"<button\b[^>]*>[\s\S]*?</button>", "", raw_md, flags=re.IGNORECASE)
            raw_md = re.sub(r"<icon\b[^>]*/>|<icon\b[^>]*>[\s\S]*?</icon>", "", raw_md, flags=re.IGNORECASE)
            raw_md = re.sub(r"</?(?:box|row|col|text|title|badge|list|list-item)\b[^>]*>", "\n", raw_md, flags=re.IGNORECASE)
            raw_md = re.sub(r"\n{3,}", "\n\n", raw_md).strip()
        return raw_md

    def send_prompt_and_wait(
        self,
        prompt_text: str,
        step_label: str = "STEP",
        timeout_sec: int = 900,
        progress_cb: Optional[Callable[[str, int], None]] = None,
        should_stop_cb: Optional[Callable[[], bool]] = None,
    ) -> str:
        """
        Bơm prompt vào ô chat của ChatGPT Web, tự động khóa Thinking effort: Medium,
        bấm Gửi kèm xác nhận sentConfirmed, theo dõi streaming (chống ảo hóa DOM đa lượt)
        và thu hoạch 2 tầng (Backend API + DOM).
        """
        if not self.ws_url:
            if not self.open_session_tab():
                raise RuntimeError(
                    f"Không thể kết nối tới khung chat ChatGPT trên {self.cfg['label']}. "
                    f"Hãy bấm mở {self.cfg['label']} trên thanh điều khiển và đăng nhập ChatGPT trước!"
                )

        step_stamp = f"seen_{int(time.time() * 1000)}"
        # Kiểm tra xem tab vừa nối tiếp có đang trong quá trình sinh câu trả lời dở (in_progress) hay không,
        # đồng thời đóng dấu (data-studio-seen) toàn bộ các node cũ để chống hiện tượng ChatGPT Web
        # ẩn/gỡ (unmount) các lượt đầu tiên khi hội thoại dài >= 4 lượt khiến nodes.length không tăng.
        init_state = _cdp_eval_js(
            self.ws_url,
            f"""
            (() => {{
                const stamp = {json.dumps(step_stamp)};
                const turnStates = Array.from(document.querySelectorAll('[data-talvt-turn-state]')).map(e => e.getAttribute('data-talvt-turn-state'));
                const hasIncomplete = turnStates.some(s => s && s !== 'complete');
                const stopBtn = document.querySelector('[data-testid="stop-button"], button[aria-label*="Stop" i], .result-streaming');
                const isStreaming = Boolean(stopBtn || hasIncomplete);
                let nodes = Array.from(document.querySelectorAll('[data-markdown-text-style="assistant-message"], [data-message-author-role="assistant"]'));
                if (nodes.length === 0) {{
                    nodes = Array.from(document.querySelectorAll('[data-content-search-unit-key$=":assistant"], article[data-turn="assistant"], div[data-turn="assistant"]'));
                }}
                let prevLastHead = '';
                if (nodes.length > 0) {{
                    const lastMd = nodes[nodes.length - 1].querySelector('.markdown') || nodes[nodes.length - 1];
                    prevLastHead = (lastMd.innerText || '').trim().slice(0, 120);
                }}
                return {{
                    isStreaming: isStreaming,
                    count: nodes.length,
                    prevLastHead: prevLastHead
                }};
            }})()
            """,
            await_promise=False,
            timeout=5.0,
        )
        already_streaming = bool(isinstance(init_state, dict) and init_state.get("isStreaming") and self.resumed_existing_chat)
        prev_last_head = "" if already_streaming else (str(init_state.get("prevLastHead") or "") if isinstance(init_state, dict) else "")

        # Đóng dấu các node cũ trước khi gửi lệnh mới
        _cdp_eval_js(
            self.ws_url,
            f"""
            (() => {{
                const stamp = {json.dumps(step_stamp)};
                const keepLastUnmarked = {'true' if already_streaming else 'false'};
                let nodes = Array.from(document.querySelectorAll('[data-markdown-text-style="assistant-message"], [data-message-author-role="assistant"]'));
                if (nodes.length === 0) {{
                    nodes = Array.from(document.querySelectorAll('[data-content-search-unit-key$=":assistant"], article[data-turn="assistant"], div[data-turn="assistant"]'));
                }}
                const limit = keepLastUnmarked ? Math.max(0, nodes.length - 1) : nodes.length;
                for (let i = 0; i < limit; i++) {{
                    nodes[i].setAttribute('data-studio-seen', stamp);
                }}
                return limit;
            }})()
            """,
            await_promise=False,
            timeout=4.0,
        )
        prev_backend_md = "" if already_streaming else self._harvest_latest_turn_from_backend_api()
        prev_backend_head = prev_backend_md[:120].strip() if prev_backend_md else ""

        if not already_streaming:
            # BẮT BUỘC KHÓA MODEL VIẾT Ở CHẾ ĐỘ "Thinking effort: Medium" TRƯỚC MỖI LẦN GỬI LỆNH
            self.ensure_thinking_effort_medium()

            # Dùng ensure_ascii=True để mã hóa an toàn tuyệt đối mọi ký tự tiếng Nhật / Việt (\uXXXX)
            escaped_prompt_json = json.dumps(prompt_text, ensure_ascii=True)
            inject_js = f"""
            (async () => {{
                const text = {escaped_prompt_json};
                // Kiểm tra chốt chặn lần cuối: nếu nút Model chưa phải Medium thì tự động gạt thanh trượt Power Slider về Medium (mốc 1/2)
                try {{
                    function dispatchMouseClickAt(el, x, y) {{
                        if (!el) return;
                        const opts = {{ bubbles: true, cancelable: true, view: window, button: 0, buttons: 1, clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', isPrimary: true }};
                        el.dispatchEvent(new PointerEvent('pointerdown', opts));
                        el.dispatchEvent(new MouseEvent('mousedown', opts));
                        if (typeof el.focus === 'function') el.focus();
                        el.dispatchEvent(new PointerEvent('pointerup', opts));
                        el.dispatchEvent(new MouseEvent('mouseup', opts));
                        el.dispatchEvent(new MouseEvent('click', opts));
                    }}
                    const modelBtn = document.querySelector('button[aria-label="Select ChatGPT model"]')
                        || document.querySelector('form button[aria-haspopup="menu"]');
                    if (modelBtn && !(modelBtn.innerText || '').toLowerCase().includes('medium')) {{
                        modelBtn.click();
                        await new Promise(res => setTimeout(res, 280));
                        const reasoningRow = document.querySelector('[data-reasoning-slider="true"], [aria-label="Power"]');
                        const slider = document.querySelector('[role="slider"]');
                        if (reasoningRow || slider) {{
                            const keyTarget = reasoningRow || slider;
                            if (typeof keyTarget.focus === 'function') keyTarget.focus();
                            for (let i = 0; i < 4; i++) {{
                                keyTarget.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'ArrowLeft', code: 'ArrowLeft', keyCode: 37, which: 37, bubbles: true, cancelable: true }}));
                                await new Promise(res => setTimeout(res, 80));
                            }}
                            for (let step = 0; step < 4; step++) {{
                                if ((modelBtn.innerText || '').toLowerCase().includes('medium')) break;
                                keyTarget.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'ArrowRight', code: 'ArrowRight', keyCode: 39, which: 39, bubbles: true, cancelable: true }}));
                                await new Promise(res => setTimeout(res, 110));
                            }}
                        }} else {{
                            const items = Array.from(document.querySelectorAll('[role="menuitem"], [role="menuitemradio"], [role="option"]'));
                            const medItem = items.find(x => (x.innerText || '').toLowerCase().includes('medium'));
                            if (medItem) medItem.click();
                        }}
                        document.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true }}));
                        await new Promise(res => setTimeout(res, 120));
                    }}
                }} catch (e) {{}}

                document.querySelectorAll('button[aria-label="Remove pasted text attachment"]').forEach(b => b.click());

                const el = document.querySelector(
                    '#prompt-textarea, #mobile-composer-prompt, textarea[id*="prompt"], div.ProseMirror[contenteditable="true"], [data-composer-markdown], div[role="textbox"][contenteditable="true"], main textarea'
                );
                if (!el) return {{ ok: false, err: 'NO_PROMPT_BOX' }};
                el.focus();

                if (el.tagName === 'TEXTAREA') {{
                    const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                    nativeSetter.call(el, text);
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    await new Promise(r => setTimeout(r, 120));
                }} else {{
                    // Master Blueprint V6.0: DataTransfer + ClipboardEvent('paste')
                    el.focus();
                    if ((el.innerText || '').trim().length > 0) {{
                        const sel = window.getSelection();
                        const range = document.createRange();
                        range.selectNodeContents(el);
                        sel.removeAllRanges();
                        sel.addRange(range);
                        document.execCommand('delete', false, null);
                        await new Promise(r => setTimeout(r, 80));
                    }}
                    if (text.length > 12000) {{
                        const headLine = text.slice(0, 1200) + '\\n\\n[xem toàn bộ nội dung đính kèm bên dưới]';
                        const dtHead = new DataTransfer();
                        dtHead.setData('text/plain', headLine);
                        el.dispatchEvent(new ClipboardEvent('paste', {{ clipboardData: dtHead, bubbles: true, cancelable: true }}));
                        await new Promise(r => setTimeout(r, 50));
                        const dtFull = new DataTransfer();
                        dtFull.setData('text/plain', text);
                        el.dispatchEvent(new ClipboardEvent('paste', {{ clipboardData: dtFull, bubbles: true, cancelable: true }}));
                    }} else {{
                        const lines = text.split('\\n');
                        const chunks = [];
                        let cur = [];
                        let curLen = 0;
                        for (const ln of lines) {{
                            if (cur.length >= 45 || (curLen + ln.length) > 3200) {{
                                chunks.push(cur.join('\\n') + '\\n');
                                cur = [];
                                curLen = 0;
                            }}
                            cur.push(ln);
                            curLen += ln.length + 1;
                        }}
                        if (cur.length > 0) chunks.push(cur.join('\\n'));
                        for (const ch of chunks) {{
                            const dt = new DataTransfer();
                            dt.setData('text/plain', ch);
                            el.dispatchEvent(new ClipboardEvent('paste', {{ clipboardData: dt, bubbles: true, cancelable: true }}));
                            await new Promise(r => setTimeout(r, 15));
                        }}
                    }}
                }}

                // Vòng lặp xác nhận gửi thật sự (sentConfirmed - Master Blueprint V6.0)
                let sentConfirmed = false;
                for (let s = 0; s < 25; s++) {{
                    await new Promise(r => setTimeout(r, 320));
                    const stopNow = document.querySelector('[data-testid="stop-button"], form button[aria-label*="Stop" i], button[aria-label*="Stop streaming" i]');
                    const curBox = document.querySelector('#prompt-textarea, #mobile-composer-prompt, textarea[id*="prompt"], div.ProseMirror[contenteditable="true"], [role="textbox"][contenteditable="true"], main textarea');
                    const curTextLen = curBox ? ((curBox.tagName === 'TEXTAREA' ? curBox.value : curBox.innerText) || '').trim().length : 0;
                    const hasAttachment = Array.from(document.querySelectorAll('form button')).some(
                        b => (b.getAttribute('aria-label') || '').includes('Remove pasted text')
                    );
                    if (stopNow || (s > 0 && curTextLen === 0 && !hasAttachment)) {{
                        sentConfirmed = true;
                        break;
                    }}
                    const sendBtn = document.querySelector('button[data-testid="send-button"], button[data-testid="fruitjuice-send-button"], form button[aria-label*="Send" i], button[aria-label*="Send prompt" i], form button[type="submit"]');
                    if (sendBtn && !sendBtn.disabled) {{
                        sendBtn.click();
                    }} else if (s >= 5 && !hasAttachment) {{
                        const enterEvt = new KeyboardEvent('keydown', {{
                            key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true
                        }});
                        el.dispatchEvent(enterEvt);
                    }}
                }}
                return {{ ok: sentConfirmed, method: 'paste_sent_confirmed' }};
            }})()
            """
            port_lock = _PORT_INJECT_LOCKS.setdefault(self.port, threading.Lock())
            inj_res = None
            for inj_attempt in range(3):
                _install_chatgpt_tab_protection_js(self.ws_url)
                with port_lock:
                    inj_res = _cdp_eval_js(self.ws_url, inject_js, await_promise=True, timeout=45.0)
                if isinstance(inj_res, dict) and inj_res.get("ok"):
                    break
                log_warn(
                    f"[{self.project_id}] Thử gửi lệnh lại vào ChatGPT ({self.cfg['label']}) lần {inj_attempt + 2}/3 (kết quả trước: {inj_res})...",
                    category="CHROME",
                    project_id=self.project_id,
                )
                tabs_chk = _cdp_get_tabs(self.port, timeout=1.5) or []
                if not any(t.get("id") == self.tab_id for t in tabs_chk):
                    self.tab_id = None
                    self.ws_url = None
                    self.open_session_tab(force_new_chat=True)
                else:
                    _cdp_navigate(self.ws_url, CHATGPT_GUARD_URL, timeout=2.5)
                    for _w in range(20):
                        time.sleep(0.5)
                        has_box = _cdp_eval_js(
                            self.ws_url,
                            f"Boolean(document.querySelector('{COMPOSER_SELECTOR}'))",
                            await_promise=False,
                            timeout=2.0,
                        )
                        if has_box:
                            break
                    self.ensure_thinking_effort_medium()
            if not isinstance(inj_res, dict) or not inj_res.get("ok"):
                raise RuntimeError(f"Không thể gửi lệnh vào ChatGPT ({self.cfg['label']}): {inj_res}")

        # Chờ ChatGPT bắt đầu sinh câu trả lời và theo dõi streaming cho đến khi hoàn tất
        start_t = time.time()
        last_text = ""
        stable_ticks = 0
        started_responding = False

        poll_js = f"""
        (() => {{
            try {{
                if (!window.location.hash.includes('studio_login_guard')) {{
                    window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search + '#studio_login_guard');
                }}
            }} catch (e) {{}}
            const stamp = {json.dumps(step_stamp)};
            const prevLastHead = {json.dumps(prev_last_head, ensure_ascii=True)};
            // Tự động bấm nút Continue generating nếu xuất hiện
            const btns = Array.from(document.querySelectorAll('button'));
            for (const b of btns) {{
                const t = (b.innerText || '').trim().toLowerCase();
                if (t.includes('continue generating') || t.includes('tiếp tục tạo') || b.getAttribute('data-testid') === 'continue-button') {{
                    b.click();
                }}
            }}
            const turnStates = Array.from(document.querySelectorAll('[data-talvt-turn-state]')).map(e => e.getAttribute('data-talvt-turn-state'));
            const hasIncompleteTurn = turnStates.some(s => s && s !== 'complete');
            const stopBtn = document.querySelector('[data-testid="stop-button"], button[aria-label*="Stop" i], button[aria-label*="Dừng" i], .result-streaming');
            const isStreaming = Boolean(stopBtn || hasIncompleteTurn);
            let nodes = Array.from(document.querySelectorAll('[data-markdown-text-style="assistant-message"], [data-message-author-role="assistant"]'));
            if (nodes.length === 0) {{
                nodes = Array.from(document.querySelectorAll('[data-content-search-unit-key$=":assistant"], article[data-turn="assistant"], div[data-turn="assistant"]'));
            }}
            if (nodes.length > 0) {{
                try {{ nodes[nodes.length - 1].scrollIntoView({{ block: 'end' }}); }} catch (e) {{}}
            }}
            let newNodes = nodes.filter(n => n.getAttribute('data-studio-seen') !== stamp);
            if (newNodes.length === 0 && nodes.length > 0 && prevLastHead) {{
                const lastMd = nodes[nodes.length - 1].querySelector('.markdown') || nodes[nodes.length - 1];
                const lastTxt = (lastMd.innerText || '').trim();
                if (lastTxt && lastTxt.slice(0, 120) !== prevLastHead) {{
                    newNodes = [nodes[nodes.length - 1]];
                }}
            }}
            let latestText = '';
            if (newNodes.length > 0) {{
                const parts = [];
                for (const n of newNodes) {{
                    const md = n.querySelector('.markdown') || n;
                    const txt = (md.innerText || '').trim();
                    if (txt) parts.push(txt);
                }}
                latestText = parts.join('\\n\\n');
            }}
            return {{
                hasNewTurn: newNodes.length > 0,
                isStreaming: isStreaming,
                text: latestText
            }};
        }})()
        """

        none_poll_ticks = 0
        while time.time() - start_t < timeout_sec:
            if should_stop_cb and should_stop_cb():
                raise RuntimeError("Đã dừng tiến trình theo yêu cầu người dùng.")

            time.sleep(1.5)
            state = _cdp_eval_js(self.ws_url, poll_js, await_promise=False, timeout=6.0)
            if not isinstance(state, dict):
                none_poll_ticks += 1
                # Nếu văn bản đã nhận được rất đầy đủ (>= 5.000 ký tự) và tab đột ngột đơ DOM khi hoàn tất render GenUI
                if len(last_text) >= 5000 and none_poll_ticks >= 3:
                    return last_text
                continue
            none_poll_ticks = 0

            has_new_turn = bool(state.get("hasNewTurn"))
            is_streaming = bool(state.get("isStreaming"))
            curr_text = str(state.get("text") or "").strip()

            if has_new_turn and curr_text:
                started_responding = True
                if progress_cb:
                    progress_cb(step_label, len(curr_text))

                if curr_text == last_text and not is_streaming:
                    stable_ticks += 1
                    # Khi nút Stop đã biến mất và văn bản đứng yên suốt 4.5 giây (3 nhịp) -> Thu hoạch Tầng 1 Backend API + Tầng 2 DOM!
                    if stable_ticks >= 3:
                        backend_md = self._harvest_latest_turn_from_backend_api()
                        if backend_md and len(backend_md) >= int(len(curr_text) * 0.85):
                            return backend_md
                        return curr_text
                else:
                    stable_ticks = 0
                    last_text = curr_text
            else:
                # Dự phòng Tầng 1: Nếu không còn streaming sau 12s mà DOM chưa hiện node mới, kiểm tra thẳng Backend API
                if not is_streaming and (time.time() - start_t) > 12:
                    backend_md = self._harvest_latest_turn_from_backend_api()
                    if backend_md and backend_md[:120].strip() != prev_backend_head and len(backend_md) > 80:
                        if progress_cb:
                            progress_cb(step_label, len(backend_md))
                        return backend_md

                # Nếu sau 25 giây vẫn chưa thấy phản hồi mới, kiểm tra xem nút Send còn đó không và bấm lại
                if not started_responding and not is_streaming and (time.time() - start_t) > 20:
                    _cdp_eval_js(
                        self.ws_url,
                        """
                        (() => {
                            const b = document.querySelector('button[type="submit"], [data-testid="send-button"], button[aria-label="Send" i]');
                            if (b && !b.disabled) b.click();
                        })()
                        """,
                        await_promise=False,
                        timeout=3.0,
                    )

        if last_text:
            backend_md = self._harvest_latest_turn_from_backend_api()
            if backend_md and len(backend_md) >= int(len(last_text) * 0.85):
                return backend_md
            return last_text
        raise RuntimeError(f"Quá thời gian chờ ({timeout_sec}s) phản hồi từ ChatGPT tại bước {step_label}.")

    def generate_image_and_harvest_base64(
        self,
        prompt_text: str,
        step_label: str = "THUMBNAIL_GEN",
        timeout_sec: int = 300,
        progress_cb: Optional[Callable[[str, int], None]] = None,
        should_stop_cb: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """
        Gửi lệnh tạo ảnh Thumbnail vào ChatGPT Web, chờ công cụ tạo ảnh (GPT-4o / DALL-E)
        vẽ xong ảnh thực tế và thu hoạch ảnh chất lượng gốc về dưới dạng Base64 PNG
        (kết hợp Tầng 1 Backend API asset_pointer + Tầng 2 DOM <img> / Canvas).
        """
        if not self.ws_url:
            if not self.open_session_tab(force_new_chat=True):
                raise RuntimeError(f"Không thể kết nối tới khung chat ChatGPT trên {self.cfg['label']}.")

        img_stamp = f"img_seen_{int(time.time() * 1000)}"
        # Đóng dấu toàn bộ ảnh và lượt trả lời cũ trước khi gửi lệnh tạo ảnh mới
        _cdp_eval_js(
            self.ws_url,
            f"""
            (() => {{
                const stamp = {json.dumps(img_stamp)};
                document.querySelectorAll('img').forEach(im => im.setAttribute('data-studio-img-seen', stamp));
                document.querySelectorAll('[data-markdown-text-style="assistant-message"], [data-message-author-role="assistant"], article[data-turn="assistant"], div[data-turn="assistant"]').forEach(n => n.setAttribute('data-studio-turn-seen', stamp));
                return true;
            }})()
            """,
            await_promise=False,
            timeout=4.0,
        )

        escaped_prompt_json = json.dumps(prompt_text, ensure_ascii=True)
        inject_js = f"""
        (async () => {{
            const text = {escaped_prompt_json};
            document.querySelectorAll('button[aria-label="Remove pasted text attachment"]').forEach(b => b.click());
            const el = document.querySelector(
                '#prompt-textarea, #mobile-composer-prompt, textarea[id*="prompt"], div.ProseMirror[contenteditable="true"], [data-composer-markdown], div[role="textbox"][contenteditable="true"], main textarea'
            );
            if (!el) return {{ ok: false, err: 'NO_PROMPT_BOX' }};
            el.focus();
            if (el.tagName === 'TEXTAREA') {{
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                nativeSetter.call(el, text);
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                await new Promise(r => setTimeout(r, 120));
            }} else {{
                if ((el.innerText || '').trim().length > 0) {{
                    const sel = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(el);
                    sel.removeAllRanges();
                    sel.addRange(range);
                    document.execCommand('delete', false, null);
                    await new Promise(r => setTimeout(r, 80));
                }}
                const dt = new DataTransfer();
                dt.setData('text/plain', text);
                el.dispatchEvent(new ClipboardEvent('paste', {{ clipboardData: dt, bubbles: true, cancelable: true }}));
                await new Promise(r => setTimeout(r, 80));
            }}

            let sentConfirmed = false;
            for (let s = 0; s < 25; s++) {{
                await new Promise(r => setTimeout(r, 320));
                const stopNow = document.querySelector('[data-testid="stop-button"], form button[aria-label*="Stop" i], button[aria-label*="Stop streaming" i]');
                const curBox = document.querySelector('#prompt-textarea, #mobile-composer-prompt, textarea[id*="prompt"], div.ProseMirror[contenteditable="true"], [role="textbox"][contenteditable="true"], main textarea');
                const curTextLen = curBox ? ((curBox.tagName === 'TEXTAREA' ? curBox.value : curBox.innerText) || '').trim().length : 0;
                if (stopNow || (s > 0 && curTextLen === 0)) {{
                    sentConfirmed = true;
                    break;
                }}
                const sendBtn = document.querySelector('button[data-testid="send-button"], button[data-testid="fruitjuice-send-button"], form button[aria-label*="Send" i], button[aria-label*="Send prompt" i], form button[type="submit"]');
                if (sendBtn && !sendBtn.disabled) {{
                    sendBtn.click();
                }} else if (s >= 6) {{
                    el.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }}));
                }}
            }}
            return {{ ok: sentConfirmed }};
        }})()
        """
        inj_res = _cdp_eval_js(self.ws_url, inject_js, await_promise=True, timeout=35.0)
        if not isinstance(inj_res, dict) or not inj_res.get("ok"):
            return {"success": False, "error": f"Không thể gửi lệnh tạo ảnh: {inj_res}"}

        start_t = time.time()
        idle_after_stream_ticks = 0

        poll_img_js = f"""
        (() => {{
            const stamp = {json.dumps(img_stamp)};
            const turnStates = Array.from(document.querySelectorAll('[data-talvt-turn-state]')).map(e => e.getAttribute('data-talvt-turn-state'));
            const hasIncompleteTurn = turnStates.some(s => s && s !== 'complete');
            const stopBtn = document.querySelector('[data-testid="stop-button"], button[aria-label*="Stop" i], button[aria-label*="Dừng" i], .result-streaming');
            const bodyTxt = (document.body ? document.body.innerText : '').slice(-1500).toLowerCase();
            const isCreatingImgText = bodyTxt.includes('creating image') || bodyTxt.includes('đang tạo hình ảnh') || bodyTxt.includes('generating image');
            const isStreaming = Boolean(stopBtn || hasIncompleteTurn);

            const allImgs = Array.from(document.querySelectorAll('main img, article img, [data-message-author-role="assistant"] img'));
            const newImgs = allImgs.filter(im => {{
                if (im.getAttribute('data-studio-img-seen') === stamp) return false;
                const alt = (im.getAttribute('alt') || '').toLowerCase();
                if (alt.includes('user') || alt.includes('profile') || alt.includes('avatar')) return false;
                const nw = im.naturalWidth || 0;
                const nh = im.naturalHeight || 0;
                const src = im.currentSrc || im.src || '';
                return im.complete && nw >= 350 && nh >= 200 && src.length > 10;
            }});

            if (newImgs.length > 0) {{
                try {{ newImgs[newImgs.length - 1].scrollIntoView({{ block: 'center' }}); }} catch (e) {{}}
            }}

            let latestText = '';
            const turns = Array.from(document.querySelectorAll('[data-markdown-text-style="assistant-message"], [data-message-author-role="assistant"], article[data-turn="assistant"], div[data-turn="assistant"]'));
            const newTurns = turns.filter(n => n.getAttribute('data-studio-turn-seen') !== stamp);
            if (newTurns.length > 0) {{
                latestText = newTurns.map(n => (n.innerText || '').trim()).join('\\n').trim();
            }}

            return {{
                isStreaming: isStreaming,
                isCreatingImgText: isCreatingImgText,
                newImgCount: newImgs.length,
                latestText: latestText
            }};
        }})()
        """

        harvest_img_js = f"""
        (async () => {{
            const stamp = {json.dumps(img_stamp)};
            const blobToDataUrl = (blob) => new Promise((resolve) => {{
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result || '');
                reader.onerror = () => resolve('');
                reader.readAsDataURL(blob);
            }});

            // Tầng 1: Thu hoạch trực tiếp từ thẻ <img> đã tải xong trên giao diện
            const allImgs = Array.from(document.querySelectorAll('main img, article img, [data-message-author-role="assistant"] img'));
            const newImgs = allImgs.filter(im => {{
                if (im.getAttribute('data-studio-img-seen') === stamp) return false;
                const alt = (im.getAttribute('alt') || '').toLowerCase();
                if (alt.includes('user') || alt.includes('profile') || alt.includes('avatar')) return false;
                const nw = im.naturalWidth || 0;
                const nh = im.naturalHeight || 0;
                return im.complete && nw >= 350 && nh >= 200;
            }});

            if (newImgs.length > 0) {{
                const targetImg = newImgs[newImgs.length - 1];
                const src = targetImg.currentSrc || targetImg.src || '';
                const nw = targetImg.naturalWidth || 1024;
                const nh = targetImg.naturalHeight || 1024;
                try {{
                    const r = await fetch(src, {{ credentials: 'include' }});
                    if (r.ok) {{
                        const b = await r.blob();
                        if (b && b.size > 15000) {{
                            const dUrl = await blobToDataUrl(b);
                            if (dUrl && dUrl.includes('base64,')) {{
                                return {{ ok: true, b64: dUrl.split('base64,')[1], width: nw, height: nh, source: 'dom_fetch' }};
                            }}
                        }}
                    }}
                }} catch (e) {{}}
                try {{
                    const canvas = document.createElement('canvas');
                    canvas.width = nw;
                    canvas.height = nh;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(targetImg, 0, 0);
                    const dUrl = canvas.toDataURL('image/png');
                    if (dUrl && dUrl.includes('base64,')) {{
                        return {{ ok: true, b64: dUrl.split('base64,')[1], width: nw, height: nh, source: 'dom_canvas' }};
                    }}
                }} catch (e) {{}}
            }}

            // Tầng 2: Thu hoạch từ Backend API (/backend-api/conversation/ -> asset_pointer -> /backend-api/files/download/)
            try {{
                const mUrl = window.location.pathname.match(/\\/c\\/([0-9a-fA-F\\-]{{16,}})/);
                if (mUrl && mUrl[1]) {{
                    const convId = mUrl[1];
                    if (!window.__studioAccessToken) {{
                        const sr = await fetch('/api/auth/session', {{ credentials: 'include' }});
                        if (sr.ok) {{
                            const sd = await sr.json();
                            if (sd && sd.accessToken) window.__studioAccessToken = sd.accessToken;
                        }}
                    }}
                    if (window.__studioAccessToken) {{
                        const cr = await fetch('/backend-api/conversation/' + convId, {{
                            credentials: 'include',
                            headers: {{ 'Authorization': 'Bearer ' + window.__studioAccessToken, 'Accept': 'application/json' }}
                        }});
                        if (cr.ok) {{
                            const conv = await cr.json();
                            const mapping = conv.mapping || {{}};
                            let cur = conv.current_node;
                            const seen = new Set();
                            let foundPointer = '';
                            let w = 1536, h = 1024;
                            while (cur && !seen.has(cur) && mapping[cur]) {{
                                seen.add(cur);
                                const msg = mapping[cur].message;
                                if (msg && msg.content && Array.isArray(msg.content.parts)) {{
                                    for (const pt of msg.content.parts) {{
                                        if (pt && typeof pt === 'object' && pt.asset_pointer) {{
                                            foundPointer = pt.asset_pointer;
                                            w = pt.width || w;
                                            h = pt.height || h;
                                            break;
                                        }}
                                    }}
                                }}
                                if (foundPointer) break;
                                cur = mapping[cur].parent;
                            }}
                            if (foundPointer) {{
                                const fileId = foundPointer.replace('sediment://', '').replace('file-service://', '').trim();
                                const dlResp = await fetch('/backend-api/files/download/' + fileId + '?inline=false', {{
                                    credentials: 'include',
                                    headers: {{ 'Authorization': 'Bearer ' + window.__studioAccessToken }}
                                }});
                                if (dlResp.ok) {{
                                    const dlJson = await dlResp.json();
                                    const dlUrl = dlJson.download_url || '';
                                    if (dlUrl) {{
                                        const imgResp = await fetch(dlUrl);
                                        if (imgResp.ok) {{
                                            const b = await imgResp.blob();
                                            const dUrl = await blobToDataUrl(b);
                                            if (dUrl && dUrl.includes('base64,')) {{
                                                return {{ ok: true, b64: dUrl.split('base64,')[1], width: w, height: h, source: 'backend_api' }};
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }} catch (e) {{}}

            return {{ ok: false }};
        }})()
        """

        while time.time() - start_t < timeout_sec:
            if should_stop_cb and should_stop_cb():
                raise RuntimeError("Đã dừng tiến trình theo yêu cầu người dùng.")

            time.sleep(2.5)
            elapsed = int(time.time() - start_t)
            st = _cdp_eval_js(self.ws_url, poll_img_js, await_promise=False, timeout=6.0)
            if not isinstance(st, dict):
                continue

            is_streaming = bool(st.get("isStreaming"))
            new_img_count = int(st.get("newImgCount") or 0)
            latest_text = str(st.get("latestText") or "").strip()

            if progress_cb:
                progress_cb(step_label, elapsed)

            if new_img_count > 0 and not is_streaming:
                # Chờ thêm 1.5s để ảnh render hoàn chỉnh độ phân giải cao nhất
                time.sleep(1.5)
                harv = _cdp_eval_js(self.ws_url, harvest_img_js, await_promise=True, timeout=25.0)
                if isinstance(harv, dict) and harv.get("ok") and harv.get("b64"):
                    return {
                        "success": True,
                        "b64_data": harv["b64"],
                        "width": int(harv.get("width") or 1024),
                        "height": int(harv.get("height") or 1024),
                        "source": harv.get("source", "dom"),
                        "assistant_text": latest_text,
                    }

            if not is_streaming and elapsed > 18:
                idle_after_stream_ticks += 1
                if idle_after_stream_ticks >= 4:
                    harv = _cdp_eval_js(self.ws_url, harvest_img_js, await_promise=True, timeout=25.0)
                    if isinstance(harv, dict) and harv.get("ok") and harv.get("b64"):
                        return {
                            "success": True,
                            "b64_data": harv["b64"],
                            "width": int(harv.get("width") or 1024),
                            "height": int(harv.get("height") or 1024),
                            "source": harv.get("source", "api"),
                            "assistant_text": latest_text,
                        }
                    if idle_after_stream_ticks >= 8 and latest_text:
                        return {
                            "success": False,
                            "error": f"ChatGPT trả lời văn bản nhưng chưa xuất ảnh: {latest_text[:150]}",
                            "assistant_text": latest_text,
                        }
            else:
                idle_after_stream_ticks = 0

        return {"success": False, "error": f"Quá thời gian chờ tạo ảnh ({timeout_sec}s) tại bước {step_label}."}
