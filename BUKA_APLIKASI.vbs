Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

' Hentikan proses lama jika ada yang tertahan di port 8501
WshShell.Run "cmd /c for /f ""tokens=5"" %a in ('netstat -aon ^| findstr :8501') do taskkill /f /pid %a", 0, True

' Jalankan batch runner
WshShell.Run "cmd /c """ & scriptDir & "\JALANKAN_APLIKASI.bat""", 0, False

