@echo off
setlocal
cd /d "%~dp0"
echo ===================================================
echo   PsychNews (精神科看護学 学術フィード) を起動しています...
echo ===================================================
echo.

:: バックグラウンドで Python サーバーを起動
:: すでに起動している場合はエラーになりますが、ブラウザは開きます
start /b python scripts/server.py

:: サーバー起動を少し待つ
timeout /t 2 >nul

:: ブラウザでアプリを開く
echo ブラウザでアプリを開きます...
start http://localhost:8000

echo.
echo 起動しました！このウィンドウは閉じて構いません。
timeout /t 3 >nul
