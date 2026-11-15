@echo off
title Aplikasi Data Curah Hujan
cd /d "%~dp0"
cls
echo ========================================================
echo   MEMULAI APLIKASI ANALISIS DATA CURAH HUJAN
echo ========================================================
echo.
echo Sedang menyiapkan sistem dan membuka browser...
echo.

:: Deteksi Python executable
set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    ) else (
        where py >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_CMD=py"
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python tidak ditemukan di sistem.
    echo Silakan install Python 3.10 atau 3.11 terlebih dahulu.
    pause
    exit /b 1
)

:: Bersihkan proses lama di port 8501 jika ada
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8501') do taskkill /f /pid %%a >nul 2>&1

:: Buka browser dan jalankan aplikasi
start "" http://localhost:8501
"%PYTHON_CMD%" -m streamlit run app.py --server.port=8501 --server.headless=false

if errorlevel 1 (
    echo.
    echo Terjadi kendala saat menjalankan aplikasi. Tekan tombol apa saja untuk menutup.
    pause
)
