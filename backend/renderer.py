import os
import sys
import re
import json
import time
import wave
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple

# Ưu tiên thư mục bin nội bộ (chứa ffmpeg/ffprobe tương thích NVENC 13.0)
_BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
if not _BIN_DIR.exists():
    _BIN_DIR = Path(__file__).resolve().parent.parent.parent / "bin"
if _BIN_DIR.exists():
    os.environ["PATH"] = str(_BIN_DIR) + os.pathsep + os.environ.get("PATH", "")

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

_NVENC_AVAILABLE: Optional[bool] = None


def check_nvenc_available() -> bool:
    global _NVENC_AVAILABLE
    if _NVENC_AVAILABLE is not None:
        return _NVENC_AVAILABLE
    try:
        res = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1:r=30",
                "-pix_fmt", "yuv420p", "-c:v", "h264_nvenc", "-f", "null", "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=8
        )
        _NVENC_AVAILABLE = (res.returncode == 0)
    except Exception:
        _NVENC_AVAILABLE = False
    return _NVENC_AVAILABLE


def get_audio_duration(file_path: str) -> float:
    if str(file_path).lower().endswith(".wav"):
        try:
            with wave.open(str(file_path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0 and frames > 0:
                    return float(frames) / float(rate)
        except Exception:
            pass
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 0.0


def parse_time_to_seconds(time_str: str) -> float:
    """Chuyển đổi HH:MM:SS.xx thành giây."""
    try:
        parts = time_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
    except Exception:
        pass
    return 0.0


def _parse_srt_time(ts: str) -> float:
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return 0.0


def _format_srt_ts(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _create_shifted_srt(src_srt_path: str, offset_sec: float, dst_srt_path: str) -> str:
    """
    Dịch chuyển mốc thời gian phụ đề SRT lùi lại `offset_sec` giây khi Render nối tiếp từ đoạn dở,
    giúp phụ đề khớp chính xác 100% với luồng Voice đã seek tới `offset_sec`.
    """
    try:
        with open(src_srt_path, "r", encoding="utf-8") as f:
            raw = f.read()
        blocks = re.split(r"\n\s*\n", raw.strip())
        shifted_blocks: List[str] = []
        new_idx = 1
        for blk in blocks:
            lines = [l.strip() for l in blk.strip().splitlines() if l.strip()]
            if len(lines) >= 3 and "-->" in lines[1]:
                ts_parts = lines[1].split("-->")
                s_t = _parse_srt_time(ts_parts[0])
                e_t = _parse_srt_time(ts_parts[1])
                if e_t <= offset_sec + 0.04:
                    continue
                new_s = max(0.0, s_t - offset_sec)
                new_e = max(new_s + 0.08, e_t - offset_sec)
                text_body = "\n".join(lines[2:])
                shifted_blocks.append(f"{new_idx}\n{_format_srt_ts(new_s)} --> {_format_srt_ts(new_e)}\n{text_body}")
                new_idx += 1
        if not shifted_blocks:
            shifted_blocks.append("1\n00:00:00,000 --> 00:00:00,100\n ")
        with open(dst_srt_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(shifted_blocks) + "\n\n")
        return dst_srt_path
    except Exception as e:
        print(f"[Renderer] Lưu ý khi tạo SRT nối tiếp: {e}")
        return src_srt_path


def get_saved_render_progress(output_path: str, total_dur: float = 0.0) -> Dict[str, Any]:
    """
    Kiểm tra xem video này có đoạn Checkpoint Render dở dang nào đã lưu trên ổ cứng hay không.
    Trả về số giây đã render xong và phần trăm tương ứng.
    """
    try:
        out_dir = os.path.dirname(os.path.abspath(output_path))
        base_stem = os.path.splitext(os.path.basename(output_path))[0]
        resume_dir = Path(out_dir) / f"_{base_stem}_resume_cache"
        if not resume_dir.exists():
            return {"has_checkpoint": False, "completed_sec": 0.0, "percent": 0.0}
        meta_file = resume_dir / "resume_meta.json"
        if total_dur <= 0 and meta_file.exists():
            try:
                total_dur = float(json.loads(meta_file.read_text(encoding="utf-8")).get("total_dur", 0.0) or 0.0)
            except Exception:
                total_dur = 0.0
        comp_sec = 0.0
        for ts_f in sorted(resume_dir.glob("seg_clean_*.ts")):
            if ts_f.stat().st_size > 100_000:
                comp_sec += get_audio_duration(str(ts_f))
        for raw_f in sorted(resume_dir.glob("seg_raw_*.ts")):
            if raw_f.stat().st_size > 100_000:
                d_r = get_audio_duration(str(raw_f))
                if d_r >= 4.0:
                    comp_sec += max(0.0, d_r - 1.5)
        pct = min(99.0, round((comp_sec / total_dur) * 100.0, 1)) if total_dur > 0 else 0.0
        return {
            "has_checkpoint": comp_sec >= 3.0,
            "completed_sec": round(comp_sec, 2),
            "total_dur": round(total_dur, 2),
            "percent": pct,
        }
    except Exception:
        return {"has_checkpoint": False, "completed_sec": 0.0, "percent": 0.0}


def _ensure_wrapped_srt(srt_path: str, max_chars: int = 17, max_segment_chars: int = 48) -> str:
    """
    Đảm bảo mọi khối phụ đề trong file .srt có TỐI ĐA 3 DÒNG cân đối (<= max_chars ký tự/dòng)
    cho cỡ chữ lớn 135. Nếu câu quá dài (> max_segment_chars), tự động tách thành 2 khối phụ đề
    nối tiếp nhau theo tỷ lệ thời gian để TUYỆT ĐỐI KHÔNG BAO GIỜ LÊN 4 DÒNG.
    """
    try:
        from backend.voice_service import format_srt_text, split_long_subtitle_segments, format_timestamp
        with open(srt_path, "r", encoding="utf-8") as f:
            raw = f.read()
        blocks = re.split(r"\n\s*\n", raw.strip())
        new_blocks = []
        changed = False
        new_idx = 1

        for blk in blocks:
            lines = [l.strip() for l in blk.strip().splitlines() if l.strip()]
            if len(lines) >= 3 and "-->" in lines[1]:
                ts_line = lines[1]
                text_lines = lines[2:]
                joined_text = "".join(text_lines)

                if len(joined_text) > max_segment_chars:
                    ts_parts = ts_line.split("-->")
                    s_t = _parse_srt_time(ts_parts[0])
                    e_t = _parse_srt_time(ts_parts[1])
                    segs = split_long_subtitle_segments(
                        joined_text, s_t, e_t,
                        max_segment_chars=max_segment_chars,
                        max_chars_per_line=max_chars
                    )
                    for seg in segs:
                        new_blocks.append(
                            f"{new_idx}\n{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n{seg['text']}"
                        )
                        new_idx += 1
                    changed = True
                else:
                    needs_rewrap = (
                        len(text_lines) > 3
                        or any(len(l) > max_chars for l in text_lines)
                        or (len(text_lines) >= 2 and any(len(l) <= 3 for l in text_lines))
                    )
                    if needs_rewrap:
                        wrapped_text = format_srt_text(joined_text, max_chars_per_line=max_chars)
                        changed = True
                    else:
                        wrapped_text = "\n".join(text_lines)
                    if str(new_idx) != lines[0]:
                        changed = True
                    new_blocks.append(f"{new_idx}\n{ts_line}\n{wrapped_text}")
                    new_idx += 1
            else:
                new_blocks.append(blk.strip())

        if changed:
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(new_blocks) + "\n\n")
    except Exception as e:
        print(f"[Renderer] Lưu ý khi chuẩn hóa SRT: {e}")
    return srt_path


def render_drama_nhat_video(
    audio_path: str,
    subtitle_path: str,
    stock_video_path: str,
    output_path: str,
    channel_name: str = "ENISHI",
    resolution: str = "1920x1080",  # Hỗ trợ: 1920x1080, 2560x1440, 3840x2160, 1280x720, 1080x1920
    fps: int = 30,  # Hỗ trợ: 24, 30, 60
    font_name: str = "Kaisei Tokumin",
    font_size: int = 135,
    outline: float = 4.0,
    sub_color: str = "&H0015FFFF",  # Vàng chanh sáng (#FFFF15 trong BGR ASS)
    watermark_opacity: float = 0.14,
    box_opacity: float = 0.65,
    stock_speed: float = 0.5,
    brightness: float = -0.50,
    contrast: float = 1.18,
    vignette_param: str = "PI/3.3",
    flip_horizontal: bool = False,
    zoom_factor: float = 1.0,
    extend_with_flip_zoom: bool = True,
    particles_clip: Optional[str] = None,
    fonts_dir: Optional[str] = None,
    bgm_path: Optional[str] = None,
    bgm_volume: float = 0.08,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    performance_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Render video Drama Nhật 5 lớp đồ họa với độ phân giải, FPS và chế độ Lật + Zoom 110%.
    """
    start_time = time.time()
    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)

    # Phân tích độ phân giải (width x height)
    try:
        w_str, h_str = resolution.lower().split("x")
        target_w, target_h = int(w_str), int(h_str)
    except Exception:
        target_w, target_h = 1920, 1080

    # Tính toán tỷ lệ co giãn cho các lớp đồ họa dựa trên chiều cao chuẩn 1080p
    scale_factor = target_h / 1080.0
    scaled_box_height = int(540 * scale_factor)
    scaled_channel_fontsize = int(160 * scale_factor)
    watermark_x = f"w-tw-{int(70 * scale_factor)}"
    watermark_y = str(int(40 * scale_factor))
    scaled_outline = round(outline * scale_factor, 1)

    dur = get_audio_duration(audio_path)
    if dur <= 0:
        raise ValueError(f"Không thể đo thời lượng audio: {audio_path}")

    if not performance_mode:
        performance_mode = os.environ.get("STUDIO_PERF_MODE", "")
        if not performance_mode:
            try:
                cfg_p = Path(__file__).resolve().parent.parent / "config.json"
                if not cfg_p.exists():
                    cfg_p = Path(__file__).resolve().parent.parent.parent / "config.json"
                if cfg_p.exists():
                    performance_mode = json.loads(cfg_p.read_text(encoding="utf-8")).get("performance_mode", "full_100")
            except Exception:
                performance_mode = "full_100"
    perf_mode = (performance_mode or "full_100").strip().lower()
    is_work_70 = perf_mode == "work_70"
    total_cores = os.cpu_count() or 8
    if is_work_70:
        cpu_threads = max(2, int(round(total_cores * 0.60)))
        filter_threads = max(2, cpu_threads // 3)
        win_flags = (0x08000000 | 0x00004000) if os.name == "nt" else 0
    else:
        cpu_threads = max(4, total_cores - 1)
        filter_threads = max(2, cpu_threads // 2)
        win_flags = 0x08000000 if os.name == "nt" else 0

    # =========================================================================
    # CƠ CHẾ LƯU CHECKPOINT & RENDER NỐI TIẾP ĐOẠN CHƯA XONG (MPEG-TS RESUME)
    # =========================================================================
    base_stem = os.path.splitext(os.path.basename(output_path))[0]
    temp_output_path = os.path.join(out_dir, f"_{base_stem}_rendering_tmp.mp4")
    resume_dir = Path(out_dir) / f"_{base_stem}_resume_cache"
    resume_dir.mkdir(parents=True, exist_ok=True)
    meta_file = resume_dir / "resume_meta.json"

    audio_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
    current_meta = {
        "audio_size": audio_size,
        "total_dur": round(dur, 3),
        "resolution": f"{target_w}x{target_h}",
        "fps": int(fps),
        "stock_video_path": stock_video_path,
        "flip_horizontal": bool(flip_horizontal),
        "zoom_factor": float(zoom_factor),
    }

    if meta_file.exists():
        try:
            old_meta = json.loads(meta_file.read_text(encoding="utf-8"))
            same_audio_and_res = (
                old_meta.get("audio_size") == audio_size
                and abs(float(old_meta.get("total_dur", 0.0)) - dur) < 2.0
                and old_meta.get("resolution") == current_meta["resolution"]
                and int(old_meta.get("fps", fps)) == int(fps)
            )
            if same_audio_and_res:
                saved_stock = old_meta.get("stock_video_path")
                if saved_stock and os.path.exists(saved_stock):
                    stock_video_path = saved_stock
                    flip_horizontal = bool(old_meta.get("flip_horizontal", flip_horizontal))
                    zoom_factor = float(old_meta.get("zoom_factor", zoom_factor))
                    current_meta["stock_video_path"] = stock_video_path
                    current_meta["flip_horizontal"] = flip_horizontal
                    current_meta["zoom_factor"] = zoom_factor
            else:
                for f_old in resume_dir.glob("*.ts"):
                    try:
                        f_old.unlink()
                    except Exception:
                        pass
        except Exception:
            pass

    try:
        meta_file.write_text(json.dumps(current_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    existing_clean_count = len(list(resume_dir.glob("seg_clean_*.ts")))
    for raw_ts in sorted(resume_dir.glob("seg_raw_*.ts")):
        d_raw = get_audio_duration(str(raw_ts))
        if d_raw >= 4.0 and raw_ts.stat().st_size > 150_000:
            safe_dur = max(2.0, round(d_raw - 1.5, 2))
            clean_target = resume_dir / f"seg_clean_{existing_clean_count:04d}.ts"
            existing_clean_count += 1
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-v", "error",
                        "-i", str(raw_ts),
                        "-t", f"{safe_dur:.2f}",
                        "-c", "copy",
                        "-f", "mpegts",
                        str(clean_target),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=win_flags,
                    timeout=30,
                )
            except Exception:
                pass
        try:
            raw_ts.unlink()
        except Exception:
            pass

    valid_clean_segments: List[str] = []
    completed_sec = 0.0
    for c_idx, c_ts in enumerate(sorted(resume_dir.glob("seg_clean_*.ts"))):
        d_c = get_audio_duration(str(c_ts))
        if d_c >= 2.0 and c_ts.stat().st_size > 100_000:
            norm_path = resume_dir / f"seg_clean_{len(valid_clean_segments):04d}.ts"
            if c_ts != norm_path:
                try:
                    c_ts.replace(norm_path)
                except Exception:
                    norm_path = c_ts
            valid_clean_segments.append(str(norm_path))
            completed_sec += d_c
        else:
            try:
                c_ts.unlink()
            except Exception:
                pass

    stock_dur = get_audio_duration(stock_video_path)
    pts_factor = 1.0 / stock_speed if stock_speed > 0 else 1.0
    single_pass_dur = stock_dur * pts_factor if stock_dur > 0 else 0.0

    effective_zoom = zoom_factor if zoom_factor > 1.0 else 1.10
    zoom_w = (int(round(target_w * effective_zoom)) // 2) * 2
    zoom_h = (int(round(target_h * effective_zoom)) // 2) * 2

    mode_desc = (
        f"LẬT NGANG (hflip) + ZOOM {int(round(effective_zoom * 100))}%"
        if (flip_horizontal or zoom_factor > 1.0)
        else "BẢN GỐC 100% (Tự động nối Lật + Zoom 110% nếu vượt thời lượng)"
    )

    print("================================================================================")
    print("🎬 [DRAMA NHẬT RENDERER] BẮT ĐẦU DỰNG VIDEO CHUẨN 5 LỚP (HỖ TRỢ RENDER NỐI TIẾP)")
    print(f"📐 Độ phân giải: {target_w}x{target_h} | 🎞️ FPS: {fps}")
    print(f"🎵 Audio Voice: {audio_path} ({dur/60:.2f} phút)")
    if completed_sec > 0:
        print(f"♻️ KHÔI PHỤC CHECKPOINT: Đã render sẵn {completed_sec:.1f}s / {dur:.1f}s ({(completed_sec/dur)*100:.1f}%) — Chạy tiếp đoạn còn lại!")
    print(f"💬 Subtitle: {subtitle_path} (Font: {font_name}, SubSize: {font_size})")
    print(f"🎥 Stock: {stock_video_path} | Chế độ: {mode_desc}")
    print(f"🏷️ Kênh: {channel_name} | 📁 Xuất: {output_path}")
    print("================================================================================")

    if font_size >= 110 and os.path.exists(subtitle_path):
        _ensure_wrapped_srt(subtitle_path, max_chars=17, max_segment_chars=48)

    active_subtitle_path = subtitle_path
    if completed_sec > 0.1 and os.path.exists(subtitle_path):
        shifted_srt_file = str(resume_dir / "subtitles_resume_shifted.srt")
        active_subtitle_path = _create_shifted_srt(subtitle_path, completed_sec, shifted_srt_file)

    abs_sub = os.path.abspath(active_subtitle_path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    fonts_arg = ""
    if fonts_dir and os.path.exists(fonts_dir):
        abs_fonts_dir = os.path.abspath(fonts_dir).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        fonts_arg = f":fontsdir='{abs_fonts_dir}'"

    has_particles = particles_clip and os.path.exists(particles_clip)
    remaining_dur = max(0.0, dur - completed_sec)

    use_nvenc = check_nvenc_available()
    gop_size = str(max(24, int(fps) * 2))
    if use_nvenc:
        v_codec_args = [
            "-c:v", "h264_nvenc",
            "-preset", "p1" if is_work_70 else "p2",
            "-tune", "hq",
            "-rc", "vbr",
            "-cq", "21",
            "-b:v", "0",
            "-g", gop_size,
            "-pix_fmt", "yuv420p"
        ]
        encoder_label = f"NVIDIA GPU NVENC ({'Chế độ 70% Mượt' if is_work_70 else 'Full 100% Turbo'})"
    else:
        v_codec_args = [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-g", gop_size,
            "-threads", str(cpu_threads),
            "-pix_fmt", "yuv420p"
        ]
        encoder_label = f"CPU Multi-Thread ({cpu_threads} threads libx264 • {'70%' if is_work_70 else '100%'})"

    for stale_f in (temp_output_path, output_path):
        if os.path.exists(stale_f):
            try:
                os.remove(stale_f)
            except Exception:
                pass

    if remaining_dur > 1.5:
        filters = []
        cmd = ["ffmpeg", "-y"]
        input_idx = 0

        stock_seek_raw = round((completed_sec / pts_factor) % max(1.0, stock_dur), 2) if (completed_sec > 0 and stock_dur > 0) else 0.0
        stock_seek_args = ["-ss", f"{stock_seek_raw:.2f}"] if stock_seek_raw > 0.1 else []

        if flip_horizontal or zoom_factor > 1.0 or (extend_with_flip_zoom and single_pass_dur > 0 and completed_sec >= single_pass_dur):
            cmd.extend(["-stream_loop", "-1", *stock_seek_args, "-i", stock_video_path])
            input_idx += 1
            flip_filter = "hflip," if (flip_horizontal or completed_sec >= single_pass_dur) else ""
            filters.append(
                f"[0:v]setpts={pts_factor}*PTS,{flip_filter}"
                f"scale={zoom_w}:{zoom_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},fps={fps},format=yuv420p,"
                f"eq=brightness={brightness}:contrast={contrast}:saturation=0.72,"
                f"vignette={vignette_param}[bg_dark]"
            )
        elif extend_with_flip_zoom and single_pass_dur > 0 and dur > single_pass_dur:
            cmd.extend([*stock_seek_args, "-i", stock_video_path])
            cmd.extend(["-stream_loop", "-1", "-i", stock_video_path])
            input_idx += 2
            filters.append(
                f"[0:v]setpts={pts_factor}*PTS,"
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},fps={fps},setsar=1[bg_pass1]"
            )
            filters.append(
                f"[1:v]setpts={pts_factor}*PTS,hflip,"
                f"scale={zoom_w}:{zoom_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},fps={fps},setsar=1[bg_pass2]"
            )
            filters.append(
                f"[bg_pass1][bg_pass2]concat=n=2:v=1:a=0,format=yuv420p,"
                f"eq=brightness={brightness}:contrast={contrast}:saturation=0.72,"
                f"vignette={vignette_param}[bg_dark]"
            )
        else:
            cmd.extend(["-stream_loop", "-1", *stock_seek_args, "-i", stock_video_path])
            input_idx += 1
            filters.append(
                f"[0:v]setpts={pts_factor}*PTS,"
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
                f"crop={target_w}:{target_h},fps={fps},format=yuv420p,"
                f"eq=brightness={brightness}:contrast={contrast}:saturation=0.72,"
                f"vignette={vignette_param}[bg_dark]"
            )

        current_v = "[bg_dark]"

        if has_particles:
            cmd.extend(["-stream_loop", "-1", "-i", particles_clip])
            filters.append(f"[{input_idx}:v]scale={target_w}:{target_h},format=yuva420p[stars_scaled]")
            filters.append(f"{current_v}[stars_scaled]overlay=shortest=1[with_stars]")
            current_v = "[with_stars]"
            input_idx += 1

        voice_input_idx = input_idx
        if completed_sec > 0.1:
            cmd.extend(["-ss", f"{completed_sec:.3f}", "-i", audio_path])
        else:
            cmd.extend(["-i", audio_path])
        input_idx += 1

        has_bgm = bgm_path and os.path.exists(bgm_path)
        if has_bgm:
            bgm_seek_args = ["-ss", f"{(completed_sec % 180.0):.2f}"] if completed_sec > 0.1 else []
            cmd.extend(["-stream_loop", "-1", *bgm_seek_args, "-i", bgm_path])
            bgm_input_idx = input_idx
            input_idx += 1

        arial_font = "C\\:/Windows/Fonts/arial.ttf"
        font_arg_watermark = f":fontfile='{arial_font}'" if os.path.exists("C:/Windows/Fonts/arial.ttf") else ""

        style_str = (
            f"PlayResX={target_w},PlayResY={target_h},WrapStyle=2,"
            f"FontName={font_name},FontSize={int(font_size * scale_factor)},Bold=1,"
            f"PrimaryColour={sub_color},OutlineColour=&H00000000,BorderStyle=1,"
            f"Outline={scaled_outline},Shadow=2.0,Alignment=10"
        )

        filters.append(
            f"{current_v}drawbox=x=0:y=(ih-{scaled_box_height})/2:w=iw:h={scaled_box_height}:color=black@{box_opacity}:t=fill,"
            f"drawtext=text='{channel_name}':fontcolor=white@{watermark_opacity}:fontsize={scaled_channel_fontsize}{font_arg_watermark}:x={watermark_x}:y={watermark_y},"
            f"subtitles='{abs_sub}'{fonts_arg}:force_style='{style_str}'[v_out]"
        )

        if has_bgm:
            filters.append(
                f"[{voice_input_idx}:a]volume=1.0[voice];"
                f"[{bgm_input_idx}:a]volume={bgm_volume}[bgm];"
                f"[voice][bgm]amix=inputs=2:duration=first[a_out]"
            )
        else:
            filters.append(f"[{voice_input_idx}:a]volume=1.0[a_out]")

        fc = ";".join(filters)

        next_seg_idx = len(valid_clean_segments)
        current_raw_seg = str(resume_dir / f"seg_raw_{next_seg_idx:04d}.ts")

        cmd.extend([
            "-t", f"{remaining_dur:.3f}",
            "-filter_complex_threads", str(filter_threads),
            "-filter_complex", fc,
            "-map", "[v_out]",
            "-map", "[a_out]",
            *v_codec_args,
            "-threads", str(cpu_threads),
            "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-flush_packets", "1",
            "-progress", "pipe:1",
            "-f", "mpegts",
            current_raw_seg
        ])

        init_pct = min(99.0, round((completed_sec / dur) * 100.0, 1)) if completed_sec > 0 else 0.0
        if completed_sec > 0:
            print(f"\n-> ♻️ Tiếp tục encode FFmpeg từ {init_pct}% ({completed_sec:.0f}s/{dur:.0f}s) ({encoder_label})...")
            if progress_callback:
                progress_callback(
                    init_pct,
                    f"♻️ Khôi phục {init_pct}% đã render ({completed_sec:.0f}s/{dur:.0f}s) — Đang render nối tiếp đoạn còn lại...",
                )
        else:
            print(f"\n-> Bắt đầu tiến trình encode FFmpeg ({encoder_label})...")
            if progress_callback:
                progress_callback(0.0, f"Đang khởi tạo FFmpeg encode ({encoder_label})...")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            creationflags=win_flags,
        )

        time_regex = re.compile(r"out_time=(\d{2}:\d{2}:\d{2}\.\d+)")
        log_tail = []

        try:
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break

                line = line.strip()
                if line:
                    log_tail.append(line)
                    if len(log_tail) > 25:
                        log_tail.pop(0)
                if "out_time=" in line:
                    match = time_regex.search(line)
                    if match:
                        curr_seg_sec = parse_time_to_seconds(match.group(1))
                        total_done_sec = min(dur, completed_sec + curr_seg_sec)
                        percent = min(99.9, round((total_done_sec / dur) * 100, 1))
                        if progress_callback:
                            prefix_lbl = "♻️ Render nối tiếp" if completed_sec > 0 else "Đang render video"
                            progress_callback(percent, f"{prefix_lbl}: {percent}% ({total_done_sec:.0f}s / {dur:.0f}s)")
        except BaseException:
            try:
                process.kill()
                process.wait(timeout=3)
            except Exception:
                pass
            print(f"💾 [CHECKPOINT SAVED] Đã lưu tiến độ Render dở dang cho '{base_stem}' tại {resume_dir}")
            raise

        rc = process.poll()
        if rc != 0:
            err_detail = "\n".join(log_tail[-8:])
            raise RuntimeError(f"FFmpeg render tạm dừng/lỗi (mã {rc}) — Đã lưu Checkpoint để chạy tiếp: {err_detail}")

        final_clean_seg = str(resume_dir / f"seg_clean_{next_seg_idx:04d}.ts")
        if os.path.exists(current_raw_seg):
            os.replace(current_raw_seg, final_clean_seg)
            valid_clean_segments.append(final_clean_seg)

    if not valid_clean_segments:
        raise RuntimeError("Không tìm thấy dữ liệu phân đoạn video nào sau khi encode.")

    if progress_callback:
        progress_callback(99.9, "Đang đóng gói & kiểm định file MP4 hoàn chỉnh (Fast Remux)...")

    if len(valid_clean_segments) == 1:
        remux_cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", valid_clean_segments[0],
            "-t", f"{dur:.3f}",
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-movflags", "+faststart",
            temp_output_path,
        ]
    else:
        concat_list_file = resume_dir / "concat_segments.txt"
        with open(concat_list_file, "w", encoding="utf-8") as f_cat:
            for seg_p in valid_clean_segments:
                clean_seg_p = os.path.abspath(seg_p).replace("\\", "/").replace("'", "'\\''")
                f_cat.write(f"file '{clean_seg_p}'\n")
        remux_cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list_file),
            "-t", f"{dur:.3f}",
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-movflags", "+faststart",
            temp_output_path,
        ]

    remux_res = subprocess.run(
        remux_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=win_flags,
    )
    if remux_res.returncode != 0:
        raise RuntimeError(f"Lỗi đóng gói MP4 từ Checkpoint: {remux_res.stderr[-300:]}")

    if not os.path.exists(temp_output_path) or os.path.getsize(temp_output_path) < 1_000_000:
        if os.path.exists(temp_output_path):
            try:
                os.remove(temp_output_path)
            except Exception:
                pass
        raise RuntimeError("FFmpeg kết thúc nhưng file MP4 đầu ra trống hoặc bị hỏng.")

    rendered_dur = get_audio_duration(temp_output_path)
    if rendered_dur <= 0 or abs(rendered_dur - dur) > max(4.5, dur * 0.01) or rendered_dur < (dur - 4.0):
        try:
            os.remove(temp_output_path)
        except Exception:
            pass
        raise RuntimeError(
            f"Video MP4 bị ngắt giữa chừng hoặc chưa đủ thời lượng "
            f"(Đạt {rendered_dur:.1f}s / Yêu cầu {dur:.1f}s) — Tự động hủy file lỗi để Render lại!"
        )

    os.replace(temp_output_path, output_path)
    shutil.rmtree(resume_dir, ignore_errors=True)

    cost = time.time() - start_time
    if progress_callback:
        progress_callback(100.0, f"Render video hoàn tất trong {cost:.1f}s!")

    print("================================================================================")
    print(f"🎉 RENDER HOÀN TẤT TRONG {cost:.1f}s ({cost/60:.2f} phút)!")
    print(f"🎬 Video thành phẩm: {output_path} ({rendered_dur/60:.2f} phút)")
    print("================================================================================")

    return {
        "output_path": output_path,
        "duration": rendered_dur,
        "render_time": cost,
        "resolution": f"{target_w}x{target_h}",
        "fps": fps
    }
