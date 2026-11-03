import os
import sys
import re
import time
import wave
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, Any

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
    progress_callback: Optional[Callable[[float, str], None]] = None
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

    stock_dur = get_audio_duration(stock_video_path)
    pts_factor = 1.0 / stock_speed if stock_speed > 0 else 1.0
    single_pass_dur = stock_dur * pts_factor if stock_dur > 0 else 0.0

    # Tính kích thước khi Zoom 110% (chẵn pixel cho yuv420p)
    effective_zoom = zoom_factor if zoom_factor > 1.0 else 1.10
    zoom_w = (int(round(target_w * effective_zoom)) // 2) * 2
    zoom_h = (int(round(target_h * effective_zoom)) // 2) * 2

    mode_desc = (
        f"LẬT NGANG (hflip) + ZOOM {int(round(effective_zoom * 100))}%"
        if (flip_horizontal or zoom_factor > 1.0)
        else "BẢN GỐC 100% (Tự động nối Lật + Zoom 110% nếu vượt thời lượng)"
    )

    print("================================================================================")
    print("🎬 [DRAMA NHẬT RENDERER] BẮT ĐẦU DỰNG VIDEO CHUẨN 5 LỚP")
    print(f"📐 Độ phân giải: {target_w}x{target_h} | 🎞️ FPS: {fps}")
    print(f"🎵 Audio Voice: {audio_path} ({dur/60:.2f} phút)")
    print(f"💬 Subtitle: {subtitle_path} (Font: {font_name}, SubSize: {font_size})")
    print(f"🎥 Stock: {stock_video_path} | Chế độ: {mode_desc}")
    print(f"🏷️ Kênh: {channel_name} | 📁 Xuất: {output_path}")
    print("================================================================================")

    if font_size >= 110 and os.path.exists(subtitle_path):
        _ensure_wrapped_srt(subtitle_path, max_chars=17, max_segment_chars=48)

    abs_sub = os.path.abspath(subtitle_path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    fonts_arg = ""
    if fonts_dir and os.path.exists(fonts_dir):
        abs_fonts_dir = os.path.abspath(fonts_dir).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
        fonts_arg = f":fontsdir='{abs_fonts_dir}'"

    has_particles = particles_clip and os.path.exists(particles_clip)

    # Lớp 1: Video Stock Background
    # - Nếu là Lần dùng 2 (flip_horizontal=True hoặc zoom_factor > 1.0): Lật ngang (hflip) + Zoom 110%
    # - Nếu là Lần dùng 1 nhưng thời lượng audio dài hơn 1 lượt stock (dur > single_pass_dur):
    #   Nối Lượt 1 (Gốc 100%) + Lượt 2 (Lật ngang + Zoom 110%) để tăng gấp đôi thời lượng không trùng lặp
    filters = []
    cmd = ["ffmpeg", "-y"]
    input_idx = 0

    if flip_horizontal or zoom_factor > 1.0:
        cmd.extend(["-stream_loop", "-1", "-i", stock_video_path])
        input_idx += 1
        flip_filter = "hflip," if flip_horizontal else ""
        filters.append(
            f"[0:v]setpts={pts_factor}*PTS,{flip_filter}"
            f"scale={zoom_w}:{zoom_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h},fps={fps},format=yuv420p,"
            f"eq=brightness={brightness}:contrast={contrast}:saturation=0.72,"
            f"vignette={vignette_param}[bg_dark]"
        )
    elif extend_with_flip_zoom and single_pass_dur > 0 and dur > single_pass_dur:
        # Lượt 1: Gốc 100% -> Lượt 2: Lật ngang + Zoom 110% (kéo dài gấp đôi thời lượng video stock)
        cmd.extend(["-i", stock_video_path])
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
        cmd.extend(["-stream_loop", "-1", "-i", stock_video_path])
        input_idx += 1
        filters.append(
            f"[0:v]setpts={pts_factor}*PTS,"
            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
            f"crop={target_w}:{target_h},fps={fps},format=yuv420p,"
            f"eq=brightness={brightness}:contrast={contrast}:saturation=0.72,"
            f"vignette={vignette_param}[bg_dark]"
        )

    current_v = "[bg_dark]"

    # Lớp 3: Star Particles
    if has_particles:
        cmd.extend(["-stream_loop", "-1", "-i", particles_clip])
        filters.append(f"[{input_idx}:v]scale={target_w}:{target_h},format=yuva420p[stars_scaled]")
        filters.append(f"{current_v}[stars_scaled]overlay=shortest=1[with_stars]")
        current_v = "[with_stars]"
        input_idx += 1

    # Voice input
    voice_input_idx = input_idx
    cmd.extend(["-i", audio_path])
    input_idx += 1

    # BGM input
    has_bgm = bgm_path and os.path.exists(bgm_path)
    if has_bgm:
        cmd.extend(["-stream_loop", "-1", "-i", bgm_path])
        bgm_input_idx = input_idx
        input_idx += 1

    # Tìm font file arial nếu có sẵn trong Windows
    arial_font = "C\\:/Windows/Fonts/arial.ttf"
    font_arg_watermark = f":fontfile='{arial_font}'" if os.path.exists("C:/Windows/Fonts/arial.ttf") else ""

    # Lớp 4 (Dải khung đen), Lớp 6 (Watermark), Lớp 5 (Sub vàng chanh — WrapStyle=2 khóa cứng tối đa 3 dòng, cấm tự rớt dòng thứ 4)
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

    # Hòa âm Audio (Voice 100% + BGM)
    if has_bgm:
        filters.append(
            f"[{voice_input_idx}:a]volume=1.0[voice];"
            f"[{bgm_input_idx}:a]volume={bgm_volume}[bgm];"
            f"[voice][bgm]amix=inputs=2:duration=first[a_out]"
        )
    else:
        filters.append(f"[{voice_input_idx}:a]volume=1.0[a_out]")

    fc = ";".join(filters)

    use_nvenc = check_nvenc_available()
    cpu_threads = max(4, (os.cpu_count() or 8) - 1)
    if use_nvenc:
        v_codec_args = [
            "-c:v", "h264_nvenc",
            "-preset", "p2",
            "-tune", "hq",
            "-rc", "vbr",
            "-cq", "21",
            "-b:v", "0",
            "-pix_fmt", "yuv420p"
        ]
        encoder_label = "NVIDIA GPU NVENC Turbo (h264_nvenc p2)"
    else:
        v_codec_args = [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-threads", str(cpu_threads),
            "-pix_fmt", "yuv420p"
        ]
        encoder_label = f"CPU Multi-Thread ({cpu_threads} threads libx264)"

    # Render ra file tạm (_rendering_tmp.mp4) trước; chỉ đổi tên sang output_path chính thức sau khi
    # FFmpeg thoát mã 0 VÀ kiểm định đủ 100% thời lượng + moov atom hợp lệ (Chống lỗi ngắt giữa chừng vẫn báo thành công)
    base_stem = os.path.splitext(os.path.basename(output_path))[0]
    temp_output_path = os.path.join(out_dir, f"_{base_stem}_rendering_tmp.mp4")
    for stale_f in (temp_output_path, output_path):
        if os.path.exists(stale_f):
            try:
                os.remove(stale_f)
            except Exception:
                pass

    cmd.extend([
        "-t", str(dur),
        "-filter_complex_threads", str(max(2, cpu_threads // 2)),
        "-filter_complex", fc,
        "-map", "[v_out]",
        "-map", "[a_out]",
        *v_codec_args,
        "-threads", str(cpu_threads),
        "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k",
        "-progress", "pipe:1",
        temp_output_path
    ])

    print(f"\n-> Bắt đầu tiến trình encode FFmpeg ({encoder_label})...")
    if progress_callback:
        progress_callback(0.0, f"Đang khởi tạo FFmpeg encode ({encoder_label})...")

    # Chạy subprocess và đọc tiến độ
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding="utf-8",
        errors="replace",
        creationflags=0x08000000 if os.name == "nt" else 0,
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
                    curr_sec = parse_time_to_seconds(match.group(1))
                    percent = min(99.9, round((curr_sec / dur) * 100, 1))
                    if progress_callback:
                        progress_callback(percent, f"Đang render video: {percent}% ({curr_sec:.0f}s / {dur:.0f}s)")
    except BaseException:
        try:
            process.kill()
            process.wait(timeout=3)
        except Exception:
            pass
        if os.path.exists(temp_output_path):
            try:
                os.remove(temp_output_path)
            except Exception:
                pass
        raise

    rc = process.poll()
    if rc != 0:
        if os.path.exists(temp_output_path):
            try:
                os.remove(temp_output_path)
            except Exception:
                pass
        err_detail = "\n".join(log_tail[-8:])
        raise RuntimeError(f"FFmpeg render thất bại với mã lỗi {rc}: {err_detail}")

    # Kiểm định nghiêm ngặt file tạm vừa xuất ra trước khi công nhận hoàn thành
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
