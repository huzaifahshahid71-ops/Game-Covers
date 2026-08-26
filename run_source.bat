@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
py Game_Covers.py
pause
