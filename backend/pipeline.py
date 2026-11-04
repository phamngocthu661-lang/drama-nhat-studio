import os
import sys
import time
import json
import ctypes
import subprocess
import traceback
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from .stock_manager import StockManager
from .voice_service import VoiceStudioService, split_japanese_script, strip_leaked_titles_and_metadata
from .voicevox_service import (
    VoicevoxStandaloneService,
    load_voice_config,
    save_voice_config,
    compute_voice_signature,
)
from .renderer import render_drama_nhat_video
from .logger_service import log_info, log_warn, log_error

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint32),
        ("dwMemoryLoad", ctypes.c_uint32),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


class HardwareResourceBalancer:
    """
    Bộ Cân Đối Tài Nguyên Động (Smart Resource Balancer — Mục tiêu tối ưu ~85%–90% GPU & CPU):
    - Đo lường tải CPU, RAM, GPU Core, GPU NVENC Encoder và VRAM theo thời gian thực.
    - Tự động mở thêm luồng xử lý song song (Voice GPU + FFmpeg NVENC) ngay khi thấy máy còn khoảng trống (< 88%–90%).
    """

    target_max_percent: float = 90.0
    max_concurrent_videos: int = 5
    performance_mode: str = "full_100"

    def __init__(self, target_max_percent: float = 90.0):
        self.target_max_percent = float(target_max_percent)
        self.max_concurrent_videos = 5
        self.performance_mode = "full_100"
        self._lock = threading.Lock()
        self._last_cpu_times = self._read_win_cpu_times()
        self._last_metrics: Dict[str, float] = {
            "cpu_percent": 15.0,
            "ram_percent": 40.0,
            "gpu_core_percent": 10.0,
            "gpu_enc_percent": 0.0,
            "gpu_percent": 10.0,
            "vram_percent": 30.0,
            "timestamp": 0.0,
        }

    def _read_win_cpu_times(self) -> Optional[tuple[int, int, int]]:
        if os.name != "nt":
            return None
        try:
            idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
            if ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
            ):
                to_u64 = lambda ft: (ft.dwHighDateTime << 32) | ft.dwLowDateTime
                return to_u64(idle), to_u64(kernel), to_u64(user)
        except Exception:
            pass
        return None

    def get_metrics(self, force_refresh: bool = False) -> Dict[str, float]:
        now = time.time()
        with self._lock:
            if not force_refresh and (now - self._last_metrics["timestamp"] < 1.2):
                return dict(self._last_metrics)

            # 1. Đo CPU % qua Windows Kernel API
            cpu_pct = self._last_metrics["cpu_percent"]
            t_now = self._read_win_cpu_times()
            if t_now and self._last_cpu_times:
                idle_d = t_now[0] - self._last_cpu_times[0]
                kern_d = t_now[1] - self._last_cpu_times[1]
                user_d = t_now[2] - self._last_cpu_times[2]
                total_d = kern_d + user_d
                if total_d > 0:
                    cpu_pct = max(0.0, min(100.0, round((1.0 - (idle_d / float(total_d))) * 100.0, 1)))
            if t_now:
                self._last_cpu_times = t_now

            # 2. Đo RAM %
            ram_pct = self._last_metrics["ram_percent"]
            if os.name == "nt":
                try:
                    mem = _MEMORYSTATUSEX()
                    mem.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
                    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
                        ram_pct = float(mem.dwMemoryLoad)
                except Exception:
                    pass

            # 3. Đo GPU Core %, NVENC Encoder % & VRAM % qua nvidia-smi
            gpu_core = 0.0
            gpu_enc = 0.0
            vram_pct = 0.0
            try:
                creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                res = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=utilization.gpu,utilization.encoder,memory.used,memory.total",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    creationflags=creation_flags,
                )
                if res.returncode == 0 and res.stdout.strip():
                    first_line = res.stdout.strip().splitlines()[0]
                    parts = [p.strip() for p in first_line.split(",")]
                    if len(parts) >= 4:
                        gpu_core = float(parts[0])
                        gpu_enc = float(parts[1])
                        mem_used = float(parts[2])
                        mem_tot = max(1.0, float(parts[3]))
                        vram_pct = round((mem_used / mem_tot) * 100.0, 1)
            except Exception:
                pass

            gpu_effective = max(gpu_core, gpu_enc)
            self._last_metrics = {
                "cpu_percent": cpu_pct,
                "ram_percent": ram_pct,
                "gpu_core_percent": gpu_core,
                "gpu_enc_percent": gpu_enc,
                "gpu_percent": gpu_effective,
                "vram_percent": vram_pct,
                "timestamp": now,
            }
            return dict(self._last_metrics)

    def has_headroom_for_parallel_task(self, current_active_tasks: int, max_concurrent: Optional[int] = None) -> bool:
        """
        Kiểm tra xem máy còn khoảng trống tài nguyên để đẩy thêm luồng chạy song song không:
        - Chế độ Full 100% (`full_100`): Tối đa 5 video cùng lúc, ngưỡng CPU/GPU < 90%, RAM < 92%.
        - Chế độ 70% (`work_70` - Vừa chạy vừa làm việc khác): Tối đa 3 video cùng lúc, ngưỡng CPU/GPU < 70%, RAM < 84%.
        """
        perf_mode = getattr(self, "performance_mode", "full_100")
        default_max = 3 if perf_mode == "work_70" else 5
        eff_max = max_concurrent if max_concurrent is not None else int(getattr(self, "max_concurrent_videos", default_max) or default_max)
        if current_active_tasks >= eff_max:
            return False
        if current_active_tasks <= 0:
            return True
        m = self.get_metrics(force_refresh=True)
        limit = float(getattr(self, "target_max_percent", 70.0 if perf_mode == "work_70" else 90.0))
        ram_limit = 84.0 if perf_mode == "work_70" else 92.0
        if m["cpu_percent"] < limit and m["gpu_percent"] < limit and m["ram_percent"] < ram_limit:
            return True
        return False


