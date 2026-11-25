import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .chatgpt_web_client import (
    ACCOUNT_LIMIT_COOLDOWN_SEC,
    ACCOUNTS_CONFIG,
    AccountRateLimitError,
    ChatGPTWebSession,
    _profile_has_saved_chatgpt_login,
    check_all_web_accounts_status,
    is_account_in_cooldown,
    mark_account_rate_limited,
)
from .logger_service import log_error, log_info, log_warn

SRT_CHATGPT_CONCURRENCY_LIMIT = 5
_SRT_CHATGPT_SEMAPHORE = threading.Semaphore(SRT_CHATGPT_CONCURRENCY_LIMIT)
_SRT_ACC_BUSY_LOCK = threading.Lock()
_SRT_ACC_IN_USE: set = set()
_SRT_ACC_RR_IDX = 0


def _acquire_srt_account_slot(
    candidate_pool: List[str],
    preferred_acc_id: Optional[str],
    excl_accs: set,
    wait_timeout_sec: float = 45.0,
    should_stop_cb: Optional[Callable[[], bool]] = None,
    logged_accs_priority: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Cấp phát ĐỘC QUYỀN tối đa 1 job SRT → SEO trên mỗi tài khoản ChatGPT tại một thời điểm
    (ưu tiên các nick đang mở sẵn `logged_accs_priority` trước rồi mới tới các nick lưu trên ổ cứng,
    xoay vòng đều qua Acc #1..#5 để tuyệt đối không dồn 3 luồng nặng vào cùng 1 nick).
    """
    global _SRT_ACC_RR_IDX
    deadline = time.time() + max(1.0, float(wait_timeout_sec))
    priority_set = set(logged_accs_priority or [])

    while True:
        if should_stop_cb and should_stop_cb():
            raise InterruptedError("Đã dừng tiến trình theo yêu cầu.")

        pool = [a for a in candidate_pool if a in ACCOUNTS_CONFIG and a not in excl_accs and not is_account_in_cooldown(a)[0]]
        if not pool:
            return None

        with _SRT_ACC_BUSY_LOCK:
            free_accs = [a for a in pool if a not in _SRT_ACC_IN_USE]
            if free_accs:
                free_logged = [a for a in free_accs if a in priority_set] if priority_set else []
                pick_from = free_logged or free_accs
                if preferred_acc_id and preferred_acc_id in free_accs:
                    chosen = preferred_acc_id
                else:
                    chosen = pick_from[_SRT_ACC_RR_IDX % len(pick_from)]
                    _SRT_ACC_RR_IDX += 1
                _SRT_ACC_IN_USE.add(chosen)
                return chosen

        if time.time() >= deadline:
            return None
        time.sleep(0.5)


def _release_srt_account_slot(acc_id: Optional[str]) -> None:
    if not acc_id:
        return
    with _SRT_ACC_BUSY_LOCK:
        _SRT_ACC_IN_USE.discard(acc_id)

_SRT_TIME_LINE_RE = re.compile(
    r"^\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})"
)
_TS_CHAPTER_LINE_RE = re.compile(
    r"^\s*(?:(?:[-•*・]+|\d+[\.\)])\s*)?(?:\*\*|`)?\[?(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})\]?(?:\*\*|`)?\s*(?:[-–—:：|]\s*)?(?P<label>.+?)\s*$"
)
_CHAPTER_HEADER_RE = re.compile(
    r"^(?:▼?\s*目次.*|チャプター.*|タイムスタンプ.*|TIMESTAMPS.*|CHAPTERS.*)$",
    re.IGNORECASE,
)


def parse_srt_hms_to_seconds(ts: str) -> float:
    """Chuyển chuỗi thời gian SRT (`HH:MM:SS,mmm` hoặc `MM:SS`) sang tổng số giây."""
    clean = (ts or "").strip().replace(",", ".")
    parts = clean.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600.0 + int(parts[1]) * 60.0 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60.0 + float(parts[1])
    except Exception:
        pass
    return 0.0


def format_youtube_timestamp(seconds: float, force_hours: bool = False) -> str:
    """Định dạng giây theo chuẩn YouTube Chapters (`MM:SS` dưới 1 giờ, `HH:MM:SS` từ 1 giờ trở lên)."""
    total_sec = max(0, int(round(seconds)))
    hours = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0 or force_hours:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def parse_srt_entries(srt_text: str) -> List[Dict[str, Any]]:
    """Tách nội dung file `.srt` thành danh sách từng câu thoại kèm `start_sec`, `end_sec`, `text`."""
    raw = (srt_text or "").lstrip("\ufeff").strip()
    if not raw:
        return []

    raw_blocks = re.split(r"\r?\n\s*\r?\n", raw)
    entries: List[Dict[str, Any]] = []
    for blk in raw_blocks:
        lines = [ln.strip() for ln in blk.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        ts_idx = -1
        ts_match = None
        for idx, ln in enumerate(lines[:3]):
            m = _SRT_TIME_LINE_RE.match(ln)
            if m:
                ts_idx = idx
                ts_match = m
                break
        if ts_match is None or ts_idx + 1 >= len(lines):
            continue
        start_sec = parse_srt_hms_to_seconds(ts_match.group(1))
        end_sec = max(start_sec, parse_srt_hms_to_seconds(ts_match.group(2)))
        joined_text = "".join(lines[ts_idx + 1 :]).strip()
        if not joined_text:
            continue
        entries.append(
            {
                "idx": len(entries) + 1,
                "start_sec": start_sec,
                "end_sec": end_sec,
                "text": joined_text,
            }
        )
    return entries


def build_srt_chronological_digest(
    srt_path: Path,
    max_chars: int = 24000,
) -> Dict[str, Any]:
    """
    Nén thông minh file `.srt` (thường dài 150KB–350KB) thành bản tóm lược theo trình tự thời gian thực
    (`< max_chars`), giữ nguyên các mốc `[MM:SS]` / `[HH:MM:SS]` thật từ đầu tới cuối để ChatGPT phân tích trọn vẹn cốt truyện.
    """
    raw_srt = Path(srt_path).read_text(encoding="utf-8-sig", errors="ignore")
    entries = parse_srt_entries(raw_srt)
    if not entries:
        return {
            "digest_text": "",
            "total_duration_sec": 0.0,
            "total_duration_str": "00:00",
            "entries_count": 0,
            "entries": [],
            "anchor_seconds": [0.0],
        }

    total_dur = max(e["end_sec"] for e in entries)
    total_dur_str = format_youtube_timestamp(total_dur)

    # Nhóm các câu thoại liên tiếp thành từng cụm ~40 giây để tiết kiệm ký tự mà vẫn giữ đủ mốc thời gian
    grouped: List[Dict[str, Any]] = []
    curr_bucket: Optional[Dict[str, Any]] = None
    for ent in entries:
        if curr_bucket is None:
            curr_bucket = {
                "start_sec": ent["start_sec"],
                "end_sec": ent["end_sec"],
                "texts": [ent["text"]],
            }
            continue
        span = ent["start_sec"] - curr_bucket["start_sec"]
        curr_len = sum(len(t) for t in curr_bucket["texts"])
        if span < 40.0 and curr_len < 360:
            curr_bucket["texts"].append(ent["text"])
            curr_bucket["end_sec"] = ent["end_sec"]
        else:
            grouped.append(curr_bucket)
            curr_bucket = {
                "start_sec": ent["start_sec"],
                "end_sec": ent["end_sec"],
                "texts": [ent["text"]],
            }
    if curr_bucket is not None:
        grouped.append(curr_bucket)

    full_lines = [
        f"[{format_youtube_timestamp(b['start_sec'])}] {''.join(b['texts'])}"
        for b in grouped
    ]
    full_digest = "\n".join(full_lines)

    if len(full_digest) <= max_chars:
        anchor_secs = [round(b["start_sec"], 1) for b in grouped]
        return {
            "digest_text": full_digest,
            "total_duration_sec": total_dur,
            "total_duration_str": total_dur_str,
            "entries_count": len(entries),
            "entries": entries,
            "anchor_seconds": anchor_secs,
            "compacted": False,
        }

    # Với video dài (60–180 phút): Chia thành ~95 cửa sổ thời gian đồng đều từ 0% đến 100%
    # Giữ độ phân giải cao cho 3 phút mở đầu và trích đầu/cuối mỗi cửa sổ sao cho tổng <= max_chars
    target_windows = min(105, max(24, len(grouped)))
    per_window_budget = max(140, (max_chars - 1200) // target_windows)
    sampled_lines: List[str] = []
    anchor_secs = [0.0]

    n_grp = len(grouped)
    for w_idx in range(target_windows):
        i_start = int(w_idx * n_grp / target_windows)
        i_end = max(i_start + 1, int((w_idx + 1) * n_grp / target_windows))
        chunk = grouped[i_start:i_end]
        ts_sec = 0.0 if w_idx == 0 else chunk[0]["start_sec"]
        anchor_secs.append(round(ts_sec, 1))
        ts_label = format_youtube_timestamp(ts_sec)
        merged = "".join("".join(c["texts"]) for c in chunk)
        if len(merged) <= per_window_budget:
            excerpt = merged
        else:
            half = max(60, (per_window_budget - 10) // 2)
            excerpt = f"{merged[:half]} … {merged[-half:]}"
        sampled_lines.append(f"[{ts_label}] {excerpt}")

    digest_text = "\n".join(sampled_lines)[:max_chars]
    return {
        "digest_text": digest_text,
        "total_duration_sec": total_dur,
        "total_duration_str": total_dur_str,
        "entries_count": len(entries),
        "entries": entries,
        "anchor_seconds": anchor_secs,
        "compacted": True,
    }


def _strip_genui_markup(text: str) -> str:
    """Loại bỏ các thẻ GenUI / XML bao quanh văn bản thuần khi nhận phản hồi từ ChatGPT."""
    if not text:
        return ""
    cleaned = re.sub(
        r"</?(?:WritingBlock|CodeBlock|box|row|col|text|title|badge|caption|divider|list|list-item)\b[^>]*>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def extract_existing_seo_sections(seo_text: str) -> Dict[str, str]:
    """Bóc tách `locked_title` và `description_ja` hiện có từ file SEO của dự án."""
    raw = seo_text or ""
    locked_title = ""
    desc_ja = ""

    m_title = re.search(
        r"(?:LOCKED_TITLE|FINAL_LOCKED_TITLE|1\.\s*FINAL_TITLE[^\r\n]*)[^\r\n]*\r?\n+([^\r\n]+)",
        raw,
        flags=re.IGNORECASE,
    )
    if m_title:
        cand = _strip_genui_markup(m_title.group(1)).strip("「」`*'\" ")
        if "Tiêu đề tiếng Nhật" in cand:
            after_pos = m_title.end()
            for ln in raw[after_pos : after_pos + 400].splitlines():
                cl = _strip_genui_markup(ln).strip("「」`*'\" ")
                if len(cl) >= 12 and re.search(r"[\u3040-\u30ff\u4e00-\u9faf]", cl):
                    cand = cl
                    break
        if len(cand) >= 8 and re.search(r"[\u3040-\u30ff\u4e00-\u9faf]", cand):
            locked_title = cand

    m_desc = re.search(
        r"(?:^|\n)\s*(?:#{1,4}\s*(?:\d+\.\s*)?)?YOUTUBE_DESCRIPTION_JA\b[^\r\n]*\r?\n+([\s\S]*?)(?=\n\s*(?:#{1,4}\s*\d+\.|3\.\s*HASHTAGS|\*\*HASHTAGS|HASHTAGS\s*[:：—\-]|YOUTUBE_TAGS_JA|TAGS_CSV|PINNED_COMMENT|VIETNAMESE_SUMMARY|FINAL_THUMBNAIL|================================================================================)|\Z)",
        raw,
        flags=re.IGNORECASE,
    )
    if m_desc:
        body = _strip_genui_markup(m_desc.group(1))
        # Loại bỏ dòng ghi chú hướng dẫn tiếng Việt nằm cuối mục 2 nếu có
        body_lines = [
            ln
            for ln in body.splitlines()
            if not ln.strip().startswith(("Mô tả ưu tiên", "Ghi chú mô tả"))
        ]
        desc_ja = "\n".join(body_lines).strip()

    return {
        "locked_title": locked_title,
        "description_ja": desc_ja,
    }


def build_srt_seo_analysis_prompt(
    ma_id: str,
    locked_title: str,
    digest_info: Dict[str, Any],
    existing_desc_ja: str = "",
) -> str:
    """Tạo lệnh gửi ChatGPT Web phân tích file SRT để bổ sung Mô tả SEO tiếng Nhật & Timestamps/Chapters chính xác."""
    total_dur_str = digest_info.get("total_duration_str") or "00:00"
    digest_text = digest_info.get("digest_text") or ""
    existing_block = (
        f"========== MÔ TẢ YOUTUBE HIỆN CÓ (CẦN GIỮ Ý MỞ ĐẦU TỐT, TỐI ƯU & BỔ SUNG THÊM TỪ SRT) ==========\n"
        f"{existing_desc_ja.strip()}\n"
        f"=================================================================================================\n\n"
        if existing_desc_ja.strip()
        else ""
    )

    return f"""NHIỆM VỤ CHUYÊN BIỆT: PHÂN TÍCH FILE PHỤ ĐỀ `subtitles.srt` ĐỂ TỐI ƯU MÔ TẢ SEO & TẠO TIMESTAMPS (CHAPTERS) YOUTUBE CHUẨN XÁC CHO DỰ ÁN `{ma_id}`.

📌 THÔNG TIN BẮT BUỘC:
- Mã dự án: `{ma_id}`
- `LOCKED_TITLE` (Bất biến, KHÔNG ĐƯỢC SỬA ĐỔI TIÊU ĐỀ): 「{locked_title}」
- Tổng thời lượng thực tế của Audio / SRT: `{total_dur_str}`

{existing_block}========== TOÀN BỘ DIỄN BIẾN PHỤ ĐỀ `subtitles.srt` KÈM MỐC THỜI GIAN THẬT (00:00 -> {total_dur_str}) ==========
{digest_text}
====================================================================================================

⚠️ YÊU CẦU THỰC HIỆN NGAY (KHÔNG DÙNG PYTHON / CODE INTERPRETER, KHÔNG TẠO FILE TẢI VỀ):
1. Hãy đọc & phân tích toàn bộ diễn biến câu chuyện từ mốc `00:00` đến `{total_dur_str}` trong `subtitles.srt` ở trên.
2. Nâng cấp & bổ sung hoàn chỉnh phần **Mô tả video tiếng Nhật (`YOUTUBE_DESCRIPTION_JA`)**:
   - Giữ & mài sắc 2 dòng mở đầu giàu cảm xúc, đúng tên nhân vật, bối cảnh và vật chứng thật xuất hiện trong `subtitles.srt` (tuyệt đối KHÔNG tiết lộ chân tướng/cái kết bất ngờ cuối truyện — ネタバレ禁止).
   - Bổ sung chi tiết đắt giá & từ khóa tự nhiên tiếng Nhật từ diễn biến SRT để tăng giữ chân & SEO YouTube.
   - **TÍCH HỢP TRỰC TIẾP BẢNG TIMESTAMPS / CHAPTERS VÀO NGAY BÊN TRONG MÔ TẢ** dưới tiêu đề:
     `▼目次（チャプター・タイムスタンプ）`
     gồm **7 đến 10 chương** bám sát chính xác các mốc chuyển cảnh/cao trào có thật trong `subtitles.srt`:
     + Chương đầu tiên BẮT BUỘC là `00:00` (VD: `00:00 【導入】...` hoặc `00:00 プロローグ・...`).
     + Các mốc thời gian phải **tăng dần liên tục**, đúng định dạng (`MM:SS` dưới 1 giờ, `HH:MM:SS` từ 1 giờ trở lên), **nhỏ hơn `{total_dur_str}`**, cách nhau hợp lý (ít nhất vài phút).
     + Tên từng chương viết bằng tiếng Nhật tự nhiên, gợi tò mò (10–24 ký tự Nhật), KHÔNG spoil bí mật cuối cùng.
   - Cuối mô tả giữ lời kêu gọi đăng ký/bình luận + các Hashtags tiếng Nhật phù hợp (`#感動する話 #朗読 #スカッとする話` + 2–3 hashtag chủ đề).
3. Xuất kết quả theo ĐÚNG cấu trúc cặp thẻ XML sau (tuyệt đối không bọc trong Markdown code fence ``` hay `<WritingBlock>`):

<UPDATED_YOUTUBE_DESCRIPTION_JA>
[Toàn bộ nội dung Mô tả tiếng Nhật hoàn chỉnh đã tích hợp sẵn mục ▼目次（チャプター・タイムスタンプ） + 00:00..HH:MM:SS + CTA + Hashtags, sẵn sàng copy dán 1 lần lên YouTube]
</UPDATED_YOUTUBE_DESCRIPTION_JA>

<YOUTUBE_TIMESTAMPS_JA>
00:00 ...
[Liệt kê lại chính xác 7–10 dòng Timestamps vừa tạo ở trên, mỗi dòng 1 mốc thời gian]
</YOUTUBE_TIMESTAMPS_JA>"""


def _normalize_chapters_list(
    raw_lines: List[str],
    total_duration_sec: float,
) -> List[Tuple[str, str]]:
    """Chuẩn hóa, sắp xếp tăng dần và xác thực danh sách Chapters theo mốc `00:00`..`< total_duration`."""
    parsed: List[Tuple[float, str]] = []
    for ln in raw_lines:
        clean_ln = _strip_genui_markup(ln).strip()
        if not clean_ln or _CHAPTER_HEADER_RE.match(clean_ln):
            continue
        m = _TS_CHAPTER_LINE_RE.match(clean_ln)
        if not m:
            continue
        ts_raw = m.group("ts").strip()
        label = re.sub(r"^[\-\–—:：\s]+", "", m.group("label")).strip().strip("`*")
        if not label:
            continue
        sec = parse_srt_hms_to_seconds(ts_raw)
        if total_duration_sec > 30 and sec >= max(10.0, total_duration_sec - 3.0):
            continue
        parsed.append((sec, label))

    if not parsed:
        return []

    parsed.sort(key=lambda x: x[0])

    # Đảm bảo chương đầu tiên bắt đầu tại 00:00
    if parsed[0][0] > 25.0:
        parsed.insert(0, (0.0, "【導入】物語の始まり"))
    else:
        parsed[0] = (0.0, parsed[0][1])

    deduped: List[Tuple[float, str]] = []
    min_gap = 12.0 if total_duration_sec >= 120 else 3.0
    for sec, label in parsed:
        if deduped and (sec - deduped[-1][0]) < min_gap:
            continue
        deduped.append((sec, label))

    return [(format_youtube_timestamp(sec), label) for sec, label in deduped]


def _ensure_timestamps_inside_description(
    desc_text: str,
    timestamps_block: str,
) -> str:
    """Đảm bảo phần Mô tả luôn chứa đúng 1 khối `▼目次（チャプター・タイムスタンプ）` + Timestamps sạch sẽ."""
    clean_desc = _strip_genui_markup(desc_text).strip()
    if not clean_desc:
        return f"▼目次（チャプター・タイムスタンプ）\n{timestamps_block}"

    # Xóa các khối timestamps cũ nếu bị trùng hoặc rời rạc
    lines = clean_desc.splitlines()
    filtered_lines: List[str] = []
    skip_chapter_block = False
    for ln in lines:
        s = ln.strip()
        if _CHAPTER_HEADER_RE.match(s):
            skip_chapter_block = True
            continue
        if skip_chapter_block:
            if _TS_CHAPTER_LINE_RE.match(s):
                continue
            if not s:
                continue
            skip_chapter_block = False
        if _TS_CHAPTER_LINE_RE.match(s) and re.match(r"^(?:[-•*・\s`\[\*]*)(?:\d{1,2}:)?\d{1,2}:\d{2}\b", s):
            continue
        filtered_lines.append(ln)

    body_clean = re.sub(r"\n{3,}", "\n\n", "\n".join(filtered_lines)).strip()
    chapter_section = f"▼目次（チャプター・タイムスタンプ）\n{timestamps_block.strip()}"

    # Chèn ngay trước lời kêu gọi đăng ký / Hashtag nếu tìm thấy, ngược lại gắn ngay sau phần giới thiệu
    insert_match = re.search(
        r"\n+(?=(?:▼?\s*(?:チャンネル登録|高評価)|最後までご視聴|ぜひ最後まで|よろしければ|ご視聴ありがとう|感想を|皆さんは、|もしこの|#[A-Za-z0-9_\u3040-\u30ff\u4e00-\u9faf]+))",
        body_clean,
    )
    if insert_match:
        pos = insert_match.start()
        head = body_clean[:pos].rstrip()
        tail = body_clean[pos:].lstrip("\r\n")
        return f"{head}\n\n{chapter_section}\n\n{tail}".strip()

    return f"{body_clean}\n\n{chapter_section}".strip()


def parse_and_validate_srt_seo_response(
    raw_resp: str,
    total_duration_sec: float,
    existing_desc_ja: str = "",
) -> Dict[str, Any]:
    """Phân tích, làm sạch và kiểm định đầu ra từ ChatGPT (Description tiếng Nhật + Timestamps)."""
    cleaned_resp = _strip_genui_markup(raw_resp or "")
    desc_out = ""
    ts_lines_raw: List[str] = []

    m_desc = re.search(
        r"<(?:UPDATED_)?YOUTUBE_DESCRIPTION_JA>([\s\S]*?)</(?:UPDATED_)?YOUTUBE_DESCRIPTION_JA>",
        cleaned_resp,
        flags=re.IGNORECASE,
    )
    if m_desc:
        desc_out = _strip_genui_markup(m_desc.group(1))

    m_ts = re.search(
        r"<YOUTUBE_TIMESTAMPS_JA>([\s\S]*?)</YOUTUBE_TIMESTAMPS_JA>",
        cleaned_resp,
        flags=re.IGNORECASE,
    )
    if m_ts:
        ts_lines_raw = [ln.strip() for ln in m_ts.group(1).splitlines() if ln.strip()]

    # Dự phòng trích timestamps từ phần mô tả hoặc toàn bộ phản hồi nếu ChatGPT bỏ thẻ XML
    if not ts_lines_raw:
        search_src = desc_out or cleaned_resp
        for ln in search_src.splitlines():
            if _TS_CHAPTER_LINE_RE.match(ln.strip()):
                ts_lines_raw.append(ln.strip())

    chapters = _normalize_chapters_list(ts_lines_raw, total_duration_sec=total_duration_sec)
    if not desc_out and cleaned_resp and len(chapters) >= 3:
        # Nếu không có thẻ XML nhưng có nội dung tiếng Nhật hợp lệ
        without_ts_tag = re.sub(r"<YOUTUBE_TIMESTAMPS_JA>[\s\S]*?</YOUTUBE_TIMESTAMPS_JA>", "", cleaned_resp, flags=re.IGNORECASE).strip()
        if re.search(r"[\u3040-\u30ff\u4e00-\u9faf]{20,}", without_ts_tag):
            desc_out = without_ts_tag

    if not desc_out:
        desc_out = existing_desc_ja.strip()

    timestamps_txt = "\n".join(f"{ts} {lbl}" for ts, lbl in chapters).strip()
    valid = len(chapters) >= 3 and bool(desc_out.strip())
    if valid and timestamps_txt:
        desc_out = _ensure_timestamps_inside_description(desc_out, timestamps_txt)

    return {
        "valid": valid,
        "description_ja": desc_out.strip(),
        "timestamps_txt": timestamps_txt,
        "chapters": [{"timestamp": ts, "label": lbl} for ts, lbl in chapters],
        "chapters_count": len(chapters),
    }


def build_fallback_srt_timestamps_and_description(
    srt_path: Path,
    existing_desc_ja: str = "",
    locked_title: str = "",
    summary_vi: str = "",
) -> Dict[str, Any]:
    """
    Phương án dự phòng bằng tiếng Nhật khi mọi tài khoản ChatGPT Web đều chưa đăng nhập hoặc bị quá tải:
    Chia file `.srt` thành 8 mốc thực tế (00:00 -> hết truyện) với nhãn tiếng Nhật sạch sẽ.
    """
    raw_srt = Path(srt_path).read_text(encoding="utf-8-sig", errors="ignore")
    entries = parse_srt_entries(raw_srt)
    total_dur = max((e["end_sec"] for e in entries), default=0.0)

    ja_chapter_labels = [
        "【序章】静かな日常の始まり",
        "【第1章】違和感が芽生えた瞬間",
        "【第2章】家族のすれ違いと葛藤",
        "【第3章】隠されていた真実の影",
        "【第4章】運命を動かす決定的な出来事",
        "【第5章】すべてが明らかになる時",
        "【第6章】それぞれの選択と後悔",
        "【終章】家族の絆と新たな歩み",
    ]
    chapters: List[Tuple[str, str]] = []
    if entries:
        num_ch = min(len(ja_chapter_labels), max(3, len(entries) // 40 or 4))
        for idx in range(num_ch):
            pos = 0 if idx == 0 else int((idx * len(entries)) / num_ch)
            pos = min(pos, len(entries) - 1)
            sec = 0.0 if idx == 0 else entries[pos]["start_sec"]
            ts_str = format_youtube_timestamp(sec)
            lbl = ja_chapter_labels[idx] if idx < len(ja_chapter_labels) else f"【第{idx}章】物語の展開"
            if not chapters or chapters[-1][0] != ts_str:
                chapters.append((ts_str, lbl))
    else:
        chapters = [("00:00", "【本編】物語の始まり")]

    timestamps_txt = "\n".join(f"{ts} {lbl}" for ts, lbl in chapters)
    base_desc = existing_desc_ja.strip()
    if not base_desc:
        base_desc = (
            f"{locked_title}\n\n"
            "長い年月の中で語られなかった家族の記憶と、静かに残された真実の記録。\n"
            "すれ違いの果てに見えてきた本当の想いを、丁寧な朗読でお届けします。\n\n"
            "ぜひ最後までごゆっくりお聴きください。\n\n"
            "▼チャンネル登録・高評価をいただけますと励みになります。\n"
            "#感動する話 #朗読 #スカッとする話 #家族の絆 #シニアライフ"
        ).strip()
    final_desc = _ensure_timestamps_inside_description(base_desc, timestamps_txt)
    return {
        "valid": True,
        "description_ja": final_desc,
        "timestamps_txt": timestamps_txt,
        "chapters": [{"timestamp": ts, "label": lbl} for ts, lbl in chapters],
        "chapters_count": len(chapters),
        "total_duration_sec": total_dur,
    }


def _replace_description_in_seo_document(
    doc_text: str,
    new_desc_ja: str,
    locked_title: str = "",
) -> str:
    """Cập nhật trực tiếp mục `YOUTUBE_DESCRIPTION_JA` bên trong tài liệu SEO hiện có."""
    src = (doc_text or "").strip()

    # Xóa block timestamps tự động bằng tiếng Việt ở cuối file (nếu phiên bản cũ từng chèn)
    src = re.sub(
        r"\n*=+\n*⏱️\s*TIMESTAMPS\s*/\s*CHAPTERS YOUTUBE[^\n]*\n*=+\n*[\s\S]*$",
        "",
        src,
        flags=re.IGNORECASE,
    ).strip()

    if not src:
        title_line = locked_title or "(LOCKED_TITLE)"
        return (
            f"## 1. FINAL_TITLE — LOCKED\n\n{title_line}\n\n"
            f"## 2. YOUTUBE_DESCRIPTION_JA\n\n{new_desc_ja.strip()}\n\n"
            f"## 3. HASHTAGS & TAGS_CSV\n"
            "#感動する話 #朗読 #スカッとする話 #家族の絆 #高齢者の暮らし #朗読ドラマ\n"
        )

    sec_pat = re.compile(
        r"(?P<header>(?:^|\n)\s*(?:#{1,4}\s*(?:\d+\.\s*)?)?YOUTUBE_DESCRIPTION_JA[^\r\n]*\r?\n+)"
        r"(?P<body>[\s\S]*?)"
        r"(?P<tail>\n\s*(?:#{1,4}\s*\d+\.|3\.\s*HASHTAGS|\*\*HASHTAGS|HASHTAGS\s*[:：—\-]|YOUTUBE_TAGS_JA|TAGS_CSV|PINNED_COMMENT|VIETNAMESE_SUMMARY|FINAL_THUMBNAIL|================================================================================)|\Z)",
        flags=re.IGNORECASE,
    )
    if sec_pat.search(src):
        # Cập nhật tất cả vị trí mục 2 (phòng trường hợp trong 00_TIEU_DE có cả phần STEP 6)
        return sec_pat.sub(
            lambda m: f"{m.group('header').rstrip()}\n\n{new_desc_ja.strip()}\n{m.group('tail')}",
            src,
        ).strip() + "\n"

    # Nếu file SEO chưa có mục YOUTUBE_DESCRIPTION_JA (VD: file tổng hợp tùy biến) -> chèn ngay sau tiêu đề khóa
    marker = "🚀 GÓI SEO YOUTUBE"
    if marker in src:
        idx = src.find(marker)
        line_end = src.find("\n", idx)
        sep_end = src.find("\n", line_end + 1) if line_end != -1 else -1
        insert_at = sep_end + 1 if sep_end != -1 else len(src)
        injected = f"\n## 2. YOUTUBE_DESCRIPTION_JA\n\n{new_desc_ja.strip()}\n\n"
        return (src[:insert_at] + injected + src[insert_at:]).strip() + "\n"

    return f"{src}\n\n## 2. YOUTUBE_DESCRIPTION_JA\n\n{new_desc_ja.strip()}\n"


def update_seo_files_with_chatgpt_srt_result(
    proj_dir: Path,
    ma_id: str,
    description_ja: str,
    timestamps_txt: str,
    final_proj_dir: Optional[Path] = None,
    locked_title: str = "",
    idea: Optional[Dict[str, Any]] = None,
    srt_sha256: str = "",
    source_tag: str = "chatgpt_web",
    acc_id: str = "",
    total_duration_sec: float = 0.0,
) -> Dict[str, Any]:
    """Ghi đồng bộ Mô tả + Timestamps vào `00_TIEU_DE_VA_SEO_YOUTUBE.txt`, `{ma_id}_SEO.txt`, `seo_publish_pack.txt` và `assets/TIMESTAMPS.txt`."""
    proj_dir = Path(proj_dir)
    final_proj_dir = Path(final_proj_dir) if final_proj_dir else proj_dir
    assets_dir = proj_dir / "assets"
    renders_dir = proj_dir / "renders"
    assets_dir.mkdir(parents=True, exist_ok=True)
    renders_dir.mkdir(parents=True, exist_ok=True)

    # 1. Cập nhật assets/TIMESTAMPS.txt sạch hoàn toàn bằng tiếng Nhật
    ts_file = assets_dir / "TIMESTAMPS.txt"
    ts_file.write_text(timestamps_txt.strip() + "\n", encoding="utf-8")

    idea = idea or {}
    eff_title = locked_title or str(idea.get("locked_title") or idea.get("draft_title_ja") or ma_id)
    updated_paths: List[str] = [str(ts_file)]

    # 2. Cập nhật seo_publish_pack.txt (nếu có)
    step6_file = proj_dir / "seo_publish_pack.txt"
    if step6_file.exists():
        try:
            old_s6 = step6_file.read_text(encoding="utf-8", errors="ignore")
            new_s6 = _replace_description_in_seo_document(old_s6, description_ja, eff_title)
            step6_file.write_text(new_s6, encoding="utf-8")
            updated_paths.append(str(step6_file))
        except Exception:
            pass

    # 3. Đọc bản master SEO gốc (hoặc tạo mới nếu chưa từng có file SEO)
    master_seo_file = proj_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"
    render_seo_file = renders_dir / f"{ma_id}_SEO.txt"
    seed_text = ""
    for cand in (master_seo_file, render_seo_file, step6_file):
        if cand.exists() and cand.stat().st_size > 50:
            seed_text = cand.read_text(encoding="utf-8", errors="ignore")
            break

    if not seed_text.strip():
        seed_text = (
            "================================================================================\n"
            f"🎬 HỒ SƠ XUẤT BẢN YOUTUBE — MÃ DỰ ÁN: {ma_id}\n"
            "================================================================================\n"
            f"📌 TIÊU ĐỀ CHÍNH THỨC ĐÃ KHÓA (LOCKED_TITLE):\n{eff_title}\n\n"
            f"📖 TÓM TẮT CỐT TRUYỆN:\n{idea.get('summary_vi', '')}\n\n"
            "================================================================================\n"
            "🚀 GÓI SEO YOUTUBE & TIMESTAMPS (PHÂN TÍCH TỪ SUBTITLES.SRT)\n"
            "================================================================================\n"
            f"## 1. FINAL_TITLE — LOCKED\n\n{eff_title}\n\n"
            f"## 2. YOUTUBE_DESCRIPTION_JA\n\n{description_ja.strip()}\n\n"
            "## 3. HASHTAGS & TAGS_CSV\n"
            "#感動する話 #朗読 #スカッとする話 #家族の絆 #高齢者の暮らし #シニアライフ\n"
        )
    else:
        seed_text = _replace_description_in_seo_document(seed_text, description_ja, eff_title)

    master_seo_file.write_text(seed_text, encoding="utf-8")
    render_seo_file.write_text(seed_text, encoding="utf-8")
    updated_paths.extend([str(master_seo_file), str(render_seo_file)])

    extra_final_dirs: List[Path] = []
    if final_proj_dir.resolve() != proj_dir.resolve() and final_proj_dir.exists():
        extra_final_dirs.append(final_proj_dir / "renders")
    loc_file = renders_dir / "video_location.json"
    if loc_file.exists():
        try:
            loc_data = json.loads(loc_file.read_text(encoding="utf-8"))
            loc_final = Path(str(loc_data.get("final_renders_dir") or "").strip())
            if str(loc_final) and loc_final.exists() and loc_final.resolve() != renders_dir.resolve():
                if all(p.resolve() != loc_final.resolve() for p in extra_final_dirs):
                    extra_final_dirs.append(loc_final)
        except Exception:
            pass

    for f_renders in extra_final_dirs:
        try:
            f_renders.mkdir(parents=True, exist_ok=True)
            f_render = f_renders / f"{ma_id}_SEO.txt"
            f_render.write_text(seed_text, encoding="utf-8")
            updated_paths.append(str(f_render))
            f_master = f_renders.parent / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"
            if f_master.exists():
                f_master.write_text(seed_text, encoding="utf-8")
                updated_paths.append(str(f_master))
        except Exception:
            pass

    # 4. Ghi hồ sơ xác thực đã chạy SRT -> ChatGPT SEO
    audit_payload = {
        "ma_id": ma_id,
        "srt_sha256": srt_sha256,
        "source": source_tag,
        "acc_id": acc_id,
        "total_duration_sec": round(total_duration_sec, 2),
        "timestamps_txt": timestamps_txt,
        "description_ja": description_ja,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (assets_dir / "srt_chatgpt_seo_result.json").write_text(
        json.dumps(audit_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "master_seo_path": str(master_seo_file),
        "render_seo_path": str(render_seo_file),
        "timestamps_path": str(ts_file),
        "updated_files": updated_paths,
        "source": source_tag,
    }


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def analyze_project_srt_with_chatgpt_sync(
    proj_dir: Path,
    ma_id: str,
    srt_path: Optional[Path] = None,
    final_proj_dir: Optional[Path] = None,
    locked_title: str = "",
    idea: Optional[Dict[str, Any]] = None,
    preferred_acc_id: Optional[str] = None,
    force: bool = False,
    allow_fallback: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
    should_stop_cb: Optional[Callable[[], bool]] = None,
    timeout_sec: int = 135,
    repair_timeout_sec: int = 90,
) -> Dict[str, Any]:
    """
    Quy trình hoàn chỉnh:
    1. Đọc & nén thông minh file `subtitles.srt` thành bản tóm lược trình tự thời gian kèm `[MM:SS]`/`[HH:MM:SS]`.
    2. Đọc Mô tả & Tiêu đề SEO hiện có của dự án.
    3. Chuyển sang ChatGPT Web phân tích nội dung SRT -> viết/bổ sung Mô tả SEO tiếng Nhật & Timestamps chuẩn xác.
    4. Cập nhật trực tiếp vào `00_TIEU_DE_VA_SEO_YOUTUBE.txt`, `renders/{ma_id}_SEO.txt` và `assets/TIMESTAMPS.txt`.
    """
    proj_dir = Path(proj_dir)
    final_proj_dir = Path(final_proj_dir) if final_proj_dir else proj_dir
    assets_dir = proj_dir / "assets"
    target_srt = Path(srt_path) if srt_path else (assets_dir / "subtitles.srt")
    if not target_srt.exists() and (final_proj_dir / "assets" / "subtitles.srt").exists():
        target_srt = final_proj_dir / "assets" / "subtitles.srt"
    if not target_srt.exists() or target_srt.stat().st_size < 30:
        raise FileNotFoundError(f"[{ma_id}] Chưa có file subtitles.srt tại {target_srt}")

    srt_sha = _file_sha256(target_srt)
    record_file = assets_dir / "srt_chatgpt_seo_result.json"
    master_seo_file = proj_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"
    render_seo_file = proj_dir / "renders" / f"{ma_id}_SEO.txt"

    # Kiểm tra nếu file subtitles.srt hiện tại đã từng được ChatGPT phân tích và bổ sung vào file SEO
    if not force and record_file.exists():
        try:
            prev = json.loads(record_file.read_text(encoding="utf-8"))
            if (
                prev.get("srt_sha256") == srt_sha
                and prev.get("source") == "chatgpt_web"
                and prev.get("timestamps_txt")
                and master_seo_file.exists()
                and "▼目次" in master_seo_file.read_text(encoding="utf-8", errors="ignore")
            ):
                if render_seo_file.exists() and "▼目次" not in render_seo_file.read_text(encoding="utf-8", errors="ignore"):
                    render_seo_file.write_text(master_seo_file.read_text(encoding="utf-8"), encoding="utf-8")
                return {
                    "success": True,
                    "reused": True,
                    "ma_id": ma_id,
                    "source": "chatgpt_web",
                    "timestamps_txt": prev["timestamps_txt"],
                    "description_ja": prev.get("description_ja", ""),
                    "master_seo_path": str(master_seo_file),
                    "render_seo_path": str(render_seo_file),
                }
        except Exception:
            pass

    if progress_cb:
        progress_cb(f"[{ma_id}] Đang đọc & phân tích cấu trúc thời gian subtitles.srt...")

    digest_info = build_srt_chronological_digest(target_srt, max_chars=18000)
    if not digest_info.get("digest_text"):
        raise RuntimeError(f"[{ma_id}] File subtitles.srt rỗng hoặc không đọc được mốc phụ đề.")

    # Đọc thông tin SEO hiện có
    existing_seo_raw = ""
    for cand in (master_seo_file, render_seo_file, proj_dir / "seo_publish_pack.txt"):
        if cand.exists() and cand.stat().st_size > 50:
            existing_seo_raw = cand.read_text(encoding="utf-8", errors="ignore")
            break
    extracted_seo = extract_existing_seo_sections(existing_seo_raw)
    eff_title = (
        locked_title
        or extracted_seo.get("locked_title")
        or str((idea or {}).get("locked_title") or (idea or {}).get("draft_title_ja") or ma_id)
    )
    existing_desc_ja = extracted_seo.get("description_ja") or ""

    prompt_text = build_srt_seo_analysis_prompt(
        ma_id=ma_id,
        locked_title=eff_title,
        digest_info=digest_info,
        existing_desc_ja=existing_desc_ja,
    )

    # Kiểm tra các tài khoản ChatGPT Web sẵn có (ưu tiên tài khoản đang đăng nhập & không bị limit)
    parsed_result: Optional[Dict[str, Any]] = None
    used_acc_id = ""
    last_err: Optional[Exception] = None

    with _SRT_CHATGPT_SEMAPHORE:
        if should_stop_cb and should_stop_cb():
            raise InterruptedError("Đã dừng tiến trình theo yêu cầu.")

        status_map = check_all_web_accounts_status(force_refresh=False).get("accounts", {})
        logged_accs = [aid for aid in tuple(ACCOUNTS_CONFIG.keys()) if status_map.get(aid, {}).get("logged_in")]
        saved_accs = [
            aid
            for aid, cfg in ACCOUNTS_CONFIG.items()
            if _profile_has_saved_chatgpt_login(cfg.get("profile_dir", ""))
        ]
        # Nếu hoàn toàn chưa có tài khoản ChatGPT nào đăng nhập hoặc lưu phiên, không bật Chrome chắn luồng render tự động
        if not logged_accs and not saved_accs:
            if allow_fallback:
                last_err = RuntimeError("Chưa có tài khoản ChatGPT Web nào đăng nhập/lưu phiên trên máy.")
            else:
                raise RuntimeError(
                    f"[{ma_id}] Chưa có tài khoản ChatGPT Web nào đăng nhập! "
                    f"Hãy bấm mở Acc #1 / #2 / #3 để đăng nhập ChatGPT trước."
                )
        else:
            excl_accs: set = set()
            # Gộp cả nick đang mở (logged_accs) và nick đã lưu phiên trên đĩa (saved_accs) để xoay vòng đều Acc #1..#5
            candidate_pool = list(logged_accs)
            for sa in saved_accs:
                if sa not in candidate_pool:
                    candidate_pool.append(sa)
            max_cap = 2 if allow_fallback else len(ACCOUNTS_CONFIG)
            max_acc_tries = max(1, min(max_cap, len(candidate_pool)))

            for acc_try in range(max_acc_tries):
                if should_stop_cb and should_stop_cb():
                    raise InterruptedError("Đã dừng tiến trình theo yêu cầu.")

                sess: Optional[ChatGPTWebSession] = None
                locked_acc_slot: Optional[str] = None
                try:
                    use_pref = preferred_acc_id if (acc_try == 0 and preferred_acc_id and preferred_acc_id not in excl_accs) else None
                    # Kiểm tra nếu tất cả tài khoản đều đang bị cooldown -> không treo vô ích khi allow_fallback=True
                    avail_non_cd = [
                        aid for aid in candidate_pool
                        if aid not in excl_accs and not is_account_in_cooldown(aid)[0]
                    ]
                    if not avail_non_cd:
                        if allow_fallback:
                            break
                        avail_non_cd = [aid for aid in candidate_pool if aid not in excl_accs]
                    if not avail_non_cd:
                        break

                    # Chiếm quyền độc quyền 1 nick rảnh (chỉ 1 job SRT/nick tại 1 thời điểm -> tránh dồn 3 tab vào Acc #1)
                    wait_slot = 45.0 if allow_fallback else 120.0
                    locked_acc_slot = _acquire_srt_account_slot(
                        candidate_pool=candidate_pool,
                        preferred_acc_id=use_pref,
                        excl_accs=excl_accs,
                        wait_timeout_sec=wait_slot,
                        should_stop_cb=should_stop_cb,
                        logged_accs_priority=logged_accs,
                    )
                    if not locked_acc_slot:
                        last_err = RuntimeError("Các tài khoản ChatGPT đang bận xử lý luồng SRT khác.")
                        if allow_fallback:
                            break
                        raise last_err

                    sess = ChatGPTWebSession(
                        project_id=f"{ma_id}_SRT_SEO",
                        acc_id=locked_acc_slot,
                        exclude_accs=excl_accs,
                    )
                    used_acc_id = sess.acc_id
                    acc_lbl = sess.cfg.get("label", sess.acc_id)
                    if progress_cb:
                        progress_cb(f"[{ma_id}] 💬 Mở ChatGPT ({acc_lbl}) phân tích SRT ({digest_info['total_duration_str']}) & tạo Mô tả + Timestamps...")

                    log_info(
                        f"[{ma_id}] 💬 Bắt đầu chuyển subtitles.srt ({digest_info['entries_count']} câu, {digest_info['total_duration_str']}) sang ChatGPT ({acc_lbl}) phân tích Mô tả & Timestamps...",
                        category="SEO",
                        project_id=ma_id,
                    )

                    # Tắt lock_thinking_medium=False để không ép Thinking Medium cho prompt phân tích SRT (nhanh gấp 3-5x, tránh treo 10p)
                    if not sess.open_session_tab(force_new_chat=True, lock_thinking_medium=False):
                        raise RuntimeError(f"Không mở được tab ChatGPT trên {acc_lbl} (Cổng {sess.port})")

                    resp_text = sess.send_prompt_and_wait(
                        prompt_text,
                        step_label="SRT_TO_SEO_TIMESTAMPS",
                        timeout_sec=max(45, int(timeout_sec)),
                        progress_cb=(lambda st, ch: progress_cb(f"[{ma_id}] ChatGPT ({acc_lbl}) đang phân tích SRT ({ch:,} ký tự)...")) if progress_cb else None,
                        should_stop_cb=should_stop_cb,
                        lock_thinking_medium=False,
                    )

                    parsed = parse_and_validate_srt_seo_response(
                        resp_text,
                        total_duration_sec=digest_info["total_duration_sec"],
                        existing_desc_ja=existing_desc_ja,
                    )

                    # Nếu lượt đầu ChatGPT trả lời thiếu thẻ/thiếu mốc -> nhắc 1 lượt ngắn sửa đúng format
                    if not parsed.get("valid"):
                        repair_prompt = (
                            f"Hãy trả về LẠI đúng 2 thẻ XML sau bằng tiếng Nhật (bắt buộc 7–10 mốc thời gian từ `00:00` đến dưới `{digest_info['total_duration_str']}` "
                            f"và tích hợp sẵn mục `▼目次（チャプター・タイムスタンプ）` ngay trong mô tả):\n"
                            f"<UPDATED_YOUTUBE_DESCRIPTION_JA>...</UPDATED_YOUTUBE_DESCRIPTION_JA>\n"
                            f"<YOUTUBE_TIMESTAMPS_JA>...</YOUTUBE_TIMESTAMPS_JA>"
                        )
                        resp_retry = sess.send_prompt_and_wait(
                            repair_prompt,
                            step_label="SRT_TO_SEO_FORMAT_FIX",
                            timeout_sec=max(30, int(repair_timeout_sec)),
                            should_stop_cb=should_stop_cb,
                            lock_thinking_medium=False,
                        )
                        parsed = parse_and_validate_srt_seo_response(
                            resp_retry,
                            total_duration_sec=digest_info["total_duration_sec"],
                            existing_desc_ja=existing_desc_ja,
                        )

                    if parsed.get("valid"):
                        parsed_result = parsed
                        break
                    raise RuntimeError("ChatGPT phản hồi chưa đủ mốc Timestamps hợp lệ.")

                except AccountRateLimitError as rl_err:
                    last_err = rl_err
                    if used_acc_id:
                        excl_accs.add(used_acc_id)
                    log_warn(
                        f"[{ma_id}] Tài khoản {used_acc_id} bị Limit khi phân tích SRT -> Tự động đổi sang nick khác!",
                        category="SEO",
                        project_id=ma_id,
                    )
                except InterruptedError:
                    raise
                except Exception as err:
                    last_err = err
                    if used_acc_id:
                        excl_accs.add(used_acc_id)
                        if "Không mở được tab" in str(err) or "Quá thời gian chờ" in str(err):
                            mark_account_rate_limited(used_acc_id, reason=str(err)[:120], cooldown_sec=300)
                    log_warn(
                        f"[{ma_id}] Lỗi phân tích SRT trên {used_acc_id or 'ChatGPT'}: {err}",
                        category="SEO",
                        project_id=ma_id,
                    )
                finally:
                    _release_srt_account_slot(locked_acc_slot or used_acc_id)
                    if sess is not None:
                        try:
                            sess.close_session_tab(keep_open=False)
                        except Exception:
                            pass

    if parsed_result and parsed_result.get("valid"):
        save_res = update_seo_files_with_chatgpt_srt_result(
            proj_dir=proj_dir,
            ma_id=ma_id,
            description_ja=parsed_result["description_ja"],
            timestamps_txt=parsed_result["timestamps_txt"],
            final_proj_dir=final_proj_dir,
            locked_title=eff_title,
            idea=idea,
            srt_sha256=srt_sha,
            source_tag="chatgpt_web",
            acc_id=used_acc_id,
            total_duration_sec=digest_info["total_duration_sec"],
        )
        log_info(
            f"✅ [{ma_id}] ChatGPT đã phân tích xong SRT & cập nhật Mô tả + {parsed_result['chapters_count']} Timestamps tiếng Nhật vào File SEO!",
            category="SEO",
            project_id=ma_id,
        )
        return {
            "success": True,
            "reused": False,
            "ma_id": ma_id,
            "chapters_count": parsed_result["chapters_count"],
            "timestamps_txt": parsed_result["timestamps_txt"],
            "description_ja": parsed_result["description_ja"],
            **save_res,
        }

    if not allow_fallback:
        raise RuntimeError(f"[{ma_id}] Không thể phân tích SRT qua ChatGPT: {last_err or 'Các tài khoản ChatGPT chưa sẵn sàng'}")

    # Fallback an toàn bằng tiếng Nhật từ chính subtitles.srt nếu tất cả tài khoản ChatGPT đều chưa đăng nhập/lỗi
    fb = build_fallback_srt_timestamps_and_description(
        srt_path=target_srt,
        existing_desc_ja=existing_desc_ja,
        locked_title=eff_title,
        summary_vi=str((idea or {}).get("summary_vi") or ""),
    )
    save_res = update_seo_files_with_chatgpt_srt_result(
        proj_dir=proj_dir,
        ma_id=ma_id,
        description_ja=fb["description_ja"],
        timestamps_txt=fb["timestamps_txt"],
        final_proj_dir=final_proj_dir,
        locked_title=eff_title,
        idea=idea,
        srt_sha256=srt_sha,
        source_tag="srt_fallback_ja",
        acc_id="",
        total_duration_sec=fb["total_duration_sec"],
    )
    log_warn(
        f"⚠️ [{ma_id}] ChatGPT tạm thời không khả dụng ({last_err}) -> Đã tạo tự động {fb['chapters_count']} Timestamps tiếng Nhật từ SRT vào File SEO.",
        category="SEO",
        project_id=ma_id,
    )
    return {
        "success": True,
        "reused": False,
        "fallback_used": True,
        "ma_id": ma_id,
        "chapters_count": fb["chapters_count"],
        "timestamps_txt": fb["timestamps_txt"],
        "description_ja": fb["description_ja"],
        **save_res,
    }
