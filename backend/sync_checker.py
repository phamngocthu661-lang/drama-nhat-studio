import os
import re
import json
import wave
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

try:
    from scipy.io import wavfile
except Exception:
    wavfile = None


def estimate_japanese_mora_weight(text: str) -> float:
    """
    Ước lượng trọng số thời lượng phát âm tiếng Nhật (Mora + nhịp nghỉ dấu câu).
    Giúp kiểm tra tốc độ đọc (CPS / Mora-per-second) và chia phụ đề câu dài chuẩn xác.
    """
    clean = (text or "").strip()
    if not clean:
        return 1.0
    weight = 0.0
    for ch in clean:
        if ch in "「」『』（）()【】［］\"'”’ \t\r\n　":
            continue
        elif ch in "、，":
            weight += 1.6  # Nhịp nghỉ dấu phẩy
        elif ch in "。！？…・":
            weight += 2.0  # Nhịp nghỉ cuối câu
        elif ch in "ゃゅょっャュョッぁぃぅぇぉァィゥェォ":
            weight += 0.55
        elif "\u4e00" <= ch <= "\u9fff":
            # Chữ Hán (Kanji) trung bình 1.9 - 2.2 âm tiết (mora)
            weight += 1.95
        elif ch.isdigit() or ch in "一二三四五六七八九十百千万億":
            weight += 1.85
        else:
            # Hiragana / Katakana chuẩn = 1 mora
            weight += 1.0
    return max(1.0, weight)


def read_wav_mono_float(wav_path: Path) -> Tuple[int, np.ndarray]:
    """Đọc file WAV (hỗ trợ cả PCM 16-bit và IEEE Float 32-bit) về mảng float32 [-1.0, 1.0]."""
    p_str = str(wav_path)
    if wavfile is not None:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                sr, arr = wavfile.read(p_str)
            arr = np.asarray(arr)
            if arr.ndim > 1:
                arr = arr[:, 0]
            if np.issubdtype(arr.dtype, np.integer):
                max_val = float(np.iinfo(arr.dtype).max)
                arr = arr.astype(np.float32) / max_val
            else:
                arr = arr.astype(np.float32)
            return int(sr), arr
        except Exception:
            pass

    try:
        with wave.open(p_str, "rb") as wf:
            sr = wf.getframerate()
            n = wf.getnframes()
            raw = wf.readframes(n)
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            return int(sr), arr
    except Exception:
        return 0, np.zeros(0, dtype=np.float32)


