Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\SUKMA AJI\.antigravity-ide\DATA CURAH HUJAN"

' Hentikan proses lama jika ada yang tertahan di port 8501
WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr :8501') do taskkill /f /pid %a", 0, True

' Jalankan server streamlit di latar belakang tanpa jendela hitam (0 = hidden)
WshShell.Run """.venv\Scripts\python.exe"" -m streamlit run app.py --server.port=8501 --server.headless=false", 0, False

' Beri jeda 2 detik lalu buka browser
WScript.Sleep 2000
WshShell.Run "http://localhost:8501"

