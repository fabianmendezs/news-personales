@echo off
cd /d "C:\Users\fabia\OneDrive\Escritorio\Data Science\Python\00 Proyectos\news-personales"
"venv\Scripts\python.exe" news_diarias.py >> logs\news.log 2>&1
echo Ejecutado: %date% %time% >> logs\news.log