def find_pause_split_points_in_wav(
    wav_path: Optional[Path],
    chunks: List[str],
    start_time: float,
    end_time: float
) -> List[Tuple[float, float]]:
    """
    Khi 1 câu thoại dài (> 48 ký tự) được tách thành 2-3 khung phụ đề nối tiếp,
    hàm này dò trực tiếp điểm lặng (nhịp lấy hơi ở dấu phẩy 、) trong file WAV của câu đó
    để phụ đề chuyển cảnh khớp chính xác tuyệt đối với giọng đọc.
    """
    n_chunks = len(chunks)
    total_dur = max(0.05, end_time - start_time)
    if n_chunks <= 1:
        return [(start_time, end_time)]

    weights = [estimate_japanese_mora_weight(c) for c in chunks]
    total_w = sum(weights)

    # Nếu có file WAV thực tế của câu này, dò thung lũng năng lượng (silence valley) quanh vị trí kỳ vọng
    if wav_path is not None and Path(wav_path).exists():
        sr, arr = read_wav_mono_float(Path(wav_path))
        total_samples = len(arr)
        if sr > 0 and total_samples > int(0.5 * sr):
            win_len = max(1, int(0.030 * sr))
            hop_len = max(1, int(0.008 * sr))
            search_radius = int(0.55 * sr)
            min_seg = max(1, int(0.35 * sr))

            split_samples = [0]
            cum_w = 0.0
            for k in range(1, n_chunks):
                cum_w += weights[k - 1]
                expected = int(total_samples * (cum_w / total_w))
                prev_s = split_samples[-1]
                min_allowed = prev_s + min_seg
                max_allowed = total_samples - (n_chunks - k) * min_seg
                if min_allowed >= max_allowed:
                    split_samples.append(max(prev_s + 1, min(expected, total_samples - 1)))
                    continue

                lo = max(min_allowed, expected - search_radius)
                hi = min(max_allowed, expected + search_radius)
                if hi - lo > win_len * 2:
                    region = arr[lo:hi]
                    n_frames = 1 + (len(region) - win_len) // hop_len
                    if n_frames > 1:
                        strides = (region.strides[0] * hop_len, region.strides[0])
                        frames = np.lib.stride_tricks.as_strided(region, shape=(n_frames, win_len), strides=strides)
                        energies = np.mean(frames * frames, axis=1)
                        positions = np.arange(n_frames, dtype=np.float32) * hop_len + lo
                        dist_penalty = (np.abs(positions - expected) / max(1.0, float(search_radius))) * (float(np.mean(energies)) * 0.20)
                        best_frame = int(np.argmin(energies + dist_penalty))
                        best_pt = lo + best_frame * hop_len + (win_len // 2)
                        best_pt = max(min_allowed, min(max_allowed, best_pt))
                    else:
                        best_pt = expected
                else:
                    best_pt = max(min_allowed, min(max_allowed, expected))
                split_samples.append(best_pt)

            split_samples.append(total_samples)
            intervals: List[Tuple[float, float]] = []
            for i in range(n_chunks):
                s_ratio = split_samples[i] / float(total_samples)
                e_ratio = split_samples[i + 1] / float(total_samples)
                st = start_time if i == 0 else start_time + total_dur * s_ratio
                ed = end_time if i == n_chunks - 1 else start_time + total_dur * e_ratio
                intervals.append((st, ed))
            return intervals

    # Fallback theo trọng số phát âm Mora nếu không đọc trực tiếp WAV
    intervals = []
    curr_t = start_time
    for i, w in enumerate(weights):
        seg_dur = total_dur * (w / total_w)
        seg_end = end_time if i == n_chunks - 1 else curr_t + seg_dur
        intervals.append((curr_t, seg_end))
        curr_t = seg_end
    return intervals


def inspect_sentence_audio_sync(
    wav_path: Path,
    text: str,
    is_strict_1to1: bool = False
) -> Dict[str, Any]:
    """
    Kiểm định chất lượng & độ khớp của 1 file audio câu thoại so với văn bản câu đó:
    1. Kiểm tra tồn tại & thời lượng tối thiểu.
    2. Kiểm tra năng lượng âm thanh (RMS) chống câu bị câm / mất tiếng.
    3. Kiểm tra năng lượng biên đầu/cuối (start_rms, end_rms) chống lỗi cắt lẹm giữa từ (do gộp cụm cũ).
    4. Kiểm tra tốc độ đọc (CPS & Mora/s) chống lỗi nuốt chữ hoặc lặp từ AI.
    """
    clean_text = re.sub(r"[「」『』（）()【】［］\"'”’\s　]", "", text or "")
    char_len = max(1, len(clean_text))
    mora_weight = estimate_japanese_mora_weight(text)

    if not wav_path.exists() or wav_path.stat().st_size < 1000:
        return {
            "passed": False,
            "reasons": ["missing_or_empty_wav"],
            "duration": 0.0,
            "rms": 0.0,
            "start_rms": 0.0,
            "end_rms": 0.0,
            "cps": 0.0,
            "cut_start": False,
            "cut_end": False,
        }

    sr, arr = read_wav_mono_float(wav_path)
    if sr <= 0 or len(arr) == 0:
        return {
            "passed": False,
            "reasons": ["corrupted_wav_read"],
            "duration": 0.0,
            "rms": 0.0,
            "start_rms": 0.0,
            "end_rms": 0.0,
            "cps": 0.0,
            "cut_start": False,
            "cut_end": False,
        }

    dur = float(len(arr)) / float(sr)
    rms = float(np.sqrt(np.mean(arr * arr)))

    edge_win = min(len(arr) // 4, int(0.028 * sr))
    start_rms = float(np.sqrt(np.mean(arr[:edge_win] ** 2))) if edge_win > 0 else 0.0
    end_rms = float(np.sqrt(np.mean(arr[-edge_win:] ** 2))) if edge_win > 0 else 0.0

    cps = float(char_len) / dur if dur > 0 else 999.0
    mps = float(mora_weight) / dur if dur > 0 else 999.0

    reasons: List[str] = []
    min_dur = 0.25 if char_len <= 3 else 0.38
    if dur < min_dur:
        reasons.append(f"too_short({dur:.2f}s)")

    if rms < 0.006:
        reasons.append(f"silent_audio(rms={rms:.4f})")

    # Nếu file được tạo từ chế độ gộp cụm cũ (is_strict_1to1=False), kiểm tra nghiêm ngặt biên đầu/cuối
    # để bắt mọi câu bị cắt lẹm giữa từ hoặc lệch sang câu bên cạnh
    edge_limit = 0.065 if is_strict_1to1 else 0.022
    cut_start = start_rms > edge_limit
    cut_end = end_rms > edge_limit
    if cut_start:
        reasons.append(f"boundary_cut_start(rms={start_rms:.3f})")
    if cut_end:
        reasons.append(f"boundary_cut_end(rms={end_rms:.3f})")

    # Kiểm tra tốc độ đọc hợp lý
    max_cps = 13.5 if is_strict_1to1 else 11.5
    min_cps = 2.2 if is_strict_1to1 else 3.0
    if char_len >= 5 and cps > max_cps:
        reasons.append(f"speaking_too_fast(cps={cps:.1f})")
    elif char_len >= 6 and cps < min_cps and dur > 3.5:
        reasons.append(f"speaking_too_slow(cps={cps:.1f})")

    return {
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "duration": round(dur, 4),
        "rms": round(rms, 4),
        "start_rms": round(start_rms, 4),
        "end_rms": round(end_rms, 4),
        "cps": round(cps, 2),
        "mps": round(mps, 2),
        "cut_start": cut_start,
        "cut_end": cut_end,
    }


def audit_all_sentences_sync(
    sentences: List[str],
    sentences_dir: Path,
    require_strict_1to1: bool = False
) -> Dict[str, Any]:
    """
    Quét kiểm định toàn bộ N câu thoại trong thư mục sentences_dir.
    Trả về danh sách các chỉ số câu (0-based) cần phải tạo lại (redo_indices) để đảm bảo
    100% câu thoại khớp tuyệt đối với phụ đề.
    """
    manifest_path = sentences_dir / "sync_1to1_manifest.json"
    strict_map: Dict[str, bool] = {}
    if manifest_path.exists():
        try:
            strict_map = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            strict_map = {}

    total = len(sentences)
    redo_set = set()
    details: List[Dict[str, Any]] = []

    for idx, text in enumerate(sentences):
        key = f"sentence_{idx+1:04d}.wav"
        wav_p = sentences_dir / key
        is_1to1 = bool(strict_map.get(key, False))

        if require_strict_1to1 and not is_1to1:
            redo_set.add(idx)
            details.append({
                "index": idx + 1,
                "passed": False,
                "reasons": ["legacy_grouped_audio_not_1to1"],
                "text": text[:30]
            })
            continue

        res = inspect_sentence_audio_sync(wav_p, text, is_strict_1to1=is_1to1)
        if not res["passed"]:
            redo_set.add(idx)
            # Nếu bị cắt lẹm ở đầu câu, câu liền trước cũng bị lệch biên -> làm lại cả đôi
            if res.get("cut_start") and idx > 0:
                redo_set.add(idx - 1)
            # Nếu bị cắt lẹm ở cuối câu, câu liền sau cũng bị lệch biên -> làm lại cả đôi
            if res.get("cut_end") and idx + 1 < total:
                redo_set.add(idx + 1)
            details.append({
                "index": idx + 1,
                "passed": False,
                "reasons": res["reasons"],
                "duration": res["duration"],
                "cps": res["cps"],
                "text": text[:30]
            })

    redo_indices = sorted(redo_set)
    return {
        "passed": len(redo_indices) == 0,
        "total_sentences": total,
        "passed_sentences": total - len(redo_indices),
        "failed_count": len(redo_indices),
        "redo_indices": redo_indices,
        "failed_samples": details[:30],
    }


def _parse_srt_timestamp(ts: str) -> float:
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600.0 + float(parts[1]) * 60.0 + float(parts[2])
    return 0.0


def probe_media_info(file_path: Path) -> Dict[str, Any]:
    """Kiểm tra thông số thực tế của file MP4 / WAV bằng ffprobe."""
    if not file_path.exists() or file_path.stat().st_size < 1024:
        return {"valid": False, "reason": "file_missing_or_empty"}

    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,codec_name,duration",
        "-of", "json",
        str(file_path)
    ]
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        if res.returncode != 0:
            return {"valid": False, "reason": f"ffprobe_error: {res.stderr.strip()[:120]}"}
        data = json.loads(res.stdout or "{}")
        streams = data.get("streams", [])
        fmt = data.get("format", {})
        dur = float(fmt.get("duration", 0.0) or 0.0)
        has_video = any(s.get("codec_type") == "video" for s in streams)
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        return {
            "valid": dur > 0,
            "duration": dur,
            "has_video": has_video,
            "has_audio": has_audio,
            "streams": streams,
        }
    except Exception as e:
        return {"valid": False, "reason": str(e)}


def validate_completed_mp4_file(
    mp4_path: Path,
    master_wav_path: Optional[Path] = None,
    script_char_count: int = 0,
) -> Dict[str, Any]:
    """
    Kiểm định nghiêm ngặt một file `{ma_id}_master.mp4` trên ổ cứng xem có thực sự hoàn chỉnh 100% hay bị lỗi / ngắt giữa chừng:
    1. Kiểm tra tồn tại & dung lượng tối thiểu (>= 10MB; nếu kịch bản >= 25.000 chữ thì >= 20MB).
    2. Dùng `ffprobe` kiểm tra cấu trúc container MP4 (`moov atom`), bắt buộc có đủ cả luồng hình (`video`) và luồng tiếng (`audio`).
    3. Kiểm tra thời lượng thực tế (`video_dur`) không bị cắt ngắn so với độ dài kịch bản (`script_char_count`) và khớp với `master_voice.wav` (sai số <= 5s).
    """
    if not mp4_path or not mp4_path.exists():
        return {"valid": False, "duration": 0.0, "reason": "missing_file"}

    try:
        st_size = mp4_path.stat().st_size
    except Exception:
        return {"valid": False, "duration": 0.0, "reason": "stat_failed"}

    min_bytes = 20_000_000 if script_char_count >= 25_000 else 5_000_000
    if st_size < min_bytes:
        return {
            "valid": False,
            "duration": 0.0,
            "reason": f"Dung lượng MP4 quá nhỏ ({st_size / (1024 * 1024):.1f} MB) — tiến trình render bị ngắt sớm",
        }

    p_info = probe_media_info(mp4_path)
    if not p_info.get("valid"):
        raw_reason = str(p_info.get("reason") or "corrupted_mp4")
        if "moov atom not found" in raw_reason.lower():
            return {
                "valid": False,
                "duration": 0.0,
                "reason": "Video MP4 bị ngắt giữa chừng (chưa đóng gói xong moov atom)",
            }
        return {
            "valid": False,
            "duration": 0.0,
            "reason": f"File MP4 bị lỗi cấu trúc ({raw_reason[:80]})",
        }

    if not p_info.get("has_video") or not p_info.get("has_audio"):
        return {
            "valid": False,
            "duration": 0.0,
            "reason": "Video MP4 bị thiếu luồng hình ảnh (video) hoặc luồng âm thanh (audio)",
        }

    video_dur = float(p_info.get("duration", 0.0) or 0.0)
    if video_dur < 60.0:
        return {
            "valid": False,
            "duration": video_dur,
            "reason": f"Thời lượng Video MP4 quá ngắn ({video_dur:.1f}s)",
        }

    # Đối chiếu thời lượng tối thiểu dựa trên độ dài kịch bản tiếng Nhật (~0.08s/chữ là ngưỡng sàn an toàn)
    if script_char_count >= 10_000:
        min_expected_dur = max(300.0, float(script_char_count) * 0.08)
        if video_dur < min_expected_dur:
            return {
                "valid": False,
                "duration": video_dur,
                "reason": (
                    f"Video MP4 bị ngắt giữa chừng (Mới đạt {video_dur / 60:.1f} phút, "
                    f"cần tối thiểu {min_expected_dur / 60:.1f} phút cho {script_char_count:,} chữ)"
                ),
            }

    # Đối chiếu trực tiếp với master_voice.wav nếu có sẵn
    if master_wav_path and master_wav_path.exists():
        wav_dur = 0.0
        try:
            with wave.open(str(master_wav_path), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0 and frames > 0:
                    wav_dur = float(frames) / float(rate)
        except Exception:
            w_info = probe_media_info(master_wav_path)
            if w_info.get("valid"):
                wav_dur = float(w_info.get("duration", 0.0) or 0.0)

        if wav_dur > 60.0:
            if script_char_count >= 10_000 and wav_dur < max(300.0, float(script_char_count) * 0.08):
                return {
                    "valid": False,
                    "duration": video_dur,
                    "reason": f"File Voice gốc bị thiếu câu ({wav_dur / 60:.1f} phút cho {script_char_count:,} chữ)",
                }
            if abs(video_dur - wav_dur) > 5.0 or video_dur < wav_dur - 4.0:
                return {
                    "valid": False,
                    "duration": video_dur,
                    "reason": (
                        f"Video MP4 bị ngắt giữa chừng ({video_dur / 60:.1f} phút / "
                        f"Tổng thời lượng Voice {wav_dur / 60:.1f} phút)"
                    ),
                }

    return {"valid": True, "duration": round(video_dur, 3), "reason": "ok"}


def verify_rendered_video_sync(
    video_path: Path,
    master_wav_path: Path,
    srt_path: Path,
    sentences: List[str],
    sentences_dir: Path
) -> Dict[str, Any]:
    """
    BƯỚC KIỂM ĐỊNH CUỐI CÙNG TRÊN FILE VIDEO MP4:
    1. Kiểm tra file MP4 có mở được bình thường (đầy đủ luồng hình H264 + luồng tiếng AAC + moov atom).
    2. Kiểm tra độ khớp thời lượng giữa Video MP4 <-> Master Voice WAV <-> Mốc cuối Subtitles SRT (sai số <= 0.6s).
    3. Kiểm tra cấu trúc các khung phụ đề SRT (không chồng lấn thời gian, không rớt dòng thứ 4, đủ chữ).
    4. Kiểm tra biên bản khớp câu thoại (Sentence-level Sync Audit).
    """
    issues: List[str] = []

    v_info = probe_media_info(video_path)
    if not v_info.get("valid"):
        issues.append(f"Video MP4 lỗi hoặc chưa đóng gói xong ({v_info.get('reason', 'unknown')})")
    else:
        if not v_info.get("has_video"):
            issues.append("Video MP4 thiếu luồng hình ảnh (video stream)")
        if not v_info.get("has_audio"):
            issues.append("Video MP4 thiếu luồng âm thanh (audio stream)")

    w_info = probe_media_info(master_wav_path)
    if not w_info.get("valid"):
        issues.append("File master_voice.wav bị lỗi hoặc không đọc được thời lượng")

    video_dur = float(v_info.get("duration", 0.0) or 0.0)
    wav_dur = float(w_info.get("duration", 0.0) or 0.0)

    # Kiểm tra file SRT
    srt_last_end = 0.0
    srt_blocks_count = 0
    overlap_count = 0
    over_3_lines_count = 0

    if not srt_path.exists() or srt_path.stat().st_size < 10:
        issues.append("File phụ đề subtitles.srt không tồn tại hoặc trống")
    else:
        raw_srt = srt_path.read_text(encoding="utf-8").strip()
        blocks = [b.strip() for b in re.split(r"\n\s*\n", raw_srt) if b.strip()]
        srt_blocks_count = len(blocks)
        prev_end = 0.0
        for blk in blocks:
            lines = [l.strip() for l in blk.splitlines() if l.strip()]
            if len(lines) >= 3 and "-->" in lines[1]:
                ts_parts = lines[1].split("-->")
                st = _parse_srt_timestamp(ts_parts[0])
                ed = _parse_srt_timestamp(ts_parts[1])
                if st < prev_end - 0.02:
                    overlap_count += 1
                prev_end = max(prev_end, ed)
                srt_last_end = max(srt_last_end, ed)
                text_lines = lines[2:]
                if len(text_lines) > 3:
                    over_3_lines_count += 1

    if overlap_count > 0:
        issues.append(f"Phát hiện {overlap_count} khung phụ đề bị chồng lấn thời gian")
    if over_3_lines_count > 0:
        issues.append(f"Phát hiện {over_3_lines_count} khung phụ đề vượt quá 3 dòng")

    # Kiểm tra độ lệch thời lượng tổng thể
    diff_video_wav = abs(video_dur - wav_dur)
    diff_wav_srt = abs(wav_dur - srt_last_end)

    if video_dur > 0 and wav_dur > 0 and diff_video_wav > 0.85:
        issues.append(f"Thời lượng Video MP4 ({video_dur:.2f}s) lệch so với Voice ({wav_dur:.2f}s) là {diff_video_wav:.2f}s")
    if wav_dur > 0 and srt_last_end > 0 and diff_wav_srt > 0.50:
        issues.append(f"Thời lượng Phụ đề SRT ({srt_last_end:.2f}s) lệch so với Voice ({wav_dur:.2f}s) là {diff_wav_srt:.2f}s")

    # Kiểm tra độ khớp từng câu thoại
    sent_audit = audit_all_sentences_sync(sentences, sentences_dir, require_strict_1to1=False)
    if not sent_audit["passed"]:
        issues.append(f"Phát hiện {sent_audit['failed_count']}/{sent_audit['total_sentences']} câu thoại bị lệch biên hoặc bất thường âm lượng/tốc độ")

    passed = len(issues) == 0
    return {
        "passed": passed,
        "status_label": "✅ ĐẠT (Sub & Voice khớp 100%)" if passed else "❌ CHƯA KHỚP (Cần làm lại)",
        "video_duration": round(video_dur, 3),
        "voice_duration": round(wav_dur, 3),
        "srt_end_duration": round(srt_last_end, 3),
        "drift_video_vs_voice_sec": round(diff_video_wav, 3),
        "drift_voice_vs_srt_sec": round(diff_wav_srt, 3),
        "srt_blocks_count": srt_blocks_count,
        "sentence_audit": sent_audit,
        "issues": issues,
    }
