@echo off
pip install -r requirements-dev.txt
pyinstaller --onefile --add-data 'img\\Phillies.png;img' main.py

