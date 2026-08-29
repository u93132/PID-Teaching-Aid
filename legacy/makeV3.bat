del .\build\PID /Q
del .\dist\PID.exe /Q
py -2 -m PyInstaller --onefile PID.spec
pause                                                                              