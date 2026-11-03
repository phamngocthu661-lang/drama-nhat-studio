import os
import re
import sys
import json
import time
import hmac
import uuid
import hashlib
import secrets
import datetime
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Khóa bí mật HMAC-SHA256 dùng chung giữa App và Tool Cấp Key Admin (Tuyệt đối bảo mật)
_MASTER_SECRET = b"DRAMA_NHAT_STUDIO_2026_MASTER_SECRET_KEY_#9988776655_ENISHI_PRO"

PLAN_LABELS = {
    "D07": "Dùng Thử 7 Ngày",
    "M01": "Gói 1 Tháng (30 Ngày)",
    "M03": "Gói 3 Tháng (90 Ngày)",
    "M06": "Gói 6 Tháng (180 Ngày)",
    "Y01": "Gói 1 Năm (365 Ngày)",
    "Y02": "Gói 2 Năm (730 Ngày)",
    "Y99": "Gói Vĩnh Viễn (Trọn Đời)",
    "VIP": "Gói Tùy Chỉnh Thời Hạn",
}


def get_machine_hwid() -> str:
    """
    Lấy Mã Máy (Hardware ID) cố định của máy tính hiện tại theo định dạng: DNS-XXXX-XXXX.
    Kết hợp MachineGuid trong Registry của Windows và thông tin phần cứng để không bị đổi.
    """
    raw_id = ""
    if os.name == "nt":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            )
            val, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            if val:
                raw_id = str(val).strip()
        except Exception:
            pass

    if not raw_id:
        try:
            raw_id = f"{uuid.getnode()}-{os.environ.get('COMPUTERNAME', 'PC')}"
        except Exception:
            raw_id = "DEFAULT-DRAMA-PC"

    digest = hashlib.sha256((raw_id + "|DRAMA_NHAT_HWID_SALT").encode("utf-8")).hexdigest().upper()
    part1 = digest[:4]
    part2 = digest[4:8]
    return f"DNS-{part1}-{part2}"


def normalize_hwid_tag(hwid_input: Optional[str]) -> str:
    """
    Chuẩn hóa Mã Máy về 8 ký tự (VD: 'DNS-8F4A-92C1' -> '8F4A92C1').
    Nếu để trống hoặc 'ANY' -> trả về 'ANYPC000' (dùng cho mọi máy).
    """
    if not hwid_input:
        return "ANYPC000"
    cleaned = re.sub(r"[^0-9A-Za-z]", "", hwid_input.upper())
    if cleaned in ("", "ANY", "ALL", "ANYPC", "ANYPC000", "MULTIPC"):
        return "ANYPC000"
    if cleaned.startswith("DNS") and len(cleaned) >= 11:
        cleaned = cleaned[3:]
    if len(cleaned) >= 8:
        return cleaned[:8]
    return cleaned.ljust(8, "0")


def _compute_signature(expiry_ymd: str, plan_code: str, hwid_tag: str, nonce: str) -> str:
    payload = f"DRAMA|{expiry_ymd}|{plan_code}|{hwid_tag}|{nonce}".encode("utf-8")
    sig = hmac.new(_MASTER_SECRET, payload, hashlib.sha256).hexdigest().upper()
    return sig[:12]


def _compute_state_mac(key_str: str, last_seen_ts: int) -> str:
    payload = f"STATE|{key_str}|{last_seen_ts}".encode("utf-8")
    return hmac.new(_MASTER_SECRET, payload, hashlib.sha256).hexdigest().upper()[:16]


