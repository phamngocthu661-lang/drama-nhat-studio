import os
import sys
import math
import json
import time
import shutil
import socket
import random
import threading
import subprocess
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


import re

def extract_youtube_id(url: str) -> Optional[str]:
    """Trích xuất ID video YouTube từ các dạng URL khác nhau."""
    patterns = [
        r'(?:v=|\/|vi=)([0-9A-Za-z_-]{11})',
        r'(?:embed\/|v\/|youtu.be\/)([0-9A-Za-z_-]{11})',
        r'(?:shorts\/)([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def check_internet_connection(timeout: float = 2.5) -> bool:
    """Kiểm tra nhanh kết nối mạng Internet tới YouTube (chỉ mất tối đa 2.5 giây)."""
    for host, port in [("www.youtube.com", 443), ("8.8.8.8", 53), ("1.1.1.1", 53)]:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            continue
    return False


def get_video_duration(file_path: str) -> float:
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


class StockManager:
    MAX_STOCK_USAGES = 1  # Dùng 1 lần duy nhất rồi tự động xóa ngay để giải phóng bộ nhớ ổ cứng

    # Cấu hình Note Online mặc định (Không cần đăng nhập, tự động liên kết mọi máy khi copy tool)
    DEFAULT_CLOUD_NOTE_SLUG = "nhat-drama-stock-9f8a7b6c"
    DEFAULT_CLOUD_NOTE_URL = "https://rentry.co/nhat-drama-stock-9f8a7b6c"
    DEFAULT_CLOUD_NOTE_EDIT_CODE = "nhatdrama2026"
    DEFAULT_CLOUD_KV_APP_KEY = "9t3ws0h4"

    # Cấu hình API Pexels & Pixabay chính thức (Tải trực tiếp CDN 720p siêu tốc, không bao giờ bị chặn Bot)
    DEFAULT_PEXELS_API_KEY = "owg1bn5dQ6B9TXl41eju0bxDJwOIfSWnvpJgWcWDuMjAiL0Tfmelj2az"
    DEFAULT_PIXABAY_API_KEY = "50938472-a59c0eb5ca08b8fdc7132ef7e"

    PEXELS_PIXABAY_QUERIES = [
        "japan nature landscape",
        "aerial forest mountain",
        "peaceful river waterfall",
        "autumn forest drone",
        "ocean coastline cliffs",
        "mountain valley mist",
        "japanese countryside scenery",
        "sunset clouds aerial nature",
        "bamboo forest kyoto",
        "alpine lake mountain",
        "cherry blossom nature",
        "green meadow hills",
        "calm lake reflection",
        "rainy forest nature",
        "misty morning mountains",
        "cinematic nature drone",
        "waterfall tropical forest",
        "snowy mountains aerial",
        "sunset ocean waves",
        "forest stream river",
        "rural village landscape",
        "sunrise mountain clouds",
        "golden hour field nature",
        "pine forest aerial view",
        "emerald lake mountains",
        "coastal road ocean drone",
        "spring flowers meadow",
        "autumn leaves river",
        "foggy forest morning",
        "mountain peak clouds",
        "island beach aerial",
        "canyon river drone",
        "countryside hills sunset",
        "zen garden japan nature",
        "tranquil water reflection",
        "wilderness forest landscape",
        "turquoise ocean aerial",
        "highland valley scenery",
        "starry night sky mountains",
        "dramatic clouds landscape",
        "rice terraces asia drone",
        "fjord mountains water",
        "glacier lake aerial",
        "redwood forest trees",
        "desert dunes sunset",
        "coral reef ocean aerial",
        "winding river forest",
        "mount fuji nature scenery",
    ]

    # Kho nguồn YouTube 4K/1080p Thiên Nhiên & Phong Cảnh dài (1h - 10h) dự phòng + từ khóa tìm kiếm tự động
    DEFAULT_STOCK_CANDIDATES = [
        {"id": "lM02vNMRRB0", "url": "https://www.youtube.com/watch?v=lM02vNMRRB0", "title": "7 HOUR 4K DRONE FILM: Earth from Above Nature Relaxation", "duration": 25207},
        {"id": "b7Cl7S0pLRw", "url": "https://www.youtube.com/watch?v=b7Cl7S0pLRw", "title": "8 HOUR DRONE FILM: Islands From Above 4K Nature Relaxation", "duration": 28831},
        {"id": "UV0mhY2Dxr0", "url": "https://www.youtube.com/watch?v=UV0mhY2Dxr0", "title": "Nature Relaxation Film 4K - Peaceful Aerial Scenery", "duration": 10919},
        {"id": "nDspkEvEqj0", "url": "https://www.youtube.com/watch?v=nDspkEvEqj0", "title": "One Hour Cinematic Drone Film | Relaxing Nature Scenery", "duration": 3615},
    ]

    AUTO_SEARCH_QUERIES = [
        "4K Drone Nature Relaxation No Copyright",
        "4K Aerial Nature Scenery Relaxation Film",
        "4K Japan Nature Scenery Drone Relaxation",
        "4K Forest River Mountains Aerial View Relaxation",
        "4K Scenic Drone Footage Nature Long Video",
        "4K Autumn Forest Drone Relaxation Film",
        "4K Japanese Countryside Scenery Relaxation",
        "4K Mountain Valley Mist Aerial Drone View",
        "4K Ocean Coastline Cliffs Drone Relaxation",
        "4K Peaceful Nature River Waterfall Drone",
        "4K Cinematic Nature Landscapes No Copyright Long",
        "4K Kyoto Japan Bamboo Forest Nature Scenery",
        "4K Alpine Lakes Mountains Drone Relaxation",
        "4K Sunset Clouds Aerial Nature Relaxation",
    ]

    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir:
            self.root_dir = Path(root_dir)
        else:
            p = Path(__file__).resolve().parent.parent
            if (p / "STOOK").exists():
                self.root_dir = p
            elif (p.parent / "STOOK").exists():
                self.root_dir = p.parent
            else:
                self.root_dir = p

        self.settings_file = self.root_dir / "settings.json"
        self.used_history_file = self.root_dir / "used_stocks_history.json"
        self.used_links_file = self.root_dir / "used_stock_links.json"
        self.custom_links_txt = self.root_dir / "custom_stock_links.txt"
        saved_dir = self.load_saved_stook_dir()
        if saved_dir and Path(saved_dir).exists():
            self.stook_dir = Path(saved_dir)
        else:
            self.stook_dir = self.root_dir / "STOOK"

        self.inventory_file = self.stook_dir / "stock_inventory.json"
        self.cookies_file = self.stook_dir / "youtube_cookies.txt"
        self._links_lock = threading.RLock()
        self.stook_dir.mkdir(parents=True, exist_ok=True)
        self.scan_and_update_inventory()

    def _find_js_runtime(self) -> Dict[str, Dict[str, str]]:
        """
        Tích hợp cơ chế JS Runtime của Panniantong/agent-reach cho yt-dlp + yt-dlp-ejs
        nhằm giải mã thử thách chữ ký (sig) và n-challenge mới của YouTube.
        """
        node_candidates = [
            shutil.which("node"),
            str(self.root_dir / "bin" / "node.exe"),
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
        ]
        local_app = os.environ.get("LOCALAPPDATA", "")
        appdata = os.environ.get("APPDATA", "")
        for base in (local_app, appdata):
            if base:
                node_candidates.append(os.path.join(base, "Programs", "nodejs", "node.exe"))
        for cand in node_candidates:
            if cand and os.path.isfile(cand):
                return {"node": {"path": cand}}

        deno_candidates = [
            shutil.which("deno"),
            str(self.root_dir / "bin" / "deno.exe"),
            os.path.expanduser(r"~\.deno\bin\deno.exe"),
        ]
        for cand in deno_candidates:
            if cand and os.path.isfile(cand):
                return {"deno": {"path": cand}}
        return {}

    def export_youtube_cookies_from_cdp(self, warmup_youtube_tab: bool = False) -> Optional[Path]:
        """
        Trích xuất Cookie xác thực thực tế từ trình duyệt Chrome CDP (cổng 9222, 9223, 9224
        hoặc cổng mặc định của agent-reach) sang định dạng chuẩn Netscape HTTP Cookie File.
        Giúp yt-dlp vượt qua hoàn toàn lỗi 'Sign in to confirm you’re not a bot' trên Windows
        mà không bị lỗi khóa file SQLite hoặc mã hóa DPAPI v20 của Chrome.
        """
        ports = [9222, 9223, 9224]
        try:
            from agent_reach.runtime.browser import configured_port
            ar_port = configured_port()
            if ar_port and ar_port not in ports:
                ports.insert(0, ar_port)
        except Exception:
            pass

        def _collect_from_ports(port_list: List[int], do_warmup: bool) -> List[Dict[str, Any]]:
            from websockets.sync.client import connect as ws_connect
            best_cookies: List[Dict[str, Any]] = []
            best_score = -1
            for p in port_list:
                try:
                    proxy_handler = urllib.request.ProxyHandler({})
                    opener = urllib.request.build_opener(proxy_handler)
                    raw = opener.open(f"http://127.0.0.1:{p}/json", timeout=2.0).read().decode("utf-8", errors="ignore")
                    tabs = json.loads(raw)
                    page_tabs = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
                    if not page_tabs:
                        continue

                    temp_target_id = None
                    ws_url = page_tabs[0]["webSocketDebuggerUrl"]
                    with ws_connect(ws_url, open_timeout=4.0, close_timeout=1.5) as ws:
                        if do_warmup:
                            ws.send(json.dumps({
                                "id": 10,
                                "method": "Target.createTarget",
                                "params": {"url": "https://www.youtube.com/?hl=ja", "background": True}
                            }))
                            resp_t = json.loads(ws.recv(timeout=4.0))
                            temp_target_id = resp_t.get("result", {}).get("targetId")
                            time.sleep(2.5)

                        ws.send(json.dumps({"id": 11, "method": "Storage.getCookies", "params": {}}))
                        resp_c = json.loads(ws.recv(timeout=5.0))
                        while resp_c.get("id") != 11:
                            resp_c = json.loads(ws.recv(timeout=5.0))
                        cookies = resp_c.get("result", {}).get("cookies", []) or []

                        if temp_target_id:
                            try:
                                ws.send(json.dumps({
                                    "id": 12,
                                    "method": "Target.closeTarget",
                                    "params": {"targetId": temp_target_id}
                                }))
                                ws.recv(timeout=2.0)
                            except Exception:
                                pass

                    yt_google = [
                        c for c in cookies
                        if "youtube.com" in str(c.get("domain", "")) or "google.com" in str(c.get("domain", ""))
                    ]
                    auth_names = {c.get("name") for c in yt_google}
                    score = len(yt_google) + (100 if ("SID" in auth_names or "__Secure-1PSID" in auth_names or "LOGIN_INFO" in auth_names) else 0)
                    if score > best_score and len(yt_google) > 0:
                        best_score = score
                        best_cookies = cookies
                        if score >= 110:
                            break
                except Exception:
                    continue
            return best_cookies

        cookies_list = _collect_from_ports(ports, warmup_youtube_tab)
        if not cookies_list:
            # Nếu chưa có cửa sổ Chrome CDP nào đang bật, tự động khởi chạy Chrome Profile Acc #1
            try:
                try:
                    from backend.chatgpt_web_client import ensure_chrome_debug_browser_open
                except ImportError:
                    from app.backend.chatgpt_web_client import ensure_chrome_debug_browser_open
                print("[StockManager] 🌐 [Agent-Reach] Đang tự động kích hoạt phiên Chrome CDP để đồng bộ Cookie YouTube...")
                ensure_chrome_debug_browser_open(
                    open_chatgpt_home=False,
                    force_bring_to_front=False,
                    run_hidden=False,
                    acc_id="acc_1",
                )
                time.sleep(3.0)
                cookies_list = _collect_from_ports(ports, True)
            except Exception as e:
                print(f"[StockManager] Lưu ý khi tự mở Chrome lấy Cookie: {e}")

        if not cookies_list:
            return None

        lines = [
            "# Netscape HTTP Cookie File",
            "# Auto-generated by Drama Nhat Studio x Agent-Reach CDP Bridge",
            ""
        ]
        yt_count = 0
        now_ts = int(time.time())
        for c in cookies_list:
            dom = str(c.get("domain", "")).strip()
            if not dom:
                continue
            include_sub = "TRUE" if dom.startswith(".") else "FALSE"
            path = str(c.get("path", "/")) or "/"
            secure = "TRUE" if c.get("secure") else "FALSE"
            exp = int(float(c.get("expires") or 0))
            if exp <= 0:
                exp = now_ts + 86400 * 30
            name = str(c.get("name", "")).strip()
            val = str(c.get("value", "")).replace("\n", "").replace("\r", "").replace("\t", "")
            if not name:
                continue
            lines.append(f"{dom}\t{include_sub}\t{path}\t{secure}\t{exp}\t{name}\t{val}")
            if "youtube.com" in dom or "google.com" in dom:
                yt_count += 1

        if yt_count == 0:
            return None

        content = "\n".join(lines) + "\n"
        for target_f in (self.cookies_file, self.root_dir / "youtube_cookies.txt"):
            try:
                target_f.parent.mkdir(parents=True, exist_ok=True)
                target_f.write_text(content, encoding="utf-8")
            except Exception:
                pass
        print(f"[StockManager] 🍪 [Agent-Reach] Đã đồng bộ {yt_count} Cookie xác thực YouTube/Google từ Chrome CDP -> {self.cookies_file.name}")
        return self.cookies_file

    def ensure_youtube_cookies_file(self, force_refresh: bool = False, warmup_youtube_tab: bool = False) -> Optional[Path]:
        """Đảm bảo luôn có file youtube_cookies.txt hợp lệ trước khi gọi yt-dlp."""
        if not force_refresh:
            for cand in (self.cookies_file, self.root_dir / "youtube_cookies.txt"):
                if cand.exists():
                    try:
                        age_sec = time.time() - cand.stat().st_mtime
                        txt = cand.read_text(encoding="utf-8", errors="ignore")
                        if age_sec < 14400 and ("youtube.com" in txt or "google.com" in txt) and len(txt.splitlines()) >= 12:
                            return cand
                    except Exception:
                        pass
        return self.export_youtube_cookies_from_cdp(warmup_youtube_tab=warmup_youtube_tab)

    def _build_agent_reach_ytdlp_opts(
        self,
        base_opts: Optional[Dict[str, Any]] = None,
        force_refresh_cookies: bool = False,
        warmup_youtube_tab: bool = False,
    ) -> Dict[str, Any]:
        """
        Tạo bộ cấu hình yt-dlp chuẩn Agent-Reach:
        1. Nạp JS Runtime (node / deno) + yt-dlp-ejs để giải mã chữ ký JS & n-challenge của YouTube.
        2. Nạp Cookie thực tế từ Chrome CDP (youtube_cookies.txt) để vượt qua hoàn toàn bước kiểm tra Bot.
        """
        opts: Dict[str, Any] = dict(base_opts or {})
        js_rt = self._find_js_runtime()
        if js_rt:
            opts["js_runtimes"] = js_rt

        cookie_path = self.ensure_youtube_cookies_file(
            force_refresh=force_refresh_cookies,
            warmup_youtube_tab=warmup_youtube_tab,
        )
        if cookie_path and cookie_path.exists():
            opts["cookiefile"] = str(cookie_path)

        opts.setdefault("nocheckcertificate", True)
        opts.setdefault("socket_timeout", 25)
        opts.setdefault("retries", 3)
        opts.setdefault("fragment_retries", 3)
        return opts

    def load_used_history(self) -> Dict[str, Any]:
        """Đọc danh sách lịch sử stock đã dùng vĩnh viễn."""
        if self.used_history_file.exists():
            try:
                with open(self.used_history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"used_items": {}}

    def save_used_history(self, data: Dict[str, Any]):
        """Lưu vĩnh viễn danh sách stock đã dùng."""
        try:
            with open(self.used_history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[StockManager] Lỗi ghi used_stocks_history: {e}")

    def load_saved_stook_dir(self) -> Optional[str]:
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    return json.load(f).get("stook_dir")
            except Exception:
                pass
        return None

    def save_stook_dir(self, dir_path: str):
        data = {}
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["stook_dir"] = dir_path
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_target_stock_hours(self) -> float:
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    val = json.load(f).get("target_stock_hours", 30.0)
                    return float(val)
            except Exception:
                pass
        return 30.0

    def save_target_stock_hours(self, target_hours: float):
        data = {}
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass
        data["target_stock_hours"] = round(float(target_hours), 2)
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_used_links_file_paths(self) -> List[Path]:
        """Trả về tất cả các đường dẫn file used_stock_links.json (gốc & trong thư mục STOOK) để đồng bộ tuyệt đối."""
        paths = [
            self.used_links_file,
            self.stook_dir / "used_stock_links.json",
            self.root_dir / "STOOK" / "used_stock_links.json",
        ]
        unique_paths: List[Path] = []
        seen_resolved = set()
        for p in paths:
            try:
                rp = str(p.resolve()).lower()
            except Exception:
                rp = str(p).lower()
            if rp not in seen_resolved:
                seen_resolved.add(rp)
                unique_paths.append(p)
        return unique_paths

    @staticmethod
    def _is_valid_stock_id(vid_id: str) -> bool:
        """Kiểm tra mã ID video hợp lệ (PX_*, PB_* hoặc YouTube 11 ký tự), loại bỏ tên máy tính DESKTOP-* bị nhận nhầm."""
        if not vid_id:
            return False
        s = str(vid_id).strip()
        upper_s = s.upper()
        if upper_s.startswith(("DESKTOP-", "LAPTOP-", "PC-", "WIN-", "WORKSTATION")):
            return False
        if re.match(r"^(?:PX|PB)_\d+$", s):
            return True
        if re.match(r"^[0-9A-Za-z_-]{11}$", s):
            return True
        return False

    @staticmethod
    def _extract_stock_id_from_url(url: str) -> Optional[str]:
        """Trích xuất mã ID (PX_*, PB_* hoặc YouTube ID) từ URL bất kỳ."""
        if not url:
            return None
        u = str(url).strip()
        m_px = re.search(r"pexels\.com/video-files/(\d+)/", u)
        if m_px:
            return f"PX_{m_px.group(1)}"
        m_pb = re.search(r"pixabay\.com/video/\d+/\d+/\d+/(\d+)_", u)
        if m_pb:
            return f"PB_{m_pb.group(1)}"
        yt_id = extract_youtube_id(u)
        if yt_id and not yt_id.upper().startswith(("DESKTOP-", "LAPTOP-", "PC-")):
            return yt_id
        return None

    def load_used_yt_links(self) -> Dict[str, Any]:
        """Đọc danh sách các link/ID YouTube, Pexels, Pixabay đã từng tải để chống tải trùng 100%."""
        with self._links_lock:
            merged_ids: Dict[str, Any] = {}
            all_links: List[str] = []
            seen_links_set = set()

            def _add_link(lnk: Optional[str]):
                if not lnk:
                    return
                s_lnk = str(lnk).strip()
                if not s_lnk or "watch?v=DESKTOP-" in s_lnk:
                    return
                if s_lnk not in seen_links_set:
                    seen_links_set.add(s_lnk)
                    all_links.append(s_lnk)

            for fpath in self._get_used_links_file_paths():
                if fpath.exists():
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            d = json.load(f)
                        for k, v in d.get("used_video_ids", {}).items():
                            if not self._is_valid_stock_id(k):
                                continue
                            if not isinstance(v, dict):
                                v = {"id": k, "url": str(v)}
                            # Sửa lại URL nếu trước đây PB_*/PX_* bị gán nhầm youtube.com/watch?v=PB_*
                            cur_u = str(v.get("url") or "")
                            if k.startswith(("PX_", "PB_")) and cur_u.startswith("https://www.youtube.com/watch?v="):
                                v["url"] = ""
                            merged_ids[k] = v
                            _add_link(v.get("url"))
                        for lnk in d.get("all_used_links", []):
                            _add_link(lnk)
                            ext_id = self._extract_stock_id_from_url(lnk)
                            if ext_id and self._is_valid_stock_id(ext_id) and ext_id not in merged_ids:
                                merged_ids[ext_id] = {
                                    "id": ext_id,
                                    "url": lnk,
                                    "title": f"Auto-recovered ({ext_id})",
                                    "status": "completed",
                                    "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                }
                    except Exception:
                        pass

            # Gộp thêm từ imported_sources của stock_inventory.json để không bỏ sót bất kỳ video nào đã tải
            for inv_p in [self.inventory_file, self.root_dir / "STOOK" / "stock_inventory.json"]:
                if inv_p.exists():
                    try:
                        with open(inv_p, "r", encoding="utf-8") as f:
                            inv_d = json.load(f)
                        for src_id, src_info in (inv_d.get("imported_sources") or {}).items():
                            if not self._is_valid_stock_id(src_id):
                                continue
                            src_url = src_info.get("url", "") if isinstance(src_info, dict) else ""
                            _add_link(src_url)
                            if src_id not in merged_ids:
                                merged_ids[src_id] = {
                                    "id": src_id,
                                    "url": src_url or ("" if src_id.startswith(("PX_", "PB_")) else f"https://www.youtube.com/watch?v={src_id}"),
                                    "title": src_info.get("title", src_id) if isinstance(src_info, dict) else src_id,
                                    "folder": src_info.get("folder", "") if isinstance(src_info, dict) else "",
                                    "segments_count": src_info.get("parts_count", 1) if isinstance(src_info, dict) else 1,
                                    "status": "completed",
                                    "added_at": src_info.get("downloaded_at", time.strftime("%Y-%m-%d %H:%M:%S")) if isinstance(src_info, dict) else time.strftime("%Y-%m-%d %H:%M:%S"),
                                }
                            elif src_url and not merged_ids[src_id].get("url"):
                                merged_ids[src_id]["url"] = src_url
                    except Exception:
                        pass

            return {
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "used_video_ids": merged_ids,
                "all_used_links": all_links,
            }

    def record_used_yt_link(
        self,
        yt_id: str,
        url: str,
        title: str,
        folder: str,
        parts_count: int,
        duration_hours: float,
        sync_cloud: bool = True,
    ):
        """
        Ghi nhận NGAY LẬP TỨC ID & Link YouTube/Pexels/Pixabay vừa tải vào used_stock_links.json,
        stock_inventory.json và đẩy lên Cloud Note Online để chống tải trùng 100%.
        """
        if not yt_id or not self._is_valid_stock_id(yt_id):
            return

        with self._links_lock:
            data = self.load_used_yt_links()
            used_ids = data.setdefault("used_video_ids", {})
            all_links = data.setdefault("all_used_links", [])

            is_px_pb = str(yt_id).startswith(("PX_", "PB_"))
            canonical_url = (url or "").strip() if is_px_pb else f"https://www.youtube.com/watch?v={yt_id}"
            now_str = time.strftime("%Y-%m-%d %H:%M:%S")

            used_ids[yt_id] = {
                "id": yt_id,
                "url": canonical_url,
                "title": title,
                "duration_hours": round(float(duration_hours), 2),
                "folder": str(folder),
                "segments_count": int(parts_count),
                "status": "completed",
                "added_at": now_str,
            }
            if canonical_url and canonical_url not in all_links:
                all_links.append(canonical_url)
            if url and url not in all_links:
                all_links.append(url)
            base_url = (url or "").split("?")[0].strip()
            if base_url and base_url not in all_links:
                all_links.append(base_url)

            data["updated_at"] = now_str

            for fpath in self._get_used_links_file_paths():
                try:
                    fpath.parent.mkdir(parents=True, exist_ok=True)
                    with open(fpath, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass

            # Cập nhật đồng thời vào imported_sources của stock_inventory.json ngay tức thì
            try:
                inv_data = self.load_inventory()
                sources = inv_data.setdefault("imported_sources", {})
                sources[yt_id] = {
                    "url": canonical_url or url,
                    "title": title,
                    "folder": str(folder),
                    "parts_count": int(parts_count),
                    "downloaded_at": now_str,
                }
                self.save_inventory(inv_data)
            except Exception:
                pass

        print(f"[StockManager] 🔒 Đã khóa & cập nhật ngay link vừa tải vào Sổ Cái chống trùng: [{yt_id}] {canonical_url or url}")

        # Tự động đẩy ngay link vừa tải lên File Note Online chung (chạy ngầm để không bao giờ gây treo tiến trình)
        if sync_cloud:
            try:
                threading.Thread(
                    target=self.sync_cloud_used_links,
                    kwargs={"push_updates": True, "force_push": True},
                    daemon=True,
                ).start()
            except Exception as e:
                print(f"[StockManager] Lưu ý khi đồng bộ Cloud Note: {e}")

    def get_cloud_note_config(self) -> Dict[str, str]:
        slug = self.DEFAULT_CLOUD_NOTE_SLUG
        edit_code = self.DEFAULT_CLOUD_NOTE_EDIT_CODE
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    st = json.load(f)
                    slug = st.get("cloud_note_slug", slug) or slug
                    edit_code = st.get("cloud_note_edit_code", edit_code) or edit_code
            except Exception:
                pass
        slug = slug.replace("https://rentry.co/", "").strip("/")
        return {
            "slug": slug,
            "url": f"https://rentry.co/{slug}",
            "edit_code": edit_code
        }

    def sync_cloud_used_links(self, push_updates: bool = True, force_push: bool = False) -> Dict[str, Any]:
        """
        Đồng bộ 2 chiều danh sách link Stock đã dùng (YouTube + Pexels + Pixabay) với File Note Online (https://rentry.co/...)
        và Cloud KV dự phòng (Không cần đăng nhập, copy tool sang máy nào cũng tự động liên kết).
        """
        with self._links_lock:
            local_data = self.load_used_yt_links()
            used_ids: Dict[str, Any] = local_data.setdefault("used_video_ids", {})
            all_links: List[str] = local_data.setdefault("all_used_links", [])

        cfg = self.get_cloud_note_config()
        note_url = cfg["url"]
        slug = cfg["slug"]
        edit_code = cfg["edit_code"]

        if not check_internet_connection(timeout=2.0):
            return {
                "success": False,
                "offline": True,
                "cloud_note_url": note_url,
                "total_synced_ids": len(used_ids),
                "message": "Máy đang Offline — Sử dụng danh sách chống trùng cục bộ trên máy."
            }

        import requests
        cloud_discovered: Dict[str, Dict[str, str]] = {}

        def _register_cloud_item(cid: str, c_url: str = "", c_title: str = "", c_time: str = ""):
            cid = str(cid or "").strip()
            if not self._is_valid_stock_id(cid):
                return
            if not c_url and not cid.startswith(("PX_", "PB_")):
                c_url = f"https://www.youtube.com/watch?v={cid}"
            if c_url and cid.startswith(("PX_", "PB_")) and c_url.startswith("https://www.youtube.com/watch?v="):
                c_url = ""
            prev = cloud_discovered.get(cid, {})
            cloud_discovered[cid] = {
                "id": cid,
                "url": c_url or prev.get("url", ""),
                "title": c_title or prev.get("title", f"Đồng bộ từ Cloud Note (#{cid})"),
                "added_at": c_time or prev.get("added_at", time.strftime("%Y-%m-%d %H:%M:%S")),
            }

        # 1. Đọc danh sách ID & Link từ trang Note Online (Ưu tiên bản /raw Markdown chuẩn xác, fallback bản HTML)
        for read_url in (f"{note_url}/raw", note_url):
            try:
                r_page = requests.get(read_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
                if r_page.status_code == 200 and r_page.text:
                    txt = r_page.text
                    # Quét các dòng bảng Markdown: | `ID` | URL | Title | Time |
                    for row_m in re.finditer(
                        r"\|\s*`?((?:PX|PB)_\d+|[0-9A-Za-z_-]{11})`?\s*\|\s*([^|\n]*?)\s*\|\s*([^|\n]*?)\s*\|\s*([^|\n]*?)\s*\|",
                        txt,
                    ):
                        r_id, r_url, r_title, r_time = (
                            row_m.group(1).strip(),
                            row_m.group(2).strip(),
                            row_m.group(3).strip(),
                            row_m.group(4).strip(),
                        )
                        _register_cloud_item(r_id, r_url, r_title, r_time)

                    # Quét thêm các mã PX_*, PB_* trong thẻ <code> hoặc dấu `...`
                    for pxpb_m in re.findall(r"(?:<code>|`)((?:PX|PB)_\d+)(?:</code>|`)", txt):
                        _register_cloud_item(pxpb_m)

                    # Quét các link Pexels / Pixabay / YouTube rời nếu người dùng dán trực tiếp vào Note
                    for raw_u in re.findall(r"https?://[^\s|<>\"'`]+", txt):
                        ext_id = self._extract_stock_id_from_url(raw_u)
                        if ext_id:
                            _register_cloud_item(ext_id, raw_u)
                    if cloud_discovered:
                        break
            except Exception as e:
                print(f"[StockManager] Lưu ý khi đọc Note Online ({read_url}): {e}")

        # 2. Đọc thêm từ Cloud KV dự phòng
        try:
            kv_url = f"https://keyvalue.immanuel.co/api/KeyVal/GetValue/{self.DEFAULT_CLOUD_KV_APP_KEY}/nhat_drama_{slug}"
            r_kv = requests.get(kv_url, timeout=3)
            if r_kv.status_code == 200:
                raw_kv = r_kv.text.strip().strip('"')
                if raw_kv and raw_kv != "null":
                    for part in raw_kv.split(","):
                        part = part.strip()
                        if self._is_valid_stock_id(part):
                            _register_cloud_item(part)
        except Exception:
            pass

        # 3. Gộp các ID & Link từ Cloud về máy hiện tại
        new_from_cloud = 0
        updated_urls_from_cloud = 0
        with self._links_lock:
            for cid, cinfo in cloud_discovered.items():
                c_url = cinfo.get("url", "")
                if cid not in used_ids:
                    new_from_cloud += 1
                    used_ids[cid] = {
                        "id": cid,
                        "url": c_url,
                        "title": cinfo.get("title") or f"Đồng bộ từ Cloud Note (#{cid})",
                        "status": "synced_from_cloud",
                        "added_at": cinfo.get("added_at") or time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                elif c_url and not used_ids[cid].get("url"):
                    used_ids[cid]["url"] = c_url
                    updated_urls_from_cloud += 1
                if c_url and c_url not in all_links:
                    all_links.append(c_url)

            if new_from_cloud > 0 or updated_urls_from_cloud > 0:
                local_data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                for fpath in self._get_used_links_file_paths():
                    try:
                        fpath.parent.mkdir(parents=True, exist_ok=True)
                        with open(fpath, "w", encoding="utf-8") as f:
                            json.dump(local_data, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

            snapshot_used_ids = dict(used_ids)

        # 4. Nếu máy hiện tại có ID/Link mới chưa có trên Cloud Note -> Đẩy ngay lên Note Online & Cloud KV
        local_only_ids = set(snapshot_used_ids.keys()) - set(cloud_discovered.keys())
        pushed_to_cloud = False
        if push_updates and (local_only_ids or force_push):
            machine_name = os.environ.get("COMPUTERNAME", "PC-STUDIO")
            lines = [
                "# 🎬 SỔ CÁI ĐỒNG BỘ VIDEO STOCK ĐA MÁY — DRAMA NHẬT STUDIO",
                f"*(Tự động liên kết chống trùng 100% giữa tất cả các máy — Cập nhật lúc: `{time.strftime('%Y-%m-%d %H:%M:%S')}` từ máy `{machine_name}`)*",
                "",
                f"### 📊 Tổng số Video Stock gốc đã khóa trên toàn hệ thống: **{len(snapshot_used_ids)} video**",
                "*(Bất kỳ máy nào tải video YouTube / Pexels / Pixabay mới sẽ lập tức ghi ID & Link vào đây để khóa chống trùng trên mọi máy)*",
                "",
                "| Mã ID Nguồn (YT/Pexels/Pixabay) | Link Video Gốc Đã Tải | Tiêu Đề / Ghi Chú | Thời Gian Khóa |",
                "| :--- | :--- | :--- | :--- |"
            ]
            for vid_id, info in snapshot_used_ids.items():
                if not self._is_valid_stock_id(vid_id):
                    continue
                default_u = "" if str(vid_id).startswith(("PX_", "PB_")) else f"https://www.youtube.com/watch?v={vid_id}"
                v_url = str(info.get("url") or default_u).strip()
                if str(vid_id).startswith(("PX_", "PB_")) and v_url.startswith("https://www.youtube.com/watch?v="):
                    v_url = ""
                v_title = str(info.get("title", "")).replace("|", "-").replace("\n", " ")[:70]
                v_time = info.get("added_at", "-")
                lines.append(f"| `{vid_id}` | {v_url} | {v_title} | {v_time} |")

            note_markdown = "\n".join(lines) + "\n"

            try:
                sess = requests.Session()
                sess.headers.update({"User-Agent": "Mozilla/5.0", "Referer": f"https://rentry.co/{slug}/edit"})
                sess.get(f"https://rentry.co/{slug}/edit", timeout=5)
                csrf = sess.cookies.get("csrftoken")
                if csrf:
                    r_ed = sess.post(
                        f"https://rentry.co/api/edit/{slug}",
                        data={
                            "csrfmiddlewaretoken": csrf,
                            "edit_code": edit_code,
                            "text": note_markdown
                        },
                        timeout=6
                    )
                    if r_ed.status_code == 200:
                        pushed_to_cloud = True
            except Exception as e:
                print(f"[StockManager] Lưu ý khi ghi Note Online: {e}")

            try:
                valid_keys = [k for k in sorted(snapshot_used_ids.keys()) if self._is_valid_stock_id(k)]
                joined_ids = ",".join(valid_keys)
                if joined_ids:
                    kv_post = f"https://keyvalue.immanuel.co/api/KeyVal/UpdateValue/{self.DEFAULT_CLOUD_KV_APP_KEY}/nhat_drama_{slug}/{joined_ids}"
                    r_kv_up = requests.post(kv_post, timeout=4)
                    if r_kv_up.status_code == 200:
                        pushed_to_cloud = True
            except Exception:
                pass

        return {
            "success": True,
            "cloud_note_url": note_url,
            "new_from_cloud": new_from_cloud,
            "pushed_to_cloud": pushed_to_cloud,
            "total_synced_ids": len(snapshot_used_ids),
            "message": f"☁️ Đã đồng bộ thành công với Note Online ({note_url})! Tổng cộng {len(snapshot_used_ids)} link nguồn đã khóa trên toàn hệ thống."
        }

    def is_yt_id_used(self, yt_id: Optional[str], url: Optional[str] = None) -> bool:
        """Kiểm tra chặt chẽ cả Mã ID (YT/PX/PB) lẫn Link URL gốc xem đã từng tải hay chưa."""
        links_data = self.load_used_yt_links()
        used_ids = links_data.get("used_video_ids", {})
        all_links = links_data.get("all_used_links", [])

        if yt_id:
            clean_id = str(yt_id).strip()
            if clean_id in used_ids:
                return True
            inv_data = self.load_inventory()
            if clean_id in inv_data.get("imported_sources", {}):
                return True

        if url:
            clean_url = str(url).strip()
            base_url = clean_url.split("?")[0].strip()
            if clean_url in all_links or (base_url and base_url in all_links):
                return True
            ext_id = self._extract_stock_id_from_url(clean_url)
            if ext_id and ext_id in used_ids:
                return True
            for info in used_ids.values():
                if isinstance(info, dict):
                    u_saved = str(info.get("url") or "").strip()
                    if u_saved and (u_saved == clean_url or u_saved.split("?")[0].strip() == base_url):
                        return True
        return False

    def set_stook_dir(self, new_dir: str) -> Dict[str, Any]:
        p = Path(new_dir)
        if p.exists() and p.is_dir():
            self.stook_dir = p
            self.inventory_file = self.stook_dir / "stock_inventory.json"
            self.save_stook_dir(str(p))
            return self.scan_and_update_inventory()
        else:
            raise ValueError(f"Thư mục không tồn tại: {new_dir}")

    def load_inventory(self) -> Dict[str, Any]:
        if self.inventory_file.exists():
            try:
                with open(self.inventory_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"items": {}}

    def save_inventory(self, data: Dict[str, Any]):
        with open(self.inventory_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def scan_and_update_inventory(self) -> Dict[str, Any]:
        """Quét toàn bộ thư mục STOOK và cập nhật thông tin video, giữ lại lịch sử đã sử dụng."""
        current_data = self.load_inventory()
        items = current_data.get("items", {})

        video_extensions = {".mp4", ".mov", ".mkv", ".webm"}
        found_files = []

        for root, _, files in os.walk(self.stook_dir):
            for file in files:
                if file.startswith("_") or file.endswith(".tmp") or file.endswith(".part"):
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in video_extensions:
                    full_path = Path(root) / file
                    # Bỏ qua các file 10 tiếng chưa cắt nếu đã có thư mục part
                    found_files.append(full_path)

        used_history = self.load_used_history().get("used_items", {})

        updated_items = {}
        for p in found_files:
            rel_path = str(p.relative_to(self.stook_dir)).replace("\\", "/")
            item_id = rel_path.replace("/", "_").replace(".", "_")

            existing = items.get(item_id, {})
            duration = existing.get("duration", 0.0)
            if duration <= 0:
                duration = get_video_duration(str(p))

            file_size_bytes = p.stat().st_size

            # KIỂM TRA SỐ LẦN ĐÃ DÙNG (TỐI ĐA 2 LẦN: LẦN 1 GỐC + LẦN 2 LẬT & ZOOM 110%)
            hist_entry = used_history.get(p.name) or used_history.get(rel_path) or used_history.get(item_id)
            hist_count = hist_entry.get("usage_count", 0) if hist_entry else 0
            existing_count = existing.get("usage_count", 0)
            usage_count = max(hist_count, existing_count)
            if hist_entry and hist_entry.get("file_deleted"):
                usage_count = max(usage_count, self.MAX_STOCK_USAGES)

            is_fully_used = usage_count >= self.MAX_STOCK_USAGES
            remaining_uses = max(0, self.MAX_STOCK_USAGES - usage_count)

            used_projects = (
                hist_entry.get("used_in_projects", [])
                if (hist_entry and hist_entry.get("used_in_projects"))
                else existing.get("used_in_projects", [])
            )
            last_used = (
                hist_entry.get("last_used_at", None)
                if (hist_entry and hist_entry.get("last_used_at"))
                else existing.get("last_used_at", None)
            )

            if usage_count == 0:
                next_mode = "original"
                next_mode_label = "Lần 1/2 (Bản Gốc 100%)"
            elif usage_count == 1:
                next_mode = "flip_zoom_110"
                next_mode_label = "Lần 2/2 (Lật Video + Zoom 110%)"
            else:
                next_mode = "locked"
                next_mode_label = "Đã khóa (Hết 2/2 lần)"

            updated_items[item_id] = {
                "id": item_id,
                "name": p.name,
                "rel_path": rel_path,
                "abs_path": str(p),
                "duration": duration,
                "duration_formatted": f"{int(duration // 60):02d}:{int(duration % 60):02d}",
                "size_mb": round(file_size_bytes / (1024 * 1024), 2),
                "size_bytes": file_size_bytes,
                "usage_count": usage_count,
                "max_uses": self.MAX_STOCK_USAGES,
                "remaining_uses": remaining_uses,
                "next_mode": next_mode,
                "next_mode_label": next_mode_label,
                "used_in_projects": used_projects if usage_count > 0 else [],
                "last_used_at": last_used if usage_count > 0 else None,
                "status": "used" if is_fully_used else "available"
            }

        # Phát hiện video trùng lặp nội dung (cùng dung lượng byte và cùng thời lượng)
        fingerprints: Dict[str, List[str]] = {}
        for iid, itm in updated_items.items():
            fp = f"{itm['size_bytes']}_{int(itm['duration'])}"
            fingerprints.setdefault(fp, []).append(iid)

        for fp, ids in fingerprints.items():
            if len(ids) > 1:
                for iid in ids:
                    updated_items[iid]["is_duplicate"] = True
            else:
                updated_items[ids[0]]["is_duplicate"] = False

        current_data["items"] = updated_items
        current_data["last_scan"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.save_inventory(current_data)
        return current_data

    def get_all_stocks(self) -> Dict[str, Any]:
        data = self.load_inventory()
        items = list(data.get("items", {}).values())
        # Ưu tiên: chưa dùng (usage_count == 0) -> dùng 1 lần (usage_count == 1) -> đã khóa (usage_count >= 2)
        items.sort(key=lambda x: (x.get("usage_count", 0), x["rel_path"]))

        available = [x for x in items if x.get("usage_count", 0) < self.MAX_STOCK_USAGES and x.get("status") == "available"]
        available_uses_count = sum(max(0, self.MAX_STOCK_USAGES - x.get("usage_count", 0)) for x in available)
        available_raw_seconds = sum(float(x.get("duration", 0.0)) for x in available)
        available_raw_hours = round(available_raw_seconds / 3600.0, 2)
        available_effective_seconds = sum(
            float(x.get("duration", 0.0)) * max(0, self.MAX_STOCK_USAGES - x.get("usage_count", 0)) * 2.0
            for x in available
        )
        available_effective_hours = round(available_effective_seconds / 3600.0, 2)
        target_stock_hours = self.load_target_stock_hours()
        missing_hours = round(max(0.0, target_stock_hours - available_raw_hours), 2)

        used = [x for x in items if x.get("usage_count", 0) >= self.MAX_STOCK_USAGES or x.get("status") == "used"]
        history = self.load_used_history().get("used_items", {})
        deleted_count = sum(1 for h in history.values() if h.get("file_deleted"))

        cfg = self.get_cloud_note_config()
        links_info = self.load_used_yt_links()

        return {
            "total": len(items),
            "available_count": len(available),
            "available_uses_count": available_uses_count,
            "available_raw_hours": available_raw_hours,
            "available_effective_hours": available_effective_hours,
            "target_stock_hours": target_stock_hours,
            "missing_hours": missing_hours,
            "max_uses_per_stock": self.MAX_STOCK_USAGES,
            "used_count": len(used),
            "deleted_count": deleted_count,
            "current_stook_dir": str(self.stook_dir),
            "cloud_note_url": cfg["url"],
            "cloud_synced_links_count": len(links_info.get("used_video_ids", {})),
            "items": items
        }

    def get_best_available_stock(self, exclude_ids: Optional[set] = None) -> Optional[Dict[str, Any]]:
        """
        Lấy 1 lượt video stock tối ưu nhất:
        - Ưu tiên 1 (Lần dùng 1/2): Video chưa dùng (usage_count == 0) -> Bản Gốc 100%
        - Ưu tiên 2 (Lần dùng 2/2): Video đã dùng 1 lần -> Tự động Lật ngang (hflip) + Zoom 110%
        - Sau 2 lần dùng: Khóa vĩnh viễn tuyệt đối không dùng lại.
        """
        stocks = self.get_all_stocks()
        items = stocks["items"]
        if not items:
            return None

        ex = exclude_ids or set()

        # 1. Tìm các video còn Lượt 1 (Bản Gốc 100%)
        pass1_candidates = [
            x for x in items
            if x.get("usage_count", 0) == 0 and x.get("status") == "available"
            and f"{x['id']}::use1" not in ex and x["id"] not in ex
        ]
        if pass1_candidates:
            long_cands = [x for x in pass1_candidates if x["duration"] >= 300]
            chosen = dict(long_cands[0] if long_cands else pass1_candidates[0])
            chosen["use_number"] = 1
            chosen["flip_horizontal"] = False
            chosen["zoom_factor"] = 1.0
            chosen["transform_label"] = "Lần 1/2 (Bản Gốc 100%)"
            chosen["slot_key"] = f"{chosen['id']}::use1"
            return chosen

        # 2. Tìm các video còn Lượt 2 (Lật Video Ngang + Zoom 110%)
        pass2_candidates = [
            x for x in items
            if x.get("usage_count", 0) < self.MAX_STOCK_USAGES and x.get("status") == "available"
            and f"{x['id']}::use2" not in ex and x["id"] not in ex
        ]
        if pass2_candidates:
            long_cands = [x for x in pass2_candidates if x["duration"] >= 300]
            chosen = dict(long_cands[0] if long_cands else pass2_candidates[0])
            chosen["use_number"] = 2
            chosen["flip_horizontal"] = True
            chosen["zoom_factor"] = 1.10
            chosen["transform_label"] = "Lần 2/2 (Lật Video + Zoom 110%)"
            chosen["slot_key"] = f"{chosen['id']}::use2"
            return chosen

        return None

    def mark_as_used(self, stock_id_or_path: str, project_name: str) -> int:
        """
        Đánh dấu đã dùng thêm 1 lượt.
        - Nếu mới dùng 1/2 lần: Vẫn giữ trạng thái 'available' cho Lần 2 (Lật + Zoom 110%).
        - Nếu đã dùng đủ 2/2 lần: Khóa vĩnh viễn ('used').
        Trả về tổng số lần đã dùng (usage_count mới).
        """
        data = self.load_inventory()
        items = data.get("items", {})

        target_id = None
        target_item = None
        for k, v in items.items():
            if k == stock_id_or_path or v["abs_path"] == stock_id_or_path or v["rel_path"] == stock_id_or_path or v["name"] == stock_id_or_path:
                target_id = k
                target_item = v
                break

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        new_count = 1

        # 1. Cập nhật trong stock_inventory.json của kho hiện tại
        if target_id and target_id in items:
            new_count = items[target_id].get("usage_count", 0) + 1
            items[target_id]["usage_count"] = new_count
            items[target_id]["max_uses"] = self.MAX_STOCK_USAGES
            items[target_id]["remaining_uses"] = max(0, self.MAX_STOCK_USAGES - new_count)
            if project_name not in items[target_id].get("used_in_projects", []):
                items[target_id].setdefault("used_in_projects", []).append(project_name)
            items[target_id]["last_used_at"] = now_str
            if new_count >= self.MAX_STOCK_USAGES:
                items[target_id]["status"] = "used"
                items[target_id]["next_mode"] = "locked"
                items[target_id]["next_mode_label"] = "Đã khóa (Hết 2/2 lần)"
            else:
                items[target_id]["status"] = "available"
                items[target_id]["next_mode"] = "flip_zoom_110"
                items[target_id]["next_mode_label"] = "Lần 2/2 (Lật Video + Zoom 110%)"
            self.save_inventory(data)

        # 2. Ghi nhận vào used_stocks_history.json
        history = self.load_used_history()
        used_items = history.setdefault("used_items", {})

        lookup_key = target_item["name"] if target_item else Path(stock_id_or_path).name
        hist_entry = used_items.get(lookup_key, {})
        hist_entry["name"] = lookup_key
        hist_entry["abs_path"] = target_item["abs_path"] if target_item else str(stock_id_or_path)
        hist_entry["size_bytes"] = target_item.get("size_bytes", 0) if target_item else 0
        hist_entry["duration"] = target_item.get("duration", 0) if target_item else 0
        hist_count = max(new_count, hist_entry.get("usage_count", 0) + 1) if not target_id else new_count
        new_count = hist_count
        hist_entry["usage_count"] = new_count
        hist_entry["max_uses"] = self.MAX_STOCK_USAGES
        if project_name not in hist_entry.get("used_in_projects", []):
            hist_entry.setdefault("used_in_projects", []).append(project_name)
        hist_entry["last_used_at"] = now_str
        used_items[lookup_key] = hist_entry

        self.save_used_history(history)
        if new_count >= self.MAX_STOCK_USAGES:
            print(f"[StockManager] 🔒 ĐÃ KHÓA VĨNH VIỄN STOCK (Đủ {new_count}/{self.MAX_STOCK_USAGES} lần): {lookup_key} (Dự án: {project_name})")
        else:
            print(f"[StockManager] 🔄 ĐÃ DÙNG LẦN {new_count}/{self.MAX_STOCK_USAGES} STOCK: {lookup_key} -> Còn 1 lần (Lật Video + Zoom 110%)")
        return new_count

    def delete_used_stock_file(self, stock_id_or_path: str) -> float:
        """Xóa vĩnh viễn file stock đã sử dụng khỏi ổ cứng để tiết kiệm dung lượng, giữ lại nhật ký."""
        data = self.load_inventory()
        items = data.get("items", {})

        target_item = None
        for k, v in items.items():
            if k == stock_id_or_path or v["abs_path"] == stock_id_or_path or v["rel_path"] == stock_id_or_path or v["name"] == stock_id_or_path:
                target_item = v
                break

        file_path = Path(target_item["abs_path"]) if target_item else Path(stock_id_or_path)

        freed_mb = 0.0
        if file_path and file_path.exists() and file_path.is_file():
            try:
                size_bytes = file_path.stat().st_size
                freed_mb = round(size_bytes / (1024 * 1024), 2)
                file_path.unlink()
                print(f"[StockManager] 🗑️ ĐÃ XÓA FILE STOCK ĐÃ DÙNG: {file_path.name} (Giải phóng: {freed_mb} MB)")
            except Exception as e:
                print(f"[StockManager] Lỗi xóa file {file_path}: {e}")

        # Cập nhật trong used_stocks_history.json
        history = self.load_used_history()
        lookup_key = target_item["name"] if target_item else file_path.name
        if lookup_key in history.get("used_items", {}):
            history["used_items"][lookup_key]["file_deleted"] = True
            history["used_items"][lookup_key]["deleted_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            history["used_items"][lookup_key]["freed_mb"] = freed_mb
            self.save_used_history(history)

        # Quét lại để cập nhật kho
        self.scan_and_update_inventory()
        return freed_mb

    def cleanup_all_used_stocks(self) -> Dict[str, Any]:
        """Quét và xóa tất cả các file stock đã dùng trên ổ cứng để giải phóng bộ nhớ."""
        data = self.load_inventory()
        items = list(data.get("items", {}).values())
        hist_data = self.load_used_history()
        history = hist_data.setdefault("used_items", {})

        deleted_count = 0
        total_freed_mb = 0.0

        for item in items:
            hist_entry = history.get(item["name"], {})
            is_used = (
                item.get("usage_count", 0) >= self.MAX_STOCK_USAGES
                or item.get("status") == "used"
                or hist_entry.get("usage_count", 0) >= self.MAX_STOCK_USAGES
            )
            if is_used:
                p = Path(item["abs_path"])
                if p.exists() and p.is_file():
                    try:
                        mb = round(p.stat().st_size / (1024 * 1024), 2)
                        p.unlink()
                        deleted_count += 1
                        total_freed_mb += mb

                        # Ghi nhận trạng thái xóa vào lịch sử
                        lookup_key = item["name"]
                        hist_entry = history.setdefault(lookup_key, {})
                        hist_entry["name"] = lookup_key
                        hist_entry["file_deleted"] = True
                        hist_entry["deleted_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        hist_entry["freed_mb"] = mb
                        if "used_in_projects" not in hist_entry:
                            hist_entry["used_in_projects"] = item.get("used_in_projects", [])

                        print(f"[StockManager] 🗑️ Dọn dẹp stock đã dùng: {p.name} ({mb} MB)")
                    except Exception as e:
                        print(f"[StockManager] Không thể xóa {p.name}: {e}")

        if deleted_count > 0:
            self.save_used_history(hist_data)

        self.scan_and_update_inventory()
        return {
            "success": True,
            "deleted_count": deleted_count,
            "freed_mb": round(total_freed_mb, 2),
            "message": f"Đã dọn dẹp {deleted_count} video stock đã dùng, giải phóng {total_freed_mb/1024:.2f} GB ổ cứng!"
        }

    def reset_usage(self, stock_id: str) -> bool:
        data = self.load_inventory()
        items = data.get("items", {})
        if stock_id in items:
            items[stock_id]["usage_count"] = 0
            items[stock_id]["used_in_projects"] = []
            items[stock_id]["last_used_at"] = None
            items[stock_id]["status"] = "available"
            self.save_inventory(data)
            return True
        return False

    def reset_all_usage(self) -> Dict[str, Any]:
        """Đặt lại toàn bộ trạng thái kho Stock về 'Chưa dùng' (Khả dụng)."""
        data = self.load_inventory()
        items = data.get("items", {})
        for item in items.values():
            item["usage_count"] = 0
            item["used_in_projects"] = []
            item["last_used_at"] = None
            item["status"] = "available"
        self.save_inventory(data)
        return self.get_all_stocks()

    def download_youtube_and_slice(
        self,
        url: str,
        folder_name: Optional[str] = None,
        slice_minutes: int = 30,
        force: bool = False,
        max_duration_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """Tải video YouTube độ nét cao, đồng bộ Note Online chống trùng đa máy và tự động cắt thành các part 30 phút bằng FFmpeg."""
        # Đồng bộ Note Online trước khi kiểm tra trùng
        try:
            self.sync_cloud_used_links(push_updates=False)
        except Exception:
            pass

        yt_id = extract_youtube_id(url)
        data = self.load_inventory()
        sources = data.setdefault("imported_sources", {})

        # So sánh kiểm tra xem video YouTube này đã từng tải trong lịch sử hoặc trong kho chưa
        if yt_id and not force and self.is_yt_id_used(yt_id):
            existing = sources.get(yt_id) or self.load_used_yt_links().get("used_video_ids", {}).get(yt_id, {})
            folder_str = existing.get("folder", f"YT_{yt_id}")
            return {
                "success": False,
                "already_exists": True,
                "title": existing.get("title", ""),
                "parts_count": existing.get("parts_count", existing.get("segments_count", 0)),
                "folder": str(folder_str),
                "error": f"Video YouTube ({yt_id}) đã từng được tải trước đó ('{existing.get('title', folder_str)}'). Hệ thống tự động chặn tải lại để chống trùng 100%!"
            }

        if not check_internet_connection():
            return {
                "success": False,
                "offline": True,
                "error": "⚠️ Máy tính hiện KHÔNG CÓ KẾT NỐI MẠNG INTERNET! Không thể tải video từ YouTube lúc này."
            }

        clean_name = folder_name or (f"YT_{yt_id}" if yt_id else f"YT_STOCK_{int(time.time())}")
        target_dir = self.stook_dir / clean_name
        target_dir.mkdir(parents=True, exist_ok=True)

        temp_video = self.stook_dir / f"_temp_download_{int(time.time())}.mp4"

        try:
            print(f"[StockManager] Đang tải video YouTube (Chuẩn 720p nhẹ & nhanh • Agent-Reach Engine): {url}...")
            import yt_dlp
            from yt_dlp.utils import download_range_func

            base_dl_opts: Dict[str, Any] = {
                "format": (
                    "bestvideo[height=720][ext=mp4][vcodec^=avc]/"
                    "best[height=720][ext=mp4][vcodec^=avc]/"
                    "bestvideo[height=720][ext=mp4]/"
                    "best[height=720][ext=mp4]/"
                    "bestvideo[height=1080][ext=mp4][vcodec^=avc]/"
                    "best[height=1080][ext=mp4][vcodec^=avc]/"
                    "bestvideo[height=1080][ext=mp4]/"
                    "best[height=1080][ext=mp4]/"
                    "bestvideo[height<=1080][height>=720]/"
                    "best[height<=1080][height>=720]"
                ),
                "outtmpl": str(temp_video),
                "quiet": False,
                "no_warnings": True
            }

            info = None
            vid_dur = 0.0
            title = clean_name
            last_dl_err = None

            for attempt_idx in range(2):
                force_cookie = attempt_idx > 0
                warmup_yt = attempt_idx > 0
                try:
                    info_opts = self._build_agent_reach_ytdlp_opts(
                        {"quiet": True, "no_warnings": True},
                        force_refresh_cookies=force_cookie,
                        warmup_youtube_tab=warmup_yt,
                    )
                    with yt_dlp.YoutubeDL(info_opts) as ydl_info:
                        pre_info = ydl_info.extract_info(url, download=False)
                        vid_dur = float(pre_info.get("duration") or 0)
                        title = pre_info.get("title", clean_name)

                    ydl_opts = self._build_agent_reach_ytdlp_opts(
                        base_dl_opts,
                        force_refresh_cookies=False,
                        warmup_youtube_tab=False,
                    )
                    if max_duration_seconds and vid_dur > (max_duration_seconds + 1200):
                        # Chọn ngẫu nhiên điểm bắt đầu trong video dài để nhiều máy độc lập không bao giờ cắt trùng đoạn
                        max_start = max(60, int(vid_dur - max_duration_seconds - 120))
                        start_offset = random.randint(60, min(max_start, 7200)) if max_start > 60 else 60
                        end_offset = start_offset + max_duration_seconds
                        print(f"[StockManager] Video gốc dài {vid_dur/3600:.1f}h -> Chỉ tải đoạn {max_duration_seconds/3600:.2f}h ({start_offset}s -> {end_offset}s) để bù đủ kho!")
                        ydl_opts["download_ranges"] = download_range_func(None, [(start_offset, end_offset)])

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        if info and info.get("title"):
                            title = info.get("title", title)
                    last_dl_err = None
                    break
                except Exception as dl_e:
                    last_dl_err = dl_e
                    print(f"[StockManager] ⚡ YouTube chặn tải không Cookie ({dl_e}) -> Chuyển thẳng sang tải Stock 720p/1080p từ Pexels & Pixabay API!")
                    fb_parts = max(2, int(math.ceil((max_duration_seconds or (slice_minutes * 60 * 2)) / max(300, slice_minutes * 60))))
                    return self.download_pexels_pixabay_stock_reel(
                        slice_minutes=slice_minutes,
                        target_parts=min(24, fb_parts),
                    )

            if last_dl_err is not None:
                raise last_dl_err

            if not temp_video.exists():
                # Tìm file tạm nếu yt-dlp thêm đuôi khác
                possibles = list(self.stook_dir.glob(f"{temp_video.stem}*"))
                if possibles:
                    temp_video = possibles[0]
                else:
                    raise RuntimeError("File tải về không tồn tại.")

            dur = get_video_duration(str(temp_video))
            # Ghi nhận & đẩy link YouTube vừa tải lên Sổ Cái + Cloud Note NGAY LẬP TỨC để khóa chống trùng
            if yt_id:
                self.record_used_yt_link(
                    yt_id=yt_id,
                    url=url,
                    title=title,
                    folder=clean_name,
                    parts_count=max(1, int(math.ceil(dur / max(60, slice_minutes * 60)))),
                    duration_hours=dur / 3600.0,
                    sync_cloud=True,
                )
            print(f"[StockManager] Tải xong ({dur/60:.1f} phút) & Đã khóa link [{yt_id}] chống trùng. Bắt đầu cắt thành các part {slice_minutes} phút...")

            part_pattern = str(target_dir / f"stock_{yt_id or int(time.time())}_part%02d.mp4")
            slice_seconds = slice_minutes * 60
            cmd = [
                "ffmpeg", "-y", "-i", str(temp_video),
                "-c", "copy", "-map", "0:v:0", "-dn", "-map_metadata", "-1",
                "-segment_time", str(slice_seconds),
                "-reset_timestamps", "1",
                "-f", "segment",
                part_pattern
            ]
            subprocess.run(cmd, check=True)

            if temp_video.exists():
                try:
                    os.remove(temp_video)
                except Exception:
                    pass

            # Xóa các part quá ngắn (< 3 phút) ở đoạn dư cuối video nếu có
            all_parts = sorted(target_dir.glob("*.mp4"))
            if len(all_parts) > 1:
                last_part = all_parts[-1]
                last_dur = get_video_duration(str(last_part))
                if 0 < last_dur < 180:
                    try:
                        last_part.unlink()
                    except Exception:
                        pass

            created_parts = sorted(target_dir.glob("*.mp4"))

            # Lưu lại lịch sử nguồn vào cả stock_inventory.json và used_stock_links.json
            if yt_id:
                sources[yt_id] = {
                    "url": url,
                    "title": title,
                    "folder": str(target_dir),
                    "parts_count": len(created_parts),
                    "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                self.save_inventory(data)
                self.record_used_yt_link(
                    yt_id=yt_id,
                    url=url,
                    title=title,
                    folder=clean_name,
                    parts_count=len(created_parts),
                    duration_hours=dur / 3600.0
                )

            self.scan_and_update_inventory()
            return {
                "success": True,
                "yt_id": yt_id,
                "title": title,
                "downloaded_hours": round(dur / 3600.0, 2),
                "parts_count": len(created_parts),
                "folder": str(target_dir)
            }
        except Exception as e:
            if temp_video.exists():
                try:
                    os.remove(temp_video)
                except Exception:
                    pass
            return {
                "success": False,
                "error": str(e)
            }

    def find_unused_youtube_stock_candidates(self, needed_seconds: int = 3600) -> List[Dict[str, Any]]:
        """
        Tự động tìm kiếm danh sách video Stock thiên nhiên / phong cảnh 4K trên YouTube
        chưa từng xuất hiện trên Note Online (đồng bộ đa máy), used_stock_links.json và stock_inventory.json.
        """
        # Đồng bộ với Note Online trước khi tìm kiếm để biết các máy khác vừa tải video nào
        try:
            self.sync_cloud_used_links(push_updates=True)
        except Exception:
            pass

        candidates: List[Dict[str, Any]] = []
        seen_ids = set()

        # 0. Nếu người dùng có tạo file custom_stock_links.txt (chứa danh sách link riêng cho máy/kênh này)
        if self.custom_links_txt.exists():
            try:
                with open(self.custom_links_txt, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        vid_id = extract_youtube_id(line)
                        if vid_id and not self.is_yt_id_used(vid_id) and vid_id not in seen_ids:
                            seen_ids.add(vid_id)
                            candidates.append({
                                "id": vid_id,
                                "url": f"https://www.youtube.com/watch?v={vid_id}",
                                "title": f"Custom Link ({vid_id})",
                                "duration": 7200
                            })
            except Exception:
                pass

        # 1. Trộn ngẫu nhiên các từ khóa tìm kiếm trên YouTube để mỗi máy / mỗi kênh lấy nguồn khác nhau
        import yt_dlp
        ydl_opts = self._build_agent_reach_ytdlp_opts(
            {"quiet": True, "extract_flat": True, "no_warnings": True},
            force_refresh_cookies=False,
            warmup_youtube_tab=False,
        )
        shuffled_queries = list(self.AUTO_SEARCH_QUERIES)
        random.shuffle(shuffled_queries)

        discovered: List[Dict[str, Any]] = []
        for query in shuffled_queries[:3]:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    res = ydl.extract_info(f"ytsearch15:{query}", download=False)
                    entries = list(res.get("entries", []) or [])
                    random.shuffle(entries)
                    for entry in entries:
                        vid_id = entry.get("id")
                        dur = float(entry.get("duration") or 0)
                        title = entry.get("title") or ""
                        if not vid_id or vid_id in seen_ids:
                            continue
                        # Chỉ chọn video >= 30 phút (1800s) và chưa từng dùng
                        if dur >= 1800 and not self.is_yt_id_used(vid_id):
                            seen_ids.add(vid_id)
                            discovered.append({
                                "id": vid_id,
                                "url": f"https://www.youtube.com/watch?v={vid_id}",
                                "title": title,
                                "duration": int(dur)
                            })
            except Exception as e:
                print(f"[StockManager] Lưu ý khi tìm kiếm '{query}': {e}")

        random.shuffle(discovered)
        candidates.extend(discovered)

        # 2. Bổ sung danh sách tuyển chọn dự phòng ở cuối (cũng trộn ngẫu nhiên)
        fallback_pool = list(self.DEFAULT_STOCK_CANDIDATES)
        random.shuffle(fallback_pool)
        for item in fallback_pool:
            vid_id = item["id"]
            if not self.is_yt_id_used(vid_id) and vid_id not in seen_ids:
                seen_ids.add(vid_id)
                candidates.append(dict(item))

        return candidates

    def get_pexels_pixabay_keys(self) -> Dict[str, str]:
        """Lấy API Key của Pexels và Pixabay (mặc định tích hợp sẵn Key của chủ hệ thống)."""
        pexels_key = self.DEFAULT_PEXELS_API_KEY
        pixabay_key = self.DEFAULT_PIXABAY_API_KEY
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    st = json.load(f)
                    pexels_key = st.get("pexels_api_key") or pexels_key
                    pixabay_key = st.get("pixabay_api_key") or pixabay_key
            except Exception:
                pass
        return {
            "pexels_api_key": pexels_key.strip(),
            "pixabay_api_key": pixabay_key.strip(),
        }

    def search_unused_pexels_pixabay_clips(
        self,
        count_needed: int = 12,
        exclude_ids: Optional[set] = None,
        sync_cloud_first: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm các video thiên nhiên / phong cảnh chuẩn 720p hoặc 1080p (16:9) chưa từng sử dụng
        từ đồng thời cả 2 kho Pexels Video API và Pixabay Video API.
        Đồng bộ Sổ Cái Cloud Note trước khi tìm kiếm và kiểm tra kép cả Mã ID lẫn Link URL gốc để chống trùng 100%.
        """
        import requests

        if sync_cloud_first:
            try:
                self.sync_cloud_used_links(push_updates=False)
            except Exception:
                pass

        keys = self.get_pexels_pixabay_keys()
        pexels_key = keys["pexels_api_key"]
        pixabay_key = keys["pixabay_api_key"]

        queries = list(self.PEXELS_PIXABAY_QUERIES)
        random.shuffle(queries)
        found_clips: List[Dict[str, Any]] = []
        seen_ids = set(exclude_ids or set())

        target_pool_size = max(count_needed * 2, 36)

        for q in queries:
            if len(found_clips) >= target_pool_size:
                break
            pages_to_try = random.sample(range(1, 15), k=3)

            for page in pages_to_try:
                if len(found_clips) >= target_pool_size:
                    break

                # 1. Tìm trên Pexels Video API (Ưu tiên 720p -> 1080p -> HD ngang 540p..1440p chưa từng tải)
                if pexels_key:
                    for _retry in range(2):
                        try:
                            r_px = requests.get(
                                "https://api.pexels.com/videos/search",
                                params={
                                    "query": q,
                                    "orientation": "landscape",
                                    "per_page": 40,
                                    "page": page,
                                },
                                headers={"Authorization": pexels_key, "User-Agent": "Mozilla/5.0"},
                                timeout=8,
                            )
                            if r_px.status_code == 200:
                                videos = r_px.json().get("videos", []) or []
                                random.shuffle(videos)
                                for v in videos:
                                    raw_id = v.get("id")
                                    if not raw_id:
                                        continue
                                    cid = f"PX_{raw_id}"
                                    if cid in seen_ids or self.is_yt_id_used(cid):
                                        continue
                                    dur = float(v.get("duration") or 0)
                                    if dur < 6:
                                        continue
                                    vfiles = v.get("video_files", []) or []
                                    best_url = None
                                    best_res_label = ""
                                    best_priority = 999
                                    for vf in vfiles:
                                        link = vf.get("link")
                                        w = int(vf.get("width") or 0)
                                        h = int(vf.get("height") or 0)
                                        ft = str(vf.get("file_type") or "video/mp4").lower()
                                        if not link or "mp4" not in ft or w < h:
                                            continue
                                        if h == 720:
                                            prio = 1
                                            res_lbl = "720p"
                                        elif h == 1080:
                                            prio = 2
                                            res_lbl = "1080p"
                                        elif 540 <= h <= 1440:
                                            prio = 3
                                            res_lbl = f"{h}p"
                                        else:
                                            continue
                                        if prio < best_priority:
                                            best_priority = prio
                                            best_url = link
                                            best_res_label = res_lbl
                                    if best_url and not self.is_yt_id_used(cid, best_url):
                                        seen_ids.add(cid)
                                        found_clips.append({
                                            "id": cid,
                                            "source": "Pexels",
                                            "resolution": best_res_label,
                                            "url": best_url,
                                            "title": f"Pexels {best_res_label} #{raw_id} ({q})",
                                            "duration": dur,
                                        })
                            break
                        except Exception as e:
                            if _retry == 1:
                                print(f"[StockManager] Lưu ý tìm Pexels ('{q}'): {e}")
                            time.sleep(0.4)

                # 2. Tìm trên Pixabay Video API (Ưu tiên 720p -> 1080p -> HD ngang 540p..1440p chưa từng tải)
                if pixabay_key:
                    for _retry in range(2):
                        try:
                            r_pb = requests.get(
                                "https://pixabay.com/api/videos/",
                                params={
                                    "key": pixabay_key,
                                    "q": q,
                                    "video_type": "film",
                                    "per_page": 40,
                                    "page": page,
                                },
                                headers={"User-Agent": "Mozilla/5.0"},
                                timeout=8,
                            )
                            if r_pb.status_code == 200:
                                hits = r_pb.json().get("hits", []) or []
                                random.shuffle(hits)
                                for h in hits:
                                    raw_id = h.get("id")
                                    if not raw_id:
                                        continue
                                    cid = f"PB_{raw_id}"
                                    if cid in seen_ids or self.is_yt_id_used(cid):
                                        continue
                                    dur = float(h.get("duration") or 0)
                                    if dur < 6:
                                        continue
                                    vdict = h.get("videos", {}) or {}
                                    best_url = None
                                    best_res_label = ""
                                    best_priority = 999
                                    for stream_name, sinfo in vdict.items():
                                        if not isinstance(sinfo, dict):
                                            continue
                                        link = sinfo.get("url")
                                        w = int(sinfo.get("width") or 0)
                                        ht = int(sinfo.get("height") or 0)
                                        if not link or w < ht:
                                            continue
                                        if ht == 720:
                                            prio = 1
                                            res_lbl = "720p"
                                        elif ht == 1080:
                                            prio = 2
                                            res_lbl = "1080p"
                                        elif 540 <= ht <= 1440:
                                            prio = 3
                                            res_lbl = f"{ht}p"
                                        else:
                                            continue
                                        if prio < best_priority:
                                            best_priority = prio
                                            best_url = link
                                            best_res_label = res_lbl
                                    if best_url and not self.is_yt_id_used(cid, best_url):
                                        seen_ids.add(cid)
                                        tags = h.get("tags", q)
                                        found_clips.append({
                                            "id": cid,
                                            "source": "Pixabay",
                                            "resolution": best_res_label,
                                            "url": best_url,
                                            "title": f"Pixabay {best_res_label} #{raw_id} ({tags})",
                                            "duration": dur,
                                        })
                            break
                        except Exception as e:
                            if _retry == 1:
                                print(f"[StockManager] Lưu ý tìm Pixabay ('{q}'): {e}")
                            time.sleep(0.4)

        random.shuffle(found_clips)
        return found_clips

    def download_pexels_pixabay_stock_reel(
        self,
        slice_minutes: int = 30,
        target_parts: int = 1,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Tải trực tiếp các video 720p & 1080p từ Pexels API & Pixabay API bằng đa luồng CDN siêu tốc,
        GIỮ NGUYÊN BẢN GỐC 100% (-c copy, không re-encode, không drop frame) và nối lặp đủ thời lượng
        yêu cầu (30 phút/cuộn) trong kho STOOK.
        - TẢI LINK NÀO UPDATE NGAY LINK ĐÓ: Ngay khi 1 video tải xong, hệ thống lập tức khóa ID & URL
          vào used_stock_links.json, stock_inventory.json và đẩy lên Cloud Note Online để không bao giờ tải trùng!
        """
        import requests
        from concurrent.futures import ThreadPoolExecutor, as_completed

        target_parts = max(1, int(target_parts))
        slice_seconds = max(300, int(slice_minutes * 60))

        print(f"[StockManager] 🚀 [Pexels + Pixabay API] Đang đồng bộ Sổ Cái chống trùng & tìm video chuẩn 720p/1080p mới cho {target_parts} cuộn Stock ({slice_minutes}p/cuộn)...")
        if progress_callback:
            progress_callback(8.0, f"Đang đồng bộ Sổ Cái chống trùng & tìm video 720p/1080p mới ({target_parts} cuộn {slice_minutes}p)...")

        candidates = self.search_unused_pexels_pixabay_clips(count_needed=target_parts + 15)
        if not candidates:
            return {
                "success": False,
                "error": "Không tìm thấy video 720p/1080p mới từ Pexels / Pixabay API. Vui lòng kiểm tra kết nối mạng!",
            }

        batch_ts = int(time.time())
        folder_name = f"PEXELS_PIXABAY_{batch_ts}"
        target_dir = self.stook_dir / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)
        temp_work_dir = target_dir / "_tmp_clips"
        temp_work_dir.mkdir(parents=True, exist_ok=True)

        cand_lock = threading.Lock()
        cand_cursor = [0]
        reserved_ids: set = set()

        def _pop_next_candidate() -> Optional[Dict[str, Any]]:
            with cand_lock:
                while True:
                    while cand_cursor[0] < len(candidates):
                        item = candidates[cand_cursor[0]]
                        cand_cursor[0] += 1
                        cid = item.get("id")
                        curl = item.get("url")
                        if not cid or cid in reserved_ids or self.is_yt_id_used(cid, curl):
                            continue
                        reserved_ids.add(cid)
                        return item

                    # Nếu hết danh sách ứng viên hiện tại, tuyệt đối KHÔNG quay vòng lại 0 (tránh tải trùng) mà tìm trang mới
                    more_clips = self.search_unused_pexels_pixabay_clips(
                        count_needed=max(16, target_parts),
                        exclude_ids=reserved_ids,
                        sync_cloud_first=False,
                    )
                    fresh_added = 0
                    for mc in more_clips:
                        mc_id = mc.get("id")
                        if mc_id and mc_id not in reserved_ids and not self.is_yt_id_used(mc_id, mc.get("url")):
                            candidates.append(mc)
                            fresh_added += 1
                    if fresh_added == 0:
                        return None

        def _build_one_part(part_idx: int) -> Optional[Dict[str, Any]]:
            # Tự động thử tối đa 5 ứng viên nếu có link mạng chập chờn hoặc lỗi file
            for attempt in range(5):
                clip_info = _pop_next_candidate()
                if not clip_info:
                    return None
                raw_path = temp_work_dir / f"raw_p{part_idx + 1:02d}_try{attempt}.mp4"
                part_out_path = target_dir / f"stock_PXPB_{batch_ts}_part{part_idx + 1:02d}.mp4"
                try:
                    with requests.get(
                        clip_info["url"],
                        headers={"User-Agent": "Mozilla/5.0"},
                        stream=True,
                        timeout=(10, 35),
                    ) as r:
                        r.raise_for_status()
                        with open(raw_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=524288):
                                if chunk:
                                    f.write(chunk)

                    if not raw_path.exists() or raw_path.stat().st_size < 100000:
                        continue

                    raw_dur = get_video_duration(str(raw_path))
                    if raw_dur <= 1.0:
                        continue

                    loops_needed = max(1, int(math.ceil(slice_seconds / raw_dur)))

                    # GIỮ NGUYÊN VIDEO GỐC (-c copy), tắt data/timecode track (-map 0:v:0 -dn -map_metadata -1) để không bao giờ lỗi Drop Frame
                    subprocess.run(
                        [
                            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                            "-stream_loop", str(loops_needed),
                            "-i", str(raw_path),
                            "-t", str(slice_seconds),
                            "-map", "0:v:0",
                            "-dn",
                            "-map_metadata", "-1",
                            "-c", "copy",
                            str(part_out_path),
                        ],
                        check=True,
                        timeout=60,
                    )

                    try:
                        raw_path.unlink()
                    except Exception:
                        pass

                    if part_out_path.exists() and part_out_path.stat().st_size > 1024 * 1024:
                        p_dur = get_video_duration(str(part_out_path))
                        if p_dur >= slice_seconds * 0.8:
                            # TẢI XONG VIDEO NÀO -> KHÓA NGAY LINK ĐÓ VÀO SỔ CÁI LOCAL & ĐỒNG BỘ CLOUD THEO LÔ!
                            self.record_used_yt_link(
                                yt_id=clip_info["id"],
                                url=clip_info["url"],
                                title=clip_info["title"],
                                folder=folder_name,
                                parts_count=1,
                                duration_hours=round(float(p_dur) / 3600.0, 2),
                                sync_cloud=False,
                            )
                            return {
                                "part_idx": part_idx,
                                "path": part_out_path,
                                "duration": p_dur,
                                "clip": clip_info,
                            }
                except Exception as err:
                    print(f"[StockManager] 🔁 Cuộn #{part_idx + 1}/{target_parts} thử lại ứng viên khác ({err})...")
                finally:
                    if raw_path.exists():
                        try:
                            raw_path.unlink()
                        except Exception:
                            pass
            return None

        created_parts: List[Path] = []
        total_dur_sec = 0.0
        used_clip_ids: List[Dict[str, Any]] = []

        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                futs = {pool.submit(_build_one_part, idx): idx for idx in range(target_parts)}
                done_cnt = 0
                for fut in as_completed(futs):
                    done_cnt += 1
                    try:
                        res_item = fut.result()
                    except Exception:
                        res_item = None
                    if res_item:
                        created_parts.append(res_item["path"])
                        total_dur_sec += res_item["duration"]
                        cinfo = res_item["clip"]
                        used_clip_ids.append(cinfo)
                        pct = min(95.0, round((done_cnt / max(1, target_parts)) * 90.0 + 5.0, 1))
                        msg_ok = (
                            f"✅ [Pexels/Pixabay {cinfo.get('resolution', '720p/1080p')}] "
                            f"Hoàn tất Cuộn #{len(created_parts)}/{target_parts} ({res_item['duration']/60:.0f}p) & Đã khóa link [{cinfo['id']}] chống trùng!"
                        )
                        print(f"[StockManager] {msg_ok}")
                        if progress_callback:
                            progress_callback(pct, msg_ok)
        finally:
            shutil.rmtree(temp_work_dir, ignore_errors=True)

        if not created_parts:
            return {
                "success": False,
                "error": "Không thể tải cuộn Stock từ Pexels/Pixabay.",
            }

        try:
            threading.Thread(
                target=self.sync_cloud_used_links,
                kwargs={"push_updates": True, "force_push": True},
                daemon=True,
            ).start()
        except Exception:
            pass

        self.scan_and_update_inventory()

        dl_hours = round(total_dur_sec / 3600.0, 2)
        print(f"[StockManager] 🎉 [Pexels + Pixabay API] Đã hoàn tất {len(created_parts)}/{target_parts} cuộn Stock 720p/1080p gốc ({dl_hours} giờ) tại {target_dir.name} & Đã update toàn bộ link lên Sổ Cái chống trùng!")
        return {
            "success": True,
            "yt_id": f"PXPB_{batch_ts}",
            "title": f"Pexels & Pixabay 720p/1080p Pack ({len(created_parts)} cuộn)",
            "downloaded_hours": dl_hours,
            "parts_count": len(created_parts),
            "folder": str(target_dir),
            "locked_ids": [c["id"] for c in used_clip_ids],
        }

    def ensure_minimum_stock_hours(
        self,
        target_hours: float = 30.0,
        slice_minutes: int = 30,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Đảm bảo trong kho STOOK luôn có đủ tối thiểu `target_hours` (mặc định 30 tiếng, hoặc 60–100 tiếng) video khả dụng.
        - SỬ DỤNG 100% PEXELS VIDEO API & PIXABAY VIDEO API (CDN trực tiếp siêu tốc, KHÔNG BAO GIỜ gọi YouTube yt-dlp để tránh lỗi chặn Bot/Cookie).
        - Tự động chia thành nhiều đợt tải liên tiếp cho đến khi đạt đủ `target_hours`.
        """
        self.save_target_stock_hours(target_hours)
        self.scan_and_update_inventory()
        st = self.get_all_stocks()
        initial_hours = st["available_raw_hours"]
        current_hours = initial_hours

        if current_hours >= target_hours:
            msg = f"✅ Kho Stock đã đủ thời lượng ({current_hours:.2f}h / {target_hours:.1f}h mục tiêu — {st['available_uses_count']} lượt xuất khả dụng)."
            if progress_callback:
                progress_callback(100.0, msg)
            return {
                "success": True,
                "already_sufficient": True,
                "initial_hours": initial_hours,
                "current_hours": current_hours,
                "target_hours": target_hours,
                "downloaded_videos": 0,
                "downloaded_parts": 0,
                "message": msg,
                "stocks": st
            }

        missing_hours = round(target_hours - current_hours, 2)

        # KIỂM TRA MẠNG INTERNET TRƯỚC KHI TẢI TỪ PEXELS & PIXABAY API
        if not check_internet_connection():
            offline_msg = (
                f"⚠️ Máy đang KHÔNG CÓ MẠNG INTERNET nên không thể tự tải bù {missing_hours:.1f}h từ Pexels & Pixabay API. "
                f"Hiện trong kho trên máy đang có sẵn {current_hours:.2f}h ({st['available_uses_count']} lượt xuất khả dụng Offline)."
            )
            print(f"[StockManager] {offline_msg}")
            return {
                "success": False,
                "offline": True,
                "error": offline_msg,
                "current_hours": current_hours,
                "target_hours": target_hours,
                "stocks": st
            }
        print(f"[StockManager] ⚡ Kho Stock hiện có {current_hours:.2f}h / {target_hours:.1f}h (Thiếu {missing_hours:.2f}h). Bắt đầu tự động tải bù video 720p/1080p từ Pexels & Pixabay API CDN...")
        if progress_callback:
            progress_callback(5.0, f"Kho hiện có {current_hours:.1f}h / {target_hours:.1f}h (Thiếu {missing_hours:.1f}h). Đang tải video Stock 720p/1080p từ Pexels & Pixabay API...")

        downloaded_videos = 0
        downloaded_parts = 0
        downloaded_titles = []
        last_error = None

        # CHỈ DÙNG 100% PEXELS VIDEO API & PIXABAY VIDEO API (Chia theo từng lô tối đa 24 cuộn = 12 giờ/lô cho tới khi đủ target_hours, tuyệt đối không gọi YouTube yt-dlp)
        max_rounds = 12
        for round_idx in range(max_rounds):
            st = self.get_all_stocks()
            current_hours = st["available_raw_hours"]
            if current_hours >= target_hours:
                break

            still_missing_sec = max(
                slice_minutes * 60,
                int(math.ceil(((target_hours - current_hours) * 3600.0) / (slice_minutes * 60)) * (slice_minutes * 60))
            )
            total_parts_needed = max(1, int(math.ceil(still_missing_sec / (slice_minutes * 60))))
            batch_parts = min(24, total_parts_needed)
            still_missing_h = round(still_missing_sec / 3600.0, 2)

            print(
                f"[StockManager] 🚀 [Pexels & Pixabay API — Đợt {round_idx + 1}] "
                f"Đang tải bù {batch_parts} cuộn ({still_missing_h}h còn thiếu | Kho: {current_hours:.1f}h/{target_hours:.1f}h)..."
            )
            pxpb_res = self.download_pexels_pixabay_stock_reel(
                slice_minutes=slice_minutes,
                target_parts=batch_parts,
                progress_callback=progress_callback,
            )
            if pxpb_res.get("success") and pxpb_res.get("parts_count", 0) > 0:
                downloaded_videos += 1
                downloaded_parts += pxpb_res.get("parts_count", 0)
                downloaded_titles.append(pxpb_res.get("title", "Pexels & Pixabay 720p"))
            else:
                last_error = pxpb_res.get("error")
                break

        st_final = self.get_all_stocks()
        final_hours = st_final["available_raw_hours"]

        if final_hours >= target_hours or downloaded_parts > 0:
            done_msg = (
                f"🎉 Đã tự động tải bù thêm {downloaded_videos} video mới ({downloaded_parts} part 30p)! "
                f"Tổng thời lượng kho hiện tại: {final_hours:.2f} giờ / {target_hours:.1f} giờ mục tiêu ({st_final['available_uses_count']} lượt xuất)."
            )
            if progress_callback:
                progress_callback(100.0, done_msg)
            return {
                "success": True,
                "already_sufficient": False,
                "initial_hours": initial_hours,
                "current_hours": final_hours,
                "target_hours": target_hours,
                "downloaded_videos": downloaded_videos,
                "downloaded_parts": downloaded_parts,
                "downloaded_titles": downloaded_titles,
                "message": done_msg,
                "stocks": st_final
            }

        return {
            "success": False,
            "error": last_error or "Không thể tải thêm video Stock mới.",
            "current_hours": final_hours,
            "target_hours": target_hours
        }
