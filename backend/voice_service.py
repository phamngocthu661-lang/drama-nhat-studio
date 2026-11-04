import os
import sys
import json
import time
import wave
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple

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


def format_timestamp(seconds: float) -> str:
    """Định dạng giây thành SRT timestamp: HH:MM:SS,mmm"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    mils = int(round((seconds - int(seconds)) * 1000))
    if mils >= 1000:
        mils = 999
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{mils:03d}"


def _find_bounded_break(s: str, target: int, lo: int, hi: int) -> int:
    """Tìm vị trí ngắt dòng tự nhiên nhất trong khoảng bắt buộc [lo, hi]."""
    lo = max(1, lo)
    hi = min(len(s) - 1, hi)
    if lo > hi:
        return max(1, min(len(s) - 1, target))

    best_idx = -1
    best_score = 9999
    # 1. Ưu tiên dấu câu 、。！？」』
    for i in range(lo - 1, hi):
        ch = s[i]
        pos = i + 1
        if ch in "、。！？」』":
            if pos < len(s) and s[pos] in "、。！？」』）":
                continue
            score = abs(pos - target)
            if score < best_score:
                best_score = score
                best_idx = pos
    if best_idx != -1:
        return best_idx

    # 2. Ưu tiên trợ từ tiếng Nhật (không cắt giữa từ)
    for i in range(lo - 1, hi):
        ch = s[i]
        pos = i + 1
        if ch in "はがをにへとでも":
            if pos < len(s) and s[pos] in "はがをにへとでも、。！？」』）":
                continue
            score = abs(pos - target) + 1
            if score < best_score:
                best_score = score
                best_idx = pos
    if best_idx != -1:
        return best_idx

    return max(lo, min(hi, target))


def format_srt_text(text: str, max_chars_per_line: int = 17) -> str:
    """
    Chia câu thoại thành TỐI ĐA 3 DÒNG cân đối (mỗi dòng <= max_chars_per_line ký tự)
    cho cỡ chữ FontSize=135. Tuyệt đối không bao giờ vượt quá 3 dòng.
    """
    text = text.replace("\n", "").strip()
    n = len(text)
    if n <= max_chars_per_line:
        return text

    # Nếu câu vừa trong 2 dòng (n <= max_chars_per_line * 2)
    if n <= max_chars_per_line * 2:
        lo = max(4, n - max_chars_per_line)
        hi = min(n - 4, max_chars_per_line)
        bp = _find_bounded_break(text, n // 2, lo, hi)
        l1, l2 = text[:bp].strip(), text[bp:].strip()
        if len(l1) <= max_chars_per_line and len(l2) <= max_chars_per_line:
            return f"{l1}\n{l2}"

    # Chia thành đúng 3 dòng cân đối, ép biên chặt chẽ để không dòng nào vượt quá max_chars_per_line
    eff_max = max(max_chars_per_line, (n + 2) // 3)
    lo1 = max(4, n - 2 * eff_max)
    hi1 = min(n - 8, eff_max)
    bp1 = _find_bounded_break(text, n // 3, lo1, hi1)
    line1 = text[:bp1].strip()

    rem = text[bp1:].strip()
    m = len(rem)
    if m <= eff_max:
        return f"{line1}\n{rem}"

    lo2 = max(4, m - eff_max)
    hi2 = min(m - 4, eff_max)
    bp2 = _find_bounded_break(rem, m // 2, lo2, hi2)
    line2 = rem[:bp2].strip()
    line3 = rem[bp2:].strip()
    return "\n".join([x for x in [line1, line2, line3] if x])


def split_long_subtitle_segments(
    text: str,
    start: float,
    end: float,
    max_segment_chars: int = 48,
    max_chars_per_line: int = 17,
    wav_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Nếu 1 câu thoại quá dài (> 48 ký tự, tức > 3 dòng x 16-17 chữ), tự động tách thành
    2 hoặc nhiều phân đoạn phụ đề nối tiếp nhau theo điểm lặng thực tế trong file WAV (hoặc trọng số Mora)
    để MỖI PHỤ ĐỀ CHỈ CÓ TỐI ĐA 3 DÒNG và chuyển phụ đề khớp đúng nhịp nghỉ giọng đọc.
    """
    clean = text.replace("\n", "").strip()
    if not clean:
        return []

    chunks: List[str] = [clean]
    while any(len(c) > max_segment_chars for c in chunks):
        new_chunks: List[str] = []
        for c in chunks:
            if len(c) <= max_segment_chars:
                new_chunks.append(c)
            else:
                n_c = len(c)
                # Nếu câu quá dài (> 2 * max_segment_chars), cắt khoảng 1/3 đầu trước
                target = max_segment_chars - 6 if n_c > max_segment_chars * 2 else n_c // 2
                lo = max(12, target - 12)
                hi = min(n_c - 10, max_segment_chars)
                bp = _find_bounded_break(c, target, lo, hi)
                new_chunks.append(c[:bp].strip())
                new_chunks.append(c[bp:].strip())
        chunks = [x for x in new_chunks if x]

    try:
        from backend.sync_checker import find_pause_split_points_in_wav
        intervals = find_pause_split_points_in_wav(
            Path(wav_path) if wav_path else None,
            chunks,
            start,
            end
        )
    except Exception:
        total_chars = max(1, sum(len(c) for c in chunks))
        total_dur = max(0.1, end - start)
        intervals = []
        curr_t = start
        for i, c in enumerate(chunks):
            seg_dur = total_dur * (len(c) / total_chars)
            seg_end = end if i == len(chunks) - 1 else curr_t + seg_dur
            intervals.append((curr_t, seg_end))
            curr_t = seg_end

    results = []
    for c, (seg_start, seg_end) in zip(chunks, intervals):
        results.append({
            "start": seg_start,
            "end": seg_end,
            "text": format_srt_text(c, max_chars_per_line=max_chars_per_line)
        })
    return results


import re as _re_mod

_FAST_MAYBE_LEAK_RE = _re_mod.compile(
    r"[A-Za-z]|日本語脚本|日本語ナレーション|```|---|===|"
    r"LOCKED_TITLE|SELECTED_TITLE|WINNING_TITLE|FINAL_TITLE|DRAFT_TITLE",
    _re_mod.IGNORECASE,
)


def strip_leaked_titles_and_metadata(raw_text: str):
    """
    Quét, ghi nhận và xóa sạch 100% các dòng [LOCKED_TITLE], [SELECTED_TITLE], [WINNING_TITLE],
    bao gồm cả phần câu tiêu đề bị tách thành 2–4 dòng kế tiếp, cũng như các dòng nhãn kỹ thuật
    (STEP 4 · BUILD PART A, PART A — 日本語脚本, <CodeBlock>, <WritingBlock>, CONTINUITY:, ENDING:...)
    để tuyệt đối không bao giờ bị lọt vào quá trình tạo Voice (TTS) hay Phụ đề Video (Render MP4).
    """
    import re
    if not raw_text:
        return "", []
    if not _FAST_MAYBE_LEAK_RE.search(raw_text):
        return raw_text.strip(), []

    cleaned_raw = re.sub(
        r"</?(?:CodeBlock|WritingBlock|title|grid|grid-item|caption)[^>]*>",
        "",
        raw_text,
        flags=re.IGNORECASE,
    )
    lines = cleaned_raw.splitlines()
    kept = []
    removed = []
    n = len(lines)
    i = 0

    title_key_re = re.compile(
        r"(?:LOCKED_TITLE|SELECTED_TITLE|WINNING_TITLE|FINAL_TITLE|DRAFT_TITLE|TITLE_LOCKED|LOCKED_TITLE_PROMISE|TITLE_FACTS)\s*[:：\-—]?",
        re.IGNORECASE,
    )
    step_part_re = re.compile(
        r"^(?:[A-Z]{1,6}\d{1,5}\s*[—–\-·:：]+\s*)?(?:STEP\s*[1-7]\b|BUILD\s+PART\s*[ABC]\b|PART\s*[:：\-—–·]?\s*[ABC]\b|SCENE\s+[ABC]?\d+\b|CHAPTER\s+\d+\b)",
        re.IGNORECASE,
    )
    stop_block_re = re.compile(
        r"^(?:PART_PURE_CHARACTER_COUNT|PART_LENGTH_GATE|CONTINUITY_LEDGER|CONTINUITY\s+LEDGER|PART_HANDOFF_LEDGER|HANDOFF_LEDGER|HANDOFF\s+LEDGER|PART_[ABC]_HANDOFF|NEXT_ACTION|READY_FOR_AUDIT|PATCH_CHANGELOG)\b",
        re.IGNORECASE,
    )
    meta_kv_re = re.compile(r"^[A-Z][A-Z0-9_/\-\s]{1,35}[:：]")
    ellipsis_endings = ("…", "…」", "…」」", "…』", "…。", "…。」", "…！」", "…？」")

    while i < n:
        raw_ln = lines[i]
        s = raw_ln.strip()
        if not s:
            kept.append(raw_ln)
            i += 1
            continue

        s_clean = re.sub(r"^[#*>\-\s`•]+", "", s).replace("**", "").replace("`", "").strip()
        if not s_clean or s_clean.startswith(("```", "---", "===")):
            removed.append((i + 1, s))
            i += 1
            continue

        if stop_block_re.match(s_clean):
            for k in range(i, n):
                if lines[k].strip():
                    removed.append((k + 1, lines[k].strip()))
            break

        # 1. Phát hiện và xóa trọn cụm LOCKED_TITLE / SELECTED_TITLE (kể cả khi tiêu đề bị tách thành 2-4 dòng)
        if title_key_re.search(s_clean):
            body0 = re.sub(
                r"^.*?(?:LOCKED_TITLE|SELECTED_TITLE|WINNING_TITLE|FINAL_TITLE|DRAFT_TITLE|TITLE_LOCKED|LOCKED_TITLE_PROMISE|TITLE_FACTS)\s*[:：\-—]*\s*",
                "",
                s_clean,
                flags=re.IGNORECASE,
            ).strip()
            end_i = i + 1
            open_q = body0.count("「")
            close_q = body0.count("」")
            if not (body0.endswith(ellipsis_endings) and open_q <= close_q + 1):
                acc = body0
                for k in range(i + 1, min(n, i + 5)):
                    cand = lines[k].strip()
                    if not cand:
                        break
                    acc += cand
                    if cand.endswith(ellipsis_endings) and len(acc) <= 185:
                        end_i = k + 1
                        break
                    if open_q > close_q and acc.count("「") <= acc.count("」") and len(acc) <= 185:
                        end_i = k + 1
                        break
            for k in range(i, end_i):
                removed.append((k + 1, lines[k].strip()))
            i = end_i
            continue

        # 2. Phát hiện và xóa các dòng tiêu đề STEP / PART / 日本語脚本
        if (step_part_re.match(s_clean) and len(s_clean) < 90) or (
            re.search(r"(?:日本語脚本|日本語ナレーション本文|HANDOFF_LEDGER|PURE_CHARACTER_COUNT)", s_clean, re.IGNORECASE)
            and len(s_clean) < 90
        ):
            removed.append((i + 1, s))
            i += 1
            continue

        # 3. Phát hiện và xóa các dòng Metadata tiếng Anh (CONTINUITY:, ENDING:, ID:, STATUS:...)
        if meta_kv_re.match(s_clean):
            removed.append((i + 1, s))
            i += 1
            continue

        kept.append(s_clean)
        i += 1

    out_text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    return out_text, removed


