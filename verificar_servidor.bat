@echo off
setlocal EnableExtensions
chcp 65001 >nul

rem ============================================================================
rem Taurus WMS - verificacion despues de actualizar
rem
rem Ejecutar como Administrador:
rem   C:\taurus\app\verificar_servidor.bat
rem
rem Chequea:
rem   - estado de Git y commit desplegado
rem   - archivos de configuracion y codigo
rem   - entorno virtual y waitress
rem   - servicios TaurusWMS / TaurusAdmin
rem   - puertos 5000 / 5001 escuchando
rem   - respuesta HTTP de /login y /admin/login
rem   - migraciones pendientes (dry-run)
rem   - ultimas lineas de los logs
rem ============================================================================

set "APP_DIR=C:\taurus\app"
set "LOG_DIR=C:\taurus\logs"
set "NSSM=C:\herramientas\nssm.exe"
set "PY=%APP_DIR%\.venv\Scripts\python.exe"
set "WAITRESS=%APP_DIR%\.venv\Scripts\waitress-serve.exe"
set "FALLOS=0"

echo === Verificacion post actualizacion ===
echo Fecha: %DATE% %TIME%
echo.

rem --- Git -------------------------------------------------------------------
echo [Git]
git -C "%APP_DIR%" log -1 --oneline
for /f "delims=" %%L in ('git -C "%APP_DIR%" status --porcelain') do (
    echo FAIL: cambio local: %%L
    set /a FALLOS+=1
)
echo.

rem --- Archivos ---------------------------------------------------------------
echo [Archivos]
call :archivo "%APP_DIR%\.env"
call :archivo "%APP_DIR%\conexiones.json"
call :archivo "%APP_DIR%\app.py"
call :archivo "%APP_DIR%\admin.py"
call :archivo "%APP_DIR%\migrate.py"
call :archivo "%APP_DIR%\actualizar_servidor.bat"
call :archivo "%APP_DIR%\instalar_servicios.bat"
call :archivo "%PY%"
call :archivo "%WAITRESS%"
echo.

rem --- Servicios --------------------------------------------------------------
echo [Servicios]
call :servicio TaurusWMS
call :servicio TaurusAdmin
echo.

rem --- Puertos ----------------------------------------------------------------
echo [Puertos]
call :puerto 5000
call :puerto 5001
echo.

rem --- HTTP -------------------------------------------------------------------
echo [HTTP]
call :http 5000 /login
call :http 5001 /admin/login
echo.

rem --- Migraciones ------------------------------------------------------------
echo [Migraciones pendientes - dry run]
"%PY%" "%APP_DIR%\migrate.py" --db admin --dry-run
"%PY%" "%APP_DIR%\migrate.py" --db wms --dry-run
"%PY%" "%APP_DIR%\migrate.py" --db intercambio --dry-run
echo.

rem --- Logs -------------------------------------------------------------------
echo [Ultimas lineas de logs]
if exist "%LOG_DIR%\wms.log" (
    echo --- wms.log ---
    powershell -NoProfile -Command "Get-Content -Tail 10 '%LOG_DIR%\wms.log'"
) else (
    echo Aviso: no existe %LOG_DIR%\wms.log
)
if exist "%LOG_DIR%\admin.log" (
    echo --- admin.log ---
    powershell -NoProfile -Command "Get-Content -Tail 10 '%LOG_DIR%\admin.log'"
) else (
    echo Aviso: no existe %LOG_DIR%\admin.log
)
echo.

rem --- Resumen ----------------------------------------------------------------
echo === Resumen ===
if "%FALLOS%"=="0" (
    echo VERIFICACION OK
    endlocal
    exit /b 0
) else (
    echo Fallos detectados: %FALLOS%
    endlocal
    exit /b 1
)

:archivo
if exist "%~1" (
    echo OK: %~1
) else (
    echo FAIL: falta %~1
    set /a FALLOS+=1
)
exit /b 0

:servicio
set "SV=%~1"
set "EST="
for /f %%S in ('%NSSM% status %SV% 2^>nul') do set "EST=%%S"
if "%EST%"=="SERVICE_RUNNING" (
    echo OK: %SV% = %EST%
) else (
    echo FAIL: %SV% = %EST%
    set /a FALLOS+=1
)
exit /b 0

:puerto
netstat -ano | findstr "LISTENING" | findstr ":%~1 " >nul
if not errorlevel 1 (
    echo OK: puerto %~1 escuchando
) else (
    echo FAIL: puerto %~1 no escucha
    set /a FALLOS+=1
)
exit /b 0

:http
set "COD="
for /f %%C in ('powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 http://127.0.0.1:%~1%~2).StatusCode } catch { 000 }"') do set "COD=%%C"
if "%COD%"=="200" (
    echo OK: http://127.0.0.1:%~1%~2 -^> %COD%
) else (
    echo FAIL: http://127.0.0.1:%~1%~2 -^> %COD%
    set /a FALLOS+=1
)
exit /b 0
