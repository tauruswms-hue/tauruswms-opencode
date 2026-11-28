@echo off
setlocal EnableExtensions
chcp 65001 >nul

rem ============================================================================
rem Taurus WMS - actualizar el servidor (Windows)
rem
rem Ejecutar como Administrador desde C:\taurus\app\actualizar_servidor.bat
rem
rem Requiere:
rem   C:\taurus\mysql.cnf con:
rem       [client]
rem       user=taurus
rem       password=CLAVE_PROPIA
rem   (NO poner la clave en este .bat ni en el repositorio)
rem
rem Si mysqldump o nssm no estan en el PATH, ajustar MYSQLDUMP y NSSM abajo.
rem ============================================================================

set "APP_DIR=C:\taurus\app"
set "LOG_DIR=C:\taurus\logs"
set "RESP_DIR=C:\taurus\respaldos"
set "NSSM=C:\herramientas\nssm.exe"
set "MYSQLDUMP=mysqldump"
set "MYSQL_CNF=C:\taurus\mysql.cnf"
set "PY=%APP_DIR%\.venv\Scripts\python.exe"
set "PIP=%APP_DIR%\.venv\Scripts\pip.exe"

if not exist "%APP_DIR%" (
    echo No existe %APP_DIR%
    exit /b 1
)
if not exist "%PY%" (
    echo Falta el entorno virtual: %PY%
    exit /b 1
)
if not exist "%MYSQL_CNF%" (
    echo Falta %MYSQL_CNF%
    echo Debe contener:
    echo   [client]
    echo   user=taurus
    echo   password=CLAVE_PROPIA
    exit /b 1
)
if not exist "%NSSM%" (
    echo Falta NSSM en %NSSM%
    exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%RESP_DIR%" mkdir "%RESP_DIR%"

cd /d "%APP_DIR%" || exit /b 1

echo === Commit actual ===
git rev-parse --short HEAD

for /f "delims=" %%L in ('git status --porcelain') do (
    echo Cambio local detectado: %%L
    goto :cambios_locales
)

echo === Deteniendo servicios ===
"%NSSM%" stop TaurusWMS   >nul 2>&1
"%NSSM%" stop TaurusAdmin >nul 2>&1

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
set "BACKUP=%RESP_DIR%\taurus_%STAMP%.sql"

echo === Backup de las tres bases ===
"%MYSQLDUMP%" --defaults-extra-file="%MYSQL_CNF%" --single-transaction --no-tablespaces --routines --events --triggers --databases taurus_admin taurus_wms taurus_intercambio > "%BACKUP%"
if errorlevel 1 (
    echo Fallo el backup. No se aplica la actualizacion.
    goto :abort
)
echo Backup: %BACKUP%

echo === Actualizando codigo (git pull) ===
git -C "%APP_DIR%" fetch --all --prune
git -C "%APP_DIR%" pull --ff-only
if errorlevel 1 (
    echo Fallo git pull.
    goto :abort
)

echo === Dependencias ===
"%PIP%" install -r requirements.txt waitress
if errorlevel 1 (
    echo Fallo pip install.
    goto :abort
)

echo === Migraciones pendientes (dry-run) ===
"%PY%" migrate.py --db admin       --dry-run
"%PY%" migrate.py --db wms         --dry-run
"%PY%" migrate.py --db intercambio --dry-run

choice /C SN /N /M "Aplicar las migraciones mostradas? [S/N]: "
if errorlevel 2 (
    echo Actualizacion cancelada por el usuario.
    goto :abort
)

echo === Aplicando migraciones ===
"%PY%" migrate.py --db admin
if errorlevel 1 goto :abort
"%PY%" migrate.py --db wms
if errorlevel 1 goto :abort
"%PY%" migrate.py --db intercambio
if errorlevel 1 goto :abort

echo === Iniciando servicios ===
"%NSSM%" start TaurusWMS
"%NSSM%" start TaurusAdmin

echo === Commit desplegado ===
git rev-parse --short HEAD
echo OK.
endlocal
exit /b 0

:cambios_locales
echo Hay cambios locales en el repositorio. Abortando.
echo Ejecutar git status y resolver antes de actualizar.
goto :abort

:abort
echo === Restaurando servicios tras abortar ===
"%NSSM%" start TaurusWMS   >nul 2>&1
"%NSSM%" start TaurusAdmin >nul 2>&1
echo ABORTADO.
endlocal
exit /b 1
