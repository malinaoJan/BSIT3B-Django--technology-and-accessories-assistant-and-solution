@echo off
cd /d "C:\Users\maria\OneDrive\Desktop\TECHFIX"
echo Starting TECHFIX Django server...
"C:\Users\maria\OneDrive\Desktop\TECHFIX\venv\Scripts\python.exe" -u manage.py runserver 127.0.0.1:8000 --noreload
pause
