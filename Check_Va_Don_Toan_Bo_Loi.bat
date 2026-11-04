@echo off
chcp 65001 >nul
title DRAMA NHAT STUDIO - CHECK VA DON TOAN BO KICH BAN + VIDEO LOI (PHUONG AN 1)
cd /d "%~dp0"

echo ============================================================================
echo   DRAMA NHAT STUDIO - CONG CU CHECK VA DON TOAN BO LOI [LOCKED_TITLE]
echo   (Phuong an 1: Quet sach .txt/.srt + Cat bo doan doc nham trong .wav/.mp4)
echo ============================================================================
echo.

if exist "python\python.exe" (
    set "PY_EXE=python\python.exe"
) else (
    set "PY_EXE=python"
)

"%PY_EXE%" -c "import os, sys; sys.path.insert(0, os.getcwd()); from backend.voice_service import check_and_repair_all_projects_sync; p_dir = os.path.join(os.getcwd(), 'projects'); res = check_and_repair_all_projects_sync(p_dir, log_cb=lambda m: print(m)); print('\n============================================================================'); print(f'HOAN TAT! Da quet {res.get(\"total_projects\",0)} du an ({res.get(\"elapsed_sec\",0)}s)'); print(f'- Kich ban (.txt) da sua: {res.get(\"scripts_repaired_count\",0)} ma ({res.get(\"total_leaked_lines_removed\",0)} dong)'); print(f'- Phu de (.srt) da don:   {res.get(\"srts_repaired_count\",0)} file'); print(f'- Voice (.wav) da cat:    {res.get(\"voices_repaired_count\",0)} file'); print(f'- Video (.mp4) da cat:    {res.get(\"videos_repaired_count\",0)} video'); print(f'- Bao cao luu tai:        {res.get(\"report_path\",\"\")}'); print('============================================================================')"

echo.
pause
