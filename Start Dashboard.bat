@echo off
title SKM Dashboard Server - RSUD Mimika
echo ============================================================
echo   SKM Dashboard Server - RSUD Mimika
echo ============================================================
echo.
echo   Starting local server with Google Sheets proxy...
echo   This eliminates CORS issues by fetching data server-side.
echo.
echo   Dashboard will open automatically in your browser.
echo   Press Ctrl+C to stop the server.
echo.

cd /d "%~dp0"
python server.py

pause
