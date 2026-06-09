@echo off
cd /d C:\OpenComputersSim
echo Installing dependencies...
pip install -r requirements.txt
echo Starting OpenComputersSim...
python run.py
pause
