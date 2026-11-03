import os
import re
import sys
import json
import time
import shutil
import argparse
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


def sync_root_to_app():
    app_dir = ROOT_DIR / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("backend", "frontend", "adas_skills"):
        src = ROOT_DIR / sub
        dst = app_dir / sub
        if src.exists():
            dst.mkdir(parents=True, exist_ok=True)
            for p in src.rglob("*"):
                if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc"):
                    rel = p.relative_to(src)
                    target = dst / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, target)

    for fname in (
        "main.py",
        "install_setup.py",
        "requirements.txt",
        "version.json",
        "QUY_TRINH_HOAT_DONG.md",
        "TIEN_DO_CODE.md",
        "HUONG_DAN_CAI_DAT_KHACH_HANG.txt",
    ):
        s = ROOT_DIR / fname
        if s.exists():
            shutil.copy2(s, app_dir / fname)


def bump_version_str(ver_str: str) -> str:
    nums = [int(x) for x in re.findall(r"\d+", str(ver_str or "V1.0.0"))]
    while len(nums) < 3:
        nums.append(0)
    nums[2] += 1
    return f"V{nums[0]}.{nums[1]}.{nums[2]}"


def main():
    parser = argparse.ArgumentParser(description="Đẩy bản cập nhật mới lên GitHub cho các máy khách (OTA Update)")
    parser.add_argument("--version", type=str, default="", help="Phiên bản mới (VD: V1.0.1). Bỏ trống sẽ tự động +1 patch.")
    parser.add_argument("--changelog", type=str, default="Cập nhật tính năng và tối ưu hiệu suất hệ thống.", help="Nội dung thay đổi hiển thị trên máy khách.")
    parser.add_argument("--keep-version", action="store_true", help="Giữ nguyên số phiên bản hiện tại trong version.json")
    args = parser.parse_args()

    ver_file = ROOT_DIR / "version.json"
    if ver_file.exists():
        info = json.loads(ver_file.read_text(encoding="utf-8"))
    else:
        info = {
            "version": "V1.0.0",
            "build_number": 100,
            "repo": "phamngocthu661-lang/drama-nhat-studio",
            "branch": "main",
        }

    if not args.keep_version:
        new_ver = args.version.strip() if args.version.strip() else bump_version_str(info.get("version", "V1.0.0"))
        new_build = int(info.get("build_number", 100)) + 1
        info["version"] = new_ver
        info["build_number"] = new_build
    elif args.version.strip():
        info["version"] = args.version.strip()

    info["released_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if args.changelog:
        info["changelog"] = args.changelog.strip()

    ver_file.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Đồng bộ số phiên bản hiển thị mặc định trong frontend/index.html
    ver_label = info["version"]
    idx_file = ROOT_DIR / "frontend" / "index.html"
    if idx_file.exists():
        html_txt = idx_file.read_text(encoding="utf-8")
        html_txt = re.sub(
            r'(<span[^>]*id="app-version-badge"[^>]*>)\s*V[\d\.]+\s*(</span>)',
            rf"\g<1>{ver_label}\g<2>",
            html_txt,
        )
        html_txt = re.sub(
            r'(<span[^>]*id="text-check-update-header"[^>]*>)\s*Cập nhật:\s*V[\d\.]+\s*(</span>)',
            rf"\g<1>Cập nhật: {ver_label}\g<2>",
            html_txt,
        )
        html_txt = re.sub(
            r'(<span[^>]*id="text-check-update-nav"[^>]*>)\s*🔄\s*CẬP NHẬT\s*\(V[\d\.]+\)\s*(</span>)',
            rf"\g<1>🔄 CẬP NHẬT ({ver_label})\g<2>",
            html_txt,
        )
        idx_file.write_text(html_txt, encoding="utf-8")

    sync_root_to_app()

    print(f"📦 Đang đóng gói và đẩy phiên bản [{ver_label}] (Build #{info['build_number']}) lên GitHub...")

    subprocess.run(["git", "add", "-A"], cwd=str(ROOT_DIR), check=True)
    status_res = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT_DIR), capture_output=True, text=True)
    if status_res.stdout.strip():
        subprocess.run(
            ["git", "commit", "-m", f"Release {ver_label}: {info.get('changelog', '')[:120]}"],
            cwd=str(ROOT_DIR),
            check=True,
        )
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=str(ROOT_DIR), check=True)
    print(f"🎉 ĐÃ CẬP NHẬT LÊN GITHUB THÀNH CÔNG: {ver_label} (Build #{info['build_number']})!")
    print("👉 Hiện tại tất cả các máy khách đang mở ứng dụng sẽ thấy nút '🚀 Cập nhật mới' để bấm tải về.")


if __name__ == "__main__":
    main()
