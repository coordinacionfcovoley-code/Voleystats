@echo off
title Ferro Voley - VoleyStats
cd /d "%~dp0"
echo Iniciando VoleyStats Ferro en http://localhost:8502 ...
python -m streamlit run app.py --server.port 8502
pause
