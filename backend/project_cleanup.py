"""
Đánh dấu dự án đã sản xuất xong Video & dọn dẹp file thừa để tiết kiệm bộ nhớ.

- VIDEO_DONE.json (nằm trong Folder Project): bằng chứng VĨNH VIỄN rằng dự án đã render xong MP4 và đã qua kiểm định.
  Dù người dùng chuyển hoặc xóa file MP4, ứng dụng vẫn nhận biết dự án đã sản xuất xong và KHÔNG render lại.
- cleanup_after_script(): sau khi viết xong kịch bản (đã ghép vào script_clean.txt) -> xóa các bản sao trùng.
- cleanup_after_render(): sau khi render MP4 xong -> xóa Voice WAV tạm, file render dở, và các bản sao trùng
  giữa Folder Project và Nơi Chứa Video Cuối.
"""

import json
import shutil
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VIDEO_DONE_MARKER = "VIDEO_DONE.json"


def _pure_char_count(text: str) -> int:
    norm = unicodedata.normalize("NFC", text or "")
    return sum(1 for ch in norm if unicodedata.category(ch)[0] in {"L", "N"})


def _file_pure_chars(p: Path) -> int:
    try:
        return _pure_char_count(p.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return 0


def _safe_unlink(p: Path, removed: List[str]) -> int:
    try:
        if p.exists() and p.is_file():
            sz = p.stat().st_size
            p.unlink()
            removed.append(str(p))
            return sz
    except Exception:
        pass
    return 0


def _safe_rmtree(p: Path, removed: List[str]) -> int:
    try:
        if p.exists() and p.is_dir():
            sz = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            shutil.rmtree(p, ignore_errors=True)
            removed.append(str(p))
            return sz
    except Exception:
        pass
    return 0


def _same_dir(a: Optional[Path], b: Optional[Path]) -> bool:
    if a is None or b is None:
        return True
    try:
        return a.resolve() == b.resolve()
    except Exception:
        return str(a) == str(b)


# ----------------------------------------------------------------------------
# DẤU "ĐÃ SẢN XUẤT XONG VIDEO"
# ----------------------------------------------------------------------------
def read_video_done_marker(proj_dir: Path) -> Optional[Dict[str, Any]]:
    f = Path(proj_dir) / VIDEO_DONE_MARKER
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"done": True}
    except Exception:
        # File hỏng vẫn coi là đã xong (không bao giờ render lại chỉ vì JSON lỗi)
        return {"done": True}


