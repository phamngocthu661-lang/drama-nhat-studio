import os
import re
import sys
import json
import time
import shutil
import zipfile
import importlib
import threading
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import requests

from backend.logger_service import log_info, log_warn, log_error

DEFAULT_GITHUB_REPO = "phamngocthu661-lang/drama-nhat-studio"
DEFAULT_GITHUB_BRANCH = "main"
DEFAULT_VERSION = "V1.0.0"
DEFAULT_BUILD_NUMBER = 100

_update_check_cache: Dict[str, Any] = {
    "ts": 0.0,
    "data": None,
}
_update_lock = threading.Lock()

# Các thư mục & file dữ liệu riêng của máy khách TUYỆT ĐỐI KHÔNG BAO GIỜ GHI ĐÈ khi cập nhật
PROTECTED_CUSTOMER_PATHS = {
    "projects",
    "STOOK",
    "VOICEVOX_ENGINE",
    "VoiceStudio",
    "pretrained_models",
    "bin",
    "assets",
    "logs",
    "ADMIN_KEYGEN",
    "BROWSER_PROFILE",
    "BROWSER_PROFILE_2",
    "BROWSER_PROFILE_3",
    "GEMINI_PROFILE_1",
    "saved_ideas.json",
    "deleted_ideas.json",
    "license.json",
    "settings.json",
    "voice_engine_config.json",
    "used_stocks_history.json",
    "used_stock_links.json",
    "youtube_cookies.txt",
    "python_path.txt",
    ".git",
}


def parse_version_tuple(ver_str: str) -> Tuple[int, int, int]:
    """Chuyển chuỗi phiên bản (VD: 'V1.0.0', 'v1.2.3') thành bộ số (1, 0, 0) để so sánh chính xác."""
    nums = [int(x) for x in re.findall(r"\d+", str(ver_str or ""))]
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])


def _resolve_root_dir(root_dir: Optional[Path] = None) -> Path:
    r = Path(root_dir).resolve() if root_dir else Path(__file__).resolve().parent.parent
    if r.name.lower() == "app":
        r = r.parent
    elif not (r / "STOOK").exists() and (r.parent / "STOOK").exists():
        r = r.parent
    return r