class ProductionPipeline:
    performance_mode: str = "full_100"

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir:
            self.root_dir = Path(root_dir)
        else:
            p = Path(__file__).resolve().parent.parent
            if (p / "STOOK").exists():
                self.root_dir = p
            elif (p.parent / "STOOK").exists():
                self.root_dir = p.parent
            else:
                self.root_dir = p
        self.default_projects_dir = self.root_dir / "projects"
        self.projects_dir = self.default_projects_dir
        self.default_projects_dir.mkdir(parents=True, exist_ok=True)

        self.stock_manager = StockManager(self.root_dir)
        self.voice_service = VoiceStudioService(self.root_dir)
        self.voicevox_service = VoicevoxStandaloneService(self.root_dir)
        self.resource_balancer = HardwareResourceBalancer(target_max_percent=90.0)
        self.performance_mode: str = "full_100"

        # Trạng thái hiện tại & Hàng đợi động đa luồng (Dynamic Multi-Worker Queue)
        self.lock = threading.Lock()
        self.stock_alloc_lock = threading.Lock()
        self.is_running = False
        self.should_stop = False
        self.pending_jobs: List[Dict[str, Any]] = []
        self.active_projects: set[str] = set()
        self.active_jobs_detail: Dict[str, Dict[str, Any]] = {}
        self.active_job_map: Dict[str, Dict[str, Any]] = {}
        self.paused_for_perf_downscale: set[str] = set()
        self.active_voice_jobs: int = 0
        self.active_ffmpeg_jobs: int = 0
        self.adas_engine: Any = None
        self.job_status_callback: Optional[Callable[[str, str, str], None]] = None

        self.state = {
            "status": "idle",  # idle, running, completed, error
            "stage": "",       # voice, stock, render, qa_sync
            "progress": 0.0,
            "message": "Hệ thống sẵn sàng (Server GPU đã bật)",
            "batch_total": 1,
            "batch_current": 1,
            "current_project": "",
            "start_time": 0,
            "elapsed_seconds": 0,
            "results": [],
            "active_jobs": [],
            "active_count": 0,
            "pending_count": 0,
            "completed_count": 0,
            "error": None,
            "hardware_load": {},
            "performance_mode": "full_100",
        }
        self.subscribers: list[Callable[[Dict[str, Any]], None]] = []

        # Khôi phục chế độ hiệu suất (100% hoặc 70%) đã lưu trong config.json
        self._init_performance_mode_from_config()

        # BẬT NGAY SERVER VOICE GPU KHI ỨNG DỤNG KHỞI ĐỘNG!
        threading.Thread(target=self._auto_start_gpu_server_on_boot, daemon=True).start()

    def _ensure_hot_reload_compat(self):
        """
        Đảm bảo tương thích ngược 100% khi Hot-Reload từ các phiên bản cũ (V1.0.0..V1.0.2)
        mà không cần tắt mở lại ứng dụng: Tự động nâng cấp class và thuộc tính của `resource_balancer` và `pipeline`.
        """
        try:
            if "active_job_map" not in self.__dict__:
                self.active_job_map = {}
            if "paused_for_perf_downscale" not in self.__dict__:
                self.paused_for_perf_downscale = set()

            env_mode = os.environ.get("STUDIO_PERF_MODE", "").strip().lower()
            if env_mode in ("full_100", "work_70"):
                self.performance_mode = env_mode
            elif "performance_mode" not in self.__dict__ or not self.performance_mode:
                saved_mode = "full_100"
                cfg_file = getattr(self, "root_dir", Path(".")) / "config.json"
                if cfg_file.exists():
                    try:
                        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
                        if cfg.get("performance_mode") in ("full_100", "work_70"):
                            saved_mode = cfg["performance_mode"]
                    except Exception:
                        pass
                self.performance_mode = saved_mode

            is_70 = self.performance_mode == "work_70"
            rb = getattr(self, "resource_balancer", None)
            if rb is None:
                self.resource_balancer = HardwareResourceBalancer(
                    target_max_percent=70.0 if is_70 else 90.0
                )
                rb = self.resource_balancer
            else:
                if rb.__class__ is not HardwareResourceBalancer:
                    for attr_name, attr_val in vars(HardwareResourceBalancer).items():
                        if not attr_name.startswith("__"):
                            try:
                                setattr(rb.__class__, attr_name, attr_val)
                            except Exception:
                                pass
                    try:
                        rb.__class__ = HardwareResourceBalancer
                    except Exception:
                        pass
            # LUÔN KHÓA CỨNG số luồng tối đa theo chế độ hiện tại (3 luồng cho 70% | 5 luồng cho 100%)
            rb.performance_mode = "work_70" if is_70 else "full_100"
            rb.max_concurrent_videos = 3 if is_70 else 5
            rb.target_max_percent = 70.0 if is_70 else 90.0
        except Exception:
            pass

    def _init_performance_mode_from_config(self):
        cfg_file = self.root_dir / "config.json"
        saved_mode = "full_100"
        if cfg_file.exists():
            try:
                cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
                if cfg.get("performance_mode") in ("full_100", "work_70"):
                    saved_mode = cfg["performance_mode"]
            except Exception:
                pass
        self.set_performance_mode(saved_mode, persist=False)

    def get_performance_mode_info(self) -> Dict[str, Any]:
        self._ensure_hot_reload_compat()
        is_70 = getattr(self, "performance_mode", "full_100") == "work_70"
        default_max_vids = 3 if is_70 else 5
        default_target_pct = 70.0 if is_70 else 90.0
        return {
            "mode": "work_70" if is_70 else "full_100",
            "label": "💼 Chạy 70% (Tối Đa 3 Luồng — Vừa Chạy Vừa Làm Việc Khác)" if is_70 else "🔥 Chạy Full 100% (Tối Đa Tốc Độ)",
            "target_max_percent": float(getattr(self.resource_balancer, "target_max_percent", default_target_pct) or default_target_pct),
            "max_concurrent_videos": 3 if is_70 else 5,
            "max_total_threads": 3 if is_70 else 9,
            "threads_per_account": 1 if is_70 else 3,
        }

    def set_performance_mode(self, mode: str, persist: bool = True) -> Dict[str, Any]:
        """
        Chuyển đổi tức thì giữa 2 chế độ hoạt động (áp dụng ngay cả khi đang chạy):
        1. `full_100`: Chạy Full 100% công suất (Tối đa 5 video render song song, <90% CPU/GPU, 3 tab AI/Acc = 9 luồng).
        2. `work_70`: Chạy 70% công suất (Khóa cứng TỐI ĐA 3 LUỒNG trên toàn hệ thống: tối đa 3 luồng viết kịch bản AI / 1 tab mỗi Acc,
           tối đa 3 luồng render video, <70% CPU/GPU, ưu tiên tiến trình BelowNormal) để người dùng vừa chạy vừa làm việc khác mượt mà.
        """
        norm_mode = "work_70" if str(mode or "").strip().lower() in ("work_70", "70", "70%", "balanced") else "full_100"
        self.performance_mode = norm_mode
        os.environ["STUDIO_PERF_MODE"] = norm_mode
        self._ensure_hot_reload_compat()

        if norm_mode == "work_70":
            self.resource_balancer.performance_mode = "work_70"
            self.resource_balancer.target_max_percent = 70.0
            self.resource_balancer.max_concurrent_videos = 3
            threads_per_acc = 1
        else:
            self.resource_balancer.performance_mode = "full_100"
            self.resource_balancer.target_max_percent = 90.0
            self.resource_balancer.max_concurrent_videos = 5
            threads_per_acc = 3

        try:
            import backend.chatgpt_web_client as _cwc
            _cwc.MAX_THREADS_PER_ACCOUNT = threads_per_acc
        except Exception:
            pass
        try:
            import backend.adas_script_engine as _ase
            _ase.MAX_THREADS_PER_ACCOUNT = threads_per_acc
        except Exception:
            pass

        with self.lock:
            self.state["performance_mode"] = norm_mode
            if norm_mode == "work_70" and len(self.active_projects) > 3:
                active_unpaused = [
                    p for p in self.active_projects
                    if p not in self.paused_for_perf_downscale
                ]
                if len(active_unpaused) > 3:
                    active_unpaused.sort(
                        key=lambda p: int((self.active_job_map.get(p) or {}).get("job_num", 999999)),
                        reverse=True,
                    )
                    for p_yield in active_unpaused[: len(active_unpaused) - 3]:
                        self.paused_for_perf_downscale.add(p_yield)
            elif norm_mode == "full_100":
                self.paused_for_perf_downscale.clear()

        # Điều chỉnh mức ưu tiên của các tiến trình ffmpeg.exe đang chạy ngay lập tức trên Windows
        if os.name == "nt":
            priority_name = "BelowNormal" if norm_mode == "work_70" else "Normal"
            try:
                subprocess.Popen(
                    [
                        "powershell",
                        "-NoProfile",
                        "-Command",
                        f"Get-Process ffmpeg -ErrorAction SilentlyContinue | ForEach-Object {{ $_.PriorityClass = '{priority_name}' }}",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=0x08000000,
                )
            except Exception:
                pass

        if persist:
            cfg_file = self.root_dir / "config.json"
            try:
                cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else {}
                cfg["performance_mode"] = norm_mode
                cfg_file.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
            log_info(
                "SYSTEM",
                f"⚡ Đã chuyển sang chế độ [{'💼 CHẠY 70% — Vừa chạy vừa làm việc khác (Giới hạn 70% CPU/GPU • Tối đa 3 video • 1 tab AI/Acc)' if norm_mode == 'work_70' else '🔥 CHẠY FULL 100% — Tối đa công suất (Ngưỡng 90% CPU/GPU • Tối đa 5 video • 3 tab AI/Acc)'}]!",
            )

        self._notify()
        return self.get_performance_mode_info()

    def _auto_start_gpu_server_on_boot(self):
        """Khởi động sẵn Server Voice GPU đang chọn ngay sau khi cửa sổ giao diện đã mở xong."""
        try:
            time.sleep(2.5)
            cfg = load_voice_config()
            active_srv = cfg.get("active_gpu_server", "voicevox_gpu")
            log_info("VOICE", f"🚀 [AUTO-BOOT GPU] Đang tự động bật Server Voice GPU ({active_srv}) ngay khi khởi động ứng dụng...")
            self.activate_gpu_voice_server(active_srv)
        except Exception as e:
            log_warn("VOICE", f"Lưu ý khi khởi động sớm Server GPU: {e}")

    def activate_gpu_voice_server(self, server_mode: Optional[str] = None) -> Dict[str, Any]:
        """
        Cho phép bật hoặc chuyển đổi giữa 2 Server Voice GPU:
        - `voicevox_gpu` (Server 1: VOICEVOX DirectML GPU Cluster — cổng 50021 & 50022, nạp sẵn giọng Drama 0.97x)
        - `omnivoice_gpu` (Server 2: OmniVoice CUDA GPU — nạp sẵn model 600M FP16 lên VRAM CUDA)
        """
        cfg = load_voice_config()
        target_srv = server_mode or cfg.get("active_gpu_server") or "voicevox_gpu"
        if target_srv not in ("voicevox_gpu", "omnivoice_gpu"):
            target_srv = "voicevox_gpu"

        saved_cfg = save_voice_config({"active_gpu_server": target_srv})

        if target_srv == "voicevox_gpu":
            # Giải phóng VRAM của OmniVoice nếu trước đó đã nạp để nhường 100% GPU cho VOICEVOX DirectML + NVENC
            if getattr(self.voice_service, "model", None) is not None:
                try:
                    import torch
                    self.voice_service.model = None
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    pass
            ok = self.voicevox_service.ensure_server_running(multi_worker=True)
            spk = int(saved_cfg.get("speaker_id", 13))
            if ok and spk >= 0:
                self.voicevox_service.warmup_speaker(spk)
            log_info(
                "VOICE",
                f"🟢 Đã bật Server 1: VOICEVOX DirectML GPU Cluster (2 cổng GPU 50021/50022 • Giọng {saved_cfg.get('selected_preset_id')} • Speed {saved_cfg.get('speedScale')}x)!",
            )
        else:
            # Tắt các worker VOICEVOX để dành trọn VRAM cho OmniVoice CUDA GPU
            self.voicevox_service.stop_all_workers()
            try:
                self.voice_service.load_model()
                log_info("VOICE", "🔵 Đã bật Server 2: OmniVoice CUDA GPU Server (Đã nạp model FP16 lên VRAM CUDA)!")
            except Exception as e:
                log_error("VOICE", f"Không thể nạp OmniVoice CUDA GPU: {e}")

        omni_loaded = getattr(self.voice_service, "model", None) is not None
        return self.voicevox_service.get_engine_status(omnivoice_loaded=omni_loaded)

    def set_job_status_callback(self, cb: Callable[[str, str, str], None]):
        """Đăng ký callback(ma_id, status_code, step_text) để đồng bộ trạng thái sang ADASScriptEngine."""
        self.job_status_callback = cb

    def _update_job_card_status(self, proj_name: str, status_code: str, step_text: str):
        if self.job_status_callback:
            try:
                self.job_status_callback(proj_name, status_code, step_text)
            except Exception:
                pass

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]):
        self.subscribers.append(callback)

    def _set_project_live_detail(
        self,
        proj_name: str,
        stage: str,
        stage_label: str,
        progress: float,
        detail: str,
        job_num: int = 0,
    ):
        now_ts = time.time()
        with self.lock:
            prev = self.active_jobs_detail.get(proj_name) or {}
            start_ts = float(prev.get("started_at") or now_ts)
            j_num = int(job_num or prev.get("job_num") or 0)
            self.active_jobs_detail[proj_name] = {
                "project_name": proj_name,
                "job_num": j_num,
                "stage": stage,
                "stage_label": stage_label,
                "progress": round(float(progress), 1),
                "detail": detail,
                "started_at": start_ts,
                "elapsed_seconds": max(0, int(now_ts - start_ts)),
            }

    def _get_sorted_active_jobs_locked(self) -> List[Dict[str, Any]]:
        now_ts = time.time()
        items: List[Dict[str, Any]] = []
        for info in self.active_jobs_detail.values():
            entry = dict(info)
            entry["elapsed_seconds"] = max(0, int(now_ts - float(entry.get("started_at") or now_ts)))
            items.append(entry)
        items.sort(key=lambda x: (int(x.get("job_num") or 999999), str(x.get("project_name") or "")))
        return items

    def _notify(self, message: str = "", progress: Optional[float] = None, stage: Optional[str] = None):
        self._ensure_hot_reload_compat()
        hw = self.resource_balancer.get_metrics(force_refresh=False)
        with self.lock:
            if message:
                self.state["message"] = message
            if progress is not None:
                self.state["progress"] = progress
            if stage is not None:
                self.state["stage"] = stage
            if self.is_running:
                self.state["elapsed_seconds"] = int(time.time() - self.state["start_time"])
            self.state["hardware_load"] = hw
            self.state["active_jobs"] = self._get_sorted_active_jobs_locked()
            self.state["active_count"] = len(self.active_jobs_detail)
            self.state["pending_count"] = len(self.pending_jobs)
            self.state["completed_count"] = len(self.state.get("results") or [])
            snapshot = dict(self.state)

        for cb in self.subscribers:
            try:
                cb(snapshot)
            except Exception:
                pass

    def get_state(self) -> Dict[str, Any]:
        self._ensure_hot_reload_compat()
        hw = self.resource_balancer.get_metrics(force_refresh=False)
        with self.lock:
            if self.is_running:
                self.state["elapsed_seconds"] = int(time.time() - self.state["start_time"])
            self.state["hardware_load"] = hw
            self.state["active_jobs"] = self._get_sorted_active_jobs_locked()
            self.state["active_count"] = len(self.active_jobs_detail)
            self.state["pending_count"] = len(self.pending_jobs)
            self.state["completed_count"] = len(self.state.get("results") or [])
            return dict(self.state)

    def stop(self):
        with self.lock:
            self.should_stop = True
            self.pending_jobs.clear()
            self.active_jobs_detail.clear()
        log_warn("Đã nhận lệnh dừng dây chuyền sản xuất Video từ người dùng.", category="RENDER")
        self._notify("🛑 Đang dừng dây chuyền sản xuất Video...", stage="stopped")

    def start_batch_production_async(
        self,
        jobs: List[Dict[str, Any]],
        output_dir: Optional[str] = None,
        channel_name: str = ".",
        resolution: str = "1920x1080",
        fps: int = 24,
        stock_selection: str = "auto_unique",
        bgm_path: Optional[str] = None,
        bgm_volume: float = 0.08,
        delete_used_stocks: bool = True,
        auto_ensure_stock_hours: bool = True,
        target_stock_hours: float = 30.0,
        voice_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Bắt đầu chạy danh sách kịch bản hoặc tự động bơm thẳng vào Pool Đa Luồng nếu dây chuyền đang chạy!
        Nếu có `voice_config` truyền từ giao diện xuống, lưu và áp dụng ngay lập tức 100%.
        """
        self._ensure_hot_reload_compat()
        if not jobs:
            return False

        # Đồng bộ chế độ hiệu suất (70% 3 luồng hoặc 100% 5 luồng) trực tiếp từ giao diện nếu có gửi kèm
        if isinstance(voice_config, dict) and voice_config.get("performance_mode") in ("full_100", "work_70"):
            self.set_performance_mode(voice_config["performance_mode"], persist=True)

        # Lưu cấu hình Voice mới nhất từ giao diện ngay khi bấm Render
        if isinstance(voice_config, dict) and voice_config:
            clean_vcfg = {k: v for k, v in voice_config.items() if k != "performance_mode"}
            saved_vcfg = save_voice_config(clean_vcfg)
            log_info(
                "VOICE",
                f"🎙️ [RENDER SYNC] Áp dụng cấu hình Voice trực tiếp từ giao diện: "
                f"{saved_vcfg.get('selected_preset_id')} (Server={saved_vcfg.get('active_gpu_server')}, Speed={saved_vcfg.get('speedScale')}x, Pitch={saved_vcfg.get('pitchScale')})",
            )
        else:
            saved_vcfg = load_voice_config()

        for j in jobs:
            if not isinstance(j.get("voice_config"), dict):
                j["voice_config"] = dict(saved_vcfg)

        with self.lock:
            if self.is_running:
                existing_names = {j.get("name") for j in self.pending_jobs if j.get("name")} | set(self.active_projects)
                added_cnt = 0
                for j in jobs:
                    jname = j.get("name")
                    if jname and jname not in existing_names:
                        self.pending_jobs.append(j)
                        existing_names.add(jname)
                        added_cnt += 1
                if added_cnt > 0:
                    self.state["batch_total"] = self.state.get("batch_total", 1) + added_cnt
                    log_info(
                        f"⚡ [AUTO-BALANCER] Đã thêm {added_cnt} video vào Pool Đa Luồng (Tổng hàng đợi: {self.state['batch_total']}). Bộ điều phối sẽ tự động đẩy lên ~90% GPU/CPU!",
                        category="RENDER",
                    )
                return True

            self.is_running = True
            self.should_stop = False
            self.pending_jobs = list(jobs)
            self.active_projects.clear()

            save_base = Path(output_dir) if output_dir and output_dir.strip() else self.default_projects_dir
            save_base.mkdir(parents=True, exist_ok=True)

            first_name = jobs[0].get("name", "video_01")
            self.state = {
                "status": "running",
                "stage": "init",
                "progress": 1.0,
                "message": f"⚡ Khởi động Bộ Điều Phối Đa Luồng (Mục tiêu ~90% GPU/CPU) cho {len(jobs)} video...",
                "batch_total": len(jobs),
                "batch_current": 1,
                "current_project": first_name,
                "start_time": time.time(),
                "elapsed_seconds": 0,
                "results": [],
                "error": None,
                "hardware_load": self.resource_balancer.get_metrics(force_refresh=True),
            }

        log_info(
            f"🚀 Khởi chạy Bộ Điều Phối Đa Luồng (Auto-Scale 90% GPU/CPU) cho {len(jobs)} dự án "
            f"(Độ phân giải: {resolution}, FPS: {fps}, Voice: {saved_vcfg.get('selected_preset_id')} {saved_vcfg.get('speedScale')}x).",
            category="RENDER",
        )

        thread = threading.Thread(
            target=self._run_batch,
            args=(
                save_base,
                channel_name,
                resolution,
                fps,
                stock_selection,
                bgm_path,
                bgm_volume,
                delete_used_stocks,
                auto_ensure_stock_hours,
                target_stock_hours,
            ),
            daemon=True,
        )
        thread.start()
        return True

    def _synthesize_project_voice(
        self,
        proj_name: str,
        script_text: str,
        assets_dir: Path,
        v_cfg: Dict[str, Any],
        voice_cb: Callable[[float, str], None],
    ) -> Dict[str, Any]:
        """Tổng hợp Voice & Subtitles trên đúng Server GPU đang được chọn (Server 1 VOICEVOX GPU hoặc Server 2 OmniVoice CUDA GPU)."""
        engine_mode = str(v_cfg.get("engine_mode") or "voicevox").lower()
        active_srv = str(v_cfg.get("active_gpu_server") or "voicevox_gpu").lower()
        preset_id = str(v_cfg.get("selected_preset_id") or "Drama")
        speaker_id = int(v_cfg.get("speaker_id", 13))
        current_sig = compute_voice_signature(v_cfg)

        if active_srv == "voicevox_gpu" and engine_mode == "voicevox" and speaker_id >= 0:
            log_info(
                f"⚡ [SERVER 1: VOICEVOX GPU] Tổng hợp giọng [{preset_id} • Speed={v_cfg.get('speedScale')}x • Pitch={v_cfg.get('pitchScale')}] cho '{proj_name}'...",
                category="VOICE",
                project_id=proj_name,
            )
            return self.voicevox_service.generate_full_voice_and_subtitles(
                script_text=script_text,
                output_dir=assets_dir,
                voice_config=v_cfg,
                progress_callback=voice_cb,
            )
        else:
            ref_wav_name = str(v_cfg.get("ref_wav") or "Drama.wav")
            ref_wav_path = self.voice_service.voices_dir / ref_wav_name
            log_info(
                f"🧬 [SERVER 2: OMNIVOICE CUDA GPU] Tổng hợp giọng Clone [{preset_id} - {ref_wav_name}] cho '{proj_name}'...",
                category="VOICE",
                project_id=proj_name,
            )
            res = self.voice_service.generate_full_voice_and_subtitles(
                script_text=script_text,
                output_dir=assets_dir,
                ref_voice=str(ref_wav_path) if ref_wav_path.exists() else None,
                progress_callback=voice_cb,
            )
            try:
                (assets_dir / "voice_signature.json").write_text(
                    json.dumps(
                        {
                            "signature": current_sig,
                            "selected_preset_id": preset_id,
                            "engine_mode": "omnivoice",
                            "ref_wav": ref_wav_name,
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception:
                pass
            return res

    def _run_batch(
        self,
        save_base: Path,
        channel_name: str,
        resolution: str,
        fps: int,
        stock_selection: str,
        bgm_path: Optional[str],
        bgm_volume: float,
        delete_used_stocks: bool = True,
        auto_ensure_stock_hours: bool = True,
        target_stock_hours: float = 30.0,
    ):
        completed_results: List[Dict[str, Any]] = []
        failed_projects: List[str] = []
        allocated_stock_ids: set[str] = set()
        job_counter = 0
        progress_map: Dict[str, float] = {}

        # KHÔNG GIỚI HẠN SỐ LUỒNG: Tự động mở thêm luồng song song liên tục miễn là CPU < 90% và GPU < 90%
        spawn_gate_lock = threading.Lock()

        try:
            # 0. Đảm bảo Server Voice GPU đang chọn đã bật sẵn sàng trên VRAM
            init_vcfg = load_voice_config()
            self.activate_gpu_voice_server(init_vcfg.get("active_gpu_server", "voicevox_gpu"))

            # Kiểm tra nhanh kho Stock 1 lần ở đầu hàng đợi
            st_check = self.stock_manager.get_all_stocks()
            avail_cnt = st_check.get("available_count", 0)
            curr_h = st_check.get("available_raw_hours", 0.0)
            if avail_cnt == 0 or (auto_ensure_stock_hours and curr_h < min(1.0, target_stock_hours)):
                log_info(
                    f"Kho Stock hiện có {avail_cnt} video ({curr_h:.1f}h). Đang tự động tải bổ sung Stock từ YouTube...",
                    category="STOCK",
                )
                self._notify(
                    f"Kho Stock hiện có {curr_h:.1f}h. Đang tải bổ sung video Stock...",
                    2.0,
                    "stock_download",
                )
                try:
                    self.stock_manager.ensure_minimum_stock_hours(
                        target_hours=max(1.5, min(target_stock_hours, 3.0)) if avail_cnt == 0 else target_stock_hours,
                        slice_minutes=30,
                        progress_callback=lambda pct, msg: self._notify(f"📥 {msg}", 3.0, "stock_download"),
                    )
                except Exception as stock_dl_err:
                    log_warn(f"Lưu ý khi tải bù Stock tự động: {stock_dl_err}.", category="STOCK")

            def _update_overall_progress(latest_msg: str, stage_name: str):
                with self.lock:
                    total_j = max(1, self.state.get("batch_total", 1))
                    sum_pct = sum(progress_map.values())
                    overall = min(99.5, max(1.0, round(sum_pct / float(total_j), 1)))
                    active_cnt = len(self.active_projects)
                    done_cnt = len(completed_results)
                    pend_cnt = len(self.pending_jobs)
                hw = self.resource_balancer.get_metrics(force_refresh=False)
                summary_header = (
                    f"⚡ Đa luồng đang chạy: {active_cnt} video song song • "
                    f"Đã xong: {done_cnt}/{total_j} video (Chờ: {pend_cnt}) | "
                    f"GPU {hw['gpu_percent']:.0f}% • CPU {hw['cpu_percent']:.0f}%"
                )
                self._notify(summary_header, overall, stage_name)

            def _process_single_job(job: Dict[str, Any], job_num: int):
                proj_name = job.get("name") or f"drama_nhat_{time.strftime('%Y%m%d_%H%M%S')}_{job_num}"
                proj_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in proj_name).strip("_")
                script_text = (job.get("script_text") or "").strip()
                proj_dir = save_base / proj_name

                with self.lock:
                    self._ensure_hot_reload_compat()
                    self.active_projects.add(proj_name)
                    self.active_job_map[proj_name] = {"job": job, "job_num": job_num}
                    self.state["current_project"] = ", ".join(sorted(self.active_projects))
                    progress_map[proj_name] = 1.0
                self._set_project_live_detail(
                    proj_name=proj_name,
                    stage="init",
                    stage_label="🚀 Khởi tạo",
                    progress=1.0,
                    detail="Đang đọc kịch bản & khởi tạo luồng sản xuất...",
                    job_num=job_num,
                )
                _update_overall_progress("", "init")

                try:
                    if not script_text:
                        for cand_script in (
                            proj_dir / "script_clean.txt",
                            proj_dir / "renders" / f"{proj_name}_KICH_BAN.txt",
                            proj_dir / "script.txt",
                        ):
                            if cand_script.exists():
                                try:
                                    script_text = cand_script.read_text(encoding="utf-8").strip()
                                    if script_text:
                                        break
                                except Exception:
                                    pass

                    if not script_text:
                        msg_skip = f"Bỏ qua '{proj_name}' vì chưa có nội dung kịch bản tiếng Nhật."
                        log_warn(msg_skip, category="RENDER", project_id=proj_name)
                        self._update_job_card_status(proj_name, "ERROR", f"❌ {msg_skip}")
                        with self.lock:
                            failed_projects.append(f"{proj_name}: Chưa có kịch bản")
                            progress_map[proj_name] = 100.0
                        return

                    # Quét và xóa tự động 100% các dòng [LOCKED_TITLE] / Metadata bị rò rỉ trước khi tạo Voice & Render Video
                    cleaned_script_text, leaked_lines = strip_leaked_titles_and_metadata(script_text)
                    if leaked_lines:
                        script_text = cleaned_script_text
                        sample_leak = " | ".join([ln[:55] for ln in leaked_lines[:2]])
                        log_warn(
                            f"🛡️ [Agent Kiểm Tra Kịch Bản] Đã phát hiện & xóa tự động {len(leaked_lines)} dòng [LOCKED_TITLE]/Metadata bị rò rỉ trong '{proj_name}' trước khi tạo Voice/Video: {sample_leak}",
                            category="RENDER",
                            project_id=proj_name,
                        )
                        try:
                            for clean_target in (
                                proj_dir / "script_clean.txt",
                                proj_dir / "renders" / f"{proj_name}_KICH_BAN.txt",
                                proj_dir / "part_a.txt",
                                proj_dir / "part_b.txt",
                                proj_dir / "part_c.txt",
                            ):
                                if clean_target.exists():
                                    ct_raw = clean_target.read_text(encoding="utf-8", errors="ignore")
                                    ct_clean, ct_rem = strip_leaked_titles_and_metadata(ct_raw)
                                    if ct_rem and ct_clean:
                                        clean_target.write_text(ct_clean, encoding="utf-8")
                        except Exception:
                            pass

                    # Luôn đọc cấu hình Voice mới nhất (ưu tiên cấu hình đi kèm job hoặc vừa chọn trên UI)
                    v_cfg = load_voice_config()
                    if isinstance(job.get("voice_config"), dict) and job["voice_config"]:
                        v_cfg.update(job["voice_config"])
                    current_sig = compute_voice_signature(v_cfg)
                    preset_id = str(v_cfg.get("selected_preset_id") or "Drama")
                    speed_val = float(v_cfg.get("speedScale", 0.97))

                    log_info(
                        f"🎬 [LUỒNG #{job_num}] Bắt đầu xử lý '{proj_name}' ({len(script_text):,} chữ) với giọng [{preset_id} • {speed_val}x]...",
                        category="RENDER",
                        project_id=proj_name,
                    )
                    self._update_job_card_status(
                        proj_name,
                        "VIDEO_RENDERING",
                        f"🎙️ Đang chuẩn bị tạo Voice GPU [{preset_id} • {speed_val}x]...",
                    )

                    proj_dir.mkdir(parents=True, exist_ok=True)
                    assets_dir = proj_dir / "assets"
                    assets_dir.mkdir(parents=True, exist_ok=True)
                    renders_dir = proj_dir / "renders"
                    renders_dir.mkdir(parents=True, exist_ok=True)
                    (proj_dir / "script.txt").write_text(script_text, encoding="utf-8")

                    # ==========================================================
                    # GIAI ĐOẠN 1: TẠO VOICE GPU & SUBTITLES (KIỂM TRA CHÍNH XÁC CHỮ KÝ GIỌNG MỚI)
                    # ==========================================================
                    existing_master_wav = assets_dir / "master_voice.wav"
                    existing_srt = assets_dir / "subtitles.srt"
                    existing_ts = assets_dir / "TIMESTAMPS.txt"
                    sig_file = assets_dir / "voice_signature.json"

                    saved_sig = ""
                    if sig_file.exists():
                        try:
                            saved_sig = json.loads(sig_file.read_text(encoding="utf-8")).get("signature", "")
                        except Exception:
                            saved_sig = ""

                    # Kiểm tra xem subtitles.srt cũ có bị dính LOCKED_TITLE / SELECTED_TITLE không
                    srt_has_leaked_meta = False
                    if existing_srt.exists():
                        try:
                            srt_txt_check = existing_srt.read_text(encoding="utf-8", errors="ignore")
                            if "LOCKED_TITLE" in srt_txt_check or "SELECTED_TITLE" in srt_txt_check or "日本語脚本" in srt_txt_check:
                                srt_has_leaked_meta = True
                                log_warn(
                                    f"🛡️ [{proj_name}] Phát hiện phụ đề/voice cũ có chứa [LOCKED_TITLE]/Metadata -> Tự động ghép lại Voice & Phụ đề sạch!",
                                    category="VOICE",
                                    project_id=proj_name,
                                )
                        except Exception:
                            pass

                    # Chỉ tái sử dụng master_voice.wav nếu CÙNG CHỮ KÝ GIỌNG (hoặc chưa có file chữ ký), KHÔNG dính LOCKED_TITLE VÀ đủ thời lượng tương ứng độ dài kịch bản!
                    reuse_wav_dur = 0.0
                    min_expected_wav_dur = max(120.0, float(len(script_text)) * 0.08) if len(script_text) >= 5000 else 15.0
                    if (
                        existing_master_wav.exists()
                        and existing_master_wav.stat().st_size > 500_000
                        and existing_srt.exists()
                        and existing_srt.stat().st_size > 200
                        and not srt_has_leaked_meta
                        and not leaked_lines
                        and (not saved_sig or saved_sig == current_sig)
                        and not job.get("force_regenerate_voice")
                    ):
                        try:
                            import wave
                            with wave.open(str(existing_master_wav), "rb") as wf:
                                reuse_wav_dur = wf.getnframes() / float(wf.getframerate() or 24000)
                        except Exception:
                            reuse_wav_dur = 0.0

                    can_reuse_voice = reuse_wav_dur >= min_expected_wav_dur

                    def voice_cb(pct, msg):
                        if self.should_stop:
                            raise InterruptedError("Đã dừng tạo Voice theo yêu cầu")
                        if proj_name in getattr(self, "paused_for_perf_downscale", set()):
                            raise InterruptedError("PERF_DOWNSCALE_YIELD")
                        job_pct = round(2.0 + (pct * 0.45), 1)
                        with self.lock:
                            progress_map[proj_name] = job_pct
                        self._set_project_live_detail(
                            proj_name=proj_name,
                            stage="voice",
                            stage_label=f"🎙️ Tạo Voice GPU [{preset_id}]",
                            progress=job_pct,
                            detail=f"Voice GPU ({pct:.0f}%): {msg}",
                            job_num=job_num,
                        )
                        _update_overall_progress(f"[{proj_name}] {msg}", "voice")
                        self._update_job_card_status(
                            proj_name,
                            "VIDEO_RENDERING",
                            f"🎙️ Voice GPU [{preset_id} {speed_val}x] ({pct:.0f}%): {msg[:48]}",
                        )

                    if can_reuse_voice:
                        dur_sec = reuse_wav_dur
                        log_info(
                            f"♻️ Khôi phục Voice [{preset_id} • {speed_val}x] có sẵn ({dur_sec/60:.1f} phút) cho '{proj_name}'.",
                            category="VOICE",
                            project_id=proj_name,
                        )
                        voice_res = {
                            "master_voice": str(existing_master_wav),
                            "subtitles_srt": str(existing_srt),
                            "timestamps_txt": str(existing_ts),
                            "total_duration": dur_sec,
                        }
                        with self.lock:
                            progress_map[proj_name] = 48.0
                        self._set_project_live_detail(
                            proj_name=proj_name,
                            stage="voice",
                            stage_label=f"♻️ Voice có sẵn [{preset_id}]",
                            progress=48.0,
                            detail=f"Khôi phục Voice [{preset_id}] ({dur_sec/60:.1f} phút)",
                            job_num=job_num,
                        )
                        _update_overall_progress(f"[{proj_name}] ♻️ Khôi phục Voice [{preset_id}] ({dur_sec/60:.1f} phút)", "voice")
                    else:
                        if existing_master_wav.exists():
                            if saved_sig != current_sig:
                                log_info(
                                    f"🔄 [{proj_name}] Phát hiện bạn đã chọn cấu hình Voice mới ({saved_sig or 'cũ'} -> {current_sig}). Đang tạo lại âm thanh bằng Voice mới trên GPU!",
                                    category="VOICE",
                                    project_id=proj_name,
                                )
                            else:
                                log_warn(
                                    f"⚠️ [{proj_name}] File master_voice.wav trước đó chưa đủ thời lượng ({reuse_wav_dur/60:.1f} phút). Đang tổng hợp tiếp các câu còn thiếu!",
                                    category="VOICE",
                                    project_id=proj_name,
                                )
                            try:
                                existing_master_wav.unlink()
                            except Exception:
                                pass

                        while not self.should_stop:
                            if proj_name in getattr(self, "paused_for_perf_downscale", set()):
                                raise InterruptedError("PERF_DOWNSCALE_YIELD")
                            with self.lock:
                                curr_v = self.active_voice_jobs
                            if self.resource_balancer.has_headroom_for_parallel_task(curr_v):
                                break
                            time.sleep(1.0)

                        if self.should_stop:
                            raise InterruptedError("Đã dừng tiến trình Render theo yêu cầu")
                        if proj_name in getattr(self, "paused_for_perf_downscale", set()):
                            raise InterruptedError("PERF_DOWNSCALE_YIELD")

                        with self.lock:
                            self.active_voice_jobs += 1
                        try:
                            voice_res = self._synthesize_project_voice(
                                proj_name=proj_name,
                                script_text=script_text,
                                assets_dir=assets_dir,
                                v_cfg=v_cfg,
                                voice_cb=voice_cb,
                            )
                        finally:
                            with self.lock:
                                self.active_voice_jobs = max(0, self.active_voice_jobs - 1)

                        log_info(
                            f"✅ Hoàn tất tạo Voice GPU [{preset_id} • {speed_val}x] & Phụ đề cho '{proj_name}' (Thời lượng: {voice_res.get('total_duration', 0)/60:.2f} phút).",
                            category="VOICE",
                            project_id=proj_name,
                        )

                    if self.should_stop:
                        raise InterruptedError("Đã dừng tiến trình Render theo yêu cầu")
                    if proj_name in getattr(self, "paused_for_perf_downscale", set()):
                        raise InterruptedError("PERF_DOWNSCALE_YIELD")

                    # ==========================================================
                    # GIAI ĐOẠN 2: CẤP PHÁT VIDEO STOCK (KHÔI PHỤC STOCK CŨ NẾU ĐANG RENDER DỞ)
                    # ==========================================================
                    saved_stock_json = assets_dir / "selected_stock.json"
                    with self.stock_alloc_lock:
                        chosen_stock = None
                        max_uses = self.stock_manager.MAX_STOCK_USAGES

                        if saved_stock_json.exists() and stock_selection == "auto_unique":
                            try:
                                prev_st = json.loads(saved_stock_json.read_text(encoding="utf-8"))
                                if isinstance(prev_st, dict) and prev_st.get("abs_path") and os.path.exists(prev_st["abs_path"]):
                                    chosen_stock = prev_st
                                    log_info(
                                        f"♻️ Khôi phục đúng Stock Video cũ '{chosen_stock.get('name')}' để Render nối tiếp cho '{proj_name}'.",
                                        category="STOCK",
                                        project_id=proj_name,
                                    )
                            except Exception:
                                chosen_stock = None

                        if not chosen_stock:
                            if stock_selection == "auto_unique":
                                chosen_stock = self.stock_manager.get_best_available_stock(exclude_ids=allocated_stock_ids)
                            else:
                                stocks = self.stock_manager.get_all_stocks()["items"]
                                for s in stocks:
                                    if s["id"] == stock_selection or s["abs_path"] == stock_selection or s["rel_path"] == stock_selection:
                                        use1_key = f"{s['id']}::use1"
                                        use2_key = f"{s['id']}::use2"
                                        curr_uses = s.get("usage_count", 0)
                                        if curr_uses >= max_uses or s.get("status") == "used" or (use1_key in allocated_stock_ids and use2_key in allocated_stock_ids):
                                            raise RuntimeError(
                                                f"Video stock '{s['name']}' đã dùng hết {max_uses}/{max_uses} lần."
                                            )
                                        chosen_stock = dict(s)
                                        if curr_uses == 0 and use1_key not in allocated_stock_ids:
                                            chosen_stock["use_number"] = 1
                                            chosen_stock["flip_horizontal"] = False
                                            chosen_stock["zoom_factor"] = 1.0
                                            chosen_stock["transform_label"] = "Lần 1/2 (Bản Gốc 100%)"
                                            chosen_stock["slot_key"] = use1_key
                                        else:
                                            chosen_stock["use_number"] = 2
                                            chosen_stock["flip_horizontal"] = True
                                            chosen_stock["zoom_factor"] = 1.10
                                            chosen_stock["transform_label"] = "Lần 2/2 (Lật Video + Zoom 110%)"
                                            chosen_stock["slot_key"] = use2_key
                                        break

                        if not chosen_stock and stock_selection == "auto_unique":
                            log_info(
                                f"⚡ Kho STOOK vừa dùng hết các cuộn hiện có -> Tự động tải bù ngay 3.0 giờ Stock 720p mới (Pexels/Pixabay) cho '{proj_name}'...",
                                category="STOCK",
                                project_id=proj_name,
                            )
                            self._update_job_card_status(
                                proj_name,
                                "VIDEO_RENDERING",
                                "📥 Kho Stock vừa hết -> Đang tự động tải thêm cuộn Stock 720p mới...",
                            )
                            try:
                                self.stock_manager.ensure_minimum_stock_hours(
                                    target_hours=max(2.0, min(target_stock_hours, 4.0)),
                                    slice_minutes=30,
                                )
                                chosen_stock = self.stock_manager.get_best_available_stock(exclude_ids=allocated_stock_ids)
                            except Exception as e_rep:
                                log_warn(f"Lưu ý khi tải bù Stock giữa chừng: {e_rep}", category="STOCK", project_id=proj_name)

                        if not chosen_stock:
                            raise RuntimeError(
                                f"Kho STOOK ({self.stock_manager.stook_dir}) hiện không còn video khả dụng nào cho dự án '{proj_name}'."
                            )

                        slot_key = chosen_stock.get("slot_key", f"{chosen_stock['id']}::use{chosen_stock.get('use_number', 1)}")
                        allocated_stock_ids.add(slot_key)
                        try:
                            saved_stock_json.write_text(json.dumps(chosen_stock, ensure_ascii=False, indent=2), encoding="utf-8")
                        except Exception:
                            pass

                    use_number = chosen_stock.get("use_number", 1)
                    flip_horizontal = chosen_stock.get("flip_horizontal", False)
                    zoom_factor = chosen_stock.get("zoom_factor", 1.0)
                    transform_label = chosen_stock.get("transform_label", "Lần 1/2 (Bản Gốc 100%)")
                    stock_file = chosen_stock["abs_path"]

                    log_info(
                        f"Đã cấp phát Stock: {chosen_stock['name']} ({transform_label}) cho '{proj_name}'.",
                        category="STOCK",
                        project_id=proj_name,
                    )

                    # ==========================================================
                    # GIAI ĐOẠN 3: CÂN ĐỐI TÀI NGUYÊN ĐA LUỒNG (~90% GPU & CPU) & RENDER FFMPEG NVENC
                    # ==========================================================
                    self._set_project_live_detail(
                        proj_name=proj_name,
                        stage="stock",
                        stage_label="🎞️ Đã cấp phát Stock",
                        progress=50.0,
                        detail=f"Stock: {chosen_stock['name']} ({transform_label})",
                        job_num=job_num,
                    )
                    _update_overall_progress("", "stock")

                    while not self.should_stop:
                        if proj_name in getattr(self, "paused_for_perf_downscale", set()):
                            raise InterruptedError("PERF_DOWNSCALE_YIELD")
                        with self.lock:
                            curr_ff = self.active_ffmpeg_jobs
                        if self.resource_balancer.has_headroom_for_parallel_task(curr_ff):
                            break
                        self._set_project_live_detail(
                            proj_name=proj_name,
                            stage="waiting_gpu",
                            stage_label="⏳ Chờ tải GPU/CPU (<90%)",
                            progress=51.0,
                            detail="Đã tạo xong Voice! Đang đợi khoảng trống GPU/CPU (<90%) để ghép MP4...",
                            job_num=job_num,
                        )
                        _update_overall_progress("", "waiting_gpu")
                        self._update_job_card_status(
                            proj_name,
                            "VIDEO_RENDERING",
                            "⏳ Đã tạo xong Voice! Đang đợi khoảng trống GPU/CPU (<90%) để ghép MP4 đa luồng...",
                        )
                        time.sleep(1.5)

                    if self.should_stop:
                        raise InterruptedError("Đã dừng tiến trình Render theo yêu cầu")
                    if proj_name in getattr(self, "paused_for_perf_downscale", set()):
                        raise InterruptedError("PERF_DOWNSCALE_YIELD")

                    final_video = renders_dir / f"{proj_name}_master.mp4"
                    particles_path = str(self.root_dir / "assets" / "particles" / "star_particles_30s.mov")
                    fonts_dir = str(self.root_dir / "assets" / "fonts")

                    def render_cb(pct, msg):
                        if self.should_stop:
                            raise InterruptedError("Đã dừng Render Video theo yêu cầu")
                        if proj_name in getattr(self, "paused_for_perf_downscale", set()):
                            raise InterruptedError("PERF_DOWNSCALE_YIELD")
                        job_pct = round(52.0 + (pct * 0.44), 1)
                        with self.lock:
                            progress_map[proj_name] = job_pct
                        self._set_project_live_detail(
                            proj_name=proj_name,
                            stage="render",
                            stage_label="🎬 Render Video FFmpeg",
                            progress=job_pct,
                            detail=msg,
                            job_num=job_num,
                        )
                        _update_overall_progress(f"[{proj_name}] {msg}", "render")
                        self._update_job_card_status(
                            proj_name,
                            "VIDEO_RENDERING",
                            f"🎬 Đang Render MP4 [{preset_id}] ({pct:.0f}% — Chờ 100%)",
                        )

                    import backend.renderer as _renderer_mod
                    import backend.sync_checker as _sync_mod

                    with self.lock:
                        self.active_ffmpeg_jobs += 1
                    try:
                        max_video_sync_attempts = 2
                        sync_report = {}

                        for sync_attempt in range(1, max_video_sync_attempts + 1):
                            if sync_attempt > 1:
                                log_warn(
                                    f"Đang tự động tạo lại các câu Voice bị lệch bằng GPU và Render lại MP4 (Lần {sync_attempt}/{max_video_sync_attempts})...",
                                    category="RENDER",
                                    project_id=proj_name,
                                )
                                voice_res = self._synthesize_project_voice(
                                    proj_name=proj_name,
                                    script_text=script_text,
                                    assets_dir=assets_dir,
                                    v_cfg=v_cfg,
                                    voice_cb=voice_cb,
                                )

                            log_info(
                                f"🔥 Bắt đầu FFmpeg GPU Render 5 lớp ra file {final_video} (Lần {sync_attempt})...",
                                category="RENDER",
                                project_id=proj_name,
                            )
                            _renderer_mod.render_drama_nhat_video(
                                audio_path=voice_res["master_voice"],
                                subtitle_path=voice_res["subtitles_srt"],
                                stock_video_path=stock_file,
                                output_path=str(final_video),
                                channel_name=channel_name,
                                resolution=resolution,
                                fps=fps,
                                font_size=135,
                                outline=4.0,
                                flip_horizontal=flip_horizontal,
                                zoom_factor=zoom_factor,
                                particles_clip=particles_path if os.path.exists(particles_path) else None,
                                fonts_dir=fonts_dir if os.path.exists(fonts_dir) else None,
                                bgm_path=bgm_path,
                                bgm_volume=bgm_volume,
                                progress_callback=render_cb,
                                performance_mode=getattr(self, "performance_mode", "full_100"),
                            )

                            # Kiểm định nghiêm ngặt tính toàn vẹn & thời lượng của file MP4 vừa xuất
                            mp4_integrity = _sync_mod.validate_completed_mp4_file(
                                mp4_path=final_video,
                                master_wav_path=Path(voice_res["master_voice"]),
                                script_char_count=len(script_text),
                            )
                            if not mp4_integrity.get("valid"):
                                bad_reason = str(mp4_integrity.get("reason") or "File MP4 không hợp lệ")
                                if final_video.exists():
                                    try:
                                        final_video.unlink()
                                    except Exception:
                                        pass
                                if sync_attempt >= max_video_sync_attempts:
                                    raise RuntimeError(f"Kiểm định Video MP4 thất bại ({bad_reason}) — Hủy kết quả lỗi để Render lại!")
                                log_warn(
                                    f"Kiểm định MP4 lần {sync_attempt} phát hiện lỗi ({bad_reason}), đang thử Render lại...",
                                    category="RENDER",
                                    project_id=proj_name,
                                )
                                continue

                            sents_list = split_japanese_script(script_text)
                            sync_report = _sync_mod.verify_rendered_video_sync(
                                video_path=final_video,
                                master_wav_path=Path(voice_res["master_voice"]),
                                srt_path=Path(voice_res["subtitles_srt"]),
                                sentences=sents_list,
                                sentences_dir=assets_dir / "sentences",
                            )
                            try:
                                (proj_dir / "qa_video_sync_report.json").write_text(
                                    json.dumps(sync_report, ensure_ascii=False, indent=2),
                                    encoding="utf-8",
                                )
                            except Exception:
                                pass

                            if sync_report.get("passed"):
                                log_info(
                                    f"Kiểm định Sub-Voice ĐẠT 100% cho '{proj_name}' (Lệch MP4/Voice: {sync_report.get('drift_video_vs_voice_sec', 0):.3f}s).",
                                    category="RENDER",
                                    project_id=proj_name,
                                )
                                break
                            else:
                                issues_str = "; ".join(sync_report.get("issues", []))
                                log_warn(f"Kiểm định Sub-Voice lần {sync_attempt} chưa khớp: {issues_str}", category="RENDER", project_id=proj_name)
                                if sync_attempt < max_video_sync_attempts:
                                    redo_idxs = sync_report.get("sentence_audit", {}).get("redo_indices", [])
                                    for r_i in redo_idxs:
                                        bad_w = assets_dir / "sentences" / f"sentence_{r_i+1:04d}.wav"
                                        if bad_w.exists():
                                            try:
                                                bad_w.unlink()
                                            except Exception:
                                                pass
                                    if final_video.exists():
                                        try:
                                            final_video.unlink()
                                        except Exception:
                                            pass
                    finally:
                        with self.lock:
                            self.active_ffmpeg_jobs = max(0, self.active_ffmpeg_jobs - 1)

                    # Xác nhận lần cuối file MP4 tồn tại và hợp lệ 100% trước khi đánh dấu COMPLETED_VIDEO
                    final_check = _sync_mod.validate_completed_mp4_file(
                        mp4_path=final_video,
                        master_wav_path=Path(voice_res["master_voice"]),
                        script_char_count=len(script_text),
                    )
                    if not final_check.get("valid"):
                        if final_video.exists():
                            try:
                                final_video.unlink()
                            except Exception:
                                pass
                        raise RuntimeError(f"Video MP4 chưa hoàn chỉnh ({final_check.get('reason')}) — Không thể công nhận thành công!")

                    # 4. ĐÁNH DẤU LƯỢT DÙNG STOCK & TỰ ĐỘNG XÓA NGAY ĐỂ GIẢI PHÓNG BỘ NHỚ
                    with self.stock_alloc_lock:
                        mode_tag = "Lần 1: Bản gốc"
                        new_usage_count = self.stock_manager.mark_as_used(chosen_stock["id"], f"{proj_name} ({mode_tag})")

                        if final_video.exists() and final_video.stat().st_size > 1024 * 1024:
                            try:
                                freed = self.stock_manager.delete_used_stock_file(chosen_stock["id"])
                                if freed > 0:
                                    log_info(
                                        f"🗑️ Đã tự động xóa ngay file stock '{chosen_stock['name']}' sau khi dùng xong (Giải phóng {freed} MB bộ nhớ).",
                                        category="STOCK",
                                        project_id=proj_name,
                                    )
                            except Exception as e:
                                log_warn(f"Không thể xóa file stock sau khi render: {e}", category="STOCK", project_id=proj_name)

                    # 5. Xuất file SEO & Kịch bản vào cùng thư mục renders
                    timestamps_content = ""
                    if os.path.exists(voice_res["timestamps_txt"]):
                        with open(voice_res["timestamps_txt"], "r", encoding="utf-8") as tf:
                            timestamps_content = tf.read()

                    seo_file = proj_dir / f"{proj_name}_seo.md"
                    seo_tech_block = (
                        f"# GÓI SEO YOUTUBE & THÔNG SỐ VIDEO: {proj_name}\n\n"
                        f"- 🏷️ Kênh: {channel_name}\n"
                        f"- 🎙️ Giọng đọc: {preset_id} ({speed_val}x)\n"
                        f"- 📐 Thông số render: {resolution} | {fps} FPS | Chế độ Stock: {transform_label}\n"
                        f"- ⏱️ Thời lượng: {voice_res['total_duration']/60:.2f} phút\n\n"
                        f"## 📋 Chapters / Timestamps:\n```\n{timestamps_content}```\n"
                    )
                    seo_file.write_text(seo_tech_block, encoding="utf-8")

                    seo_dest = renders_dir / f"{proj_name}_SEO.txt"
                    script_dest = renders_dir / f"{proj_name}_KICH_BAN.txt"
                    try:
                        script_dest.write_text(script_text, encoding="utf-8")
                        master_seo_src = proj_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"
                        if master_seo_src.exists():
                            full_seo_txt = master_seo_src.read_text(encoding="utf-8")
                            if "Chapters / Timestamps" not in full_seo_txt and timestamps_content:
                                full_seo_txt += (
                                    "\n\n================================================================================\n"
                                    "⏱️ TIMESTAMPS / CHAPTERS YOUTUBE (TỰ ĐỘNG TÍNH THEO GIỌNG ĐỌC)\n"
                                    "================================================================================\n"
                                    f"{timestamps_content}\n"
                                )
                            seo_dest.write_text(full_seo_txt, encoding="utf-8")
                        elif job.get("seo_text"):
                            seo_dest.write_text(str(job["seo_text"]), encoding="utf-8")
                        else:
                            seo_dest.write_text(seo_tech_block, encoding="utf-8")
                    except Exception as copy_err:
                        log_warn(f"Lưu ý khi sao chép Kịch bản & SEO sang renders: {copy_err}", category="RENDER", project_id=proj_name)

                    job_result = {
                        "project_name": proj_name,
                        "project_dir": str(renders_dir),
                        "final_video": str(final_video),
                        "master_voice": voice_res["master_voice"],
                        "subtitles_srt": voice_res["subtitles_srt"],
                        "timestamps_txt": voice_res["timestamps_txt"],
                        "seo_pack": str(seo_dest),
                        "script_file": str(script_dest),
                        "duration": voice_res["total_duration"],
                        "duration_formatted": f"{int(voice_res['total_duration'] // 60):02d}:{int(voice_res['total_duration'] % 60):02d}",
                        "resolution": resolution,
                        "fps": fps,
                        "voice_preset": preset_id,
                        "stock_used": chosen_stock["name"],
                        "stock_use_number": use_number,
                        "stock_transform": transform_label,
                    }
                    with self.lock:
                        completed_results.append(job_result)
                        self.state["results"] = list(completed_results)
                        progress_map[proj_name] = 100.0

                    self._update_job_card_status(
                        proj_name,
                        "COMPLETED_VIDEO",
                        f"✅ Đã xuất xong Video MP4 [{preset_id}] ({job_result['duration_formatted']}) tại renders/{final_video.name}",
                    )
                    _update_overall_progress(f"🎉 Hoàn tất xuất MP4 cho {proj_name} ({job_result['duration_formatted']})!", "completed_one")
                    log_info(
                        f"🎉 XUẤT VIDEO THÀNH CÔNG 100%: {final_video} (Giọng: {preset_id} {speed_val}x • Thời lượng: {job_result['duration_formatted']})",
                        category="RENDER",
                        project_id=proj_name,
                    )

                except InterruptedError as yield_err:
                    try:
                        r_dir = proj_dir / "renders"
                        if r_dir.exists():
                            for tmp_f in r_dir.glob("*_rendering_tmp.mp4"):
                                try:
                                    tmp_f.unlink()
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    if "PERF_DOWNSCALE_YIELD" in str(yield_err):
                        with self.lock:
                            self.paused_for_perf_downscale.discard(proj_name)
                            existing_q = {j.get("name") for j in self.pending_jobs if j.get("name")}
                            if proj_name not in existing_q:
                                self.pending_jobs.insert(0, job)
                            progress_map.pop(proj_name, None)
                        self._update_job_card_status(
                            proj_name,
                            "VIDEO_QUEUED",
                            "⏳ Đã lưu Checkpoint & tạm nhường luồng (Chế độ 70% chạy tối đa 3 video song song)",
                        )
                        log_info(
                            f"💼 [{proj_name}] Đã lưu Checkpoint & tạm xếp hàng chờ để đảm bảo Chế độ 70% chạy tối đa 3 video song song!",
                            category="RENDER",
                            project_id=proj_name,
                        )
                    else:
                        ckpt_msg = "⏸️ Đã dừng theo yêu cầu (Đã lưu Checkpoint để chạy tiếp)"
                        try:
                            import backend.renderer as _r_ckpt
                            ckpt_info = _r_ckpt.get_saved_render_progress(str(proj_dir / "renders" / f"{proj_name}_master.mp4"))
                            if ckpt_info.get("has_checkpoint"):
                                ckpt_pct = ckpt_info.get("percent", 0.0)
                                ckpt_sec = ckpt_info.get("completed_sec", 0.0)
                                ckpt_msg = f"⏸️ Đã lưu Checkpoint Render {ckpt_pct}% ({ckpt_sec:.0f}s) — Bấm Render để chạy tiếp đoạn còn lại!"
                        except Exception:
                            pass
                        self._update_job_card_status(proj_name, "ERROR_VIDEO", ckpt_msg)
                        with self.lock:
                            failed_projects.append(f"{proj_name}: {yield_err}")
                            progress_map[proj_name] = 100.0

                except Exception as job_err:
                    # Dọn sạch mọi file MP4 dở dang / lỗi trong thư mục renders để tuyệt đối không bao giờ bị nhận nhầm là thành công
                    try:
                        r_dir = proj_dir / "renders"
                        if r_dir.exists():
                            for tmp_f in r_dir.glob("*_rendering_tmp.mp4"):
                                try:
                                    tmp_f.unlink()
                                except Exception:
                                    pass
                            cand_mp4 = r_dir / f"{proj_name}_master.mp4"
                            if cand_mp4.exists():
                                import backend.sync_checker as _sc_clean
                                chk = _sc_clean.validate_completed_mp4_file(
                                    cand_mp4,
                                    master_wav_path=proj_dir / "assets" / "master_voice.wav",
                                    script_char_count=len(script_text),
                                )
                                if not chk.get("valid"):
                                    cand_mp4.unlink()
                    except Exception:
                        pass

                    log_error(
                        f"Lỗi hoặc ngắt giữa chừng khi tạo Voice/Render cho dự án '{proj_name}': {job_err}",
                        category="RENDER",
                        project_id=proj_name,
                        exc=job_err,
                    )
                    ckpt_msg = f"❌ Chưa xong / Lỗi Render (Chờ chạy lại): {str(job_err)[:85]}"
                    try:
                        import backend.renderer as _r_ckpt
                        ckpt_info = _r_ckpt.get_saved_render_progress(str(proj_dir / "renders" / f"{proj_name}_master.mp4"))
                        if ckpt_info.get("has_checkpoint"):
                            ckpt_pct = ckpt_info.get("percent", 0.0)
                            ckpt_sec = ckpt_info.get("completed_sec", 0.0)
                            ckpt_msg = f"⏸️ Đã lưu Checkpoint Render {ckpt_pct}% ({ckpt_sec:.0f}s) — Bấm Render để chạy tiếp đoạn còn lại!"
                        elif (proj_dir / "assets" / "master_voice.wav").exists():
                            ckpt_msg = "⏸️ Đã tạo xong 100% Voice GPU — Bấm Render để ghép tiếp Video MP4!"
                    except Exception:
                        pass
                    self._update_job_card_status(
                        proj_name,
                        "ERROR_VIDEO",
                        ckpt_msg,
                    )
                    with self.lock:
                        failed_projects.append(f"{proj_name}: {job_err}")
                        progress_map[proj_name] = 100.0
                finally:
                    with self.lock:
                        self.active_projects.discard(proj_name)
                        self.active_jobs_detail.pop(proj_name, None)
                        if hasattr(self, "active_job_map"):
                            self.active_job_map.pop(proj_name, None)
                        if hasattr(self, "paused_for_perf_downscale"):
                            self.paused_for_perf_downscale.discard(proj_name)
                        self.state["current_project"] = ", ".join(sorted(self.active_projects))
                    if self.is_running and not self.should_stop:
                        _update_overall_progress("", "running")

            # ==================================================================
            # VÒNG LẶP ĐIỀU PHỐI ĐA LUỒNG ĐỘNG (DYNAMIC MULTI-VIDEO DISPATCHER)
            # Cân đối thông minh:
            # - Chế độ Full 100%: Tối đa 5 video song song (~90% GPU/CPU)
            # - Chế độ 70%: Khóa cứng TỐI ĐA 3 video song song (~70% GPU/CPU)
            # ==================================================================
            active_threads: List[threading.Thread] = []

            while True:
                active_threads = [t for t in active_threads if t.is_alive()]

                with self.lock:
                    if self.should_stop:
                        break
                    has_pending = len(self.pending_jobs) > 0

                if not has_pending and not active_threads:
                    for t in active_threads:
                        t.join()
                    with self.lock:
                        if not self.pending_jobs or self.should_stop:
                            if completed_results and not failed_projects:
                                self.state["status"] = "completed"
                                self.state["progress"] = 100.0
                                self.state["message"] = f"🎉 Hoàn tất xuất thành công 100% ({len(completed_results)} video MP4)!"
                            elif completed_results and failed_projects:
                                self.state["status"] = "completed"
                                self.state["progress"] = 100.0
                                self.state["message"] = (
                                    f"⚠️ Đã xuất xong {len(completed_results)} video MP4 • "
                                    f"Có {len(failed_projects)} video lỗi/bị ngắt (Đã lọc vào mục '📦 Chưa Render' để chạy tiếp)"
                                )
                            else:
                                self.state["status"] = "error"
                                self.state["error"] = "; ".join(failed_projects)
                                self.state["message"] = (
                                    f"❌ Có {len(failed_projects)} video bị lỗi hoặc ngắt giữa chừng (Đã lọc vào '📦 Chưa Render' để render tiếp): "
                                    f"{failed_projects[0] if failed_projects else ''}"
                                )
                            self.state["results"] = completed_results
                            self.is_running = False
                            break
                        else:
                            # Có kịch bản mới vừa được AI viết xong và đẩy vào đúng lúc video trước hoàn tất -> chạy tiếp ngay!
                            continue

                # ĐIỀU PHỐI THEO CHẾ ĐỘ HIỆU SUẤT ĐỘNG (Full 100%: tối đa 5 video <90% CPU/GPU | Chế độ 70%: KHÓA CỨNG TỐI ĐA 3 VIDEO <70% CPU/GPU):
                self._ensure_hot_reload_compat()
                is_70_mode = (
                    getattr(self, "performance_mode", "full_100") == "work_70"
                    or os.environ.get("STUDIO_PERF_MODE") == "work_70"
                )
                max_concurrent_videos = 3 if is_70_mode else 5
                self.resource_balancer.max_concurrent_videos = max_concurrent_videos
                self.resource_balancer.target_max_percent = 70.0 if is_70_mode else 90.0
                self.resource_balancer.performance_mode = "work_70" if is_70_mode else "full_100"

                # Nếu đang chạy 5 video mà chuyển sang chế độ 70%, lập tức tạm dừng 2 video thừa (đã lưu Checkpoint) để chỉ giữ đúng 3 video chạy!
                if is_70_mode:
                    with self.lock:
                        if len(self.active_projects) > 3:
                            active_unpaused = [
                                p for p in self.active_projects
                                if p not in self.paused_for_perf_downscale
                            ]
                            if len(active_unpaused) > 3:
                                active_unpaused.sort(
                                    key=lambda p: int((self.active_job_map.get(p) or {}).get("job_num", 999999)),
                                    reverse=True,
                                )
                                for p_yield in active_unpaused[: len(active_unpaused) - 3]:
                                    self.paused_for_perf_downscale.add(p_yield)

                if has_pending and len(active_threads) < max_concurrent_videos and len(self.active_projects) < max_concurrent_videos:
                    if len(active_threads) == 0:
                        can_dispatch = True
                    else:
                        try:
                            can_dispatch = self.resource_balancer.has_headroom_for_parallel_task(
                                len(active_threads),
                                max_concurrent=max_concurrent_videos,
                            )
                        except TypeError:
                            can_dispatch = (
                                len(active_threads) < max_concurrent_videos
                                and self.resource_balancer.has_headroom_for_parallel_task(len(active_threads))
                            )
                    if can_dispatch:
                        with self.lock:
                            if self.pending_jobs and not self.should_stop and len(self.active_projects) < max_concurrent_videos:
                                next_job = self.pending_jobs.pop(0)
                                job_counter += 1
                                total_jobs = max(
                                    len(completed_results) + len(self.active_projects) + 1 + len(self.pending_jobs),
                                    self.state.get("batch_total", 1),
                                )
                                self.state["batch_total"] = total_jobs
                                self.state["batch_current"] = len(completed_results) + len(self.active_projects) + 1
                            else:
                                next_job = None

                        if next_job is not None:
                            t_worker = threading.Thread(
                                target=_process_single_job,
                                args=(next_job, job_counter),
                                daemon=True,
                            )
                            t_worker.start()
                            active_threads.append(t_worker)
                            # Chờ 2.5s để luồng mới kịp ăn tải CPU/GPU thực tế trước khi xét mở luồng tiếp theo
                            time.sleep(2.5)
                            continue

                time.sleep(0.8)

            for t in active_threads:
                t.join()

            with self.lock:
                self.is_running = False

            self._notify()

        except Exception as e:
            log_error(f"Lỗi nghiêm trọng trong luồng Batch Pipeline: {e}", category="RENDER", exc=e)
            with self.lock:
                self.state["status"] = "error"
                self.state["error"] = str(e)
                self.state["message"] = f"❌ Lỗi hệ thống Render: {str(e)}"
                self.is_running = False
            self._notify()


def _auto_patch_live_instances_on_reload():
    """
    Tự động chạy ngay khi `importlib.reload(backend.pipeline)` được gọi trong quá trình Update OTA:
    1. Nâng cấp trực tiếp các instance `ProductionPipeline`, `HardwareResourceBalancer`, `VoicevoxStandaloneService`
       đang sống trong RAM của máy khách.
    2. Tự động gắn route `/api/performance-mode` vào FastAPI `app` đang chạy (nếu máy khách bật app từ bản V1.0.0 cũ)
       mà không cần tắt mở lại ứng dụng!
    """
    try:
        import gc
        live_pipelines: List[Any] = []
        live_balancers: List[Any] = []
        live_fastapi_apps: List[Any] = []

        for obj in gc.get_objects():
            try:
                cls_name = type(obj).__name__
                if cls_name == "HardwareResourceBalancer":
                    live_balancers.append(obj)
                elif cls_name == "ProductionPipeline":
                    live_pipelines.append(obj)
                elif cls_name == "FastAPI":
                    live_fastapi_apps.append(obj)
            except Exception:
                continue

        for rb in live_balancers:
            try:
                for k, v in vars(HardwareResourceBalancer).items():
                    if not k.startswith("__"):
                        try:
                            setattr(rb.__class__, k, v)
                        except Exception:
                            pass
                try:
                    rb.__class__ = HardwareResourceBalancer
                except Exception:
                    pass
            except Exception:
                pass

        for p_inst in live_pipelines:
            try:
                for k, v in vars(ProductionPipeline).items():
                    if not k.startswith("__"):
                        try:
                            setattr(p_inst.__class__, k, v)
                        except Exception:
                            pass
                try:
                    p_inst.__class__ = ProductionPipeline
                except Exception:
                    pass
                if hasattr(p_inst, "_ensure_hot_reload_compat"):
                    p_inst._ensure_hot_reload_compat()
                if getattr(p_inst, "performance_mode", "full_100") == "work_70":
                    p_inst.set_performance_mode("work_70", persist=False)
            except Exception:
                pass

        # Tự động tiêm route /api/performance-mode vào FastAPI app nếu server cũ (V1.0.0) chưa có route này
        if live_pipelines and live_fastapi_apps:
            main_pipeline = live_pipelines[0]
            from starlette.routing import Route
            from starlette.responses import JSONResponse

            async def _dynamic_perf_mode_handler(request):
                if request.method == "POST":
                    try:
                        body = await request.json()
                    except Exception:
                        body = {}
                    mode_val = body.get("mode", "full_100") if isinstance(body, dict) else "full_100"
                    info = main_pipeline.set_performance_mode(mode_val, persist=True)
                    return JSONResponse({"success": True, **info})
                return JSONResponse({"success": True, **main_pipeline.get_performance_mode_info()})

            for f_app in live_fastapi_apps:
                try:
                    routes_list = getattr(getattr(f_app, "router", None), "routes", None)
                    if isinstance(routes_list, list):
                        existing_paths = {getattr(r, "path", "") for r in routes_list}
                        if "/api/performance-mode" not in existing_paths:
                            routes_list.insert(
                                0,
                                Route(
                                    "/api/performance-mode",
                                    endpoint=_dynamic_perf_mode_handler,
                                    methods=["GET", "POST"],
                                ),
                            )
                except Exception:
                    pass
    except Exception:
        pass


_auto_patch_live_instances_on_reload()
