@echo off
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name RoofStudio_v1.0 --icon app_icon.ico --add-data "app_icon.png;." --add-data "app_icon.ico;." roofstudio.py
pause
