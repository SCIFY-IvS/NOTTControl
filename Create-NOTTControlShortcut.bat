@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0nottcontrol\windows\Create-NOTTControlShortcut.ps1" %*
