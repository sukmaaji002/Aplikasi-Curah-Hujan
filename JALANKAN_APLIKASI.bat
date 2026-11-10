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

:: Bersihkan proses lama di port 8501 jika ada
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8501') do taskkill /f /pid %%a >nul 2>&1

:: Buka browser dan jalankan aplikasi
start "" http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py --server.port=8501 --server.headless=false

pause
