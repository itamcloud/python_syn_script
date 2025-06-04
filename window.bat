@echo off
REM filepath: d:\itamcloud\KGT_Python_sync\KGT_Python_sync\setup_run.bat

REM Check Python version
python --version

REM Create virtual environment
python -m venv myenv

REM Activate virtual environment
call myenv\Scripts\activate

REM Install requirements
pip install -r requirements.txt

REM Run the main script
python -m src.main