@echo off
echo Setting up Chatbot Backend...

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip to latest version
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install/update dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Start the application
echo Starting the application...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause