# -*- coding: utf-8 -*-
"""
HỆ THỐNG GHI LOG & CHẨN ĐOÁN LỖI TOÀN DIỆN (SYSTEM LOGGER & DIAGNOSTICS)
========================================================================
Ghi nhận toàn bộ hoạt động và lỗi của:
1. Khởi động Server (main.py / FastAPI / Uvicorn) -> logs/server_startup.log
2. Toàn bộ tiến trình chạy Đa luồng Kịch bản, Chrome CDP, Voice AI, Stock, FFmpeg Render -> logs/system_runtime.log
3. Riêng các lỗi / nguyên nhân bị dừng -> logs/error_diagnostic.log
4. Cung cấp bộ đệm Ring-Buffer trong RAM để hiển thị thời gian thực trên giao diện Web/Desktop.
"""

import os
import sys
import time
import json
import subprocess
import traceback
import threading
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

ROOT_DIR = Path(__file__).resolve().parent.parent
if ROOT_DIR.name.lower() == "app":
    ROOT_DIR = ROOT_DIR.parent
elif not (ROOT_DIR / "bin").exists() and (ROOT_DIR.parent / "bin").exists():
    ROOT_DIR = ROOT_DIR.parent

LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

RUNTIME_LOG_FILE = LOGS_DIR / "system_runtime.log"
ERROR_LOG_FILE = LOGS_DIR / "error_diagnostic.log"
STARTUP_LOG_FILE = LOGS_DIR / "server_startup.log"