def get_local_version_info(root_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Đọc thông tin phiên bản hiện tại của ứng dụng từ file version.json."""
    root_dir = _resolve_root_dir(root_dir)

    candidates = [
        root_dir / "version.json",
        root_dir / "app" / "version.json",
    ]
    for vf in candidates:
        if vf.exists():
            try:
                data = json.loads(vf.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("version"):
                    return {
                        "version": str(data.get("version", DEFAULT_VERSION)).strip(),
                        "build_number": int(data.get("build_number", DEFAULT_BUILD_NUMBER)),
                        "released_at": str(data.get("released_at", "")).strip(),
                        "repo": str(data.get("repo", DEFAULT_GITHUB_REPO)).strip(),
                        "branch": str(data.get("branch", DEFAULT_GITHUB_BRANCH)).strip(),
                        "changelog": str(data.get("changelog", "")).strip(),
                    }
            except Exception:
                pass

    return {
        "version": DEFAULT_VERSION,
        "build_number": DEFAULT_BUILD_NUMBER,
        "released_at": "2026-11-03 16:30:00",
        "repo": DEFAULT_GITHUB_REPO,
        "branch": DEFAULT_GITHUB_BRANCH,
        "changelog": "Phiên bản chính thức V1.0.0.",
    }


def _fetch_remote_version_json(repo: str, branch: str = "main", timeout: float = 8.0) -> Optional[Dict[str, Any]]:
    """
    Lấy file version.json mới nhất trực tiếp từ GitHub.
    Ưu tiên GitHub REST API (không bị trễ cache CDN) và dự phòng sang raw.githubusercontent.com + bỏ qua lỗi SSL nếu máy khách thiếu chứng chỉ.
    """
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

    headers_api = {
        "Accept": "application/vnd.github.v3.raw",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "User-Agent": "DramaNhatStudio-Updater/1.0",
    }
    api_url = f"https://api.github.com/repos/{repo}/contents/version.json?ref={branch}&_t={int(time.time())}"
    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/version.json?t={int(time.time())}"

    for url, hdrs in [(api_url, headers_api), (raw_url, {"Cache-Control": "no-cache", "User-Agent": "DramaNhatStudio-Updater/1.0"})]:
        for verify_ssl in (True, False):
            try:
                resp = requests.get(url, headers=hdrs, timeout=timeout, verify=verify_ssl)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and data.get("version"):
                        return data
            except Exception:
                continue

    return None


def check_for_github_update(root_dir: Optional[Path] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Kiểm tra xem trên GitHub đã có phiên bản mới hơn phiên bản đang chạy ở máy khách hay chưa.
    """
    root_dir = _resolve_root_dir(root_dir)
    local_info = get_local_version_info(root_dir)
    now = time.time()

    if (
        not force_refresh
        and _update_check_cache["data"] is not None
        and (now - _update_check_cache["ts"]) < 15.0
    ):
        cached = dict(_update_check_cache["data"])
        cached["current_version"] = local_info["version"]
        cached["current_build"] = local_info["build_number"]
        local_tuple = parse_version_tuple(local_info["version"])
        remote_tuple = parse_version_tuple(cached.get("latest_version", local_info["version"]))
        cached["update_available"] = (
            int(cached.get("latest_build", 0)) > int(local_info["build_number"])
            or remote_tuple > local_tuple
        )
        return cached

    repo = local_info.get("repo") or DEFAULT_GITHUB_REPO
    branch = local_info.get("branch") or DEFAULT_GITHUB_BRANCH

    remote_info = _fetch_remote_version_json(repo=repo, branch=branch)
    if not remote_info:
        return {
            "success": False,
            "current_version": local_info["version"],
            "current_build": local_info["build_number"],
            "latest_version": local_info["version"],
            "latest_build": local_info["build_number"],
            "update_available": False,
            "released_at": local_info.get("released_at", ""),
            "changelog": local_info.get("changelog", ""),
            "repo": repo,
            "error": "Không thể kết nối tới máy chủ cập nhật GitHub (Kiểm tra mạng Internet).",
        }

    latest_ver = str(remote_info.get("version", local_info["version"])).strip()
    latest_build = int(remote_info.get("build_number", local_info["build_number"]))
    local_ver = local_info["version"]
    local_build = int(local_info["build_number"])

    is_newer = (
        latest_build > local_build
        or parse_version_tuple(latest_ver) > parse_version_tuple(local_ver)
    )

    result = {
        "success": True,
        "current_version": local_ver,
        "current_build": local_build,
        "latest_version": latest_ver,
        "latest_build": latest_build,
        "update_available": is_newer,
        "released_at": str(remote_info.get("released_at", "")).strip(),
        "changelog": str(remote_info.get("changelog", "")).strip(),
        "repo": repo,
        "branch": branch,
    }
    _update_check_cache["ts"] = now
    _update_check_cache["data"] = dict(result)
    return result


def _hot_reload_backend_modules(adas_engine: Any = None, pipeline: Any = None):
    """
    Nạp nóng (Hot-Reload) các module và phương thức mới vừa tải về ngay trong bộ nhớ
    để máy khách áp dụng code mới ngay lập tức mà không làm gián đoạn cửa sổ đang mở.
    """
    module_names = [
        "backend.voice_service",
        "backend.sync_checker",
        "backend.renderer",
        "backend.stock_manager",
        "backend.voicevox_service",
        "backend.pipeline",
        "backend.adas_script_engine",
    ]
    reloaded_mods = {}
    for m_name in module_names:
        if m_name in sys.modules:
            try:
                reloaded_mods[m_name] = importlib.reload(sys.modules[m_name])
            except Exception as e:
                log_warn("UPDATER", f"Lưu ý khi hot-reload module {m_name}: {e}")

    # Cập nhật các phương thức (methods) mới lên các instance singleton đang chạy
    try:
        if "backend.adas_script_engine" in reloaded_mods and adas_engine is not None:
            new_cls = getattr(reloaded_mods["backend.adas_script_engine"], "ADASScriptEngine", None)
            if new_cls is not None:
                for attr_name, attr_val in vars(new_cls).items():
                    if callable(attr_val) and not attr_name.startswith("__"):
                        setattr(adas_engine.__class__, attr_name, attr_val)
    except Exception as e:
        log_warn("UPDATER", f"Lưu ý khi cập nhật nóng ADASScriptEngine: {e}")

    try:
        if "backend.pipeline" in reloaded_mods and pipeline is not None:
            new_p_cls = getattr(reloaded_mods["backend.pipeline"], "ProductionPipeline", None)
            if new_p_cls is not None:
                for attr_name, attr_val in vars(new_p_cls).items():
                    if not attr_name.startswith("__"):
                        setattr(pipeline.__class__, attr_name, attr_val)
            new_rb_cls = getattr(reloaded_mods["backend.pipeline"], "HardwareResourceBalancer", None)
            rb_inst = getattr(pipeline, "resource_balancer", None)
            if new_rb_cls is not None and rb_inst is not None:
                for attr_name, attr_val in vars(new_rb_cls).items():
                    if not attr_name.startswith("__"):
                        setattr(rb_inst.__class__, attr_name, attr_val)
            if hasattr(pipeline, "_ensure_hot_reload_compat"):
                pipeline._ensure_hot_reload_compat()
    except Exception as e:
        log_warn("UPDATER", f"Lưu ý khi cập nhật nóng ProductionPipeline: {e}")

    try:
        if "backend.voicevox_service" in reloaded_mods and pipeline is not None and getattr(pipeline, "voicevox_service", None) is not None:
            new_vv_cls = getattr(reloaded_mods["backend.voicevox_service"], "VoicevoxStandaloneService", None)
            if new_vv_cls is not None:
                for attr_name, attr_val in vars(new_vv_cls).items():
                    if not attr_name.startswith("__"):
                        setattr(pipeline.voicevox_service.__class__, attr_name, attr_val)
    except Exception as e:
        log_warn("UPDATER", f"Lưu ý khi cập nhật nóng VoicevoxStandaloneService: {e}")

    try:
        if "backend.stock_manager" in reloaded_mods and pipeline is not None and getattr(pipeline, "stock_manager", None) is not None:
            new_s_cls = getattr(reloaded_mods["backend.stock_manager"], "StockManager", None)
            if new_s_cls is not None:
                for attr_name, attr_val in vars(new_s_cls).items():
                    if callable(attr_val) and not attr_name.startswith("__"):
                        setattr(pipeline.stock_manager.__class__, attr_name, attr_val)
    except Exception as e:
        log_warn("UPDATER", f"Lưu ý khi cập nhật nóng StockManager: {e}")


def _safe_copy_file(src_file: Path, dst_file: Path) -> bool:
    """
    Sao chép file an toàn trên Windows:
    - Tự động gỡ cờ Read-Only nếu có.
    - Nếu file đích đang bị khóa bởi tiến trình đang chạy (VD: Drama_Nhat_Studio.exe),
      tự động đổi tên file đang chạy sang `.old_locked` rồi chép file mới vào để không bao giờ văng PermissionError!
    """
    try:
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        if dst_file.exists():
            try:
                os.chmod(dst_file, 0o666)
            except Exception:
                pass
        shutil.copy2(src_file, dst_file)
        return True
    except PermissionError:
        try:
            old_locked = dst_file.with_suffix(dst_file.suffix + ".old_locked")
            if old_locked.exists():
                try:
                    old_locked.unlink()
                except Exception:
                    pass
            dst_file.rename(old_locked)
            shutil.copy2(src_file, dst_file)
            return True
        except Exception as e2:
            log_warn("UPDATER", f"Bỏ qua file đang khóa {dst_file.name}: {e2}")
            return False
    except Exception as e:
        log_warn("UPDATER", f"Lưu ý khi chép file {dst_file.name}: {e}")
        return False


def _stop_all_tasks_and_subprocesses(adas_engine: Any = None, pipeline: Any = None):
    """
    Đóng sạch 100% mọi tác vụ đang chạy (Render FFmpeg, Tạo Voice VOICEVOX, Dây chuyền ADAS AI, tải Stock yt-dlp)
    trước khi áp dụng bản cập nhật và Reset ứng dụng để không còn bất kỳ tiến trình cũ nào bị treo hoặc giữ khóa file.
    """
    import subprocess
    log_info("UPDATER", "🛑 Đang đóng toàn bộ tác vụ đang chạy (Render FFmpeg, Voice Engine, ADAS AI) để cập nhật chuẩn xác...")

    try:
        if pipeline is not None and hasattr(pipeline, "stop"):
            pipeline.stop()
    except Exception as e:
        log_warn("UPDATER", f"Lưu ý khi dừng Pipeline: {e}")

    try:
        if adas_engine is not None:
            setattr(adas_engine, "live_auto_produce_video", False)
            if hasattr(adas_engine, "stop"):
                adas_engine.stop()
    except Exception as e:
        log_warn("UPDATER", f"Lưu ý khi dừng ADAS Engine: {e}")

    try:
        from backend.voicevox_service import VoicevoxStandaloneService
        VoicevoxStandaloneService.shutdown_all_workers()
    except Exception:
        pass

    if os.name == "nt":
        for img in ("ffmpeg.exe", "ffprobe.exe", "run.exe", "yt-dlp.exe"):
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", img, "/T"],
                    capture_output=True,
                    timeout=3,
                    creationflags=0x08000000,
                )
            except Exception:
                pass


