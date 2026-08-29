del .\build\PID /Q
del .\dist\PID.exe /Q
py -3 -m PyInstaller PID.spec
pause
