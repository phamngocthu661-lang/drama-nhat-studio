import os
import sys
import json
import time
import wave
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

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
