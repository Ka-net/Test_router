@echo off
:: Anmod om administratorrettigheder og kør Python-scriptet
powershell -Command "Start-Process cmd -ArgumentList '/c cd /d %CD% && python \"C:\Users\IT-Tekniker\Desktop\Ny mappe\set_static_ip.py\" || echo Fejl ved kørsel af Python-scriptet' -Verb runAs"