class SystemLogger:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self.max_entries = 600
        self.file_lock = threading.Lock()
        self.subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._load_recent_logs_from_disk()

    def subscribe(self, cb: Callable[[Dict[str, Any]], None]):
        if cb not in self.subscribers:
            self.subscribers.append(cb)

    @classmethod
    def get_instance(cls) -> "SystemLogger":
        with cls._lock:
            if cls._instance is None:
                cls._instance = SystemLogger()
            return cls._instance

    def _load_recent_logs_from_disk(self):
        """Khôi phục 150 dòng log gần nhất từ ổ cứng khi khởi động lại app để không mất dấu lỗi cũ."""
        if not RUNTIME_LOG_FILE.exists():
            return
        try:
            lines = RUNTIME_LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-150:]
            for ln in lines:
                ln = ln.strip()
                if not ln:
                    continue
                level = "ERROR" if "[ERROR]" in ln or "❌" in ln else ("WARN" if "[WARN]" in ln or "⚠️" in ln else "INFO")
                cat = "SYSTEM"
                for c_candidate in ("SCRIPT", "VOICE", "RENDER", "CHROME", "SERVER", "STOCK"):
                    if f"[{c_candidate}]" in ln:
                        cat = c_candidate
                        break
                self.entries.append(
                    {
                        "ts": ln[1:20] if ln.startswith("[20") and len(ln) > 21 else time.strftime("%Y-%m-%d %H:%M:%S"),
                        "timestamp": ln[1:20] if ln.startswith("[20") and len(ln) > 21 else time.strftime("%Y-%m-%d %H:%M:%S"),
                        "level": level,
                        "category": cat,
                        "project_id": "",
                        "message": ln,
                        "detail": "",
                    }
                )
        except Exception:
            pass

    def _trim_log_file_if_huge(self, file_path: Path, max_bytes: int = 5 * 1024 * 1024):
        try:
            if file_path.exists() and file_path.stat().st_size > max_bytes:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                kept = "\n".join(content.splitlines()[-2500:]) + "\n"
                file_path.write_text(kept, encoding="utf-8")
        except Exception:
            pass

    def log(
        self,
        message: str,
        level: str = "INFO",
        category: str = "SYSTEM",
        project_id: str = "",
        exc: Optional[BaseException] = None,
        detail: str = "",
    ):
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        lvl = (level or "INFO").upper()
        cat = (category or "SYSTEM").upper()
        proj_tag = f"[{project_id}] " if project_id else ""

        tb_str = ""
        if exc is not None:
            tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).strip()
        if detail:
            tb_str = f"{detail}\n{tb_str}".strip() if tb_str else detail

        formatted_line = f"[{ts}] [{lvl}] [{cat}] {proj_tag}{message}"

        entry = {
            "ts": ts,
            "timestamp": ts,
            "level": lvl,
            "category": cat,
            "project_id": project_id or "",
            "message": f"{proj_tag}{message}",
            "detail": tb_str,
            "raw_line": formatted_line,
        }

        with self.file_lock:
            self.entries.append(entry)
            if len(self.entries) > self.max_entries:
                self.entries = self.entries[-self.max_entries :]

            try:
                self._trim_log_file_if_huge(RUNTIME_LOG_FILE)
                with open(RUNTIME_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(formatted_line + "\n")
                    if tb_str:
                        for tbl in tb_str.splitlines():
                            f.write(f"    | {tbl}\n")

                if lvl in ("ERROR", "CRITICAL", "WARN", "WARNING") or "❌" in message:
                    self._trim_log_file_if_huge(ERROR_LOG_FILE)
                    with open(ERROR_LOG_FILE, "a", encoding="utf-8") as ef:
                        ef.write(formatted_line + "\n")
                        if tb_str:
                            for tbl in tb_str.splitlines():
                                ef.write(f"    | {tbl}\n")
                            ef.write("-" * 72 + "\n")

                if cat == "SERVER" or cat == "STARTUP":
                    with open(STARTUP_LOG_FILE, "a", encoding="utf-8") as sf:
                        sf.write(formatted_line + "\n")
                        if tb_str:
                            sf.write(tb_str + "\n")
            except Exception:
                pass

        for cb in list(self.subscribers):
            try:
                cb({"type": "sys_log", "entry": entry})
            except Exception:
                pass

    def get_logs(
        self,
        limit: int = 200,
        level_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self.file_lock:
            items = list(self.entries)

        if level_filter and level_filter.upper() != "ALL":
            lf = level_filter.upper()
            if lf == "ERROR":
                items = [
                    x
                    for x in items
                    if x["level"] in ("ERROR", "CRITICAL", "WARN", "WARNING")
                    or "❌" in x["message"]
                    or "⚠️" in x["message"]
                ]
            else:
                items = [x for x in items if x["level"] == lf]

        if category_filter and category_filter.upper() != "ALL":
            cf = category_filter.upper()
            if cf == "VIDEO":
                items = [x for x in items if x["category"] in ("VIDEO", "VOICE", "RENDER", "STOCK")]
            else:
                items = [x for x in items if x["category"] == cf]

        return items[-max(1, min(limit, 600)) :]

    def get_recent_logs(
        self,
        limit: int = 200,
        level_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self.get_logs(limit=limit, level_filter=level_filter, category_filter=category_filter)

    def clear_logs(self):
        with self.file_lock:
            self.entries.clear()
            for fp in (RUNTIME_LOG_FILE, ERROR_LOG_FILE):
                try:
                    if fp.exists():
                        fp.write_text("", encoding="utf-8")
                except Exception:
                    pass
        self.log("Đã xóa trắng lịch sử nhật ký theo yêu cầu người dùng.", level="INFO", category="SYSTEM")

    def clear_memory_logs(self):
        self.clear_logs()

    def get_log_file_paths(self) -> Dict[str, str]:
        return {
            "logs_dir": str(LOGS_DIR),
            "runtime_log_file": str(RUNTIME_LOG_FILE),
            "error_log_file": str(ERROR_LOG_FILE),
            "startup_log_file": str(STARTUP_LOG_FILE),
        }


_KNOWN_CATEGORIES = {"SYSTEM", "SERVER", "STARTUP", "SCRIPT", "VIDEO", "VOICE", "RENDER", "STOCK", "CHROME"}


def _normalize_cat_and_msg(arg1: str, arg2: str = "SYSTEM") -> tuple[str, str]:
    """Hỗ trợ cả 2 kiểu gọi: log_info(msg, category) hoặc log_info(category, msg)."""
    a1 = (arg1 or "").strip()
    a2 = (arg2 or "SYSTEM").strip()
    if a1.upper() in _KNOWN_CATEGORIES and a2.upper() not in _KNOWN_CATEGORIES:
        return a2, a1.upper()
    return a1, (a2.upper() if a2.upper() in _KNOWN_CATEGORIES else "SYSTEM")


def get_logger(root_dir: Optional[Path] = None) -> SystemLogger:
    return SystemLogger.get_instance()


def log_info(
    arg1: str,
    arg2: str = "SYSTEM",
    category: Optional[str] = None,
    project_id: str = "",
    detail: str = "",
):
    msg, cat = _normalize_cat_and_msg(arg1, category or arg2)
    SystemLogger.get_instance().log(msg, level="INFO", category=cat, project_id=project_id, detail=detail)


def log_warn(
    arg1: str,
    arg2: str = "SYSTEM",
    category: Optional[str] = None,
    project_id: str = "",
    detail: str = "",
):
    msg, cat = _normalize_cat_and_msg(arg1, category or arg2)
    SystemLogger.get_instance().log(msg, level="WARN", category=cat, project_id=project_id, detail=detail)


def log_error(
    arg1: str,
    arg2: str = "SYSTEM",
    category: Optional[str] = None,
    project_id: str = "",
    exc: Optional[BaseException] = None,
    detail: str = "",
    include_trace: bool = False,
):
    msg, cat = _normalize_cat_and_msg(arg1, category or arg2)
    if include_trace and exc is None:
        tb_cur = traceback.format_exc()
        if tb_cur and "NoneType: None" not in tb_cur:
            detail = f"{detail}\n{tb_cur}".strip() if detail else tb_cur
    SystemLogger.get_instance().log(
        msg, level="ERROR", category=cat, project_id=project_id, exc=exc, detail=detail
    )


REQUIRED_PYTHON_LIBRARIES = [
    ("torch", "torch", "PyTorch (Nhân AI & GPU CUDA)"),
    ("torchaudio", "torchaudio", "TorchAudio (Xử lý âm thanh GPU)"),
    ("transformers", "transformers", "Transformers (Model ngôn ngữ & Voice)"),
    ("accelerate", "accelerate", "Accelerate (Tối ưu nạp Model GPU)"),
    ("safetensors", "safetensors", "SafeTensors (Đọc trọng số Model)"),
    ("huggingface_hub", "huggingface-hub", "HuggingFace Hub (Tải Model AI)"),
    ("soundfile", "soundfile", "SoundFile (Xuất file WAV chất lượng cao)"),
    ("scipy", "scipy", "SciPy (Xử lý tín hiệu âm thanh)"),
    ("numpy", "numpy", "NumPy (Tính toán ma trận)"),
    ("einops", "einops", "Einops (Biến đổi Tensor cho OmniVoice)"),
    ("yt_dlp", "yt-dlp", "yt-dlp (Tải Video Stock YouTube 720p)"),
    ("fastapi", "fastapi", "FastAPI (Máy chủ Backend)"),
    ("uvicorn", "uvicorn", "Uvicorn (ASGI Server)"),
    ("websockets", "websockets", "WebSockets (Đồng bộ Log & Chrome CDP)"),
    ("requests", "requests", "Requests (Giao tiếp HTTP)"),
    ("webview", "pywebview", "PyWebView (Giao diện cửa sổ Desktop)"),
]


def _detect_nvidia_hardware() -> Dict[str, Any]:
    """Kiểm tra phần cứng Card rời NVIDIA và Driver qua nvidia-smi."""
    info = {
        "has_nvidia_gpu": False,
        "gpu_name": "",
        "driver_version": "",
        "vram_total_mb": 0,
        "raw_error": "",
    }
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
             encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if res.returncode == 0 and res.stdout.strip():
            first_line = res.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in first_line.split(",")]
            info["has_nvidia_gpu"] = True
            if len(parts) >= 1:
                info["gpu_name"] = parts[0]
            if len(parts) >= 2:
                info["driver_version"] = parts[1]
            if len(parts) >= 3:
                try:
                    info["vram_total_mb"] = int(float(parts[2]))
                except Exception:
                    pass
    except FileNotFoundError:
        info["raw_error"] = "Không tìm thấy nvidia-smi (Chưa cài NVIDIA Driver hoặc máy không có card NVIDIA)."
    except Exception as e:
        info["raw_error"] = str(e)
    return info


def _check_ffmpeg_nvenc_support(ffmpeg_bin: Path) -> bool:
    """Kiểm tra xem FFmpeg có hỗ trợ bộ mã hóa phần cứng h264_nvenc hay không."""
    if not ffmpeg_bin.exists():
        return False
    try:
        res = subprocess.run(
            [str(ffmpeg_bin), "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return "h264_nvenc" in (res.stdout or "")
    except Exception:
        return False


def run_system_diagnostics(root_dir: Optional[Path] = None, pipeline: Any = None, adas_engine: Any = None) -> Dict[str, Any]:
    """
    Chạy kiểm tra sức khỏe toàn diện 7 hạng mục (bao gồm Phần cứng GPU, Driver NVIDIA, CUDA, Thư viện Python, FFmpeg NVENC, Model Voice, Kho Stock, Chrome):
    Thông báo rõ những thành phần nào máy khách hàng CHƯA CÓ để yêu cầu tải về hoặc bấm cài đặt tự động.
    """
    base = Path(root_dir) if root_dir else ROOT_DIR
    if base.name.lower() == "app":
        base = base.parent
    elif not (base / "bin").exists() and (base.parent / "bin").exists():
        base = base.parent

    checks: List[Dict[str, Any]] = []
    missing_requirements: List[Dict[str, str]] = []
    overall_ok = True

    # 1. Kiểm tra Phần cứng Card đồ họa NVIDIA & Driver + CUDA PyTorch
    nv_hw = _detect_nvidia_hardware()
    cuda_ok = False
    torch_ver = "Chưa cài"
    cuda_ver = "Không có"
    cudnn_ok = False
    gpu_name = nv_hw.get("gpu_name") or "CPU Mode"

    try:
        import torch
        torch_ver = getattr(torch, "__version__", "Đã cài")
        cuda_ok = bool(torch.cuda.is_available())
        cuda_ver = getattr(torch.version, "cuda", None) or "CPU-only"
        if cuda_ok:
            gpu_name = torch.cuda.get_device_name(0)
            cudnn_ok = bool(torch.backends.cudnn.is_available())
    except Exception as e:
        torch_ver = f"Lỗi ({e})"

    if cuda_ok:
        vram_gb = round(nv_hw.get("vram_total_mb", 0) / 1024.0, 1) if nv_hw.get("vram_total_mb") else "?"
        checks.append(
            {
                "name": "1. Tối Ưu Hóa GPU & Thư Viện NVIDIA CUDA",
                "ok": True,
                "detail": (
                    f"✅ ĐÃ BẬT TĂNG TỐC GPU: {gpu_name} ({vram_gb} GB VRAM) | "
                    f"NVIDIA Driver: {nv_hw.get('driver_version', 'OK')} | "
                    f"PyTorch: {torch_ver} (CUDA {cuda_ver}, cuDNN: {'Bật' if cudnn_ok else 'Tắt'})"
                ),
            }
        )
    elif nv_hw.get("has_nvidia_gpu"):
        overall_ok = False
        missing_requirements.append(
            {
                "id": "pytorch_cuda",
                "title": f"Thư viện PyTorch CUDA cho Card rời {nv_hw.get('gpu_name')}",
                "reason": f"Máy của bạn có Card NVIDIA ({nv_hw.get('gpu_name')}, Driver {nv_hw.get('driver_version')}) nhưng Python đang chạy PyTorch bản thường ({torch_ver}) chưa có CUDA nên chưa tối ưu được GPU!",
                "action_label": "⚡ Bấm nút [Tự Động Cài Thư Viện Thiếu & CUDA] bên dưới hoặc tải CUDA PyTorch",
                "download_url": "https://pytorch.org/get-started/locally/",
                "command": f'"{sys.executable}" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124 --upgrade',
            }
        )
        checks.append(
            {
                "name": "1. Tối Ưu Hóa GPU & Thư Viện NVIDIA CUDA",
                "ok": False,
                "detail": (
                    f"⚠️ PHÁT HIỆN CARD RỜI {nv_hw.get('gpu_name')} (Driver {nv_hw.get('driver_version')}) NHƯNG THIẾU THƯ VIỆN PYTORCH CUDA! "
                    f"Hiện đang chạy {torch_ver} (Chế độ CPU chậm). Vui lòng bấm nút [⚡ Cài Đặt CUDA & Thư Viện Thiếu] để kích hoạt tối ưu GPU!"
                ),
            }
        )
    else:
        missing_requirements.append(
            {
                "id": "nvidia_driver_cuda",
                "title": "Driver Card Đồ Họa NVIDIA & CUDA Toolkit",
                "reason": "Không phát hiện Card đồ họa rời NVIDIA (hoặc máy chưa cài đặt NVIDIA Driver). Hệ thống sẽ chạy bằng CPU (tốc độ tạo Voice và Render sẽ chậm hơn GPU).",
                "action_label": "Nếu máy có Card rời NVIDIA, vui lòng tải và cài đặt NVIDIA Driver + CUDA",
                "download_url": "https://www.nvidia.com/Download/index.aspx",
                "command": "",
            }
        )
        checks.append(
            {
                "name": "1. Tối Ưu Hóa GPU & Thư Viện NVIDIA CUDA",
                "ok": False,
                "detail": (
                    "⚠️ CHƯA PHÁT HIỆN GPU NVIDIA / DRIVER CUDA: Máy đang chạy chế độ CPU. "
                    "Nếu máy có card rời NVIDIA, hãy tải và cài đặt NVIDIA Game Ready / Studio Driver tại https://www.nvidia.com/Download/index.aspx để mở khóa tăng tốc GPU!"
                ),
            }
        )

    # 2. Kiểm tra đầy đủ 16 Thư viện Python cần thiết để chạy Tool
    installed_libs: List[str] = []
    missing_libs: List[Dict[str, str]] = []
    for mod_name, pip_name, desc in REQUIRED_PYTHON_LIBRARIES:
        spec = importlib.util.find_spec(mod_name)
        if spec is not None:
            installed_libs.append(mod_name)
        else:
            missing_libs.append({"module": mod_name, "pip": pip_name, "desc": desc})

    if not missing_libs:
        checks.append(
            {
                "name": f"2. Thư Viện Python Hệ Thống ({len(installed_libs)}/{len(REQUIRED_PYTHON_LIBRARIES)} thư viện)",
                "ok": True,
                "detail": f"✅ Đầy đủ 100% ({len(installed_libs)}/{len(REQUIRED_PYTHON_LIBRARIES)}) thư viện bắt buộc: {', '.join(installed_libs[:10])}...",
            }
        )
    else:
        overall_ok = False
        missing_names = ", ".join([f"{x['pip']} ({x['desc']})" for x in missing_libs])
        pip_pkgs = " ".join([x["pip"] for x in missing_libs])
        missing_requirements.append(
            {
                "id": "missing_python_libs",
                "title": f"Thiếu {len(missing_libs)} thư viện Python bắt buộc",
                "reason": f"Máy chưa có các thư viện: {missing_names}",
                "action_label": "Bấm nút [⚡ Cài Đặt CUDA & Thư Viện Thiếu] để tải tự động",
                "download_url": "https://pypi.org/",
                "command": f'"{sys.executable}" -m pip install {pip_pkgs}',
            }
        )
        checks.append(
            {
                "name": f"2. Thư Viện Python Hệ Thống ({len(installed_libs)}/{len(REQUIRED_PYTHON_LIBRARIES)} thư viện)",
                "ok": False,
                "detail": f"❌ THIẾU {len(missing_libs)} THƯ VIỆN CẦN TẢI VỀ: {missing_names}",
            }
        )

    # 3. Kiểm tra FFmpeg & FFprobe & Mã hóa GPU h264_nvenc
    ffmpeg_bin = base / "bin" / "ffmpeg.exe"
    ffprobe_bin = base / "bin" / "ffprobe.exe"
    ffmpeg_ok = ffmpeg_bin.exists() and ffprobe_bin.exists()
    nvenc_ok = _check_ffmpeg_nvenc_support(ffmpeg_bin) if ffmpeg_ok else False
    if not ffmpeg_ok:
        overall_ok = False
        missing_requirements.append(
            {
                "id": "ffmpeg_bin",
                "title": "Bộ công cụ Render Video FFmpeg & FFprobe",
                "reason": f"Thiếu file thực thi ffmpeg.exe hoặc ffprobe.exe trong thư mục {base / 'bin'}.",
                "action_label": "Tải FFmpeg Windows Build (gyan.dev / BtbN) và giải nén vào thư mục bin/",
                "download_url": "https://github.com/BtbN/FFmpeg-Builds/releases",
                "command": "",
            }
        )
    checks.append(
        {
            "name": "3. Bộ Kết Xuất Video (FFmpeg & Mã Hóa GPU NVENC)",
            "ok": ffmpeg_ok,
            "detail": (
                f"✅ Đã sẵn sàng tại {base / 'bin'} | Hỗ trợ Render GPU (h264_nvenc): {'🟢 Có' if nvenc_ok else '🟡 Không'}"
                if ffmpeg_ok
                else f"❌ Thiếu ffmpeg.exe hoặc ffprobe.exe trong {base / 'bin'}! Vui lòng tải về bổ sung."
            ),
        }
    )

    # 4. Kiểm tra Bộ Tạo Giọng Đọc AI (VOICEVOX DirectML Engine + Giọng Drama 0.97x & OmniVoice)
    vv_ready = False
    vv_detail = ""
    try:
        from .voicevox_service import get_voicevox_service
        vv_st = get_voicevox_service().get_engine_status()
        vv_ready = bool(vv_st.get("installed"))
        active_p = vv_st.get("active_preset", {})
        vv_cfg = vv_st.get("config", {})
        vv_detail = (
            f"VOICEVOX DirectML: {'🟢 Đang chạy' if vv_st.get('running') else '✅ Đã tích hợp sẵn'} "
            f"(Giọng đang chọn: {active_p.get('name', 'Drama')} | Speed={vv_cfg.get('speedScale', 0.97)}x)"
            if vv_ready
            else "❌ Chưa tìm thấy VOICEVOX_ENGINE/run.exe"
        )
    except Exception as e:
        vv_detail = f"Lỗi kiểm tra VOICEVOX: {e}"

    model_dir = base / "pretrained_models" / "OmniVoice"
    main_w = model_dir / "model.safetensors"
    tok_w = model_dir / "audio_tokenizer" / "model.safetensors"
    weights_ready = main_w.exists() and main_w.stat().st_size > 1_000_000_000 and tok_w.exists()
    voice_ok = vv_ready or weights_ready
    if not voice_ok:
        missing_requirements.append(
            {
                "id": "omnivoice_model",
                "title": "Bộ Tạo Giọng Đọc AI Nhật Bản (VOICEVOX DirectML / OmniVoice)",
                "reason": f"Chưa có VOICEVOX_ENGINE hoặc trọng số model.safetensors tại {model_dir}.",
                "action_label": "Kiểm tra thư mục VOICEVOX_ENGINE hoặc tải từ HuggingFace (k2-fsa/OmniVoice)",
                "download_url": "https://huggingface.co/k2-fsa/OmniVoice",
                "command": "",
            }
        )
    checks.append(
        {
            "name": "4. Bộ Tạo Giọng Đọc AI (VOICEVOX DirectML — Giọng Drama 0.97x & OmniVoice)",
            "ok": voice_ok,
            "detail": (
                f"✅ {vv_detail} | OmniVoice Clone: {'Đã sẵn sàng' if weights_ready else 'Tự tải khi cần'}"
                if voice_ok
                else f"⚠️ {vv_detail} | Chưa tải sẵn Model OmniVoice tại {model_dir}"
            ),
        }
    )

    # 5. Kiểm tra Kho Video Stock (STOOK)
    try:
        if pipeline and hasattr(pipeline, "stock_manager"):
            st_info = pipeline.stock_manager.get_all_stocks()
            avail_cnt = st_info.get("available_count", 0)
            avail_h = st_info.get("available_raw_hours", 0.0)
            stook_path = st_info.get("stook_dir", "")
            stock_ok = avail_cnt > 0
            checks.append(
                {
                    "name": "5. Kho Video Nền 720p (STOOK)",
                    "ok": stock_ok,
                    "detail": (
                        f"✅ Sẵn sàng {avail_cnt} video khả dụng ({avail_h:.1f} giờ) tại {stook_path}"
                        if stock_ok
                        else f"⚠️ Kho STOOK ({stook_path}) đang trống (0 video khả dụng) — Hệ thống sẽ tự động tải 720p từ YouTube khi chạy!"
                    ),
                }
            )
    except Exception as e:
        checks.append({"name": "5. Kho Video Nền 720p (STOOK)", "ok": False, "detail": f"❌ Lỗi đọc kho Stock: {e}"})

    # 6. Kiểm tra 3 Tài khoản Chrome ChatGPT Web
    try:
        from .chatgpt_web_client import check_all_web_accounts_status
        acc_st = check_all_web_accounts_status(force_refresh=False).get("accounts", {})
        logged_in_labels = [v.get("label", k) for k, v in acc_st.items() if v.get("logged_in")]
        open_labels = [v.get("label", k) for k, v in acc_st.items() if v.get("browser_open")]
        checks.append(
            {
                "name": "6. Trạm Chrome ChatGPT Web (3 Tài Khoản)",
                "ok": len(logged_in_labels) > 0,
                "detail": (
                    f"✅ Đã đăng nhập {len(logged_in_labels)}/3 tài khoản: {', '.join(logged_in_labels)}"
                    if logged_in_labels
                    else (
                        f"⚠️ Đang mở {len(open_labels)} trình duyệt nhưng chưa đăng nhập ChatGPT!"
                        if open_labels
                        else "⚪ Chưa mở trình duyệt Chrome ChatGPT (Chỉ cần mở khi viết kịch bản mới; chạy Voice/Render không cần mở Chrome)."
                    )
                ),
            }
        )
    except Exception as e:
        checks.append({"name": "6. Trạm Chrome ChatGPT Web", "ok": False, "detail": f"Lỗi kiểm tra Chrome: {e}"})

    # 7. Kiểm tra các Dự án đã có Kịch bản chờ Render hoặc bị lỗi
    script_ready_list = []
    projects_ready_for_video = []
    video_done_list = []
    error_list = []
    try:
        if adas_engine:
            adas_engine._sync_projects_disk_state()
            ideas = adas_engine.load_saved_ideas()
            for it in ideas:
                mid = it.get("ma_id", "")
                pdir = adas_engine.projects_dir / mid
                has_script, _, sc_chars = adas_engine.has_valid_script_on_disk(mid)
                has_mp4, _, _ = adas_engine.has_valid_video_mp4_on_disk(mid, sc_chars=sc_chars)
                if has_mp4:
                    video_done_list.append(mid)
                elif has_script:
                    script_ready_list.append(mid)
                    projects_ready_for_video.append({"ma_id": mid, "pure_chars": sc_chars})
                if "ERROR" in str(it.get("status", "")).upper() and not has_mp4:
                    error_list.append(f"{mid} ({it.get('current_step', '')})")
    except Exception:
        pass

    checks.append(
        {
            "name": "7. Trạng Thái Kho Dự Án & Hàng Đợi Render",
            "ok": len(error_list) == 0,
            "detail": (
                f"🎬 Đã xuất MP4: {len(video_done_list)} mã | "
                f"📝 Đã có sẵn Kịch bản (Chờ Render MP4): {len(script_ready_list)} mã ({', '.join(script_ready_list[:8]) or 'Không có'}) | "
                f"❌ Dự án báo lỗi gần nhất: {len(error_list)} ({'; '.join(error_list[:3]) or 'Không có lỗi'})"
            ),
        }
    )

    for c in checks:
        c["status"] = "OK" if c.get("ok") else ("WARN" if "⚠️" in str(c.get("detail", "")) or "⚪" in str(c.get("detail", "")) else "ERROR")

    overall_status = "OK" if all(c["status"] == "OK" for c in checks) else ("ERROR" if any(c["status"] == "ERROR" for c in checks) else "WARN")
    ts_now = time.strftime("%Y-%m-%d %H:%M:%S")

    log_info(
        f"🔍 Chẩn Đoán Hệ Thống & GPU: GPU={'CUDA (' + gpu_name + ')' if cuda_ok else 'Chưa có CUDA'}, "
        f"Thư viện={len(installed_libs)}/{len(REQUIRED_PYTHON_LIBRARIES)}, "
        f"MP4={len(video_done_list)}, Chờ Render={len(script_ready_list)}",
        category="SYSTEM",
    )

    return {
        "overall_ok": overall_ok,
        "overall_status": overall_status,
        "checked_at": ts_now,
        "timestamp": ts_now,
        "logs_dir": str(LOGS_DIR),
        "runtime_log_file": str(RUNTIME_LOG_FILE),
        "error_log_file": str(ERROR_LOG_FILE),
        "startup_log_file": str(STARTUP_LOG_FILE),
        "checks": checks,
        "gpu_hardware": nv_hw,
        "cuda_available": cuda_ok,
        "torch_version": torch_ver,
        "cuda_version": cuda_ver,
        "missing_libs": missing_libs,
        "missing_requirements": missing_requirements,
        "script_ready_ids": script_ready_list,
        "projects_ready_for_video": projects_ready_for_video,
        "video_done_ids": video_done_list,
        "error_projects": error_list,
    }


def install_missing_libraries_async(install_cuda: bool = True) -> Dict[str, Any]:
    """
    Tự động tải và cài đặt các thư viện Python còn thiếu và/hoặc bản PyTorch CUDA tối ưu GPU
    trong luồng nền, đồng thời đẩy thông báo tiến trình trực tiếp lên bảng Nhật Ký Hệ Thống (System Logs).
    """
    missing_pkgs: List[str] = []
    for mod_name, pip_name, _ in REQUIRED_PYTHON_LIBRARIES:
        if importlib.util.find_spec(mod_name) is None:
            missing_pkgs.append(pip_name)

    nv_hw = _detect_nvidia_hardware()
    need_cuda_torch = False
    try:
        import torch
        if nv_hw.get("has_nvidia_gpu") and not torch.cuda.is_available():
            need_cuda_torch = True
    except Exception:
        need_cuda_torch = bool(nv_hw.get("has_nvidia_gpu"))

    if not missing_pkgs and not (install_cuda and need_cuda_torch):
        log_info("SYSTEM", "✅ Máy đã cài đặt đầy đủ 100% thư viện Python và tối ưu GPU CUDA, không cần tải thêm!")
        return {
            "started": False,
            "message": "Máy đã có đầy đủ thư viện và tối ưu GPU CUDA!",
        }

    def _worker():
        try:
            if missing_pkgs:
                log_info("SYSTEM", f"⏳ Đang tự động tải và cài đặt {len(missing_pkgs)} thư viện thiếu: {', '.join(missing_pkgs)}...")
                cmd = [sys.executable, "-m", "pip", "install", *missing_pkgs]
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                if proc.stdout:
                    for line in proc.stdout:
                        ln = line.strip()
                        if ln:
                            log_info("SYSTEM", f"[PIP] {ln}")
                proc.wait()
                if proc.returncode == 0:
                    log_info("SYSTEM", f"✅ Đã cài đặt xong các thư viện: {', '.join(missing_pkgs)}")
                else:
                    log_error("SYSTEM", f"❌ Lỗi khi cài thư viện (Mã lỗi {proc.returncode}).")

            if install_cuda and need_cuda_torch:
                log_info("SYSTEM", "🚀 Đang tải và cài đặt bộ thư viện PyTorch CUDA 12.4 để tối ưu GPU NVIDIA (Dung lượng ~2.4GB, vui lòng đợi)...")
                cmd_cuda = [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "torch",
                    "torchaudio",
                    "--index-url",
                    "https://download.pytorch.org/whl/cu124",
                    "--upgrade",
                ]
                proc_c = subprocess.Popen(
                    cmd_cuda,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                if proc_c.stdout:
                    for line in proc_c.stdout:
                        ln = line.strip()
                        if ln:
                            log_info("SYSTEM", f"[CUDA-PIP] {ln}")
                proc_c.wait()
                if proc_c.returncode == 0:
                    log_info("SYSTEM", "✅ Đã cài đặt thành công PyTorch CUDA! Vui lòng khởi động lại ứng dụng để nhận GPU CUDA.")
                else:
                    log_error("SYSTEM", f"❌ Cài đặt PyTorch CUDA thất bại (Mã lỗi {proc_c.returncode}).")
        except Exception as e:
            log_error("SYSTEM", f"❌ Lỗi trong quá trình tự động cài đặt thư viện: {e}", exc=e)

    threading.Thread(target=_worker, daemon=True).start()
    return {
        "started": True,
        "message": "Đã bắt đầu tải và cài đặt thư viện thiếu / CUDA trong nền. Xem tiến trình tại bảng Nhật Ký Hệ Thống!",
    }