def split_japanese_script(raw_text: str) -> List[str]:
    """Tách kịch bản thành các câu thoại chuẩn cảm xúc, giữ nguyên dấu đóng ngoặc kép (tự động lọc bỏ LOCKED_TITLE & Metadata rò rỉ)."""
    cleaned_script, _ = strip_leaked_titles_and_metadata(raw_text)
    closing_chars = set("」』）)】］\"'”’")
    punct_only_chars = set("。！？、…・　 \t\r\n「『（(【［」』）)】］\"'”’")

    lines = cleaned_script.strip().split("\n")
    sentences = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        # Tách theo dấu chấm câu Nhật, gộp dấu đóng ngoặc đi kèm ngay sau dấu kết câu
        sub_sentences = []
        curr = ""
        n = len(line)
        i = 0
        while i < n:
            char = line[i]
            curr += char
            if char in "。！？":
                while i + 1 < n and line[i + 1] in closing_chars:
                    i += 1
                    curr += line[i]
                sub_sentences.append(curr.strip())
                curr = ""
            i += 1
        if curr.strip():
            sub_sentences.append(curr.strip())

        for s in sub_sentences:
            s = s.strip()
            if s and any(ch not in punct_only_chars for ch in s):
                sentences.append(s)
    return sentences


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
        try:
            import torchaudio
            info = torchaudio.info(str(file_path))
            if info.sample_rate > 0 and info.num_frames > 0:
                return float(info.num_frames) / float(info.sample_rate)
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