def generate_license_key(
    plan_code: str = "M01",
    expiry_date_str: Optional[str] = None,
    days: Optional[int] = None,
    hwid_input: Optional[str] = None,
    nonce: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tạo mã License Key bản quyền có chữ ký số HMAC-SHA256.
    Định dạng Key: DRAMA-YYYYMMDD-PLAN-HWIDTAG8-NONCE4-SIG12
    """
    plan_code = (plan_code or "M01").upper().strip()[:3]
    if plan_code not in PLAN_LABELS:
        plan_code = "VIP"

    now_dt = datetime.date.today()
    if expiry_date_str:
        clean_ymd = re.sub(r"[^0-9]", "", expiry_date_str)
        if len(clean_ymd) == 8:
            expiry_ymd = clean_ymd
            exp_dt = datetime.date(int(clean_ymd[:4]), int(clean_ymd[4:6]), int(clean_ymd[6:8]))
        else:
            raise ValueError("Ngày hết hạn phải có định dạng YYYY-MM-DD hoặc YYYYMMDD.")
    else:
        plan_days_map = {
            "D07": 7,
            "M01": 30,
            "M03": 90,
            "M06": 180,
            "Y01": 365,
            "Y02": 730,
            "Y99": 36500,
        }
        add_days = days if (days is not None and days > 0) else plan_days_map.get(plan_code, 30)
        exp_dt = now_dt + datetime.timedelta(days=add_days)
        expiry_ymd = exp_dt.strftime("%Y%m%d")

    hwid_tag = normalize_hwid_tag(hwid_input)
    if not nonce:
        nonce = secrets.token_hex(2).upper()
    else:
        nonce = re.sub(r"[^0-9A-F]", "", nonce.upper())[:4].ljust(4, "A")

    sig = _compute_signature(expiry_ymd, plan_code, hwid_tag, nonce)
    full_key = f"DRAMA-{expiry_ymd}-{plan_code}-{hwid_tag}-{nonce}-{sig}"

    return {
        "key": full_key,
        "plan_code": plan_code,
        "plan_label": PLAN_LABELS.get(plan_code, "Gói Tùy Chỉnh"),
        "expiry_ymd": expiry_ymd,
        "expiry_formatted": exp_dt.strftime("%d/%m/%Y"),
        "hwid_tag": hwid_tag,
        "hwid_display": "Mọi Máy (Multi-PC)" if hwid_tag == "ANYPC000" else f"DNS-{hwid_tag[:4]}-{hwid_tag[4:8]}",
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def get_network_timestamp(timeout: float = 2.5) -> Optional[int]:
    """
    Lấy thời gian thực từ Header Date của Google / Cloudflare để chống gian lận chỉnh lùi ngày giờ Windows.
    Nếu không có mạng, trả về None (sẽ đối chiếu với mốc thời gian monotonic lưu trên máy).
    """
    import urllib.request
    import email.utils

    urls = [
        "https://www.google.com",
        "https://1.1.1.1",
        "https://rentry.co"
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                date_hdr = resp.headers.get("Date")
                if date_hdr:
                    dt = email.utils.parsedate_to_datetime(date_hdr)
                    return int(dt.timestamp())
        except Exception:
            continue
    return None


class LicenseManager:
    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir:
            self.root_dir = Path(root_dir)
        else:
            p = Path(__file__).resolve().parent.parent
            self.root_dir = p.parent if p.name == "app" else p

        self.license_file = self.root_dir / "license.json"
        local_appdata = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        self.backup_dir = Path(local_appdata) / "DramaNhatStudio"
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self.backup_file = self.backup_dir / "license_state.json"
        self.hwid = get_machine_hwid()
        self.hwid_tag = normalize_hwid_tag(self.hwid)

    def _load_saved_data(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        app_lic = self.root_dir / "app" / "license.json"
        for fpath in [self.license_file, self.backup_file, app_lic]:
            if fpath.exists():
                try:
                    with open(fpath, "r", encoding="utf-8-sig") as f:
                        d = json.load(f)
                        if isinstance(d, dict) and d.get("license_key"):
                            # Giữ mốc last_seen_ts lớn nhất giữa các file để chống xóa file lùi giờ
                            prev_ts = int(data.get("last_seen_ts", 0) or 0)
                            cur_ts = int(d.get("last_seen_ts", 0) or 0)
                            if not data or cur_ts >= prev_ts:
                                data = dict(d)
                                data["last_seen_ts"] = max(prev_ts, cur_ts)
                except Exception:
                    pass
        return data

    def _save_data(self, data: Dict[str, Any]):
        targets = [self.license_file, self.backup_file]
        if (self.root_dir / "app").exists():
            targets.append(self.root_dir / "app" / "license.json")
        for fpath in targets:
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

    def verify_key_string(self, key_str: str, check_online_time: bool = True) -> Dict[str, Any]:
        """Kiểm tra tính hợp lệ, chữ ký số, mã máy HWID và thời hạn của một License Key."""
        if not key_str or not key_str.strip():
            return {
                "valid": False,
                "status": "missing",
                "hwid": self.hwid,
                "message": "Chưa kích hoạt Key bản quyền. Vui lòng nhập Key để mở khóa ứng dụng."
            }

        clean_key = key_str.strip().upper()
        pattern = r"^DRAMA-(\d{8})-([A-Z0-9]{3})-([A-Z0-9]{8})-([A-Z0-9]{4})-([A-Z0-9]{12})$"
        m = re.match(pattern, clean_key)
        if not m:
            return {
                "valid": False,
                "status": "invalid_format",
                "hwid": self.hwid,
                "message": "❌ Định dạng Key không hợp lệ! Vui lòng kiểm tra lại mã Key (VD: DRAMA-YYYYMMDD-...)."
            }

        expiry_ymd, plan_code, key_hwid_tag, nonce, sig = m.groups()
        expected_sig = _compute_signature(expiry_ymd, plan_code, key_hwid_tag, nonce)
        if not hmac.compare_digest(sig, expected_sig):
            return {
                "valid": False,
                "status": "invalid_signature",
                "hwid": self.hwid,
                "message": "❌ Mã Key không hợp lệ hoặc đã bị chỉnh sửa sai chữ ký bảo mật!"
            }

        # Kiểm tra khóa Mã Máy (HWID)
        if key_hwid_tag != "ANYPC000" and key_hwid_tag != self.hwid_tag:
            bound_display = f"DNS-{key_hwid_tag[:4]}-{key_hwid_tag[4:8]}"
            return {
                "valid": False,
                "status": "hwid_mismatch",
                "hwid": self.hwid,
                " message": f"❌ Key này đã được khóa riêng cho máy [{bound_display}], không thể dùng trên máy hiện tại [{self.hwid}]!",
                "message": f"❌ Key này được cấp riêng cho Mã Máy [{bound_display}], không khớp với Mã Máy hiện tại [{self.hwid}]!"
            }

        # Phân tích ngày hết hạn (23:59:59 của ngày expiry_ymd)
        try:
            exp_year = int(expiry_ymd[:4])
            exp_month = int(expiry_ymd[4:6])
            exp_day = int(expiry_ymd[6:8])
            exp_date = datetime.date(exp_year, exp_month, exp_day)
            exp_dt_end = datetime.datetime(exp_year, exp_month, exp_day, 23, 59, 59)
            exp_ts = int(exp_dt_end.timestamp())
        except Exception:
            return {
                "valid": False,
                "status": "invalid_date",
                "hwid": self.hwid,
                "message": "❌ Ngày hết hạn trong Key không hợp lệ!"
            }

        # Kiểm tra thời gian thực tế & chống chỉnh lùi giờ hệ thống
        sys_ts = int(time.time())
        net_ts = get_network_timestamp(timeout=2.0) if check_online_time else None
        effective_ts = net_ts if net_ts is not None else sys_ts

        saved = self._load_saved_data()
        last_seen_ts = int(saved.get("last_seen_ts", 0) or 0)

        # Nếu không có mạng mà giờ máy tính bị vặn lùi quá 6 tiếng so với lần chạy trước
        if net_ts is None and last_seen_ts > 0 and sys_ts < (last_seen_ts - 21600):
            return {
                "valid": False,
                "status": "clock_tampered",
                "hwid": self.hwid,
                "expiry_formatted": exp_date.strftime("%d/%m/%Y"),
                "message": "⚠️ Phát hiện đồng hồ máy tính bị chỉnh lùi ngày giờ! Vui lòng chỉnh lại đúng ngày giờ thực tế hoặc kết nối Internet."
            }

        now_dt = datetime.datetime.fromtimestamp(effective_ts)
        today_date = now_dt.date()

        if effective_ts > exp_ts or today_date > exp_date:
            return {
                "valid": False,
                "status": "expired",
                "hwid": self.hwid,
                "license_key": clean_key,
                "plan_code": plan_code,
                "plan_label": PLAN_LABELS.get(plan_code, "Gói Bản Quyền"),
                "expiry_ymd": expiry_ymd,
                "expiry_formatted": exp_date.strftime("%d/%m/%Y"),
                "days_remaining": 0,
                "message": f"⏰ Key bản quyền của bạn đã HẾT HẠN vào ngày {exp_date.strftime('%d/%m/%Y')}. Vui lòng liên hệ Admin để gia hạn Key mới!"
            }

        days_left = (exp_date - today_date).days + 1
        mode_label = "Đa Máy (Multi-PC)" if key_hwid_tag == "ANYPC000" else f"Khóa Máy ({self.hwid})"
        plan_label = PLAN_LABELS.get(plan_code, "Gói Bản Quyền")

        return {
            "valid": True,
            "status": "active",
            "hwid": self.hwid,
            "license_key": clean_key,
            "plan_code": plan_code,
            "plan_label": plan_label,
            "mode_label": mode_label,
            "expiry_ymd": expiry_ymd,
            "expiry_formatted": exp_date.strftime("%d/%m/%Y"),
            "days_remaining": days_left,
            "effective_ts": max(effective_ts, last_seen_ts),
            "message": f"✅ Bản quyền hợp lệ ({plan_label}) — Hạn dùng đến hết {exp_date.strftime('%d/%m/%Y')} (Còn {days_left} ngày)."
        }

    def activate_license(self, key_str: str) -> Dict[str, Any]:
        """Kích hoạt và lưu Key bản quyền vào máy."""
        res = self.verify_key_string(key_str, check_online_time=True)
        if not res.get("valid"):
            return res

        now_ts = int(res.get("effective_ts") or time.time())
        clean_key = res["license_key"]
        save_payload = {
            "license_key": clean_key,
            "hwid": self.hwid,
            "plan_code": res["plan_code"],
            "plan_label": res["plan_label"],
            "expiry_ymd": res["expiry_ymd"],
            "expiry_formatted": res["expiry_formatted"],
            "activated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_seen_ts": now_ts,
            "state_mac": _compute_state_mac(clean_key, now_ts)
        }
        self._save_data(save_payload)
        return res

    def get_license_status(self, check_online_time: bool = False) -> Dict[str, Any]:
        """Kiểm tra trạng thái bản quyền hiện tại của ứng dụng."""
        saved = self._load_saved_data()
        key_str = saved.get("license_key", "")
        if not key_str:
            return {
                "valid": False,
                "status": "missing",
                "hwid": self.hwid,
                "plan_label": "Chưa kích hoạt",
                "expiry_formatted": "--/--/----",
                "days_remaining": 0,
                "message": "Vui lòng nhập Key bản quyền để sử dụng Drama Nhật Studio."
            }

        res = self.verify_key_string(key_str, check_online_time=check_online_time)
        if res.get("valid"):
            now_ts = int(res.get("effective_ts") or time.time())
            prev_ts = int(saved.get("last_seen_ts", 0) or 0)
            if now_ts > prev_ts:
                saved["last_seen_ts"] = now_ts
                saved["state_mac"] = _compute_state_mac(key_str, now_ts)
                self._save_data(saved)
        return res
