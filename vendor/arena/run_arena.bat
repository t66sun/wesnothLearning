@echo off
cd /d "%~dp0"
python arena.py
if errorlevel 1 pause
