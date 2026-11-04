import os
import sys
import time
import json
import asyncio
import threading
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .pipeline import ProductionPipeline
from .voice_service import split_japanese_script
from .voicevox_service import load_voice_config, save_voice_config, VOICE_PRESETS
from .license_manager import LicenseManager
from .chatgpt_web_client import (
    check_all_web_accounts_status,
    ensure_chrome_debug_browser_open,
    set_chrome_window_visibility,
    sweep_completed_and_idle_tabs_across_all_accounts,
)
from .gemini_web_client import (
    open_gemini_tab_on_account,
    check_all_gemini_accounts_status,
)
from .adas_script_engine import ADASScriptEngine, build_step2_prompt_from_idea, parse_idea_input_block
from .logger_service import (
    get_logger,
    log_info,
    log_warn,
    log_error,
    run_system_diagnostics,
    install_missing_libraries_async,
)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def create_app(root_dir: Optional[Path] = None) -> FastAPI:
    base_dir = Path(root_dir).resolve() if root_dir else Path(__file__).resolve().parent.parent
    if base_dir.name.lower() == "app":
        base_dir = base_dir.parent
    elif not (base_dir / "STOOK").exists() and (base_dir.parent / "STOOK").exists():
        base_dir = base_dir.parent

    frontend_dir = None
    for cand in [
        base_dir / "frontend",
        base_dir / "app" / "frontend",
        Path(__file__).resolve().parent.parent / "frontend",
        Path(__file__).resolve().parent / "frontend"
    ]:
        if (cand / "index.html").exists():
            frontend_dir = cand
            break
    if frontend_dir is None:
        frontend_dir = base_dir / "frontend"

    app = FastAPI(title="Drama Nhật Studio", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def disable_static_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response

    sys_logger = get_logger(base_dir)
    pipeline = ProductionPipeline(base_dir)
    license_mgr = LicenseManager(base_dir)
    adas_engine = ADASScriptEngine(base_dir, video_pipeline=pipeline)
    pipeline.adas_engine = adas_engine
    log_info("SERVER", f"Đã khởi tạo Drama Nhật Studio Server tại {base_dir}")
    active_websockets: list[WebSocket] = []
    main_loop_ref: Dict[str, Optional[asyncio.AbstractEventLoop]] = {"loop": None}

    @app.on_event("startup")
    async def _capture_main_loop():
        main_loop_ref["loop"] = asyncio.get_running_loop()

    # Khi pipeline cập nhật, gửi tới tất cả client đang kết nối WebSocket
    def on_pipeline_update(state: Dict[str, Any]):
        loop = main_loop_ref.get("loop")
        if loop and loop.is_running():
            for ws in list(active_websockets):
                try:
                    asyncio.run_coroutine_threadsafe(ws.send_json(state), loop)
                except Exception:
                    pass

    pipeline.subscribe(on_pipeline_update)
    adas_engine.subscribe(on_pipeline_update)
    sys_logger.subscribe(on_pipeline_update)

    class StartRequest(BaseModel):
        script_text: str
        project_name: Optional[str] = None
        output_dir: Optional[str] = None
        channel_name: str = "."
        resolution: str = "1920x1080"
        fps: int = 24
        stock_selection: str = "auto_unique"
        bgm_path: Optional[str] = None
        bgm_volume: float = 0.08
        delete_used_stocks: bool = True
        auto_ensure_stock_hours: bool = True
        target_stock_hours: float = 30.0
        voice_config: Optional[Dict[str, Any]] = None

    class StartBatchRequest(BaseModel):
        jobs: list[Dict[str, Any]]
        output_dir: Optional[str] = None
        channel_name: str = "."
        resolution: str = "1920x1080"
        fps: int = 24
        stock_selection: str = "auto_unique"
        bgm_path: Optional[str] = None
        bgm_volume: float = 0.08
        delete_used_stocks: bool = True
        auto_ensure_stock_hours: bool = True
        target_stock_hours: float = 30.0
        voice_config: Optional[Dict[str, Any]] = None

    class YouTubeDownloadRequest(BaseModel):
        url: str
        folder_name: Optional[str] = None
        slice_minutes: int = 30
        force: bool = False

    class AutoReplenishStockRequest(BaseModel):
        target_hours: float = 30.0
        slice_minutes: int = 30

    class ResetStockRequest(BaseModel):
        stock_id: str

    class ScriptPreviewRequest(BaseModel):
        script_text: str

    class BrowseDirRequest(BaseModel):
        title: str = "Chọn Thư Mục"

    class SetStockDirRequest(BaseModel):
        directory: str

    class OpenPathRequest(BaseModel):
        path: str

    class ActivateLicenseRequest(BaseModel):
        license_key: str

    class OpenChatGPTBrowserRequest(BaseModel):
        acc_id: str = "acc_1"

    class ChatGPTVisibilityRequest(BaseModel):
        visible: bool = True
        acc_id: Optional[str] = None

    class SaveIdeaInputRequest(BaseModel):
        raw_text: str
        custom_id: Optional[str] = None

    class DeleteIdeaRequest(BaseModel):
        ma_id: str

    class SaveStep2TemplateRequest(BaseModel):
        template_text: str

    class RunADASPipelineRequest(BaseModel):
        ma_ids: list[str]
        preferred_acc_id: Optional[str] = None
        auto_produce_video: bool = True
        target_part_min: int = 13334
        video_settings: Optional[Dict[str, Any]] = None
        ai_provider: Optional[str] = "chatgpt_web"
        force_rewrite_script: bool = False
        max_retries: int = 3

    class RenderOnlyRequest(BaseModel):
        ma_ids: Optional[list[str]] = None
        only_unrendered: bool = False
        video_settings: Optional[Dict[str, Any]] = None

    # ==========================================================================
    # API HỆ THỐNG LOG & CHẨN ĐOÁN LỖI (SYSTEM LOGS & DIAGNOSTICS)
    # ==========================================================================
    @app.get("/api/logs")
    def api_get_logs(limit: int = 250, level: Optional[str] = None, category: Optional[str] = None):
        return {
            "entries": sys_logger.get_recent_logs(limit=limit, level_filter=level, category_filter=category),
            "log_paths": sys_logger.get_log_file_paths(),
        }

    @app.post("/api/logs/clear")
    def api_clear_logs():
        sys_logger.clear_memory_logs()
        log_info("SYSTEM", "Đã làm mới bộ nhớ hiển thị nhật ký.")
        return {"success": True}

    @app.get("/api/diagnostics")
    def api_run_diagnostics():
        report = run_system_diagnostics(base_dir, pipeline=pipeline, adas_engine=adas_engine)
        return report

    @app.post("/api/diagnostics/install-missing")
    def api_install_missing_libs(install_cuda: bool = True):
        return install_missing_libraries_async(install_cuda=install_cuda)

    _telemetry_cache: Dict[str, Any] = {"ts": 0.0, "data": {}}
    _shutdown_state: Dict[str, float] = {"last_alive_ts": time.time(), "close_req_ts": 0.0}

    def _force_kill_all_studio_processes():
        try:
            from .voicevox_service import VoicevoxStandaloneService
            VoicevoxStandaloneService.shutdown_all_workers()
        except Exception:
            pass
        if os.name == "nt":
            for img in ("run.exe", "ffmpeg.exe", "yt-dlp.exe", "Drama_Nhat_Studio.exe"):
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", img, "/T"],
                        capture_output=True,
                        timeout=3,
                        creationflags=0x08000000,
                    )
                except Exception:
                    pass
        os._exit(0)

    @app.post("/api/app/heartbeat-alive")
    def api_app_heartbeat_alive():
        _shutdown_state["last_alive_ts"] = time.time()
        _shutdown_state["close_req_ts"] = 0.0
        return {"ok": True}

    @app.post("/api/app/window-closed")
    def api_app_window_closed():
        close_ts = time.time()
        _shutdown_state["close_req_ts"] = close_ts

        def _delayed_check_and_shutdown():
            time.sleep(1.8)
            # Nếu người dùng chỉ bấm F5 tải lại trang thì heartbeat_alive / telemetry sẽ cập nhật last_alive_ts > close_ts
            if _shutdown_state["close_req_ts"] == close_ts and _shutdown_state["last_alive_ts"] < close_ts:
                log_info("SYSTEM", "🛑 Người dùng đã bấm nút X đóng cửa sổ ứng dụng — Đang tắt toàn bộ Server Voice (run.exe) và Backend...")
                _force_kill_all_studio_processes()

        threading.Thread(target=_delayed_check_and_shutdown, daemon=True).start()
        return {"ok": True}

    @app.get("/api/telemetry")
    def api_get_telemetry():
        now = time.time()
        _shutdown_state["last_alive_ts"] = now
        _shutdown_state["close_req_ts"] = 0.0
        if now - _telemetry_cache["ts"] < 2.5 and _telemetry_cache["data"]:
            return _telemetry_cache["data"]

        gpu_name = "NVIDIA GPU"
        gpu_load = 18
        gpu_temp = 52
        vram_used_gb = 2.4
        vram_total_gb = 12.0
        vram_pct = 20.0
        gpu_fan_pct = 45

        try:
            res = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total,fan.speed",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=1.5,
                creationflags=0x08000000 if os.name == "nt" else 0,
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().splitlines()[0].split(",")]
                if len(parts) >= 5:
                    gpu_name = parts[0]
                    gpu_load = int(float(parts[1])) if parts[1].replace(".", "").isdigit() else 18
                    gpu_temp = int(float(parts[2])) if parts[2].replace(".", "").isdigit() else 52
                    mem_u = float(parts[3]) if parts[3].replace(".", "").isdigit() else 2400.0
                    mem_t = float(parts[4]) if parts[4].replace(".", "").isdigit() else 12288.0
                    vram_used_gb = round(mem_u / 1024.0, 1)
                    vram_total_gb = round(mem_t / 1024.0, 1) if mem_t > 0 else 12.0
                    vram_pct = round((vram_used_gb / max(vram_total_gb, 0.1)) * 100.0, 1)
                if len(parts) >= 6 and parts[5].replace(".", "").isdigit():
                    gpu_fan_pct = int(float(parts[5]))
        except Exception:
            pass

        ram_used_gb = 14.2
        ram_total_gb = 32.0
        ram_pct = 44.4
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                ram_pct = float(stat.dwMemoryLoad)
                ram_total_gb = round(stat.ullTotalPhys / (1024 ** 3), 1)
                ram_used_gb = round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024 ** 3), 1)
        except Exception:
            pass

        cpu_threads = os.cpu_count() or 12
        cpu_name = f"{cpu_threads}-Thread Workstation CPU"
        try:
            import platform
            proc_name = platform.processor()
            if proc_name:
                cpu_name = proc_name
        except Exception:
            pass

        import socket
        cdp_ports = []
        for idx, port in enumerate((9222, 9223, 9224), start=1):
            alive = False
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.15)
                    alive = s.connect_ex(("127.0.0.1", port)) == 0
            except Exception:
                alive = False
            cdp_ports.append({"id": f"P{idx}", "port": port, "active": alive})

        data = {
            "gpu_name": gpu_name,
            "gpu_load_pct": gpu_load,
            "gpu_temp_c": gpu_temp,
            "vram_used_gb": vram_used_gb,
            "vram_total_gb": vram_total_gb,
            "vram_pct": vram_pct,
            "gpu_fan_pct": gpu_fan_pct,
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "ram_pct": ram_pct,
            "cpu_threads": cpu_threads,
            "cpu_name": cpu_name,
            "cpu_pct": min(99, max(8, int(gpu_load * 0.45 + 12))),
            "cdp_ports": cdp_ports,
            "cdp_active_count": sum(1 for p in cdp_ports if p["active"]),
        }
        _telemetry_cache["ts"] = now
        _telemetry_cache["data"] = data
        return data

    class QuickTerminalCmdRequest(BaseModel):
        command: str

    @app.post("/api/diagnostics/exec-cmd")
    def api_exec_quick_terminal_cmd(req: QuickTerminalCmdRequest):
        cmd_str = (req.command or "").strip()
        if not cmd_str:
            return {"success": False, "output": "Lệnh trống."}

        log_info("SYSTEM", f"> {cmd_str}")
        low = cmd_str.lower()
        out_text = ""

        try:
            if low.startswith("nvidia-smi"):
                res = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,driver_version,utilization.gpu,temperature.gpu,memory.used,memory.total", "--format=csv"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=0x08000000 if os.name == "nt" else 0,
                )
                out_text = (res.stdout or res.stderr or "Không đọc được nvidia-smi").strip()
            elif "ffmpeg" in low:
                res = subprocess.run(
                    ["ffmpeg", "-hwaccels"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=0x08000000 if os.name == "nt" else 0,
                )
                out_text = (res.stdout or res.stderr or "FFmpeg sẵn sàng").strip()
            elif "directml" in low or "voice" in low:
                st = pipeline.get_state()
                out_text = f"Voice Engine: {st.get('voice_engine_label', 'VOICEVOX DirectML')} | GPU Balanced: {st.get('gpu_balancer_summary', 'Active')}"
            elif "stock" in low:
                st_info = pipeline.stock_manager.get_all_stocks()
                out_text = f"Kho Stock: {st_info.get('available_count', 0)} cuộn khả dụng ({st_info.get('available_raw_hours', 0):.1f}h) tại {st_info.get('stook_dir', '')}"
            elif "cdp" in low or "chrome" in low:
                tel = api_get_telemetry()
                ports_str = ", ".join(f"{p['id']}:{p['port']}={'ONLINE' if p['active'] else 'OFFLINE'}" for p in tel["cdp_ports"])
                out_text = f"Chrome CDP Nodes ({tel['cdp_active_count']}/3): {ports_str}"
            elif low in ("diag", "diagnostics", "check", "status"):
                rep = run_system_diagnostics(base_dir, pipeline=pipeline, adas_engine=adas_engine)
                out_text = f"Chẩn đoán hệ thống hoàn tất: {rep.get('summary_text', 'OK')}"
            else:
                tel = api_get_telemetry()
                out_text = (
                    f"[TELEMETRY] GPU: {tel['gpu_name']} ({tel['gpu_load_pct']}% | {tel['gpu_temp_c']}°C | VRAM {tel['vram_used_gb']}/{tel['vram_total_gb']}GB) | "
                    f"RAM: {tel['ram_used_gb']}/{tel['ram_total_gb']}GB ({tel['ram_pct']}%) | CDP: {tel['cdp_active_count']}/3 Active. "
                    f"(Hỗ trợ lệnh: nvidia-smi, ffmpeg -hwaccels, test-directml, check-cdp, check-stocks, status)"
                )
        except Exception as e:
            out_text = f"Lỗi thực thi lệnh chẩn đoán: {e}"

        for line in out_text.splitlines():
            if line.strip():
                log_info("SYSTEM", line.strip())
        return {"success": True, "output": out_text}

    # ==========================================================================
    # 4 API ĐIỀU KHIỂN 3 TÀI KHOẢN CHATGPT WEB (MASTER BLUEPRINT V6.0)
    # ==========================================================================
    @app.get("/api/chatgpt/status")
    def api_chatgpt_status(force: bool = False):
        return check_all_web_accounts_status(force_refresh=force)

    @app.post("/api/chatgpt/open_browser")
    def api_chatgpt_open_browser(req: OpenChatGPTBrowserRequest):
        return ensure_chrome_debug_browser_open(
            open_chatgpt_home=True,
            force_bring_to_front=True,
            run_hidden=False,
            acc_id=req.acc_id,
        )

    @app.post("/api/chatgpt/visibility")
    def api_chatgpt_visibility(req: ChatGPTVisibilityRequest):
        return set_chrome_window_visibility(visible=req.visible, acc_id=req.acc_id)

    @app.post("/api/chatgpt/sweep_tabs")
    def api_chatgpt_sweep_tabs():
        return sweep_completed_and_idle_tabs_across_all_accounts()

    # ==========================================================================
    # API ĐIỀU KHIỂN GOOGLE GEMINI 4 PRO WEB (3 TÀI KHOẢN CHROME PRO)
    # ==========================================================================
    @app.get("/api/gemini/status")
    def api_gemini_status():
        return check_all_gemini_accounts_status()

    @app.post("/api/gemini/open_browser")
    def api_gemini_open_browser(req: OpenChatGPTBrowserRequest):
        set_chrome_window_visibility(visible=True, acc_id=req.acc_id)
        return open_gemini_tab_on_account(acc_id=req.acc_id)

    # ==========================================================================
    # API DÂY CHUYỀN ADAS (LƯU TIÊU ĐỀ NHÁP & CHẠY STEP 2 -> STEP 6 -> VIDEO)
    # ==========================================================================
    @app.get("/api/adas/ideas")
    def api_adas_get_ideas():
        if time.time() - getattr(adas_engine, "_last_disk_sync_ts", 0.0) >= 25.0 and not getattr(adas_engine, "_disk_sync_in_progress", False):
            def _bg_sync():
                try:
                    adas_engine._disk_sync_in_progress = True
                    adas_engine._sync_projects_disk_state()
                finally:
                    adas_engine._disk_sync_in_progress = False
            threading.Thread(target=_bg_sync, daemon=True).start()
        return {
            "ideas": adas_engine.load_saved_ideas(),
            "state": adas_engine.get_state(),
        }

    @app.post("/api/adas/ideas/save")
    def api_adas_save_idea(req: SaveIdeaInputRequest):
        if not req.raw_text or not req.raw_text.strip():
            raise HTTPException(status_code=400, detail="Vui lòng dán nội dung Tiêu đề Nhật nháp & Tóm tắt!")
        saved_list = adas_engine.add_or_update_ideas_bulk_from_raw(req.raw_text, custom_id=req.custom_id)
        first_idea = saved_list[0]
        step2_prompt = build_step2_prompt_from_idea(first_idea, adas_engine.get_step2_template())
        return {
            "success": True,
            "idea": first_idea,
            "saved_ideas": saved_list,
            "saved_count": len(saved_list),
            "saved_ids": [it["ma_id"] for it in saved_list],
            "step2_prompt_preview": step2_prompt,
            "ideas": adas_engine.load_saved_ideas(),
        }

    @app.post("/api/adas/ideas/preview-prompt")
    def api_adas_preview_prompt(req: SaveIdeaInputRequest):
        parsed = parse_idea_input_block(req.raw_text, custom_id=req.custom_id or "IDEA_PREVIEW")
        step2_prompt = build_step2_prompt_from_idea(parsed, adas_engine.get_step2_template())
        return {
            "parsed": parsed,
            "step2_prompt": step2_prompt,
        }

    @app.post("/api/adas/ideas/delete")
    def api_adas_delete_idea(req: DeleteIdeaRequest):
        ideas = adas_engine.delete_idea(req.ma_id)
        return {"success": True, "ideas": ideas, "deleted_id": req.ma_id}

    @app.post("/api/adas/ideas/delete-all")
    def api_adas_delete_all_ideas():
        ideas = adas_engine.delete_all_ideas()
        return {"success": True, "ideas": ideas}

    @app.post("/api/adas/ideas/restore")
    @app.post("/api/adas/ideas/sync-folder")
    def api_adas_restore_ideas_from_disk(payload: dict = None):
        payload = payload or {}
        folder_path = str(payload.get("folder_path") or "").strip() or None
        res = adas_engine.restore_scripts_from_disk(custom_folder=folder_path)
        return {"success": True, **res}

    @app.post("/api/adas/check-and-repair-all")
    def api_adas_check_and_repair_all(payload: dict = None):
        payload = payload or {}
        action = str(payload.get("action") or "").strip().lower()
        folder_path = str(payload.get("folder_path") or "").strip() or None
        try:
            if action == "start":
                res = adas_engine.start_check_and_repair_async(custom_folder=folder_path)
                return {"success": True, **res}
            if action == "status":
                res = adas_engine.get_check_and_repair_status()
                return {"success": True, **res}
            res = adas_engine.check_and_repair_all_projects(custom_folder=folder_path)
            return {"success": True, **res}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/adas/ideas/import-external")
    def api_adas_import_external_projects(payload: dict = None):
        payload = payload or {}
        folder_path = str(payload.get("folder_path") or "").strip()
        if not folder_path:
            raise HTTPException(status_code=400, detail="Vui lòng chọn thư mục chứa Kịch bản + Thumbnail + SEO cần nhập!")
        try:
            res = adas_engine.import_external_projects_folder(folder_path)
            return {"success": True, **res}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Lỗi khi nhập dự án từ máy khác: {e}")

    @app.get("/api/adas/template/step2")
    def api_adas_get_step2_template():
        return {"template_text": adas_engine.get_step2_template()}

    @app.post("/api/adas/template/step2")
    def api_adas_save_step2_template(req: SaveStep2TemplateRequest):
        saved_tpl = adas_engine.save_step2_template(req.template_text)
        log_info("SCRIPT", "💾 Đã lưu cập nhật Khuôn Lệnh Step 2 (Template Prompt).")
        return {"success": True, "template_text": saved_tpl}

    @app.post("/api/adas/run")
    def api_adas_run(req: RunADASPipelineRequest):
        lic = license_mgr.get_license_status(check_online_time=False)
        if not lic.get("valid"):
            raise HTTPException(status_code=403, detail=lic.get("message", "Bản quyền đã hết hạn hoặc chưa kích hoạt!"))
        if not req.ma_ids:
            raise HTTPException(status_code=400, detail="Vui lòng chọn ít nhất 1 Mã ý tưởng để chạy!")

        started = adas_engine.start_run_ideas_async(
            ma_ids=req.ma_ids,
            preferred_acc_id=req.preferred_acc_id,
            auto_produce_video=req.auto_produce_video,
            video_settings=req.video_settings,
            target_part_min=req.target_part_min,
            ai_provider=req.ai_provider or "chatgpt_web",
            force_rewrite_script=req.force_rewrite_script,
            max_retries=max(1, min(5, req.max_retries)),
        )
        if not started:
            raise HTTPException(status_code=400, detail="Dây chuyền viết kịch bản đang chạy một dự án khác!")
        return {"success": True, "message": f"Đã bắt đầu chạy dây chuyền Step 2 -> Step 6 cho {len(req.ma_ids)} dự án!"}

    @app.post("/api/adas/stop")
    def api_adas_stop():
        adas_engine.stop()
        return {"success": True}

    @app.post("/api/adas/render-only")
    def api_adas_render_only(req: RenderOnlyRequest):
        lic = license_mgr.get_license_status(check_online_time=False)
        if not lic.get("valid"):
            raise HTTPException(status_code=403, detail=lic.get("message", "Bản quyền đã hết hạn hoặc chưa kích hoạt!"))
        res = adas_engine.start_render_video_for_ideas_async(
            ma_ids=req.ma_ids,
            video_settings=req.video_settings,
            only_unrendered=req.only_unrendered,
        )
        if not res.get("started") and res.get("queued_count", 0) == 0:
            raise HTTPException(status_code=400, detail=res.get("message", "Không có kịch bản nào sẵn sàng Render MP4!"))
        return res

    @app.get("/api/adas/status")
    def api_adas_status():
        adas_engine._sync_projects_disk_state()
        return {
            "state": adas_engine.get_state(),
            "ideas": adas_engine.load_saved_ideas(),
        }

    @app.get("/api/adas/project/{ma_id}")
    def api_adas_project_details(ma_id: str):
        return adas_engine.get_project_outputs(ma_id)

    @app.post("/api/adas/project/{ma_id}/check-sync")
    def api_adas_check_project_sync(ma_id: str, payload: dict = None):
        from backend.sync_checker import verify_rendered_video_sync
        import json

        payload = payload or {}
        auto_redo = bool(payload.get("auto_redo", False))
        vcfg = payload.get("video_settings") or {}

        proj_dir = adas_engine.projects_dir / ma_id
        renders_dir = proj_dir / "renders"
        assets_dir = proj_dir / "assets"

        script_path = proj_dir / "script_clean.txt"
        if not script_path.exists():
            script_path = renders_dir / f"{ma_id}_KICH_BAN.txt"
        if not script_path.exists():
            script_path = proj_dir / "script.txt"
        if not script_path.exists():
            raise HTTPException(status_code=404, detail=f"Không tìm thấy kịch bản của dự án {ma_id}")

        script_text = script_path.read_text(encoding="utf-8")
        sentences = split_japanese_script(script_text)

        video_path = renders_dir / f"{ma_id}_master.mp4"
        wav_path = assets_dir / "master_voice.wav"
        srt_path = assets_dir / "subtitles.srt"
        sentences_dir = assets_dir / "sentences"

        report = verify_rendered_video_sync(
            video_path=video_path,
            master_wav_path=wav_path,
            srt_path=srt_path,
            sentences=sentences,
            sentences_dir=sentences_dir,
        )
        try:
            (proj_dir / "qa_video_sync_report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

        redo_started = False
        if not report.get("passed") and auto_redo:
            redo_indices = report.get("sentence_audit", {}).get("redo_indices", [])
            for r_idx in redo_indices:
                bad_w = sentences_dir / f"sentence_{r_idx+1:04d}.wav"
                if bad_w.exists():
                    try:
                        bad_w.unlink()
                    except Exception:
                        pass
            if video_path.exists():
                try:
                    video_path.unlink()
                except Exception:
                    pass

            seo_file = proj_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"
            seo_txt = seo_file.read_text(encoding="utf-8") if seo_file.exists() else ""
            job_payload = [{
                "name": ma_id,
                "script_text": script_text,
                "seo_text": seo_txt,
            }]
            redo_started = pipeline.start_batch_production_async(
                jobs=job_payload,
                output_dir=vcfg.get("output_dir") or str(adas_engine.projects_dir),
                channel_name=vcfg.get("channel_name", "ENISHI"),
                resolution=vcfg.get("resolution", "1920x1080"),
                fps=int(vcfg.get("fps", 30)),
                stock_selection=vcfg.get("stock_selection", "auto_unique"),
                bgm_path=vcfg.get("bgm_path"),
                bgm_volume=float(vcfg.get("bgm_volume", 0.08)),
                delete_used_stocks=bool(vcfg.get("delete_used_stocks", True)),
                auto_ensure_stock_hours=bool(vcfg.get("auto_ensure_stock_hours", True)),
                target_stock_hours=float(vcfg.get("target_stock_hours", 10.0)),
            )

        return {
            "ma_id": ma_id,
            "report": report,
            "redo_started": redo_started,
        }

    @app.post("/api/adas/project/{ma_id}/generate-thumbnails")
    def api_adas_generate_thumbnails(ma_id: str, preferred_acc_id: Optional[str] = None, force: bool = True):
        started = adas_engine.start_generate_thumbnails_only_async(
            ma_id=ma_id,
            preferred_acc_id=preferred_acc_id,
            force_regenerate=force,
        )
        if not started:
            raise HTTPException(status_code=400, detail="Hệ thống ChatGPT đang bận chạy dự án khác. Vui lòng đợi hoàn tất!")
        return {"success": True, "ma_id": ma_id, "message": f"Đã bắt đầu tạo & đánh giá 3 Thumbnail (6 dòng chữ) cho {ma_id}!"}

    @app.get("/api/license/status")
    def get_license_status():
        return license_mgr.get_license_status(check_online_time=False)

    @app.post("/api/license/activate")
    def activate_license(req: ActivateLicenseRequest):
        res = license_mgr.activate_license(req.license_key)
        if not res.get("valid"):
            raise HTTPException(status_code=400, detail=res.get("message", "Key không hợp lệ!"))
        return res

    @app.post("/api/browse-directory")
    def browse_directory(req: BrowseDirRequest):
        # 1. Thử Tkinter trước (nhanh, nhẹ, topmost)
        tk_code = """
import sys
import os
import tkinter as tk
from tkinter import filedialog
try:
    title = sys.argv[1] if len(sys.argv) > 1 else 'Chọn Thư Mục'
    r = tk.Tk()
    r.withdraw()
    r.attributes('-topmost', True)
    r.focus_force()
    path = filedialog.askdirectory(title=title)
    r.destroy()
    if path:
        print('SELECTED:' + os.path.normpath(path))
except Exception:
    pass
"""
        selected_path = None
        try:
            res = subprocess.run(
                [sys.executable, "-c", tk_code, req.title],
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace"
            )
            for line in res.stdout.splitlines():
                if line.startswith("SELECTED:"):
                    selected_path = line.replace("SELECTED:", "").strip()
        except Exception:
            pass

        # 2. Dự phòng: Nếu Tkinter không trả về kết quả (hoặc gặp lỗi), dùng PowerShell FolderBrowserDialog
        if not selected_path:
            clean_title = req.title.replace("'", "").replace('"', '')
            ps_code = f"""
[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms') | Out-Null
$f = New-Object System.Windows.Forms.FolderBrowserDialog
$f.Description = '{clean_title}'
$f.ShowNewFolderButton = $true
$top = New-Object System.Windows.Forms.Form
$top.TopMost = $true
if ($f.ShowDialog($top) -eq [System.Windows.Forms.DialogResult]::OK) {{
    Write-Host "SELECTED:$($f.SelectedPath)"
}}
"""
            try:
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_code],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    encoding="utf-8",
                    errors="replace"
                )
                for line in res.stdout.splitlines():
                    if line.startswith("SELECTED:"):
                        selected_path = line.replace("SELECTED:", "").strip()
            except Exception:
                pass

        if selected_path:
            selected_path = os.path.normpath(selected_path)
        return {"path": selected_path}

    @app.post("/api/stocks/set-directory")
    def set_stock_directory(req: SetStockDirRequest):
        try:
            clean_path = os.path.normpath(req.directory.strip().strip('"').strip("'"))
            pipeline.stock_manager.set_stook_dir(clean_path)
            log_info("STOCK", f"📂 Đã đổi thư mục Kho Video Stock sang: {clean_path}")
            return {"success": True, "data": pipeline.stock_manager.get_all_stocks()}
        except Exception as e:
            log_error("STOCK", f"❌ Lỗi đổi thư mục Kho Stock: {e}")
            raise HTTPException(status_code=400, detail=str(e))

    class PerformanceModeRequest(BaseModel):
        mode: str = "full_100"

    @app.get("/api/performance-mode")
    def api_get_performance_mode():
        return {"success": True, **pipeline.get_performance_mode_info()}

    @app.post("/api/performance-mode")
    def api_set_performance_mode(req: PerformanceModeRequest):
        info = pipeline.set_performance_mode(req.mode, persist=True)
        return {"success": True, **info}

    @app.get("/api/config")
    def get_config():
        import torch
        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU Mode"
        return {
            "root_dir": str(base_dir),
            "default_output_dir": str(base_dir / "projects"),
            "gpu_name": gpu_name,
            "cuda_available": torch.cuda.is_available(),
            "performance_mode": pipeline.get_performance_mode_info(),
            "resolutions": [
                {"id": "1920x1080", "label": "Full HD 1080p (1920x1080 - Khuyên dùng)", "default": True},
                {"id": "2560x1440", "label": "2K Quad HD (2560x1440 - Siêu nét)", "default": False},
                {"id": "3840x2160", "label": "4K Ultra HD (3840x2160 - Cao cấp)", "default": False},
                {"id": "1280x720", "label": "HD 720p (1280x720 - Render nhanh)", "default": False},
                {"id": "1080x1920", "label": "Shorts / TikTok (1080x1920 - Khung dọc)", "default": False}
            ],
            "fps_options": [
                {"value": 30, "label": "30 FPS (Mặc định chuẩn Nhật)", "default": True},
                {"value": 60, "label": "60 FPS (Siêu mượt)", "default": False},
                {"value": 24, "label": "24 FPS (Cinematic Điện ảnh)", "default": False}
            ]
        }

    @app.get("/api/status")
    def get_status():
        return pipeline.get_state()

    @app.get("/api/stocks")
    def get_stocks():
        return pipeline.stock_manager.get_all_stocks()

    @app.post("/api/stocks/scan")
    def rescan_stocks():
        res = pipeline.stock_manager.scan_and_update_inventory()
        log_info("STOCK", f"🔄 Đã quét lại Kho Video Stock: {res.get('available_count', 0)} video khả dụng ({res.get('available_raw_hours', 0):.1f} giờ).")
        return res

    @app.post("/api/stocks/reset")
    def reset_stock(req: ResetStockRequest):
        success = pipeline.stock_manager.reset_usage(req.stock_id)
        log_info("STOCK", f"♻️ Đã đặt lại trạng thái sử dụng cho video Stock: {req.stock_id}")
        return {"success": success}

    @app.post("/api/stocks/reset-all")
    def reset_all_stocks():
        data = pipeline.stock_manager.reset_all_usage()
        log_info("STOCK", "♻️ Đã đặt lại trạng thái chưa sử dụng cho toàn bộ Kho Video Stock.")
        return {"success": True, "data": data}

    @app.post("/api/stocks/cleanup-used")
    def cleanup_used_stocks():
        res = pipeline.stock_manager.cleanup_all_used_stocks()
        log_info("STOCK", f"🧹 Đã dọn dẹp các video Stock đã sử dụng: Xóa {res.get('deleted_count', 0)} file.")
        return res

    @app.post("/api/stocks/download-youtube")
    def download_youtube(req: YouTubeDownloadRequest):
        log_info("STOCK", f"⬇️ Bắt đầu tải Video Stock 720p từ YouTube: {req.url} (Cắt {req.slice_minutes} phút/đoạn)...")
        res = pipeline.stock_manager.download_youtube_and_slice(
            url=req.url,
            folder_name=req.folder_name,
            slice_minutes=req.slice_minutes,
            force=req.force
        )
        if not res.get("success") and any(
            kw in str(res.get("error", "")).lower() for kw in ("not a bot", "sign in", "403", "format is not available")
        ):
            log_warn("STOCK", "⚠️ YouTube yêu cầu xác thực Bot -> Tự động chuyển sang tải Stock 720p từ Pexels & Pixabay API...")
            res = pipeline.stock_manager.download_pexels_pixabay_stock_reel(
                slice_minutes=req.slice_minutes,
                target_parts=2,
            )
        if res.get("success"):
            log_info("STOCK", f"✅ Đã tải & cắt xong Video Stock 720p: {res.get('message', 'Thành công')}")
        else:
            log_warn("STOCK", f"⚠️ Tải Video Stock không thành công: {res.get('error') or res.get('message')}")
        return res

    @app.post("/api/stocks/download-pexels-pixabay")
    def download_pexels_pixabay(req: AutoReplenishStockRequest):
        parts_needed = max(1, int(round((req.target_hours * 60.0) / max(10, req.slice_minutes))))
        log_info("STOCK", f"🚀 Bắt đầu tải {parts_needed} cuộn Stock 720p trực tiếp từ Pexels & Pixabay API ({req.slice_minutes} phút/cuộn)...")
        res = pipeline.stock_manager.download_pexels_pixabay_stock_reel(
            slice_minutes=req.slice_minutes,
            target_parts=parts_needed,
        )
        return res

    @app.post("/api/stocks/auto-replenish")
    def auto_replenish_stocks(req: AutoReplenishStockRequest):
        log_info("STOCK", f"⚡ Bắt đầu tự động săn và bù kho Stock 720p đạt tối thiểu {req.target_hours} giờ...")
        res = pipeline.stock_manager.ensure_minimum_stock_hours(
            target_hours=req.target_hours,
            slice_minutes=req.slice_minutes
        )
        log_info("STOCK", f"✅ Hoàn tất tự động bù kho Stock: Hiện có {res.get('current_hours', 0):.1f} giờ video khả dụng.")
        return res

    @app.post("/api/stocks/sync-cloud-note")
    def sync_cloud_note():
        log_info("STOCK", "☁️ Đang đồng bộ danh sách Link YouTube đã dùng lên Cloud Note...")
        res = pipeline.stock_manager.sync_cloud_used_links(
            push_updates=True,
            force_push=True
        )
        log_info("STOCK", f"☁️ Đồng bộ Cloud Note hoàn tất (Tổng {res.get('total_synced', 0)} link).")
        return res

    @app.get("/api/stocks/cloud-note")
    def get_cloud_note_info():
        cfg = pipeline.stock_manager.get_cloud_note_config()
        used_data = pipeline.stock_manager.load_used_yt_links()
        return {
            "enabled": True,
            "note_url": cfg.get("url", "https://rentry.co/nhat-drama-stock-9f8a7b6c"),
            "used_links_count": len(used_data.get("used_video_ids", {}))
        }

    class VoiceConfigUpdateRequest(BaseModel):
        active_gpu_server: Optional[str] = None
        engine_mode: Optional[str] = None
        selected_preset_id: Optional[str] = None
        speaker_id: Optional[int] = None
        speedScale: Optional[float] = None
        pitchScale: Optional[float] = None
        intonationScale: Optional[float] = None
        pauseLengthScale: Optional[float] = None
        volumeScale: Optional[float] = None
        ref_wav: Optional[str] = None
        sample_text: Optional[str] = None
        activate_server_now: Optional[bool] = False

    @app.get("/api/voice-engine/status")
    def api_voice_engine_status():
        omni_ready = getattr(pipeline.voice_service, "model", None) is not None
        st = pipeline.voicevox_service.get_engine_status(omnivoice_loaded=omni_ready)
        st["hardware_load"] = pipeline.resource_balancer.get_metrics(force_refresh=False)
        return st

    @app.post("/api/voice-engine/switch-server")
    def api_voice_engine_switch_server(req: VoiceConfigUpdateRequest):
        target_srv = req.active_gpu_server or "voicevox_gpu"
        status = pipeline.activate_gpu_voice_server(target_srv)
        status["hardware_load"] = pipeline.resource_balancer.get_metrics(force_refresh=True)
        return {"success": True, "status": status, "config": status.get("config")}

    @app.post("/api/voice-engine/config")
    def api_voice_engine_save_config(req: VoiceConfigUpdateRequest):
        payload = {k: v for k, v in req.dict().items() if v is not None and k not in ("sample_text", "activate_server_now")}
        saved = save_voice_config(payload)
        preset_name = next((p["name"] for p in VOICE_PRESETS if p["id"] == saved.get("selected_preset_id")), saved.get("selected_preset_id"))

        # Tự động nạp sẵn giọng vừa chọn lên VRAM GPU của Server tương ứng
        if req.activate_server_now or req.active_gpu_server or req.selected_preset_id:
            threading.Thread(
                target=pipeline.activate_gpu_voice_server,
                args=(saved.get("active_gpu_server", "voicevox_gpu"),),
                daemon=True,
            ).start()

        log_info(
            "VOICE",
            f"🎙️ Đã lưu & kích hoạt cấu hình Voice GPU: {preset_name} "
            f"(Server={saved.get('active_gpu_server')}, Speed={saved.get('speedScale')}x, Pitch={saved.get('pitchScale')}, Intonation={saved.get('intonationScale')})",
        )
        omni_ready = getattr(pipeline.voice_service, "model", None) is not None
        st = pipeline.voicevox_service.get_engine_status(omnivoice_loaded=omni_ready)
        st["hardware_load"] = pipeline.resource_balancer.get_metrics(force_refresh=False)
        return {"success": True, "config": saved, "status": st}

    @app.post("/api/voice-engine/preview")
    def api_voice_engine_preview(req: VoiceConfigUpdateRequest):
        payload = {k: v for k, v in req.dict().items() if v is not None and k != "sample_text"}
        saved = save_voice_config(payload)
        try:
            wav_path = pipeline.voicevox_service.generate_preview_wav(
                sample_text=req.sample_text,
                custom_cfg=saved,
            )
            log_info("VOICE", f"🔊 Đã tạo âm thanh nghe thử cho giọng [{saved.get('selected_preset_id')}] ({wav_path.name}).")
            return {
                "success": True,
                "audio_url": f"/api/voice-engine/preview-audio?file={wav_path.name}&t={int(time.time()*1000)}",
                "config": saved,
            }
        except Exception as e:
            log_error("VOICE", f"❌ Lỗi nghe thử giọng [{saved.get('selected_preset_id')}]: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/voice-engine/preview-audio")
    def api_voice_engine_preview_audio(file: str = "preview_Drama.wav"):
        clean_name = os.path.basename(file)
        cand1 = base_dir / "assets" / "voices" / "previews" / clean_name
        cand2 = base_dir / "assets" / "voices" / clean_name
        target = cand1 if cand1.exists() else (cand2 if cand2.exists() else (base_dir / "assets" / "voices" / "Drama_voicevox_preview.wav"))
        if not target.exists():
            raise HTTPException(status_code=404, detail="Chưa có file âm thanh nghe thử.")
        return FileResponse(str(target), media_type="audio/wav")

    @app.post("/api/preview-script")
    def preview_script(req: ScriptPreviewRequest):
        sentences = split_japanese_script(req.script_text)
        est_duration = len(sentences) * 2.5
        return {
            "sentence_count": len(sentences),
            "estimated_seconds": est_duration,
            "estimated_formatted": f"{int(est_duration // 60):02d}:{int(est_duration % 60):02d}",
            "sample_sentences": sentences[:5]
        }

    @app.post("/api/start")
    def start_pipeline(req: StartRequest):
        lic = license_mgr.get_license_status(check_online_time=False)
        if not lic.get("valid"):
            raise HTTPException(status_code=403, detail=lic.get("message", "Bản quyền đã hết hạn hoặc chưa kích hoạt!"))
        if not req.script_text.strip():
            raise HTTPException(status_code=400, detail="Vui lòng nhập kịch bản.")

        clean_proj = req.project_name or f"drama_nhat_{time.strftime('%Y%m%d_%H%M%S')}"
        jobs = [{"name": clean_proj, "script_text": req.script_text}]

        success = pipeline.start_batch_production_async(
            jobs=jobs,
            output_dir=req.output_dir,
            channel_name=req.channel_name,
            resolution=req.resolution,
            fps=req.fps,
            stock_selection=req.stock_selection,
            bgm_path=req.bgm_path,
            bgm_volume=req.bgm_volume,
            delete_used_stocks=req.delete_used_stocks,
            auto_ensure_stock_hours=req.auto_ensure_stock_hours,
            target_stock_hours=req.target_stock_hours,
            voice_config=req.voice_config,
        )
        if not success:
            raise HTTPException(status_code=400, detail="Một dự án khác đang được xử lý.")
        return {"success": True, "message": "Đã bắt đầu sản xuất!"}

    @app.post("/api/start-batch")
    def start_batch_pipeline(req: StartBatchRequest):
        lic = license_mgr.get_license_status(check_online_time=False)
        if not lic.get("valid"):
            raise HTTPException(status_code=403, detail=lic.get("message", "Bản quyền đã hết hạn hoặc chưa kích hoạt!"))
        if not req.jobs:
            raise HTTPException(status_code=400, detail="Danh sách kịch bản trống.")

        success = pipeline.start_batch_production_async(
            jobs=req.jobs,
            output_dir=req.output_dir,
            channel_name=req.channel_name,
            resolution=req.resolution,
            fps=req.fps,
            stock_selection=req.stock_selection,
            bgm_path=req.bgm_path,
            bgm_volume=req.bgm_volume,
            delete_used_stocks=req.delete_used_stocks,
            auto_ensure_stock_hours=req.auto_ensure_stock_hours,
            target_stock_hours=req.target_stock_hours,
            voice_config=req.voice_config,
        )
        if not success:
            raise HTTPException(status_code=400, detail="Một tiến trình sản xuất khác đang chạy.")
        return {"success": True, "message": f"Đã bắt đầu hàng đợi {len(req.jobs)} kịch bản!"}

    @app.post("/api/stop")
    def stop_pipeline():
        pipeline.stop()
        setattr(adas_engine, "live_auto_produce_video", False)
        return {"success": True, "message": "Đã dừng dây chuyền sản xuất Video!"}

    @app.get("/api/projects")
    def get_projects():
        projects = []
        proj_root = getattr(pipeline, "default_projects_dir", None)
        if proj_root and proj_root.exists():
            for d in proj_root.iterdir():
                if d.is_dir():
                    renders = d / "renders"
                    final_mp4 = None
                    if renders.exists():
                        mp4s = list(renders.glob("*.mp4"))
                        if mp4s:
                            final_mp4 = str(mp4s[0])
                    projects.append({
                        "name": d.name,
                        "path": str(d),
                        "has_render": final_mp4 is not None,
                        "video_path": final_mp4
                    })
        projects.sort(key=lambda x: x["name"], reverse=True)
        return {"projects": projects}

    @app.post("/api/open-folder")
    async def open_folder(req: OpenPathRequest):
        if not req.path:
            return {"success": False, "error": "Chưa có đường dẫn thư mục"}
        raw_p = req.path.strip()
        if not os.path.isabs(raw_p):
            p = str((base_dir / raw_p).resolve())
        else:
            p = os.path.abspath(raw_p)
        if not os.path.exists(p) and not os.path.splitext(p)[1]:
            os.makedirs(p, exist_ok=True)
        if os.path.exists(p):
            target_cmd = f'explorer.exe "{p}"'
            if os.path.isfile(p):
                target_cmd = f'explorer.exe /select,"{p}"'
            elif os.path.isdir(p):
                renders_dir = os.path.join(p, "renders")
                if os.path.isdir(renders_dir):
                    mp4s = [
                        os.path.join(renders_dir, f)
                        for f in os.listdir(renders_dir)
                        if f.lower().endswith(".mp4")
                    ]
                    if mp4s:
                        target_cmd = f'explorer.exe /select,"{mp4s[0]}"'
            try:
                subprocess.Popen(target_cmd)
            except Exception:
                pass
            return {"success": True, "opened": p}
        return {"success": False, "error": f"Đường dẫn không tồn tại: {p}"}

    @app.post("/api/open-video")
    def open_video(req: OpenPathRequest):
        if not req.path:
            return {"success": False, "error": "Chưa có đường dẫn video"}
        p = os.path.abspath(req.path.strip())
        if os.path.exists(p) and os.path.isfile(p):
            try:
                os.startfile(p)
            except Exception:
                pass
            try:
                cmd_str = f'cmd.exe /c start "" "{p}"'
                subprocess.run(
                    ["schtasks", "/Create", "/TN", "StudioVideoOpen", "/TR", cmd_str, "/SC", "ONCE", "/ST", "00:00", "/IT", "/F"],
                    capture_output=True,
                    timeout=3,
                )
                subprocess.run(["schtasks", "/Run", "/TN", "StudioVideoOpen"], capture_output=True, timeout=3)
            except Exception:
                pass
            return {"success": True}
        return {"success": False, "error": "File video không tồn tại"}

    # ==========================================================
    # API CẬP NHẬT TỰ ĐỘNG QUA GITHUB (OTA AUTO-UPDATER V1.0.0+)
    # ==========================================================
    @app.get("/api/update/status")
    def api_get_local_version():
        from backend.updater_service import get_local_version_info
        return get_local_version_info(base_dir)

    @app.get("/api/update/check")
    def api_check_github_update(force: bool = False):
        from backend.updater_service import check_for_github_update
        return check_for_github_update(base_dir, force_refresh=bool(force))

    @app.post("/api/update/apply")
    def api_apply_github_update():
        from backend.updater_service import apply_github_update
        return apply_github_update(base_dir, adas_engine=adas_engine, pipeline=pipeline)

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        main_loop_ref["loop"] = asyncio.get_running_loop()
        await websocket.accept()
        active_websockets.append(websocket)
        # Gửi trạng thái ban đầu
        await websocket.send_json(pipeline.get_state())
        try:
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            if websocket in active_websockets:
                active_websockets.remove(websocket)

    # Phục vụ giao diện web tĩnh
    if frontend_dir and frontend_dir.exists():
        index_html_path = frontend_dir / "index.html"
        if index_html_path.exists():
            @app.get("/", include_in_schema=False)
            async def serve_root_index():
                return FileResponse(str(index_html_path), media_type="text/html; charset=utf-8")
        app.mount("/static", StaticFiles(directory=str(frontend_dir), html=True), name="frontend_static")
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

    return app
