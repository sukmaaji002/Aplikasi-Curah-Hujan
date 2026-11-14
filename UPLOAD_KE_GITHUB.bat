@echo off
title Upload Aplikasi Curah Hujan ke GitHub
cd /d "%~dp0"
cls
echo ========================================================
echo   UPLOAD APLIKASI CURAH HUJAN KE GITHUB
echo ========================================================
echo.
echo Sedang mengunggah data ke:
echo https://github.com/sukmaaji002/Aplikasi-Curah-Hujan.git
echo.
echo Jika muncul jendela popup atau tab browser, silakan klik
echo "Sign in with your browser" / "Authorize git-ecosystem".
echo.
git add .
git commit -m "Fix duplicate column name in monthly aggregation"
git push -u origin main
echo.
if %ERRORLEVEL% equ 0 (
    echo ========================================================
    echo   BERHASIL! Seluruh file sukses ter-upload ke GitHub.
    echo ========================================================
) else (
    echo ========================================================
    echo   Ada kendala saat upload. Silakan periksa koneksi.
    echo ========================================================
)
echo.
pause

