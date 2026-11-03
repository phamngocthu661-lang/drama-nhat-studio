@echo off
chcp 65001 >nul
title CẬP NHẬT NHANH DRAMA NHẬT STUDIO (KHÔNG MẤT KỊCH BẢN & BẢN QUYỀN)
color 0A

echo ============================================================================
echo   CÔNG CỤ CẬP NHẬT NHANH — DRAMA NHẬT STUDIO (BẢN TỔNG HỢP ĐẦY ĐỦ)
echo   - Giữ nguyên 100%% Kịch bản đã tạo (projects/, saved_ideas.json)
echo   - Giữ nguyên 100%% Key bản quyền (license.json) ^& Chrome (BROWSER_PROFILE)
echo ============================================================================
echo.

set "SRC_DIR=%~dp0"
if "%SRC_DIR:~-1%"=="\" set "SRC_DIR=%SRC_DIR:~0,-1%"

:: 1. Tắt tiến trình cũ (Drama_Nhat_Studio.exe, cổng 8899 và VOICEVOX run.exe) để nạp giao diện & code mới 100%
echo [1/4] Đang làm mới tiến trình Studio ^& Voice Engine ngầm...
taskkill /F /IM Drama_Nhat_Studio.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8899" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
taskkill /F /IM run.exe >nul 2>&1

:: 2. Tự động nhận diện thư mục cài đặt chính nếu khách giải nén ra thư mục con Drama_Nhat_Studio_Ban_Update_Nhanh
set "TARGET_DIR=%SRC_DIR%"
if exist "%SRC_DIR%\bin" (
    set "TARGET_DIR=%SRC_DIR%"
) else if exist "%SRC_DIR%\..\bin" (
    for %%I in ("%SRC_DIR%\..") do set "TARGET_DIR=%%~fI"
) else if exist "%SRC_DIR%\..\Drama_Nhat_Studio\bin" (
    for %%I in ("%SRC_DIR%\..\Drama_Nhat_Studio") do set "TARGET_DIR=%%~fI"
) else if exist "%SRC_DIR%\..\TOOL_NHAT_DRAMA\bin" (
    for %%I in ("%SRC_DIR%\..\TOOL_NHAT_DRAMA") do set "TARGET_DIR=%%~fI"
)

if /I not "%SRC_DIR%"=="%TARGET_DIR%" (
    echo [2/4] Phát hiện giải nén ra thư mục phụ. Đang tự động chép bản cập nhật vào:
    echo       "%TARGET_DIR%"
    xcopy "%SRC_DIR%\backend\*" "%TARGET_DIR%\backend\" /E /I /Y /Q >nul
    xcopy "%SRC_DIR%\frontend\*" "%TARGET_DIR%\frontend\" /E /I /Y /Q >nul
    xcopy "%SRC_DIR%\adas_skills\*" "%TARGET_DIR%\adas_skills\" /E /I /Y /Q >nul
    if exist "%SRC_DIR%\agent_reach" xcopy "%SRC_DIR%\agent_reach\*" "%TARGET_DIR%\agent_reach\" /E /I /Y /Q >nul
    if exist "%SRC_DIR%\yt_dlp_ejs" xcopy "%SRC_DIR%\yt_dlp_ejs\*" "%TARGET_DIR%\yt_dlp_ejs\" /E /I /Y /Q >nul
    xcopy "%SRC_DIR%\app\*" "%TARGET_DIR%\app\" /E /I /Y /Q >nul
    if exist "%SRC_DIR%\assets\voices" xcopy "%SRC_DIR%\assets\voices\*" "%TARGET_DIR%\assets\voices\" /E /I /Y /Q >nul
    for %%F in (Drama_Nhat_Studio.exe main.py install_setup.py requirements.txt voice_engine_config.json Chay_App.bat Cai_Dat_May_Moi.bat CHI_TIET_BAN_CAP_NHAT_NHANH.txt CHI_TIET_BAN_CAP_NHAT_NHANH.md QUY_TRINH_HOAT_DONG.md TIEN_DO_CODE.md) do (
        if exist "%SRC_DIR%\%%F" copy /Y "%SRC_DIR%\%%F" "%TARGET_DIR%\%%F" >nul
    )
    echo       -^> Đã đồng bộ 100%% file cập nhật vào thư mục chính!
) else (
    echo [2/4] Đang cập nhật trực tiếp tại thư mục chính: "%TARGET_DIR%"
    xcopy "%TARGET_DIR%\backend\*" "%TARGET_DIR%\app\backend\" /E /I /Y /Q >nul
    xcopy "%TARGET_DIR%\frontend\*" "%TARGET_DIR%\app\frontend\" /E /I /Y /Q >nul
    xcopy "%TARGET_DIR%\adas_skills\*" "%TARGET_DIR%\app\adas_skills\" /E /I /Y /Q >nul
    if exist "%TARGET_DIR%\agent_reach" xcopy "%TARGET_DIR%\agent_reach\*" "%TARGET_DIR%\app\agent_reach\" /E /I /Y /Q >nul
    if exist "%TARGET_DIR%\yt_dlp_ejs" xcopy "%TARGET_DIR%\yt_dlp_ejs\*" "%TARGET_DIR%\app\yt_dlp_ejs\" /E /I /Y /Q >nul
    copy /Y "%TARGET_DIR%\main.py" "%TARGET_DIR%\app\main.py" >nul 2>&1
    copy /Y "%TARGET_DIR%\voice_engine_config.json" "%TARGET_DIR%\app\voice_engine_config.json" >nul 2>&1
)

echo [3/4] Đã kích hoạt toàn bộ tính năng mới:
echo       + Bật sẵn Server Voice GPU (VOICEVOX DirectML GPU 0.97x / OmniVoice CUDA GPU)
echo       + Nhận diện 100%% Voice mới khi bấm Render ^& Tự cân đối đa luồng ~90%% GPU/CPU
echo       + Tách 3 Đoạn Chat độc lập cho Part A/B/C + Nút [Viết Tiếp] cho kịch bản thiếu Part (P16, P17)
echo       + Khóa cố định Model viết ở mức Thinking effort: Medium
echo       + Mỗi kịch bản chỉ tạo đúng 1 Thumbnail duy nhất ({MA_ID}_THUMBNAIL_1.png)
echo.
echo [4/4] Đang khởi động Drama Nhật Studio...
cd /d "%TARGET_DIR%"
if exist "%TARGET_DIR%\Drama_Nhat_Studio.exe" (
    start "" "%TARGET_DIR%\Drama_Nhat_Studio.exe"
) else (
    call "%TARGET_DIR%\Chay_App.bat"
)
timeout /t 3 >nul
exit /b 0