def write_video_done_marker(proj_dir: Path, ma_id: str, mp4_path: Optional[Path] = None, **extra: Any) -> None:
    proj_dir = Path(proj_dir)
    if not proj_dir.exists():
        return
    data = read_video_done_marker(proj_dir) or {}
    data.update({
        "ma_id": ma_id,
        "done": True,
        "completed_at": data.get("completed_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    if mp4_path is not None:
        data["video_mp4_path"] = str(mp4_path)
        try:
            data["video_size_bytes"] = Path(mp4_path).stat().st_size
        except Exception:
            pass
    for k, v in extra.items():
        if v is not None:
            data[k] = v
    try:
        (proj_dir / VIDEO_DONE_MARKER).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def has_legacy_video_done_evidence(proj_dir: Path, ma_id: str) -> bool:
    """Dự án render xong từ trước khi có VIDEO_DONE.json: pipeline chỉ ghi 2 file này SAU KHI MP4 đã qua kiểm định."""
    proj_dir = Path(proj_dir)
    return (proj_dir / f"{ma_id}_seo.md").exists() or (proj_dir / "renders" / "video_location.json").exists()


def clear_video_done_marker(proj_dir: Path, ma_id: str) -> None:
    """Gỡ dấu đã xong (khi người dùng chủ động Viết Lại hoặc Render Lại)."""
    proj_dir = Path(proj_dir)
    removed: List[str] = []
    for p in (
        proj_dir / VIDEO_DONE_MARKER,
        proj_dir / f"{ma_id}_seo.md",
        proj_dir / "renders" / "video_location.json",
    ):
        _safe_unlink(p, removed)


# ----------------------------------------------------------------------------
# DỌN DẸP
# ----------------------------------------------------------------------------
def cleanup_after_script(proj_dir: Path, ma_id: str, min_pure_chars: int) -> Tuple[int, List[str]]:
    """
    Sau khi kịch bản đã ghép xong vào `script_clean.txt` (đủ độ dài):
    xóa part_a/b/c.txt (đã nằm trong script_clean), bản lưu Part ngắn và bản sao renders/{ID}_KICH_BAN.txt.
    Không làm gì nếu script_clean.txt chưa đủ dài hoặc chưa chứa đủ nội dung các Part.
    """
    proj_dir = Path(proj_dir)
    removed: List[str] = []
    sc = proj_dir / "script_clean.txt"
    if not sc.exists():
        return 0, removed
    sc_chars = _file_pure_chars(sc)
    if sc_chars < int(min_pure_chars):
        return 0, removed

    part_files = [proj_dir / f"part_{x}.txt" for x in ("a", "b", "c")]
    parts_total = sum(_file_pure_chars(p) for p in part_files if p.exists())
    freed = 0
    # Chỉ xóa Part khi script_clean.txt đã chứa đủ nội dung của cả 3 Part (cho phép lệch nhỏ do lọc metadata)
    if parts_total == 0 or sc_chars >= int(parts_total * 0.97):
        for p in part_files:
            freed += _safe_unlink(p, removed)
    for p in proj_dir.glob("part_*.short_backup.txt"):
        freed += _safe_unlink(p, removed)

    kb = proj_dir / "renders" / f"{ma_id}_KICH_BAN.txt"
    if kb.exists() and _file_pure_chars(kb) <= sc_chars:
        freed += _safe_unlink(kb, removed)
    return freed, removed


def cleanup_after_render(
    proj_dir: Path,
    ma_id: str,
    min_pure_chars: int,
    final_proj_dir: Optional[Path] = None,
) -> Tuple[int, List[str]]:
    """
    Sau khi Video MP4 đã render xong & qua kiểm định. Giữ lại:
      Folder Project: script_clean.txt, idea_info.json, step2/step3/step5, SEO, Thumbnail, subtitles.srt, TIMESTAMPS.txt, VIDEO_DONE.json
      Nơi Chứa Video Cuối: {ID}_master.mp4, {ID}_SEO.txt, {ID}_THUMBNAIL_*.png (bộ file để đăng YouTube)
    Xóa: Voice WAV (master_voice.wav + từng câu), file render dở / checkpoint, script.txt, các bản sao kịch bản/metadata trùng.
    """
    proj_dir = Path(proj_dir)
    removed: List[str] = []
    freed = 0

    freed_s, rem_s = cleanup_after_script(proj_dir, ma_id, min_pure_chars)
    freed += freed_s
    removed.extend(rem_s)

    assets = proj_dir / "assets"
    freed += _safe_unlink(assets / "master_voice.wav", removed)
    freed += _safe_rmtree(assets / "sentences", removed)
    if assets.exists():
        for wav in assets.glob("*.wav"):
            freed += _safe_unlink(wav, removed)

    has_clean_script = (proj_dir / "script_clean.txt").exists()
    if has_clean_script:
        freed += _safe_unlink(proj_dir / "script.txt", removed)

    render_dirs = [proj_dir / "renders"]
    separate_final = final_proj_dir is not None and not _same_dir(proj_dir, final_proj_dir)
    if separate_final:
        render_dirs.append(Path(final_proj_dir) / "renders")
    for r_dir in render_dirs:
        if not r_dir.exists():
            continue
        for tmp in r_dir.glob("*_rendering_tmp.mp4"):
            freed += _safe_unlink(tmp, removed)
        for cache_dir in r_dir.glob("_*_resume_cache"):
            freed += _safe_rmtree(cache_dir, removed)

    if separate_final:
        fp = Path(final_proj_dir)
        # Các file chỉ là BẢN SAO của Folder Project -> xóa ở Nơi Chứa Video Cuối (Folder Project vẫn giữ bản gốc)
        for fn, src in (
            ("script_clean.txt", proj_dir / "script_clean.txt"),
            ("idea_info.json", proj_dir / "idea_info.json"),
            ("00_TIEU_DE_VA_SEO_YOUTUBE.txt", proj_dir / "00_TIEU_DE_VA_SEO_YOUTUBE.txt"),
        ):
            if src.exists():
                freed += _safe_unlink(fp / fn, removed)
        if has_clean_script:
            freed += _safe_unlink(fp / "renders" / f"{ma_id}_KICH_BAN.txt", removed)
            freed += _safe_unlink(fp / f"{ma_id}_KICH_BAN.txt", removed)
        freed += _safe_rmtree(fp / "assets", removed)
    return freed, removed
