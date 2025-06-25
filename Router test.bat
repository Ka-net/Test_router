@echo off
:: Skift til den mappe, hvor batch-filen ligger
cd /d "%~dp0"

:: Anmod om administratorrettigheder og kør Python-scriptet
powershell -Command "Start-Process python -ArgumentList '\"%~dp0GUI.py\"' -Verb runAs"
