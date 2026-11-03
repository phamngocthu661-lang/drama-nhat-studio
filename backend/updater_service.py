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


def get_local_version_info(root_dir: Path) -> Dict[str, Any]:
    """Đọc thông tin phiên bản hiện tại của ứng dụng từ file version.json."""
    root_dir = Path(root_dir).resolve()
    if root_dir.name.lower() == "app":
        root_dir = root_dir.parent

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
    Ưu tiên GitHub REST API (không bị trễ cache CDN) và dự phòng sang raw.githubusercontent.com.
    """
    headers_api = {
        "Accept": "application/vnd.github.v3.raw",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "User-Agent": "DramaNhatStudio-Updater/1.0",
    }
    api_url = f"https://api.github.com/repos/{repo}/contents/version.json?ref={branch}&_t={int(time.time())}"
    try:
        resp = requests.get(api_url, headers=headers_api, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("version"):
                return data
    except Exception:
        pass

    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/version.json?t={int(time.time())}"
    try:
        resp2 = requests.get(
            raw_url,
            headers={"Cache-Control": "no-cache", "User-Agent": "DramaNhatStudio-Updater/1.0"},
            timeout=timeout,
        )
        if resp2.status_code == 200:
            data2 = resp2.json()
            if isinstance(data2, dict) and data2.get("version"):
                return data2
    except Exception:
        pass

    return None


def check_for_github_update(root_dir: Path, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Kiểm tra xem trên GitHub đã có phiên bản mới hơn phiên bản đang chạy ở máy khách hay chưa.
    """
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
                    if callable(attr_val) and not attr_name.startswith("__"):
                        setattr(pipeline.__class__, attr_name, attr_val)
    except Exception as e:
        log_warn("UPDATER", f"Lưu ý khi cập nhật nóng ProductionPipeline: {e}")

    try:
        if "backend.stock_manager" in reloaded_mods and pipeline is not None and getattr(pipeline, "stock_manager", None) is not None:
            new_s_cls = getattr(reloaded_mods["backend.stock_manager"], "StockManager", None)
            if new_s_cls is not None:
                for attr_name, attr_val in vars(new_s_cls).items():
                    if callable(attr_val) and not attr_name.startswith("__"):
                        setattr(pipeline.stock_manager.__class__, attr_name, attr_val)
    except Exception as e:
        log_warn("UPDATER", f"Lưu ý khi cập nhật nóng StockManager: {e}")


def apply_github_update(
    root_dir: Path,
    adas_engine: Any = None,
    pipeline: Any = None,
) -> Dict[str, Any]:
    """
    Tải gói cập nhật mới nhất từ GitHub và tự động nâng cấp toàn bộ mã nguồn (backend, frontend, adas_skills, version.json...)
    mà giữ nguyên 100% dữ liệu dự án, kho Stock, bản quyền và cấu hình của máy khách.
    """
    with _update_lock:
        root_dir = Path(root_dir).resolve()
        if root_dir.name.lower() == "app":
            root_dir = root_dir.parent

        local_info = get_local_version_info(root_dir)
        old_version = local_info.get("version", DEFAULT_VERSION)
        repo = local_info.get("repo") or DEFAULT_GITHUB_REPO
        branch = local_info.get("branch") or DEFAULT_GITHUB_BRANCH

        log_info("UPDATER", f"🚀 Bắt đầu tải bản cập nhật mới nhất từ GitHub ({repo}@{branch})...")

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
            try:
                resp = requests.get(
                    d_url,
                    headers={"User-Agent": "DramaNhatStudio-Updater/1.0", "Cache-Control": "no-cache"},
                    stream=True,
                    timeout=45,
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

        # 1. Cập nhật các thư mục code: backend, frontend, adas_skills
        for folder_name in ("backend", "frontend", "adas_skills"):
            s_folder = src_root / folder_name
            if not s_folder.exists():
                continue
            for src_file in s_folder.rglob("*"):
                if src_file.is_file() and "__pycache__" not in src_file.parts and not src_file.name.endswith(".pyc"):
                    rel_path = src_file.relative_to(s_folder)
                    # Copy vào root/<folder_name>
                    dst_main = root_dir / folder_name / rel_path
                    dst_main.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, dst_main)
                    updated_files_count += 1
                    # Đồng bộ vào root/app/<folder_name> nếu có thư mục app/
                    if app_subdir.exists():
                        dst_app = app_subdir / folder_name / rel_path
                        dst_app.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, dst_app)

        # 2. Cập nhật các file lẻ ở thư mục gốc (trừ các file cấu hình/dữ liệu khách hàng trong PROTECTED_CUSTOMER_PATHS)
        for item in src_root.iterdir():
            if item.is_file() and item.name not in PROTECTED_CUSTOMER_PATHS and not item.name.startswith(".git"):
                try:
                    shutil.copy2(item, root_dir / item.name)
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
                        shutil.copy2(item, app_subdir / item.name)
                except Exception:
                    pass

        shutil.rmtree(tmp_dir, ignore_errors=True)

        # Làm mới cache kiểm tra phiên bản
        _update_check_cache["ts"] = 0.0
        _update_check_cache["data"] = None

        new_info = get_local_version_info(root_dir)
        new_version = new_info.get("version", DEFAULT_VERSION)
        changelog = new_info.get("changelog", "")

        # Hot-reload các module backend đang chạy
        _hot_reload_backend_modules(adas_engine=adas_engine, pipeline=pipeline)

        log_info(
            "UPDATER",
            f"🎉 Đã cập nhật ứng dụng thành công từ [{old_version}] lên [{new_version}] ({updated_files_count} file được nâng cấp)!",
        )
        return {
            "success": True,
            "old_version": old_version,
            "new_version": new_version,
            "build_number": new_info.get("build_number", DEFAULT_BUILD_NUMBER),
            "changelog": changelog,
            "updated_files_count": updated_files_count,
            "message": f"🎉 Đã cập nhật thành công lên phiên bản {new_version}!",
        }
