import os
import sys
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable


def run_pip(args, desc=""):
    if desc:
        print(f"\n>>> {desc}")
    cmd = [PYTHON_EXE, "-m", "pip"] + args
    print("    Lệnh:", " ".join(cmd))
    res = subprocess.run(cmd)
    return res.returncode == 0


def check_module(mod_name: str) -> bool:
    res = subprocess.run(
        [PYTHON_EXE, "-c", f"import {mod_name}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return res.returncode == 0


def main():
    print("================================================================================")
    print("🚀 [DRAMA NHẬT STUDIO] TRÌNH TỰ ĐỘNG TẢI & CÀI ĐẶT THƯ VIỆN CHO MÁY MỚI")
    print(f"🐍 Python đang dùng: {PYTHON_EXE}")
    print(f"📂 Thư mục gốc:      {ROOT_DIR}")
    print("================================================================================")

    # Lưu đường dẫn Python chuẩn vào python_path.txt và %LOCALAPPDATA% để khi cập nhật hoặc giải nén thư mục mới vẫn nhớ đúng bản Python đã cài thư viện
    try:
        with open(ROOT_DIR / "python_path.txt", "w", encoding="utf-8") as f:
            f.write(PYTHON_EXE.strip())
        local_app = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        for app_sub in ("Drama_Nhat_Studio", "DramaNhatStudio"):
            d_sub = local_app / app_sub
            d_sub.mkdir(parents=True, exist_ok=True)
            (d_sub / "python_path.txt").write_text(PYTHON_EXE.strip(), encoding="utf-8")
    except Exception:
        pass

    # 1. Đảm bảo pip hoạt động và được nâng cấp
    print("\n[BƯỚC 1/4] Kiểm tra và nâng cấp trình quản lý gói PIP...")
    subprocess.run([PYTHON_EXE, "-m", "ensurepip", "--upgrade"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    run_pip(["install", "--upgrade", "pip", "setuptools", "wheel"], "Đang nâng cấp pip, setuptools, wheel...")

    # 2. Cài đặt PyTorch + TorchAudio (Ưu tiên CUDA GPU, dự phòng bản chuẩn nếu máy không hỗ trợ)
    print("\n[BƯỚC 2/4] Kiểm tra và cài đặt PyTorch + TorchAudio (GPU CUDA)...")
    has_nvidia_gpu = False
    try:
        gpu_res = subprocess.run(["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        has_nvidia_gpu = (gpu_res.returncode == 0)
    except Exception:
        has_nvidia_gpu = False

    has_torch = check_module("torch") and check_module("torchaudio")
    if has_torch and has_nvidia_gpu:
        cuda_ok = subprocess.run(
            [PYTHON_EXE, "-c", "import torch; raise SystemExit(0 if torch.cuda.is_available() else 1)"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ).returncode == 0
        if not cuda_ok:
            print("[!] Phát hiện card rời NVIDIA nhưng PyTorch hiện tại là bản CPU. Đang nâng cấp lên bản GPU CUDA...")
            has_torch = False

    if not has_torch:
        ok_cu121 = run_pip(
            ["install", "--prefer-binary", "torch==2.5.1", "torchaudio==2.5.1", "--index-url", "https://download.pytorch.org/whl/cu121"],
            "Đang tải PyTorch 2.5.1 GPU (CUDA 12.1)..."
        )
        if not ok_cu121 or not check_module("torch"):
            print("[!] Đang chuyển sang tải PyTorch GPU (CUDA 12.4)...")
            ok_cu124 = run_pip(
                ["install", "--prefer-binary", "torch>=2.5.0,<2.9.0", "torchaudio>=2.5.0,<2.9.0", "--index-url", "https://download.pytorch.org/whl/cu124"],
                "Đang tải PyTorch GPU (CUDA 12.4)..."
            )
            if not ok_cu124 or not check_module("torch"):
                run_pip(["install", "--prefer-binary", "torch>=2.5.0,<2.9.0", "torchaudio>=2.5.0,<2.9.0"], "Đang tải PyTorch bản tiêu chuẩn...")
    else:
        print("✅ PyTorch & TorchAudio (GPU CUDA) đã được cài đặt sẵn!")

    # 3. Cài đặt toàn bộ thư viện trong requirements.txt
    print("\n[BƯỚC 3/4] Đang tải và cài đặt các thư viện AI VoiceStudio & Giao diện...")
    req_file = ROOT_DIR / "requirements.txt"
    if req_file.exists():
        ok_req = run_pip(
            ["install", "--prefer-binary", "-r", str(req_file)],
            "Đang cài đặt danh sách thư viện từ requirements.txt..."
        )
        if not ok_req:
            print("[!] Đang thử cài đặt từng thư viện quan trọng...")
            with open(req_file, "r", encoding="utf-8") as f:
                for line in f:
                    pkg = line.strip()
                    if pkg and not pkg.startswith("#"):
                        run_pip(["install", "--prefer-binary", pkg])
    else:
        essential_pkgs = [
            "fastapi", "uvicorn", "websockets", "websocket-client", "pywebview", "yt-dlp[default]", "yt-dlp-ejs",
            "loguru", "pyyaml", "pydantic", "aiofiles", "requests", "transformers", "accelerate",
            "safetensors", "huggingface-hub", "librosa", "soundfile", "pydub",
            "scipy", "numpy", "tqdm", "playwright", "Pillow", "cryptography", "faster-whisper"
        ]
        run_pip(["install", "--prefer-binary"] + essential_pkgs, "Đang cài đặt các thư viện thiết yếu...")

    # Kiểm tra lại các thư viện cốt lõi
    critical_mods = [
        "torch", "torchaudio", "fastapi", "uvicorn", "webview", "yt_dlp",
        "transformers", "huggingface_hub", "playwright", "PIL", "cryptography", "faster_whisper"
    ]
    missing = [m for m in critical_mods if not check_module(m)]
    if missing:
        print(f"⚠️ Đang cài bổ sung các gói còn thiếu: {missing}")
        pkg_map = {
            "webview": "pywebview",
            "yt_dlp": "yt-dlp",
            "huggingface_hub": "huggingface-hub",
            "PIL": "Pillow",
            "faster_whisper": "faster-whisper",
        }
        for m in missing:
            run_pip(["install", "--prefer-binary", pkg_map.get(m, m)])

    # Tự động đảm bảo onnxruntime-gpu được kích hoạt trên máy có card NVIDIA RTX/GTX
    if has_nvidia_gpu:
        has_ort_gpu = subprocess.run(
            [PYTHON_EXE, "-c", "import onnxruntime as ort; raise SystemExit(0 if 'CUDAExecutionProvider' in ort.get_available_providers() else 1)"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ).returncode == 0
        if not has_ort_gpu:
            print("⚡ Phát hiện GPU NVIDIA: Đang nâng cấp onnxruntime sang bản onnxruntime-gpu (CUDA)...")
            subprocess.run([PYTHON_EXE, "-m", "pip", "uninstall", "-y", "onnxruntime"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            run_pip(["install", "--prefer-binary", "onnxruntime-gpu"], "Đang cài đặt onnxruntime-gpu...")

    # 4. Kiểm tra và tự động tải Model AI OmniVoice (1.6 GB) nếu chưa có
    print("\n[BƯỚC 4/4] Kiểm tra bộ não giọng đọc AI Nhật Bản (OmniVoice)...")
    model_dir = ROOT_DIR / "pretrained_models" / "OmniVoice"
    main_weights = model_dir / "model.safetensors"
    tok_weights = model_dir / "audio_tokenizer" / "model.safetensors"

    model_ready = (
        main_weights.exists() and main_weights.stat().st_size > 1_000_000_000
        and tok_weights.exists() and tok_weights.stat().st_size > 800_000_000
    )
    if not model_ready:
        print("📥 Đang tự động tải Model AI OmniVoice từ HuggingFace về máy (Khoảng 1.6 GB)...")
        print("   Vui lòng đợi cho đến khi tải xong 100%...")
        try:
            from huggingface_hub import snapshot_download
            model_dir.mkdir(parents=True, exist_ok=True)
            snapshot_download(
                repo_id="k2-fsa/OmniVoice",
                local_dir=str(model_dir)
            )
            print("✅ Đã tải hoàn tất Model AI OmniVoice!")
        except Exception as e:
            print(f"⚠️ Lưu ý khi tải trước Model AI: {e}")
            print("   (Hệ thống sẽ tự động tải lại khi bạn bấm chạy sản xuất video đầu tiên).")
    else:
        print("✅ Model AI OmniVoice đã có sẵn đầy đủ trong máy!")

    print("\n================================================================================")
    print("🎉 [HOÀN TẤT 100%] ĐÃ CÀI ĐẶT XONG TOÀN BỘ THƯ VIỆN & MODEL AI!")
    print("👉 Bây giờ ứng dụng Drama_Nhat_Studio.exe sẽ tự động mở lên.")
    print("================================================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