def _schedule_full_application_reset(root_dir: Path):
    """
    Khởi chạy tiến trình phụ độc lập (_ota_restart_helper.py) tách biệt hoàn toàn khỏi cây tiến trình cũ:
    1. Chờ 1.2s cho Server trả xong phản hồi HTTP về giao diện.
    2. Tắt tiến trình Server cũ (PID cũ & cổng 8899) và Drama_Nhat_Studio.exe KHÔNG dùng cờ /T (để không bao giờ tự tắt chính _ota_restart_helper.py).
    3. Đóng sạch toàn bộ tác vụ con (run.exe, ffmpeg.exe, ffprobe.exe, yt-dlp.exe) và cửa sổ Desktop UI cũ.
    4. Khởi động lại main.py và tự động kiểm tra đảm bảo cả Server cổng 8899 lẫn cửa sổ giao diện Desktop App đều mở lên 100%.
    """
    import subprocess
    try:
        logs_dir = root_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        helper_path = logs_dir / "_ota_restart_helper.py"
        lock_path = logs_dir / "_ota_restart.lock"
        try:
            if lock_path.exists():
                lock_path.unlink()
        except Exception:
            pass

        helper_code = '''import os
import sys
import time
import socket
import subprocess
import urllib.request

old_pid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
root_dir = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
my_pid = os.getpid()

logs_dir = os.path.join(root_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(logs_dir, "ota_restart.log")
lock_file = os.path.join(logs_dir, "_ota_restart.lock")

def wlog(msg):
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [PID={my_pid}] {msg}\\n")
    except Exception:
        pass

# Đảm bảo chỉ 1 tiến trình helper duy nhất chạy nếu được kích hoạt song song qua cả WMI và Popen
try:
    if os.path.exists(lock_file):
        age = time.time() - os.path.getmtime(lock_file)
        if age < 15.0:
            sys.exit(0)
    with open(lock_file, "w", encoding="utf-8") as lf:
        lf.write(str(my_pid))
except Exception:
    pass

wlog(f"Bắt đầu quy trình Full Reset ứng dụng (old_pid={old_pid}, root_dir={root_dir})")
time.sleep(1.2)

# 1. Đóng sạch toàn bộ tiến trình tác vụ con (Voice Engine run.exe, FFmpeg, ffprobe, yt-dlp)
for img in ("run.exe", "ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe"):
    try:
        subprocess.run(["taskkill", "/F", "/IM", img, "/T"], capture_output=True, timeout=3, creationflags=0x08000000)
    except Exception:
        pass

# 2. Tắt Launcher Drama_Nhat_Studio.exe và tiến trình Server cũ (KHÔNG dùng /T để không bao giờ tự giết tiến trình helper!)
try:
    subprocess.run(["taskkill", "/F", "/IM", "Drama_Nhat_Studio.exe"], capture_output=True, timeout=3, creationflags=0x08000000)
except Exception:
    pass

if old_pid > 0 and old_pid != my_pid:
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True, timeout=4, creationflags=0x08000000)
    except Exception:
        pass

try:
    ps_kill_port = (
        f"Get-NetTCPConnection -LocalPort 8899 -State Listen -ErrorAction SilentlyContinue | "
        f"Where-Object {{ $_.OwningProcess -ne {my_pid} }} | "
        f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_kill_port], capture_output=True, timeout=4, creationflags=0x08000000)
except Exception:
    pass

# 3. Đóng cửa sổ Desktop UI cũ và chờ giải phóng khóa Profile Chrome
try:
    ps_close_ui = (
        "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { "
        "$_.Name -in @('chrome.exe','msedge.exe') -and "
        "($_.CommandLine -like '*DesktopUI_Profile_V*' -or $_.CommandLine -like '*--app=http://127.0.0.1:8899*') "
        "} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_close_ui], capture_output=True, timeout=4, creationflags=0x08000000)
except Exception:
    pass

# 4. Đợi cổng 8899 được giải phóng hoàn toàn
for _ in range(25):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", 8899)) != 0:
            break
    time.sleep(0.25)

time.sleep(0.8)

# 5. Khởi động lại ứng dụng hoàn toàn mới từ main.py
env = os.environ.copy()
env["DRAMA_PYTHON_SWITCHED"] = "1"
main_py = os.path.join(root_dir, "main.py")
wlog(f"Đang khởi chạy lại main.py bằng {sys.executable}...")

def spawn_main():
    try:
        return subprocess.Popen(
            [sys.executable, main_py],
            cwd=root_dir,
            env=env,
            creationflags=0x08000000 | 0x00000200,
        )
    except Exception as e:
        wlog(f"Lỗi khi gọi Popen main.py: {e}")
        return None

spawn_main()

# 6. Kiểm tra đảm bảo Server cổng 8899 đã sống dậy và cửa sổ giao diện Desktop đã mở trên màn hình
server_up = False
for i in range(50):
    time.sleep(0.5)
    if i == 18 and not server_up:
        wlog("Sau 9s cổng 8899 chưa lên, đang kích hoạt lại main.py lần 2...")
        spawn_main()
    try:
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
        with opener.open("http://127.0.0.1:8899/api/status", timeout=1.2) as resp:
            if resp.status == 200:
                server_up = True
                break
    except Exception:
        pass

wlog(f"Trạng thái Server 8899 sau khi khởi động lại: server_up={server_up}")

if server_up:
    time.sleep(2.5)
    try:
        ps_check_ui = (
            "$p = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { "
            "$_.Name -in @('chrome.exe','msedge.exe') -and "
            "($_.CommandLine -like '*DesktopUI_Profile_V*' -or $_.CommandLine -like '*--app=http://127.0.0.1:8899*') "
            "}; if ($p) { Write-Output 'UI_OPEN' }"
        )
        r_ui = subprocess.run(["powershell", "-NoProfile", "-Command", ps_check_ui], capture_output=True, text=True, timeout=4, creationflags=0x08000000)
        if "UI_OPEN" not in (r_ui.stdout or ""):
            wlog("Phát hiện cửa sổ UI chưa hiển thị -> Đang chủ động mở cửa sổ App Native...")
            local_app = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            ui_profile_dir = os.path.join(local_app, "Drama_Nhat_Studio", "DesktopUI_Profile_V6")
            os.makedirs(ui_profile_dir, exist_ok=True)
            url_open = f"http://127.0.0.1:8899/?v={int(time.time())}"
            browser_exe = ""
            for cand_b in (
                os.path.join(os.environ.get("ProgramFiles", r"C:\\Program Files"), "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(local_app, "Google", "Chrome", "Application", "chrome.exe"),
                os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)"), "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(os.environ.get("ProgramFiles", r"C:\\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe"),
            ):
                if os.path.isfile(cand_b):
                    browser_exe = cand_b
                    break
            if browser_exe:
                subprocess.Popen(
                    [
                        browser_exe,
                        f"--app={url_open}",
                        f"--user-data-dir={ui_profile_dir}",
                        "--window-size=1480,920",
                        "--window-position=60,30",
                        "--disk-cache-size=1",
                        "--media-cache-size=1",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-features=Translate,CalculateNativeWinOcclusion",
                        "--disable-gpu-sandbox",
                        "--proxy-bypass-list=<-loopback>",
                    ],
                    cwd=root_dir,
                )
            else:
                os.startfile(url_open)
    except Exception as ui_err:
        wlog(f"Lưu ý khi kiểm tra/mở lại cửa sổ UI: {ui_err}")

wlog("Hoàn tất 100% quy trình Reset & mở lại ứng dụng!")
'''
        helper_path.write_text(helper_code, encoding="utf-8")
        env = os.environ.copy()
        env["DRAMA_PYTHON_SWITCHED"] = "1"
        curr_pid = os.getpid()

        # Cách 1: Khởi chạy qua WMI Win32_Process.Create để tiến trình helper thuộc về WmiPrvSE.exe (tách khỏi 100% cây tiến trình và Job Object cũ)
        spawned_wmi = False
        if os.name == "nt":
            try:
                cmd_line = f'"{sys.executable}" "{helper_path}" {curr_pid} "{root_dir}"'
                ps_wmi = (
                    f"Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
                    f"-Arguments @{{ CommandLine = '{cmd_line.replace(chr(39), chr(39)+chr(39))}'; CurrentDirectory = '{str(root_dir).replace(chr(39), chr(39)+chr(39))}' }} | Out-Null"
                )
                r_wmi = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_wmi],
                    capture_output=True,
                    timeout=3,
                    creationflags=0x08000000,
                )
                if r_wmi.returncode == 0:
                    spawned_wmi = True
            except Exception:
                spawned_wmi = False

        # Cách 2: Dự phòng Popen tách Job/Group (có file lock _ota_restart.lock chống chạy trùng)
        for flags in (
            0x08000000 | 0x00000200 | 0x01000000,  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB
            0x08000000 | 0x00000200,               # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        ):
            try:
                subprocess.Popen(
                    [sys.executable, str(helper_path), str(curr_pid), str(root_dir)],
                    cwd=str(root_dir),
                    env=env,
                    creationflags=flags,
                    close_fds=True,
                )
                break
            except Exception:
                continue

        def _force_self_exit():
            time.sleep(1.5)
            os._exit(0)

        threading.Thread(target=_force_self_exit, daemon=True).start()
    except Exception as e:
        log_warn("UPDATER", f"Lưu ý khi lên lịch khởi động lại ứng dụng: {e}")


def apply_github_update(
    root_dir: Optional[Path] = None,
    adas_engine: Any = None,
    pipeline: Any = None,
    restart_app: bool = True,
) -> Dict[str, Any]:
    """
    Tải gói cập nhật mới nhất từ GitHub, đóng toàn bộ tác vụ đang chạy, nâng cấp toàn bộ mã nguồn
    (backend, frontend, adas_skills, version.json...) và Reset khởi động lại toàn bộ ứng dụng từ đầu.
    Giữ nguyên 100% dữ liệu dự án, Checkpoint đang render dở, kho Stock, bản quyền và cấu hình của máy khách.
    """
    with _update_lock:
        try:
            import subprocess
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass

            root_dir = _resolve_root_dir(root_dir)

            local_info = get_local_version_info(root_dir)
            old_version = local_info.get("version", DEFAULT_VERSION)
            repo = local_info.get("repo") or DEFAULT_GITHUB_REPO
            branch = local_info.get("branch") or DEFAULT_GITHUB_BRANCH

            log_info("UPDATER", f"🚀 Bắt đầu tải bản cập nhật mới nhất từ GitHub ({repo}@{branch})...")

            if restart_app:
                _stop_all_tasks_and_subprocesses(adas_engine=adas_engine, pipeline=pipeline)

            tmp_dir = root_dir / "_ota_update_tmp"
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
            tmp_dir.mkdir(parents=True, exist_ok=True)
            zip_path = tmp_dir / "update_package.zip"

            download_urls = [
                f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}?t={int(time.time())}",
                f"https://api.github.com/repos/{repo}/zipball/{branch}",
            ]

            downloaded = False
            last_err = ""
            for d_url in download_urls:
                for verify_ssl in (True, False):
                    try:
                        resp = requests.get(
                            d_url,
                            headers={"User-Agent": "DramaNhatStudio-Updater/1.0", "Cache-Control": "no-cache"},
                            stream=True,
                            timeout=60,
                            verify=verify_ssl,
                        )
                        if resp.status_code == 200:
                            with open(zip_path, "wb") as f:
                                for chunk in resp.iter_content(chunk_size=256 * 1024):
                                    if chunk:
                                        f.write(chunk)
                            if zip_path.exists() and zip_path.stat().st_size > 10_000:
                                downloaded = True
                                break
                        else:
                            last_err = f"HTTP {resp.status_code}"
                    except Exception as e:
                        last_err = str(e)
                if downloaded:
                    break

            # Dự phòng tải bằng curl.exe có sẵn trên Windows nếu Python requests bị chặn bởi Firewall/SSL máy khách
            if not downloaded:
                try:
                    subprocess.run(
                        ["curl.exe", "-L", "-k", "-s", "-o", str(zip_path), download_urls[0]],
                        timeout=60,
                        check=False,
                    )
                    if zip_path.exists() and zip_path.stat().st_size > 10_000:
                        downloaded = True
                except Exception as e_curl:
                    last_err = f"{last_err} | curl: {e_curl}"

            if not downloaded:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                msg = f"Không thể tải gói cập nhật từ GitHub ({last_err}). Vui lòng kiểm tra kết nối mạng!"
                log_error("UPDATER", msg)
                return {"success": False, "error": msg}

            extract_dir = tmp_dir / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(extract_dir)
            except Exception as e:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                msg = f"Gói cập nhật tải về bị lỗi giải nén: {e}"
                log_error("UPDATER", msg)
                return {"success": False, "error": msg}

            # Tìm thư mục gốc bên trong file zip của GitHub (thường là <repo>-<branch>/)
            sub_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
            src_root = sub_dirs[0] if len(sub_dirs) == 1 else extract_dir

            if not (src_root / "backend").exists() or not (src_root / "frontend").exists():
                shutil.rmtree(tmp_dir, ignore_errors=True)
                msg = "Gói cập nhật không hợp lệ (Thiếu thư mục backend/frontend)."
                log_error("UPDATER", msg)
                return {"success": False, "error": msg}

            updated_files_count = 0
            app_subdir = root_dir / "app"

            # 1. Cập nhật các thư mục code: backend, frontend, adas_skills (An toàn chống lỗi PermissionError)
            for folder_name in ("backend", "frontend", "adas_skills"):
                s_folder = src_root / folder_name
                if not s_folder.exists():
                    continue
                for src_file in s_folder.rglob("*"):
                    if src_file.is_file() and "__pycache__" not in src_file.parts and not src_file.name.endswith(".pyc"):
                        rel_path = src_file.relative_to(s_folder)
                        dst_main = root_dir / folder_name / rel_path
                        if _safe_copy_file(src_file, dst_main):
                            updated_files_count += 1
                        if app_subdir.exists():
                            dst_app = app_subdir / folder_name / rel_path
                            _safe_copy_file(src_file, dst_app)

            # 2. Cập nhật các file lẻ ở thư mục gốc (trừ các file cấu hình/dữ liệu khách hàng trong PROTECTED_CUSTOMER_PATHS,
            #    và bỏ qua Drama_Nhat_Studio.exe đang chạy để không chạm vào file thực thi đang mở)
            for item in src_root.iterdir():
                if (
                    item.is_file()
                    and item.name not in PROTECTED_CUSTOMER_PATHS
                    and not item.name.startswith(".git")
                    and item.name.lower() != "drama_nhat_studio.exe"
                ):
                    if _safe_copy_file(item, root_dir / item.name):
                        updated_files_count += 1
                    if app_subdir.exists() and item.name in (
                        "main.py",
                        "install_setup.py",
                        "requirements.txt",
                        "version.json",
                        "QUY_TRINH_HOAT_DONG.md",
                        "TIEN_DO_CODE.md",
                        "HUONG_DAN_CAI_DAT_KHACH_HANG.txt",
                    ):
                        _safe_copy_file(item, app_subdir / item.name)

            shutil.rmtree(tmp_dir, ignore_errors=True)

            # Làm mới cache kiểm tra phiên bản
            _update_check_cache["ts"] = 0.0
            _update_check_cache["data"] = None

            new_info = get_local_version_info(root_dir)
            new_version = new_info.get("version", DEFAULT_VERSION)
            changelog = new_info.get("changelog", "")

            # Hot-reload các module backend đang chạy (phòng hờ nếu gọi với restart_app=False)
            _hot_reload_backend_modules(adas_engine=adas_engine, pipeline=pipeline)

            if restart_app:
                log_info(
                    "UPDATER",
                    f"🎉 Đã cập nhật [{old_version}] -> [{new_version}] ({updated_files_count} file). Đang đóng toàn bộ tác vụ và RESET khởi động lại ứng dụng hoàn toàn...",
                )
                _schedule_full_application_reset(root_dir)
            else:
                log_info(
                    "UPDATER",
                    f"🎉 Đã cập nhật ứng dụng thành công từ [{old_version}] lên [{new_version}] ({updated_files_count} file được nâng cấp)!",
                )

            return {
                "success": True,
                "restarting": bool(restart_app),
                "old_version": old_version,
                "new_version": new_version,
                "build_number": new_info.get("build_number", DEFAULT_BUILD_NUMBER),
                "changelog": changelog,
                "updated_files_count": updated_files_count,
                "message": (
                    f"🎉 Đã cập nhật lên {new_version} (Build #{new_info.get('build_number', DEFAULT_BUILD_NUMBER)})! Đang đóng toàn bộ tác vụ và Reset ứng dụng..."
                    if restart_app
                    else f"🎉 Đã cập nhật thành công lên phiên bản {new_version}!"
                ),
            }
        except Exception as fatal_err:
            err_msg = f"Lỗi khi áp dụng bản cập nhật: {fatal_err}"
            log_error("UPDATER", err_msg, exc=fatal_err)
            return {"success": False, "error": err_msg}
