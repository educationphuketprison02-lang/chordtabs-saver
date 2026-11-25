@echo off
chcp 65001 >nul
cd /d "%~dp0"
pip install playwright customtkinter pyinstaller
pyinstaller --noconfirm --onefile --windowed --name ChordtabsSaver --icon icon.ico ^
  --collect-data customtkinter --collect-all playwright --hidden-import gui chord_saver.py
echo.
echo ไฟล์ exe อยู่ที่ dist\ChordtabsSaver.exe
pause
