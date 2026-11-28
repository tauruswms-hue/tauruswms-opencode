@echo off
setlocal EnableExtensions
chcp 65001 >nul

rem ============================================================================
rem Taurus WMS - instalar los servicios de Windows con NSSM
rem
rem Ejecutar como Administrador:
rem   C:\taurus\app\instalar_servicios.bat
rem
rem Crea/actualiza:
rem   TaurusWMS   -> puerto 5000 (app:app)
rem   TaurusAdmin -> puerto 5001 (admin:app)
rem
rem Usa waitress (servidor WSGI), nunca el servidor de desarrollo de Flask.
rem Los logs van a C:\taurus\logs\ con rotacion a 10 MB.
rem
rem Si .env tiene APP_ENV=production, los servicios escuchan solo en
rem 127.0.0.1 y hay que poner un proxy inverso con HTTPS delante.
rem Para LAN con APP_ENV=development escuchan en 0.0.0.0.
rem ============================================================================

set "APP_DIR=C:\taurus\app"
set "LOG_DIR=C:\taurus\logs"
set "NSSM=C:\herramientas\nssm.exe"
set "WAITRESS=%APP_DIR%\.venv\Scripts\waitress-serve.exe"
set "HOST=0.0.0.0"
set "THREADS=8"

if exist "%APP_DIR%\.env" (
    findstr /I /C:"APP_ENV=production" "%APP_DIR%\.env" >nul
    if not errorlevel 1 (
        set "HOST=127.0.0.1"
        echo AVISO: APP_ENV=production; los servicios quedan en 127.0.0.1.
        echo        Ponga un proxy inverso con HTTPS delante antes de publicar.
    )
)

if not exist "%NSSM%" (
    echo Falta NSSM en %NSSM%
    exit /b 1
)
if not exist "%WAITRESS%" (
    echo Falta waitress-serve.exe en %WAITRESS%
    echo Corre antes: C:\taurus\app\.venv\Scripts\python.exe -m pip install waitress
    exit /b 1
)
if not exist "%APP_DIR%\app.py" (
    echo No existe %APP_DIR%\app.py
    exit /b 1
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo === Instalando servicios con waitress ===
echo Host: %HOST%   Threads: %THREADS%
echo.

call :instalar TaurusWMS 5000 app:app wms.log
if errorlevel 1 goto :abort
echo.

call :instalar TaurusAdmin 5001 admin:app admin.log
if errorlevel 1 goto :abort

echo.
echo === Listo ===
echo   TaurusWMS   : http://%HOST%:5000
echo   TaurusAdmin : http://%HOST%:5001/admin
echo   Logs        : %LOG_DIR%
echo.
echo Si APP_ENV=development y es LAN, abrir 5000/5001 en el firewall.
echo Si APP_ENV=production, publicar solo 443 y NO abrir 5000/5001.
endlocal
exit /b 0

:instalar
set "SVC=%~1"
set "PORT=%~2"
set "MODULE=%~3"
set "LOG=%~4"
set "ESTADO="

echo --- %SVC% (puerto %PORT%, modulo %MODULE%) ---

"%NSSM%" status "%SVC%" >nul 2>&1
if not errorlevel 1 (
    echo Deteniendo servicio anterior...
    "%NSSM%" stop "%SVC%" >nul 2>&1
    "%NSSM%" remove "%SVC%" confirm >nul 2>&1
    if errorlevel 1 goto :abort
)

"%NSSM%" install "%SVC%" "%WAITRESS%"
if errorlevel 1 goto :abort

"%NSSM%" set "%SVC%" AppDirectory "%APP_DIR%"
if errorlevel 1 goto :abort
"%NSSM%" set "%SVC%" AppParameters "--listen=%HOST%:%PORT% --threads=%THREADS% %MODULE%"
if errorlevel 1 goto :abort
"%NSSM%" set "%SVC%" AppStdout "%LOG_DIR%\%LOG%"
if errorlevel 1 goto :abort
"%NSSM%" set "%SVC%" AppStderr "%LOG_DIR%\%LOG%"
if errorlevel 1 goto :abort
"%NSSM%" set "%SVC%" AppRotateFiles 1
if errorlevel 1 goto :abort
"%NSSM%" set "%SVC%" AppRotateBytes 10485760
if errorlevel 1 goto :abort
"%NSSM%" set "%SVC%" Start SERVICE_AUTO_START
if errorlevel 1 goto :abort

"%NSSM%" start "%SVC%"
if errorlevel 1 goto :abort

for /f %%S in ('%NSSM% status %SVC%') do set "ESTADO=%%S"
echo Estado: %ESTADO%
exit /b 0

:abort
echo.
echo ERROR instalando %SVC%. Verificar que se ejecuta como Administrador
echo y que las rutas de NSSM y waitress sean correctas.
endlocal
exit /b 1