def split_waveform_for_group(wav_tensor, group_texts: List[str], sample_rate: int):
    """Tách waveform của cụm câu (2-3 câu) về từng câu riêng biệt tại điểm lặng tự nhiên giữa các câu."""
    import torch

    if wav_tensor.dim() == 1:
        wav_tensor = wav_tensor.unsqueeze(0)
    if len(group_texts) <= 1:
        return [wav_tensor]

    total_samples = wav_tensor.shape[-1]
    n_sents = len(group_texts)
    min_seg = max(1, int(0.22 * sample_rate))

    if total_samples <= min_seg * n_sents:
        chunk_sz = max(1, total_samples // n_sents)
        pieces = []
        for i in range(n_sents):
            st = i * chunk_sz
            ed = total_samples if i == n_sents - 1 else (i + 1) * chunk_sz
            pieces.append(wav_tensor[:, st:ed])
        return pieces

    weights = [max(2.0, float(len(t.strip())) + 3.0) for t in group_texts]
    total_w = sum(weights)

    win_len = max(1, int(0.035 * sample_rate))
    hop_len = max(1, int(0.010 * sample_rate))
    search_radius = int(0.45 * sample_rate)
    mono = wav_tensor[0]

    split_points = [0]
    cum_w = 0.0
    for k in range(1, n_sents):
        cum_w += weights[k - 1]
        expected = int(total_samples * (cum_w / total_w))
        prev_pt = split_points[-1]
        min_allowed = prev_pt + min_seg
        max_allowed = total_samples - (n_sents - k) * min_seg

        if min_allowed >= max_allowed:
            split_points.append(max(prev_pt + 1, min(expected, total_samples - 1)))
            continue

        lo = max(min_allowed, expected - search_radius)
        hi = min(max_allowed, expected + search_radius)

        if hi - lo > win_len * 2:
            region = mono[lo:hi]
            frames = region.unfold(0, win_len, hop_len)
            energies = frames.pow(2).mean(dim=-1)
            # Ưu tiên điểm lặng gần vị trí kỳ vọng
            positions = torch.arange(energies.numel(), device=energies.device, dtype=torch.float32) * hop_len + lo
            dist_penalty = ((positions - expected).abs() / max(1.0, float(search_radius))) * (energies.mean().item() * 0.15)
            best_frame = int((energies + dist_penalty).argmin().item())
            best_pt = lo + best_frame * hop_len + (win_len // 2)
            best_pt = max(min_allowed, min(max_allowed, best_pt))
        else:
            best_pt = max(min_allowed, min(max_allowed, expected))

        split_points.append(best_pt)

    split_points.append(total_samples)
    return [wav_tensor[:, split_points[i]:split_points[i + 1]] for i in range(n_sents)]


class VoiceStudioService:
    _instance = None
    _model = None
    _prompt_cache: Dict[str, Any] = {}

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir:
            self.root_dir = Path(root_dir)
        else:
            p = Path(__file__).resolve().parent.parent
            if (p / "VoiceStudio").exists():
                self.root_dir = p
            elif (p.parent / "VoiceStudio").exists():
                self.root_dir = p.parent
            else:
                self.root_dir = p
        self.voicestudio_dir = self.root_dir / "VoiceStudio"
        self.model_path = self.root_dir / "pretrained_models" / "OmniVoice"
        self.voices_dir = self.root_dir / "assets" / "voices"
        self.ref_voice_path = self.voices_dir / "Nhat_Drama.wav"
        self.ref_text_path = self.voices_dir / "Nhat_Drama.txt"

        # Đảm bảo đường dẫn tới VoiceStudio
        if str(self.voicestudio_dir) not in sys.path:
            sys.path.insert(0, str(self.voicestudio_dir))

        self.engine = None

    def _ensure_engine(self):
        if self.engine is None:
            main_weights = self.model_path / "model.safetensors"
            tok_weights = self.model_path / "audio_tokenizer" / "model.safetensors"
            if not main_weights.exists() or main_weights.stat().st_size < 1_000_000_000 or not tok_weights.exists() or tok_weights.stat().st_size < 800_000_000:
                print(f"[VoiceStudioService] Đang tự động tải Model AI OmniVoice về {self.model_path} (Chỉ tải 1 lần đầu)...")
                from huggingface_hub import snapshot_download
                self.model_path.mkdir(parents=True, exist_ok=True)
                snapshot_download(repo_id="k2-fsa/OmniVoice", local_dir=str(self.model_path))

            print(f"[VoiceStudioService] Nạp VoiceStudio OmniVoice từ {self.model_path}...")
            from omnivoice.models.omnivoice import OmniVoice
            import torch

            if torch.cuda.is_available():
                torch.backends.cudnn.benchmark = True
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if device == "cuda" else torch.float32

            if VoiceStudioService._model is None:
                VoiceStudioService._model = OmniVoice.from_pretrained(
                    str(self.model_path),
                    device_map=device,
                    dtype=dtype
                )
            if hasattr(VoiceStudioService._model, "llm") and hasattr(VoiceStudioService._model.llm, "config"):
                VoiceStudioService._model.llm.config.use_cache = False

            self.model = VoiceStudioService._model
            self.device = device
            self.engine = True
            print(f"[VoiceStudioService] Nạp model thành công vào {device.upper()} (Turbo Batch Mode)!")

    def _get_voice_clone_prompt(self, ref_audio: str, ref_text: str):
        cache_key = f"{os.path.abspath(ref_audio)}::{ref_text}"
        if cache_key not in VoiceStudioService._prompt_cache:
            print(f"[VoiceStudioService] Khởi tạo VoiceClonePrompt tối ưu từ mẫu giọng: {ref_audio}...")
            import torchaudio

            ref_input: Any = str(ref_audio)
            use_text = ref_text
            try:
                wav, sr = torchaudio.load(str(ref_audio))
                dur_s = wav.shape[-1] / float(sr)
                # Nếu là file mẫu Nhat_Drama.wav dài 9.6s (2 câu), trích đoạn câu đầu (0.55s -> 4.05s)
                # để giảm 62% độ dài token mẫu tham chiếu, giúp tăng tốc gấp đôi mỗi bước giải mã GPU
                if dur_s > 6.5 and "夜景が見下ろせる最高級タワーマンションのリビング。" in ref_text:
                    s_idx = int(0.55 * sr)
                    e_idx = min(wav.shape[-1], int(4.05 * sr))
                    ref_input = (wav[:, s_idx:e_idx], sr)
                    use_text = "夜景が見下ろせる最高級タワーマンションのリビング。"
                elif dur_s > 6.5 and "奥さん、早く来てください。これを見てください。" in ref_text:
                    s_idx = 0
                    e_idx = min(wav.shape[-1], int(4.25 * sr))
                    ref_input = (wav[:, s_idx:e_idx], sr)
                    use_text = "奥さん、早く来てください。これを見てください。"
            except Exception:
                pass

            VoiceStudioService._prompt_cache[cache_key] = self.model.create_voice_clone_prompt(
                ref_audio=ref_input,
                ref_text=use_text
            )
        return VoiceStudioService._prompt_cache[cache_key]

    def generate_full_voice_and_subtitles(
        self,
        script_text: str,
        output_dir: Path,
        ref_voice: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """Tạo trọn bộ Voice và Subtitles từ văn bản kịch bản (Turbo GPU Batch + Multi-Sentence Grouping)."""
        import torch
        import torchaudio

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        sentences_dir = output_dir / "sentences"
        sentences_dir.mkdir(parents=True, exist_ok=True)

        ref_audio = ref_voice or str(self.ref_voice_path)
        ref_text = ""
        txt_path = Path(ref_audio).with_suffix(".txt")
        if txt_path.exists():
            with open(txt_path, "r", encoding="utf-8") as f:
                ref_text = f.read().strip()
        else:
            ref_text = "夫が突然、家を出て行った。"

        sentences = split_japanese_script(script_text)
        total_sentences = len(sentences)
        if total_sentences == 0:
            raise ValueError("Kịch bản không có câu thoại nào hợp lệ.")

        print(f"[VoiceStudioService] Bắt đầu xử lý {total_sentences} câu thoại...")
        self._ensure_engine()
        clone_prompt = self._get_voice_clone_prompt(str(ref_audio), ref_text)
        sample_rate = getattr(self.model, "sampling_rate", 24000) or 24000

        # 1. Chế độ 1 CÂU = 1 FILE VOICE ĐỘC LẬP (Strict 1-to-1 Sync) + Kiểm định & Tự động làm lại
        from backend.sync_checker import audit_all_sentences_sync

        manifest_path = sentences_dir / "sync_1to1_manifest.json"
        strict_map: Dict[str, bool] = {}
        if manifest_path.exists():
            try:
                strict_map = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                strict_map = {}

        cached_durations: Dict[int, float] = {}

        def _synthesize_sentence_indices_1to1(indices_to_run: List[int], step_count: int = 16, tag_prefix: str = "⚡ GPU 1-to-1"):
            if not indices_to_run:
                return
            batch_sz = 8 if self.device == "cuda" else 1
            win_sz = batch_sz * 6
            done_in_pass = 0
            total_in_pass = len(indices_to_run)

            for w_start in range(0, total_in_pass, win_sz):
                win_indices = indices_to_run[w_start : w_start + win_sz]
                # Sắp xếp cục bộ theo độ dài câu để tối ưu tốc độ GPU Batch mà vẫn giữ 1 câu = 1 phần tử độc lập
                win_sorted = sorted(win_indices, key=lambda idx_val: len(sentences[idx_val]))

                for b_start in range(0, len(win_sorted), batch_sz):
                    b_indices = win_sorted[b_start : b_start + batch_sz]
                    b_texts = [sentences[i] for i in b_indices]
                    first_txt = b_texts[0]

                    if progress_callback:
                        overall_done = len(cached_durations)
                        pct = round((overall_done / max(1, total_sentences)) * 90.0, 1)
                        progress_callback(
                            pct,
                            f"{tag_prefix} đang tạo câu ({done_in_pass + 1}..{min(total_in_pass, done_in_pass + len(b_indices))}/{total_in_pass}): {first_txt[:18]}..."
                        )

                    try:
                        audios = self.model.generate(
                            text=b_texts,
                            language="ja",
                            voice_clone_prompt=clone_prompt,
                            num_step=step_count
                        )
                    except RuntimeError as e:
                        if "out of memory" in str(e).lower() and torch.cuda.is_available():
                            torch.cuda.empty_cache()
                            audios = []
                            for bt in b_texts:
                                a = self.model.generate(
                                    text=bt,
                                    language="ja",
                                    voice_clone_prompt=clone_prompt,
                                    num_step=step_count
                                )
                                audios.append(a[0])
                        else:
                            raise

                    for s_idx, wav_out in zip(b_indices, audios):
                        wav_cpu = wav_out.detach().cpu()
                        if wav_cpu.dim() == 1:
                            wav_cpu = wav_cpu.unsqueeze(0)
                        fname = f"sentence_{s_idx+1:04d}.wav"
                        part_wav = sentences_dir / fname
                        torchaudio.save(str(part_wav), wav_cpu, sample_rate)
                        cached_durations[s_idx] = float(wav_cpu.shape[-1]) / float(sample_rate)
                        strict_map[fname] = True
                        done_in_pass += 1

                try:
                    manifest_path.write_text(json.dumps(strict_map, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    pass
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

        # Kiểm tra câu nào chưa có file WAV trên ổ cứng
        missing_indices: List[int] = []
        for idx in range(total_sentences):
            part_wav = sentences_dir / f"sentence_{idx+1:04d}.wav"
            if part_wav.exists() and part_wav.stat().st_size > 1000:
                cached_durations[idx] = get_audio_duration(str(part_wav))
            else:
                missing_indices.append(idx)

        if missing_indices:
            print(
                f"[VoiceStudioService] ⚡ Chế độ Khớp Tuyệt Đối (1 Câu = 1 File Voice): "
                f"Đã có {len(cached_durations)}/{total_sentences} câu, đang tạo {len(missing_indices)} câu mới..."
            )
            _synthesize_sentence_indices_1to1(missing_indices, step_count=16, tag_prefix="⚡ GPU 1-to-1")

        # 2. BƯỚC KIỂM ĐỊNH ĐỘ KHỚP SUB & VOICE TỰ ĐỘNG + LÀM LẠI CÁC CÂU LỆCH (TỐI ĐA 3 VÒNG)
        max_redo_rounds = 3
        audit_report = {}
        for redo_round in range(1, max_redo_rounds + 1):
            if progress_callback:
                progress_callback(
                    91.0 + redo_round,
                    f"🔍 [Kiểm định Sub-Voice Lần {redo_round}] Đang rà soát độ khớp của {total_sentences} câu thoại..."
                )
            audit_report = audit_all_sentences_sync(sentences, sentences_dir, require_strict_1to1=False)
            if audit_report["passed"]:
                print(f"[VoiceStudioService] ✅ Kiểm định Sub-Voice ĐẠT 100% ({total_sentences}/{total_sentences} câu khớp hoàn hảo)!")
                break

            redo_list = audit_report["redo_indices"]
            print(
                f"[VoiceStudioService] ⚠️ [Vòng {redo_round}/{max_redo_rounds}] Phát hiện {len(redo_list)}/{total_sentences} câu "
                f"chưa khớp chuẩn (bị cắt biên hoặc lệch nhịp) -> Đang tự động làm lại 1-to-1..."
            )
            for r_idx in redo_list:
                cached_durations.pop(r_idx, None)
                bad_wav = sentences_dir / f"sentence_{r_idx+1:04d}.wav"
                if bad_wav.exists():
                    try:
                        bad_wav.unlink()
                    except Exception:
                        pass

            _synthesize_sentence_indices_1to1(
                redo_list,
                step_count=18 if redo_round == 1 else 20,
                tag_prefix=f"🔄 Làm lại Sub-Voice (Vòng {redo_round})"
            )

        # Kiểm định chốt cuối sau khi làm lại
        final_sent_audit = audit_all_sentences_sync(sentences, sentences_dir, require_strict_1to1=False)
        try:
            (output_dir / "qa_sentence_sync_report.json").write_text(
                json.dumps(final_sent_audit, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass

        # 3. Tổng hợp danh sách audio_parts và timeline theo đúng thứ tự câu 1..N
        audio_parts = []
        timeline = []
        current_time = 0.0

        for idx, text in enumerate(sentences):
            idx_str = f"{idx+1:04d}"
            part_wav = sentences_dir / f"sentence_{idx_str}.wav"
            dur = cached_durations.get(idx)
            if dur is None or dur <= 0:
                dur = get_audio_duration(str(part_wav))
            start_t = current_time
            end_t = current_time + dur
            current_time = end_t

            audio_parts.append(str(part_wav))
            timeline.append({
                "index": idx + 1,
                "text": text,
                "start": start_t,
                "end": end_t,
                "duration": dur,
                "audio_path": str(part_wav)
            })

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Ghép master_voice.wav không nén qua FFmpeg concat
        if progress_callback:
            progress_callback(96.0, "Đang ghép nối audio master bằng FFmpeg...")

        concat_list = output_dir / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for p in audio_parts:
                clean_p = p.replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{clean_p}'\n")

        master_wav = output_dir / "master_voice.wav"
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:a", "pcm_s16le",
            str(master_wav)
        ]
        subprocess.run(cmd, check=True)

        # Xuất subtitles.srt (Đảm bảo tối đa 3 dòng / khung phụ đề, tự động tách câu dài tại đúng điểm nghỉ trong WAV)
        srt_file = output_dir / "subtitles.srt"
        srt_idx = 1
        with open(srt_file, "w", encoding="utf-8") as f:
            for item in timeline:
                segs = split_long_subtitle_segments(
                    item["text"],
                    item["start"],
                    item["end"],
                    max_segment_chars=48,
                    max_chars_per_line=17,
                    wav_path=item["audio_path"]
                )
                for seg in segs:
                    f.write(f"{srt_idx}\n")
                    f.write(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n")
                    f.write(f"{seg['text']}\n\n")
                    srt_idx += 1

        # Xuất TIMESTAMPS.txt
        timestamps_file = output_dir / "TIMESTAMPS.txt"
        with open(timestamps_file, "w", encoding="utf-8") as f:
            f.write("00:00:00 - Bắt đầu câu chuyện\n")
            chapter_interval = max(180.0, current_time / 6)  # Mỗi 3-5 phút một chapter
            last_ch = 0.0
            for item in timeline:
                if item["start"] - last_ch >= chapter_interval:
                    m = int(item["start"] // 60)
                    s = int(item["start"] % 60)
                    h = int(m // 60)
                    m = int(m % 60)
                    f.write(f"{h:02d}:{m:02d}:{s:02d} - {item['text'][:20]}...\n")
                    last_ch = item["start"]

        if progress_callback:
            progress_callback(100.0, f"Tạo Voice và Subtitle hoàn tất ({current_time/60:.2f} phút)!")

        return {
            "master_voice": str(master_wav),
            "subtitles_srt": str(srt_file),
            "timestamps_txt": str(timestamps_file),
            "total_duration": current_time,
            "sentence_count": total_sentences,
            "timeline": timeline
        }


# ==============================================================================
# HỆ THỐNG QUÉT, SỬA KỊCH BẢN & CẮT ĐOẠN LỖI [LOCKED_TITLE] TRONG VIDEO MP4 (PHƯƠNG ÁN 1)
# ==============================================================================

def _parse_srt_time_sec(ts_str: str) -> float:
    s = (ts_str or "").strip().replace(",", ".")
    parts = s.split(":")
    if len(parts) != 3:
        return 0.0
    try:
        return int(parts[0]) * 3600.0 + int(parts[1]) * 60.0 + float(parts[2])
    except Exception:
        return 0.0


def parse_srt_blocks(srt_text: str) -> List[Dict[str, Any]]:
    import re
    raw = (srt_text or "").strip()
    if not raw:
        return []
    chunks = [c.strip() for c in re.split(r"\n\s*\n", raw) if c.strip()]
    blocks: List[Dict[str, Any]] = []
    for ch in chunks:
        lines = [ln.strip() for ln in ch.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        ts_line_idx = 1 if "-->" in lines[1] else (0 if "-->" in lines[0] else -1)
        if ts_line_idx < 0:
            continue
        ts_parts = lines[ts_line_idx].split("-->")
        st = _parse_srt_time_sec(ts_parts[0])
        ed = _parse_srt_time_sec(ts_parts[1])
        txt_lines = lines[ts_line_idx + 1 :]
        body_text = "\n".join(txt_lines).strip()
        flat_text = "".join(txt_lines).replace(" ", "").strip()
        blocks.append(
            {
                "idx": len(blocks) + 1,
                "start": st,
                "end": ed,
                "text": body_text,
                "flat_text": flat_text,
            }
        )
    return blocks


def detect_leaked_srt_blocks_and_intervals(
    srt_blocks: List[Dict[str, Any]],
    removed_script_lines: Optional[List[str]] = None,
    locked_title_hint: str = "",
) -> Tuple[List[int], List[Tuple[float, float]], str, List[str]]:
    """
    Phát hiện chính xác các khung phụ đề SRT bị dính [LOCKED_TITLE], SELECTED_TITLE,
    PART A/B/C, CONTINUITY, ENDING (kể cả khi câu tiêu đề bị tách thành nhiều khung SRT liên tiếp).
    Trả về:
      - `leaked_indices`: Danh sách chỉ số block (0-based) bị dính lỗi
      - `cut_intervals`: Danh sách khoảng thời gian `[(start_sec, end_sec), ...]` cần cắt khỏi Video/Voice
      - `cleaned_srt_text`: Nội dung file `.srt` mới đã xóa các block lỗi và dịch chuyển (shift) lại thời gian chuẩn xác
      - `leaked_previews`: Danh sách nội dung các block đã bị xóa để ghi báo cáo
    """
    import re
    if not srt_blocks:
        return [], [], "", []

    title_key_re = re.compile(
        r"(?:LOCKED_TITLE|SELECTED_TITLE|WINNING_TITLE|FINAL_TITLE|DRAFT_TITLE|TITLE_LOCKED|LOCKED_TITLE_PROMISE|TITLE_FACTS)\s*[:：\-—]?",
        re.IGNORECASE,
    )
    step_part_re = re.compile(
        r"^(?:[A-Z]{1,6}\d{1,5}\s*[—–\-·:：]+\s*)?(?:STEP\s*[1-7]\b|BUILD\s+PART\s*[ABC]\b|PART\s*[:：\-—–·]?\s*[ABC]\b|SCENE\s+[ABC]?\d+\b|CHAPTER\s+\d+\b)",
        re.IGNORECASE,
    )
    stop_block_re = re.compile(
        r"^(?:PART_PURE_CHARACTER_COUNT|PART_LENGTH_GATE|CONTINUITY_LEDGER|CONTINUITY\s+LEDGER|PART_HANDOFF_LEDGER|HANDOFF_LEDGER|HANDOFF\s+LEDGER|PART_[ABC]_HANDOFF|NEXT_ACTION|READY_FOR_AUDIT|PATCH_CHANGELOG)\b",
        re.IGNORECASE,
    )
    meta_kv_re = re.compile(r"^[A-Z][A-Z0-9_/\-\s]{1,35}[:：]")
    ellipsis_endings = ("…", "…」", "…」」", "…』", "…。", "…。」", "…！」", "…？」")
    sent_end_chars = ("。", "！", "？", "…", "」", "』", "）", ")")

    norm_removed_pool: List[str] = []
    for rl in (removed_script_lines or []):
        nr = re.sub(r"[\s#*`>]+", "", str(rl or "")).strip()
        if len(nr) >= 4:
            norm_removed_pool.append(nr)
    norm_title_hint = re.sub(r"[\s#*`>]+", "", str(locked_title_hint or "")).strip()

    n = len(srt_blocks)
    leaked_set = set()
    i = 0

    while i < n:
        ft = srt_blocks[i]["flat_text"]
        ft_clean = re.sub(r"^[#*>\-\s`•]+", "", ft).replace("**", "").replace("`", "").strip()

        # 1. Nếu bắt đầu bằng LOCKED_TITLE / SELECTED_TITLE
        if title_key_re.search(ft_clean):
            body0 = re.sub(
                r"^.*?(?:LOCKED_TITLE|SELECTED_TITLE|WINNING_TITLE|FINAL_TITLE|DRAFT_TITLE|TITLE_LOCKED|LOCKED_TITLE_PROMISE|TITLE_FACTS)\s*[:：\-—]*\s*",
                "",
                ft_clean,
                flags=re.IGNORECASE,
            ).strip()
            end_i = i + 1
            acc = body0
            # Nếu block hiện tại bị ngắt giữa câu bởi split_long_subtitle_segments (chưa có dấu kết câu), gom tiếp
            while end_i < n and not acc.endswith(sent_end_chars) and len(acc) <= 210:
                acc += srt_blocks[end_i]["flat_text"]
                end_i += 1

            open_q = acc.count("「")
            close_q = acc.count("」")
            if not (acc.endswith(ellipsis_endings) and open_q <= close_q + 1):
                # Chỉ kiểm tra câu kế tiếp ngay sau câu đầu của LOCKED_TITLE (có thể gồm 1-2 khung SRT nếu câu dài > 48 chữ)
                next_sent_acc = ""
                next_sent_end_idx = end_i
                for k in range(end_i, min(n, end_i + 3)):
                    cand = srt_blocks[k]["flat_text"]
                    if not cand or title_key_re.search(cand) or step_part_re.match(cand):
                        break
                    next_sent_acc += cand
                    next_sent_end_idx = k + 1
                    if cand.endswith(sent_end_chars):
                        break
                if next_sent_acc and len(acc + next_sent_acc) <= 210:
                    if (
                        next_sent_acc.endswith(ellipsis_endings)
                        or (norm_title_hint and len(next_sent_acc) >= 6 and next_sent_acc in norm_title_hint)
                        or any(len(next_sent_acc) >= 6 and next_sent_acc in nr for nr in norm_removed_pool)
                    ):
                        end_i = next_sent_end_idx

            for k in range(i, end_i):
                leaked_set.add(k)
            i = end_i
            continue

        # 2. Nếu là dòng STEP / PART / 日本語脚本 / Metadata tiếng Anh
        if (
            (step_part_re.match(ft_clean) and len(ft_clean) < 95)
            or (re.search(r"(?:日本語脚本|日本語ナレーション本文|HANDOFF_LEDGER|PURE_CHARACTER_COUNT)", ft_clean, re.IGNORECASE) and len(ft_clean) < 95)
            or stop_block_re.match(ft_clean)
            or meta_kv_re.match(ft_clean)
        ):
            leaked_set.add(i)
            i += 1
            continue

        # 3. Đối chiếu trực tiếp với các dòng đã bị xóa khỏi file kịch bản .txt (nếu có)
        if norm_removed_pool and len(ft_clean) >= 6:
            matched_pool = False
            for nr in norm_removed_pool:
                if ft_clean == nr or (len(ft_clean) >= 10 and ft_clean in nr and ("LOCKED_TITLE" in nr or "SELECTED_TITLE" in nr or nr.endswith(ellipsis_endings))):
                    matched_pool = True
                    break
            if matched_pool:
                leaked_set.add(i)
                i += 1
                continue

        i += 1

    if not leaked_set:
        return [], [], "", []

    leaked_indices = sorted(leaked_set)
    leaked_previews = [srt_blocks[idx]["flat_text"] for idx in leaked_indices]

    # Gom các khoảng thời gian cần cắt bỏ (gộp các block lỗi liền kề cách nhau <= 0.45s)
    raw_intervals = [(srt_blocks[idx]["start"], srt_blocks[idx]["end"]) for idx in leaked_indices]
    cut_intervals: List[Tuple[float, float]] = []
    for st, ed in raw_intervals:
        if ed <= st:
            continue
        if not cut_intervals:
            cut_intervals.append((st, ed))
        else:
            prev_st, prev_ed = cut_intervals[-1]
            if st <= prev_ed + 0.45:
                cut_intervals[-1] = (prev_st, max(prev_ed, ed))
            else:
                cut_intervals.append((st, ed))

    # Xây dựng lại nội dung subtitles.srt mới với thời gian đã trừ đi các đoạn bị cắt
    def _calc_shifted_time(t_val: float) -> float:
        removed_before = 0.0
        for cst, ced in cut_intervals:
            if ced <= t_val:
                removed_before += (ced - cst)
            elif cst < t_val < ced:
                removed_before += (t_val - cst)
        return max(0.0, t_val - removed_before)

    new_srt_lines: List[str] = []
    new_idx = 1
    for idx, blk in enumerate(srt_blocks):
        if idx in leaked_set:
            continue
        new_st = _calc_shifted_time(blk["start"])
        new_ed = _calc_shifted_time(blk["end"])
        if new_ed <= new_st + 0.02:
            new_ed = new_st + max(0.2, blk["end"] - blk["start"])
        new_srt_lines.append(f"{new_idx}")
        new_srt_lines.append(f"{format_timestamp(new_st)} --> {format_timestamp(new_ed)}")
        new_srt_lines.append(f"{blk['text']}\n")
        new_idx += 1

    cleaned_srt_text = "\n".join(new_srt_lines).strip() + "\n"
    return leaked_indices, cut_intervals, cleaned_srt_text, leaked_previews


def compute_keep_intervals(total_duration: float, cut_intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Tính danh sách các khoảng thời gian giữ lại `[keep_start, keep_end]` từ `total_duration` và `cut_intervals`."""
    if total_duration <= 0.0:
        return []
    if not cut_intervals:
        return [(0.0, total_duration)]

    sorted_cuts = sorted(cut_intervals, key=lambda x: x[0])
    merged: List[Tuple[float, float]] = []
    for st, ed in sorted_cuts:
        st_c = max(0.0, min(total_duration, st))
        ed_c = max(0.0, min(total_duration, ed))
        if ed_c <= st_c:
            continue
        if not merged:
            merged.append((st_c, ed_c))
        else:
            pst, ped = merged[-1]
            if st_c <= ped + 0.15:
                merged[-1] = (pst, max(ped, ed_c))
            else:
                merged.append((st_c, ed_c))

    keep: List[Tuple[float, float]] = []
    cursor = 0.0
    for st, ed in merged:
        if st - cursor > 0.15:
            keep.append((cursor, st))
        cursor = max(cursor, ed)
    if total_duration - cursor > 0.15:
        keep.append((cursor, total_duration))
    return keep


def _probe_duration_sec(media_path: Path) -> float:
    import subprocess
    if not media_path.exists():
        return 0.0
    win_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(media_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=win_flags,
        )
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _replace_file_with_retry(src_path: Path, dst_path: Path, retries: int = 6) -> None:
    last_err = None
    for attempt in range(retries):
        try:
            os.replace(str(src_path), str(dst_path))
            return
        except Exception as e:
            last_err = e
            time.sleep(0.25 * (attempt + 1))
    if last_err:
        raise last_err


def _fast_trim_wav_pcm(wav_path: Path, cut_intervals: List[Tuple[float, float]], tmp_out: Path) -> Tuple[bool, float, float, str]:
    """
    Cắt trực tiếp file PCM WAV bằng module `wave` nội bộ của Python (không cần mở subprocess FFmpeg).
    Tốc độ: 0.2s – 0.8s cho file WAV dài 2 tiếng (~700MB).
    """
    with wave.open(str(wav_path), "rb") as wf_in:
        params = wf_in.getparams()
        sr = float(wf_in.getframerate() or 24000)
        total_frames = wf_in.getnframes()
        if sr <= 0 or total_frames <= 0:
            raise RuntimeError("Header WAV không hợp lệ")
        old_dur = total_frames / sr
        keep_intervals = compute_keep_intervals(old_dur, cut_intervals)
        if not keep_intervals:
            raise RuntimeError("Danh sách đoạn giữ lại rỗng")

        written_frames = 0
        chunk_frames = int(sr * 120)  # Đọc/ghi theo khối 120 giây (~5.7MB)
        with wave.open(str(tmp_out), "wb") as wf_out:
            wf_out.setparams(params)
            for ks, ke in keep_intervals:
                if ke - ks <= 0.05:
                    continue
                f_start = max(0, min(total_frames, int(round(ks * sr))))
                f_end = max(f_start, min(total_frames, int(round(ke * sr))))
                rem = f_end - f_start
                if rem <= 0:
                    continue
                wf_in.setpos(f_start)
                while rem > 0:
                    take = min(rem, chunk_frames)
                    raw_bytes = wf_in.readframes(take)
                    if not raw_bytes:
                        break
                    wf_out.writeframes(raw_bytes)
                    rem -= take
                written_frames += (f_end - f_start)

        new_dur = written_frames / sr
        return True, round(old_dur, 2), round(new_dur, 2), "Đã cắt sạch WAV siêu tốc"


def trim_media_file_by_keep_intervals(
    media_path: Path,
    cut_intervals: List[Tuple[float, float]],
    is_video: bool = True,
) -> Tuple[bool, float, float, str]:
    """
    Cắt bỏ trực tiếp các đoạn `cut_intervals` khỏi file Video `.mp4` hoặc Audio `.wav`
    bằng FFmpeg Stream Copy (`-c copy` input-seeking) và Python PCM Slicer siêu tốc (~3–8 giây / video 2 tiếng).
    Trả về `(success, old_duration, new_duration, message)`.
    """
    import shutil
    import subprocess
    if not media_path.exists():
        return False, 0.0, 0.0, "File không tồn tại"
    if not cut_intervals:
        dur = _probe_duration_sec(media_path)
        return True, dur, dur, "Không có đoạn lỗi cần cắt"

    # Đặt thư mục tạm ở cấp proj_dir (ngoài renders/) để không làm thay đổi mtime của renders/ khi đang cắt
    base_tmp_parent = media_path.parent.parent if media_path.parent.name in ("renders", "assets") else media_path.parent
    tmp_dir = base_tmp_parent / f"_clean_trim_tmp_{media_path.stem}"
    shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    ext = ".mp4" if is_video else ".wav"
    tmp_out = tmp_dir / f"cleaned_output{ext}"

    # Nhánh 1: Nếu là file WAV -> Ưu tiên cắt siêu tốc trực tiếp bằng Python wave (0.3s - 0.8s)
    if not is_video:
        try:
            ok_w, old_w, new_w, msg_w = _fast_trim_wav_pcm(media_path, cut_intervals, tmp_out)
            if ok_w and tmp_out.exists() and tmp_out.stat().st_size > 1000:
                _replace_file_with_retry(tmp_out, media_path)
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return True, old_w, new_w, msg_w
        except Exception:
            pass

    old_dur = _probe_duration_sec(media_path)
    if old_dur <= 1.0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False, old_dur, old_dur, "Không đọc được thời lượng file gốc"

    keep_intervals = compute_keep_intervals(old_dur, cut_intervals)
    if not keep_intervals:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False, old_dur, old_dur, "Danh sách đoạn giữ lại rỗng"

    win_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    seg_files: List[Path] = []

    try:
        valid_keeps = [(ks, ke) for ks, ke in keep_intervals if (ke - ks) > 0.10]
        if not valid_keeps:
            raise RuntimeError("Không có phân đoạn giữ lại hợp lệ")

        # Tối ưu 1-Pass: Nếu chỉ có đúng 1 đoạn giữ lại (VD: lỗi LOCKED_TITLE nằm ở Dòng 1 đầu video hoặc cuối video),
        # cắt thẳng 1 lần từ media_path ra tmp_out (không cần ghi seg_000 rồi lại copy sang tmp_out)!
        if len(valid_keeps) == 1:
            ks, ke = valid_keeps[0]
            dur_seg = ke - ks
            if is_video:
                cmd_one = ["ffmpeg", "-y", "-v", "error"]
                if ks > 0.05:
                    cmd_one.extend(["-ss", f"{ks:.3f}"])
                cmd_one.extend([
                    "-i", str(media_path),
                    "-t", f"{dur_seg:.3f}",
                    "-c", "copy",
                    "-avoid_negative_ts", "make_zero",
                    str(tmp_out),
                ])
            else:
                cmd_one = [
                    "ffmpeg", "-y", "-v", "error",
                    "-ss", f"{ks:.3f}",
                    "-i", str(media_path),
                    "-t", f"{dur_seg:.3f}",
                    "-c:a", "pcm_s16le",
                    str(tmp_out),
                ]
            res_one = subprocess.run(cmd_one, capture_output=True, text=True, creationflags=win_flags)
            if res_one.returncode != 0 or not tmp_out.exists() or tmp_out.stat().st_size < 5000:
                raise RuntimeError(f"Lỗi cắt 1-pass: {res_one.stderr[-200:]}")
        else:
            # Tối ưu Multi-Segment: Đặt -ss TRƯỚC -i để FFmpeg nhảy trực tiếp theo bảng chỉ mục MP4 moov trong 0.001s
            for idx, (ks, ke) in enumerate(valid_keeps):
                dur_seg = ke - ks
                seg_f = tmp_dir / f"seg_{idx:03d}{ext}"
                if is_video:
                    cmd_seg = ["ffmpeg", "-y", "-v", "error"]
                    if ks > 0.05:
                        cmd_seg.extend(["-ss", f"{ks:.3f}"])
                    cmd_seg.extend([
                        "-i", str(media_path),
                        "-t", f"{dur_seg:.3f}",
                        "-c", "copy",
                        "-avoid_negative_ts", "make_zero",
                        str(seg_f),
                    ])
                else:
                    cmd_seg = [
                        "ffmpeg", "-y", "-v", "error",
                        "-ss", f"{ks:.3f}",
                        "-i", str(media_path),
                        "-t", f"{dur_seg:.3f}",
                        "-c:a", "pcm_s16le",
                        str(seg_f),
                    ]
                res = subprocess.run(cmd_seg, capture_output=True, text=True, creationflags=win_flags)
                if res.returncode != 0 or not seg_f.exists() or seg_f.stat().st_size < 1000:
                    raise RuntimeError(f"Lỗi cắt phân đoạn {idx}: {res.stderr[-200:]}")
                seg_files.append(seg_f)

            concat_txt = tmp_dir / "concat_list.txt"
            with open(concat_txt, "w", encoding="utf-8") as f:
                for sf in seg_files:
                    p_clean = str(sf.resolve()).replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{p_clean}'\n")
            if is_video:
                # Không dùng -movflags +faststart để tránh việc FFmpeg phải đọc & ghi lại toàn bộ file 2.5GB lần 2
                cmd_cat = [
                    "ffmpeg", "-y", "-v", "error",
                    "-f", "concat", "-safe", "0",
                    "-i", str(concat_txt),
                    "-c", "copy",
                    str(tmp_out),
                ]
            else:
                cmd_cat = [
                    "ffmpeg", "-y", "-v", "error",
                    "-f", "concat", "-safe", "0",
                    "-i", str(concat_txt),
                    "-c:a", "pcm_s16le",
                    str(tmp_out),
                ]
            res_cat = subprocess.run(cmd_cat, capture_output=True, text=True, creationflags=win_flags)
            if res_cat.returncode != 0 or not tmp_out.exists() or tmp_out.stat().st_size < 5000:
                raise RuntimeError(f"Lỗi ghép phân đoạn sạch: {res_cat.stderr[-200:]}")

        new_dur = _probe_duration_sec(tmp_out)
        expected_dur = sum(ke - ks for ks, ke in valid_keeps)
        if new_dur <= 1.0 or abs(new_dur - expected_dur) > 12.0:
            raise RuntimeError(f"Thời lượng sau khi cắt bất thường ({new_dur:.1f}s vs kỳ vọng {expected_dur:.1f}s)")

        _replace_file_with_retry(tmp_out, media_path)
        return True, round(old_dur, 2), round(new_dur, 2), "Đã cắt sạch đoạn lỗi thành công"
    except Exception as e:
        return False, round(old_dur, 2), round(old_dur, 2), str(e)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def clean_single_project_scripts_and_detect_media_cuts(proj_dir: Path) -> Dict[str, Any]:
    """
    GIAI ĐOẠN 1 (Siêu tốc ~0.005s / dự án):
    1. Quét và xóa sạch ngay lập tức các dòng `[LOCKED_TITLE]` / Metadata rò rỉ trong tất cả file kịch bản `.txt`.
    2. Phân tích `assets/subtitles.srt` để xác định xem dự án có các đoạn giây đọc nhầm `[LOCKED_TITLE]`
       cần cắt trong Video `.mp4` / Voice `.wav` hay không.
    """
    import re
    proj_dir = Path(proj_dir)
    ma_id = proj_dir.name
    renders_dir = proj_dir / "renders"
    assets_dir = proj_dir / "assets"

    result: Dict[str, Any] = {
        "ma_id": ma_id,
        "proj_dir": proj_dir,
        "script_cleaned": False,
        "script_removed_lines_count": 0,
        "script_removed_samples": [],
        "srt_cleaned": False,
        "srt_removed_blocks_count": 0,
        "video_repaired": False,
        "voice_repaired": False,
        "needs_media_trim": False,
        "has_mp4_to_trim": False,
        "has_wav_to_trim": False,
        "cut_intervals": [],
        "raw_cut_intervals": [],
        "cleaned_srt_text": "",
        "old_video_duration": 0.0,
        "new_video_duration": 0.0,
        "video_message": "",
    }

    if not proj_dir.exists() or not proj_dir.is_dir():
        return result

    locked_title_hint = ""
    info_f = proj_dir / "idea_info.json"
    if info_f.exists():
        try:
            d_info = json.loads(info_f.read_text(encoding="utf-8", errors="ignore"))
            locked_title_hint = str(d_info.get("locked_title") or d_info.get("draft_title_ja") or "")
        except Exception:
            pass

    script_targets = [
        proj_dir / "part_a.txt",
        proj_dir / "part_b.txt",
        proj_dir / "part_c.txt",
        proj_dir / "script_clean.txt",
        proj_dir / "script.txt",
        renders_dir / f"{ma_id}_KICH_BAN.txt",
    ]
    removed_texts_pool: List[str] = []
    leaked_log_f = assets_dir / "leaked_lines_log.json"
    if leaked_log_f.exists():
        try:
            prev_logged = json.loads(leaked_log_f.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(prev_logged, list):
                removed_texts_pool.extend([str(x) for x in prev_logged if x])
        except Exception:
            pass

    # Khôi phục thêm các dòng đã xóa từ step5_audit_report.txt (nếu Build #106 đã xóa .txt trước đó)
    audit_f = proj_dir / "step5_audit_report.txt"
    if audit_f.exists():
        try:
            aud_txt = audit_f.read_text(encoding="utf-8", errors="ignore")
            for m_rem in re.finditer(r"^\s*-\s*(?:Removed:\s*)?(.+)$", aud_txt, flags=re.MULTILINE):
                cand_r = m_rem.group(1).strip()
                if ("LOCKED_TITLE" in cand_r or "SELECTED_TITLE" in cand_r or "PART " in cand_r) and cand_r not in removed_texts_pool:
                    removed_texts_pool.append(cand_r)
        except Exception:
            pass

    for tf in script_targets:
        if not tf.exists():
            continue
        try:
            raw_txt = tf.read_text(encoding="utf-8", errors="ignore")
            cleaned_txt, removed_tuples = strip_leaked_titles_and_metadata(raw_txt)
            if removed_tuples and cleaned_txt:
                tf.write_text(cleaned_txt, encoding="utf-8")
                result["script_cleaned"] = True
                result["script_removed_lines_count"] += len(removed_tuples)
                for _, r_str in removed_tuples:
                    if r_str not in removed_texts_pool:
                        removed_texts_pool.append(r_str)
                    if len(result["script_removed_samples"]) < 6 and r_str not in result["script_removed_samples"]:
                        result["script_removed_samples"].append(r_str)
        except Exception:
            pass

    pa, pb, pc = proj_dir / "part_a.txt", proj_dir / "part_b.txt", proj_dir / "part_c.txt"
    if result["script_cleaned"] and pa.exists() and pb.exists() and pc.exists():
        try:
            ta = pa.read_text(encoding="utf-8", errors="ignore").strip()
            tb = pb.read_text(encoding="utf-8", errors="ignore").strip()
            tc = pc.read_text(encoding="utf-8", errors="ignore").strip()
            if len(ta) >= 8000 and len(tb) >= 8000 and len(tc) >= 8000:
                comb, _ = strip_leaked_titles_and_metadata("\n\n".join([ta, tb, tc]).strip())
                for sync_f in (proj_dir / "script_clean.txt", renders_dir / f"{ma_id}_KICH_BAN.txt"):
                    if sync_f.exists():
                        cur_s = sync_f.read_text(encoding="utf-8", errors="ignore").strip()
                        if cur_s != comb:
                            sync_f.write_text(comb, encoding="utf-8")
        except Exception:
            pass

    if removed_texts_pool and assets_dir.exists():
        try:
            leaked_log_f.write_text(json.dumps(removed_texts_pool, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    if result["script_cleaned"]:
        try:
            note_txt = (
                f"\n[AUTO-CLEAN NOTE — {time.strftime('%Y-%m-%d %H:%M:%S')}]: "
                f"Đã quét và xóa {result['script_removed_lines_count']} dòng [LOCKED_TITLE]/Metadata rò rỉ:\n"
                + "\n".join([f"  - {s}" for s in result["script_removed_samples"]])
                + "\n"
            )
            if audit_f.exists():
                cur_a = audit_f.read_text(encoding="utf-8", errors="ignore")
                if "[AUTO-CLEAN NOTE" not in cur_a:
                    audit_f.write_text(cur_a + note_txt, encoding="utf-8")
        except Exception:
            pass

    srt_file = assets_dir / "subtitles.srt"
    master_wav = assets_dir / "master_voice.wav"
    master_mp4 = renders_dir / f"{ma_id}_master.mp4"
    video_clean_marker = renders_dir / ".cleaned_locked_title_v106.json"

    if srt_file.exists() and srt_file.stat().st_size > 50:
        try:
            raw_srt = srt_file.read_text(encoding="utf-8", errors="ignore")
            srt_blocks = parse_srt_blocks(raw_srt)
            leaked_idxs, cut_intervals, cleaned_srt_text, leaked_srt_previews = detect_leaked_srt_blocks_and_intervals(
                srt_blocks,
                removed_script_lines=removed_texts_pool,
                locked_title_hint=locked_title_hint,
            )
            if leaked_idxs:
                result["srt_cleaned"] = True
                result["srt_removed_blocks_count"] = len(leaked_idxs)
                result["cut_intervals"] = [(round(s, 3), round(e, 3)) for s, e in cut_intervals]
                result["raw_cut_intervals"] = cut_intervals
                result["cleaned_srt_text"] = cleaned_srt_text
                for lp in leaked_srt_previews:
                    if len(result["script_removed_samples"]) < 6 and lp not in result["script_removed_samples"]:
                        result["script_removed_samples"].append(lp)

                has_mp4 = master_mp4.exists() and master_mp4.stat().st_size > 100_000
                has_wav = master_wav.exists() and master_wav.stat().st_size > 100_000
                if has_mp4 or has_wav:
                    result["needs_media_trim"] = True
                    result["has_mp4_to_trim"] = has_mp4
                    result["has_wav_to_trim"] = has_wav
                elif cleaned_srt_text:
                    # Chỉ có SRT mà chưa render WAV/MP4 -> Ghi SRT sạch luôn
                    try:
                        srt_file.write_text(cleaned_srt_text, encoding="utf-8")
                    except Exception:
                        pass
        except Exception as e_srt:
            result["video_message"] = f"Lỗi đọc SRT: {e_srt}"

    if not result["raw_cut_intervals"] and video_clean_marker.exists():
        result["needs_media_trim"] = False

    return result


def execute_project_media_trim(item_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    GIAI ĐOẠN 2: Thực thi cắt đoạn đọc nhầm `[LOCKED_TITLE]` khỏi Video `.mp4` và Voice `.wav`
    cho một dự án đã được phát hiện ở Giai đoạn 1.
    """
    proj_dir: Path = item_state["proj_dir"]
    ma_id: str = item_state["ma_id"]
    renders_dir = proj_dir / "renders"
    assets_dir = proj_dir / "assets"
    srt_file = assets_dir / "subtitles.srt"
    master_wav = assets_dir / "master_voice.wav"
    master_mp4 = renders_dir / f"{ma_id}_master.mp4"
    video_clean_marker = renders_dir / ".cleaned_locked_title_v106.json"
    cut_intervals: List[Tuple[float, float]] = item_state.get("raw_cut_intervals") or []
    cleaned_srt_text: str = item_state.get("cleaned_srt_text") or ""

    if not cut_intervals:
        return item_state

    # 1. Cắt Video MP4 nếu có
    if master_mp4.exists() and master_mp4.stat().st_size > 100_000:
        ok_v, old_vd, new_vd, msg_v = trim_media_file_by_keep_intervals(
            master_mp4, cut_intervals, is_video=True
        )
        item_state["video_repaired"] = ok_v
        item_state["old_video_duration"] = old_vd
        item_state["new_video_duration"] = new_vd
        item_state["video_message"] = msg_v
        if not ok_v:
            return item_state

    # 2. Cắt Master Voice WAV đồng bộ 100% thời lượng (bằng Python wave siêu tốc ~0.4s)
    if master_wav.exists() and master_wav.stat().st_size > 100_000:
        ok_w, _, _, _ = trim_media_file_by_keep_intervals(
            master_wav, cut_intervals, is_video=False
        )
        item_state["voice_repaired"] = ok_w

    # 3. Lưu subtitles.srt đã xóa khung lỗi & dịch khớp thời gian
    if cleaned_srt_text:
        try:
            srt_file.write_text(cleaned_srt_text, encoding="utf-8")
        except Exception:
            pass

    # 4. Lưu dấu đã dọn sạch để lần bấm sau bỏ qua ngay lập tức
    try:
        renders_dir.mkdir(parents=True, exist_ok=True)
        video_clean_marker.write_text(
            json.dumps(
                {
                    "ma_id": ma_id,
                    "cleaned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "cut_intervals": item_state["cut_intervals"],
                    "old_video_duration": item_state["old_video_duration"],
                    "new_video_duration": item_state["new_video_duration"],
                    "removed_samples": item_state["script_removed_samples"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass

    return item_state


def repair_single_project_script_and_video(proj_dir: Path) -> Dict[str, Any]:
    """Hàm tương thích xử lý trọn gói Giai đoạn 1 + Giai đoạn 2 cho 1 dự án đơn lẻ."""
    st = clean_single_project_scripts_and_detect_media_cuts(proj_dir)
    if st.get("needs_media_trim"):
        st = execute_project_media_trim(st)
    st.pop("proj_dir", None)
    st.pop("raw_cut_intervals", None)
    st.pop("cleaned_srt_text", None)
    return st


def check_and_repair_all_projects_sync(
    projects_dir: Path,
    progress_cb: Optional[Callable[[float, str], None]] = None,
    log_cb: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Quét toàn bộ thư mục `projects/` (Nút "🛡️ Check Toàn Bộ") theo kiến trúc 2 Giai đoạn siêu tốc:
    - GIAI ĐOẠN 1 (1–2 giây cho toàn bộ kho): Quét và xóa sạch 100% lỗi `[LOCKED_TITLE]` / Metadata
      trong TẤT CẢ các kịch bản `.txt` của mọi dự án trước tiên! Báo cáo ngay lập tức số kịch bản đã dọn xong.
    - GIAI ĐOẠN 2 (4–8 giây / video): Chỉ chạy cắt FFmpeg Stream Copy & Python WAV Slicer trên đúng những dự án
      đã tạo Video `.mp4` / Voice `.wav` bị dính đoạn đọc nhầm, báo cáo tiến độ từng video `1/N`, `2/N` theo thời gian thực!
    """
    t0 = time.time()
    projects_dir = Path(projects_dir)
    if not projects_dir.exists():
        return {
            "total_projects": 0,
            "total_scanned": 0,
            "scripts_repaired_count": 0,
            "srts_repaired_count": 0,
            "videos_repaired_count": 0,
            "voices_repaired_count": 0,
            "total_leaked_lines_removed": 0,
            "total_lines_removed": 0,
            "repaired_script_ids": [],
            "repaired_voice_ids": [],
            "repaired_video_ids": [],
            "elapsed_sec": 0.0,
            "details": [],
            "report_path": "",
        }

    proj_folders = sorted([d for d in projects_dir.iterdir() if d.is_dir() and not d.name.startswith(".")])
    total = len(proj_folders)
    repaired_script_ids: List[str] = []
    repaired_voice_ids: List[str] = []
    repaired_video_ids: List[str] = []
    srts_repaired_count = 0
    voices_repaired_count = 0
    total_lines_removed = 0
    details: List[Dict[str, Any]] = []
    media_trim_queue: List[Dict[str, Any]] = []

    # ==========================================================================
    # GIAI ĐOẠN 1: QUÉT & DỌN SẠCH TOÀN BỘ KỊCH BẢN (.TXT) TRƯỚC TIÊN (1-2 GIÂY)
    # ==========================================================================
    t_phase1_start = time.time()
    for idx, p_dir in enumerate(proj_folders):
        if progress_cb and (idx % 10 == 0 or idx == total - 1):
            pct1 = round(((idx + 1) / max(1, total)) * 30.0, 1)
            try:
                progress_cb(
                    pct1,
                    f"⚡ [Bước 1/2: Dọn Kịch Bản] Đang quét {idx + 1}/{total} dự án [{p_dir.name}] (Đã sửa sạch {len(repaired_script_ids)} KB)...",
                )
            except Exception:
                pass

        st = clean_single_project_scripts_and_detect_media_cuts(p_dir)
        if st["script_cleaned"] or st["srt_cleaned"]:
            repaired_script_ids.append(st["ma_id"])
            total_lines_removed += st["script_removed_lines_count"] + st["srt_removed_blocks_count"]
        if st["srt_cleaned"]:
            srts_repaired_count += 1
        if st["needs_media_trim"]:
            media_trim_queue.append(st)
        elif st["script_cleaned"] or st["srt_cleaned"]:
            st_clean = {k: v for k, v in st.items() if k not in ("proj_dir", "raw_cut_intervals", "cleaned_srt_text")}
            details.append(st_clean)

    phase1_sec = round(time.time() - t_phase1_start, 2)
    phase1_msg = (
        f"✅ [Bước 1/2 Hoàn tất trong {phase1_sec}s] Đã quét xong {total} kịch bản (.txt): "
        f"Làm sạch {len(repaired_script_ids)} kịch bản ({total_lines_removed} dòng lỗi) | "
        f"Phát hiện {len(media_trim_queue)} dự án có Video/Voice cần cắt đoạn đọc nhầm."
    )
    if log_cb:
        try:
            log_cb(phase1_msg)
        except Exception:
            pass
    if progress_cb:
        try:
            progress_cb(35.0 if media_trim_queue else 99.0, phase1_msg)
        except Exception:
            pass

    # ==========================================================================
    # GIAI ĐOẠN 2: CẮT ĐOẠN ĐỌC NHẦM TRONG VIDEO (.MP4) & VOICE (.WAV)
    # ==========================================================================
    total_media = len(media_trim_queue)
    for m_idx, st in enumerate(media_trim_queue, 1):
        mid = st["ma_id"]
        pct2 = round(35.0 + ((m_idx - 0.5) / max(1, total_media)) * 63.0, 1)
        start_v_msg = (
            f"✂️ [Bước 2/2: Cắt Video {m_idx}/{total_media} • {mid}] "
            f"Đang cắt {len(st['cut_intervals'])} đoạn [LOCKED_TITLE] ({st['cut_intervals']})..."
        )
        if progress_cb:
            try:
                progress_cb(pct2, start_v_msg)
            except Exception:
                pass
        if log_cb:
            try:
                log_cb(start_v_msg)
            except Exception:
                pass

        t_v0 = time.time()
        st_after = execute_project_media_trim(st)
        v_sec = round(time.time() - t_v0, 2)

        if st_after["video_repaired"]:
            repaired_video_ids.append(mid)
        if st_after["voice_repaired"]:
            voices_repaired_count += 1
            repaired_voice_ids.append(mid)

        st_clean = {k: v for k, v in st_after.items() if k not in ("proj_dir", "raw_cut_intervals", "cleaned_srt_text")}
        details.append(st_clean)

        done_v_msg = (
            f"✅ [Xong Video {m_idx}/{total_media} • {mid} trong {v_sec}s] "
            f"MP4: {st_after['old_video_duration']}s -> {st_after['new_video_duration']}s | "
            f"Voice WAV: {'Đã cắt' if st_after['voice_repaired'] else 'Bỏ qua'} | "
            f"SRT: Đã xóa {st_after['srt_removed_blocks_count']} khung."
        )
        if log_cb:
            try:
                log_cb(done_v_msg)
            except Exception:
                pass
        if progress_cb:
            pct2_done = round(35.0 + (m_idx / max(1, total_media)) * 63.0, 1)
            try:
                progress_cb(pct2_done, done_v_msg)
            except Exception:
                pass

    elapsed_sec = round(time.time() - t0, 2)

    # Ghi file báo cáo tổng hợp rõ ràng cho người dùng / khách hàng
    report_path = projects_dir.parent / "BAO_CAO_CHECK_VA_DON_TOAN_BO.txt"
    try:
        lines_rep = [
            "================================================================================",
            "BÁO CÁO KIỂM TRA & DỌN SẠCH LỖI [LOCKED_TITLE] TRONG KỊCH BẢN & VIDEO MP4",
            "================================================================================",
            f"- Thời gian thực hiện: {time.strftime('%Y-%m-%d %H:%M:%S')} (Tổng: {elapsed_sec}s | Dọn KB: {phase1_sec}s)",
            f"- Thư mục gốc kiểm tra: {projects_dir}",
            f"- Tổng số dự án đã quét: {total}",
            f"- Số kịch bản phát hiện lỗi & đã sửa sạch: {len(repaired_script_ids)} dự án",
            f"- Số phụ đề (.srt) đã dọn & dịch khớp thời gian: {srts_repaired_count} file",
            f"- Số file Voice (.wav) đã cắt bỏ đoạn đọc nhầm: {voices_repaired_count} file",
            f"- Số Video MP4 đã cắt bỏ đoạn voice/sub lỗi [LOCKED_TITLE]: {len(repaired_video_ids)} video",
            f"- Tổng số dòng/khung [LOCKED_TITLE] & Metadata đã xóa: {total_lines_removed}",
            "================================================================================",
            "",
            f"1. DANH SÁCH MÃ KỊCH BẢN ĐÃ ĐƯỢC LÀM SẠCH ({len(repaired_script_ids)} dự án):",
            "--------------------------------------------------------------------------------",
            (", ".join(repaired_script_ids) if repaired_script_ids else "Không có kịch bản nào còn lỗi (100% đã sạch)."),
            "",
            f"2. DANH SÁCH VIDEO MP4 ĐÃ ĐƯỢC CẮT SẠCH ĐOẠN VOICE LỖI ({len(repaired_video_ids)} video):",
            "--------------------------------------------------------------------------------",
            (", ".join(repaired_video_ids) if repaired_video_ids else "Không có video MP4 nào bị dính lỗi (hoặc đã được dọn sạch)."),
            "",
            "3. CHI TIẾT TỪNG DỰ ÁN ĐÃ XỬ LÝ:",
            "================================================================================",
        ]
        for i_d, d in enumerate(details, 1):
            lines_rep.append(f"[{i_d}] Dự án: {d['ma_id']}")
            lines_rep.append(f"    - Đã xóa dòng lỗi trong Kịch bản (.txt): {d['script_removed_lines_count']} dòng")
            lines_rep.append(f"    - Đã xóa khung lỗi trong Phụ đề (.srt): {d['srt_removed_blocks_count']} khung")
            if d["video_repaired"]:
                lines_rep.append(
                    f"    - Đã cắt sạch Video MP4: {d['old_video_duration']}s -> {d['new_video_duration']}s (Các đoạn đã cắt: {d['cut_intervals']})"
                )
            for smp in d.get("script_removed_samples", []):
                lines_rep.append(f"      + Đã xóa: {smp}")
            lines_rep.append("--------------------------------------------------------------------------------")
        report_path.write_text("\n".join(lines_rep), encoding="utf-8")
    except Exception:
        pass

    if progress_cb:
        try:
            progress_cb(
                100.0,
                f"✅ Hoàn tất Check Toàn Bộ {total} dự án ({elapsed_sec}s): Đã làm sạch {len(repaired_script_ids)} Kịch bản & cắt sạch lỗi {len(repaired_video_ids)} Video MP4!",
            )
        except Exception:
            pass

    return {
        "total_projects": total,
        "total_scanned": total,
        "scripts_repaired_count": len(repaired_script_ids),
        "srts_repaired_count": srts_repaired_count,
        "videos_repaired_count": len(repaired_video_ids),
        "voices_repaired_count": voices_repaired_count,
        "total_leaked_lines_removed": total_lines_removed,
        "total_lines_removed": total_lines_removed,
        "repaired_script_ids": repaired_script_ids,
        "repaired_voice_ids": repaired_voice_ids,
        "repaired_video_ids": repaired_video_ids,
        "phase1_script_sec": phase1_sec,
        "elapsed_sec": elapsed_sec,
        "details": details,
        "report_path": str(report_path),
    }

