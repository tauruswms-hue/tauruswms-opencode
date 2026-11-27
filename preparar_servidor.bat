@echo off
setlocal EnableExtensions
chcp 65001 >nul

rem ============================================================================
rem Taurus WMS - preparar el servidor para actualizar
rem
rem Copiar este archivo a C:\taurus\preparar_servidor.bat (FUERA de la carpeta
rem de la app) y ejecutarlo como Administrador.
rem
rem Hace:
rem   1. Quita el flag skip-worktree de .env si lo habias puesto.
rem   2. Guarda una copia de tu .env de produccion en C:\taurus\respaldos.
rem   3. Descarta cambios locales en archivos versionados (.env e
rem      INSTALACION_LAN.txt).
rem   4. Elimina la copia suelta de actualizar_servidor.bat si no esta
rem      versionada todavia.
rem   5. git fetch + git pull --ff-only.
rem   6. Restaura tu .env de produccion desde el backup.
rem   7. Muestra el estado final y el commit desplegado.
rem
rem Despues correr: C:\taurus\app\actualizar_servidor.bat
rem ============================================================================

set "APP_DIR=C:\taurus\app"
set "RESP_DIR=C:\taurus\respaldos"

if not exist "%APP_DIR%\.git" (
    echo No existe el repositorio en %APP_DIR%
    exit /b 1
)
if not exist "%RESP_DIR%" mkdir "%RESP_DIR%"

cd /d "%APP_DIR%" || exit /b 1

echo === Commit actual ===
git rev-parse --short HEAD

echo === Estado antes ===
git status --short

rem --- 1. Quitar skip-worktree si estaba puesto -------------------------------
git update-index --no-skip-worktree .env >nul 2>&1

rem --- 2. Backup del .env de produccion --------------------------------------
if exist ".env" (
    for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"
    copy /Y ".env" "%RESP_DIR%\env.produccion_%STAMP%.txt" >nul
    copy /Y ".env" "%RESP_DIR%\env.produccion.txt" >nul
    echo Backup de .env: %RESP_DIR%\env.produccion.txt
) else (
    echo Aviso: no hay .env en %APP_DIR%
)

rem --- 3. Descartar cambios locales en archivos versionados ------------------
git ls-files --error-unmatch .env >nul 2>&1
if not errorlevel 1 (
    echo Restaurando .env versionado para limpiar el estado...
    git checkout -- .env
)
git checkout -- INSTALACION_LAN.txt

rem --- 4. Sacar la copia suelta del actualizar_servidor.bat ------------------
git ls-files --error-unmatch actualizar_servidor.bat >nul 2>&1
if errorlevel 1 (
    if exist "actualizar_servidor.bat" (
        echo Eliminando copia suelta de actualizar_servidor.bat...
        del /f /q "actualizar_servidor.bat"
    )
)

rem --- 5. Verificar que no queden cambios locales ----------------------------
set "SUCIO="
for /f "delims=" %%L in ('git status --porcelain') do set "SUCIO=%%L"
if defined SUCIO (
    echo Queda cambio local: %SUCIO%
    echo Resolverlo a mano antes de continuar.
    echo Tu .env esta guardado en %RESP_DIR%\env.produccion.txt
    endlocal
    exit /b 1
)

rem --- 6. Traer los commits --------------------------------------------------
echo === Actualizando codigo ===
git fetch --all --prune
if errorlevel 1 goto :abort
git pull --ff-only
if errorlevel 1 goto :abort

rem --- 7. Restaurar el .env de produccion ------------------------------------
if exist "%RESP_DIR%\env.produccion.txt" (
    copy /Y "%RESP_DIR%\env.produccion.txt" ".env" >nul
    echo .env de produccion restaurado.
)

rem --- 8. Verificacion final -------------------------------------------------
echo === Estado despues ===
git status --short
echo === Commit desplegado ===
git rev-parse --short HEAD

echo.
echo OK. Ahora pode correr C:\taurus\app\actualizar_servidor.bat
endlocal
exit /b 0

:abort
echo.
echo Fallo el git pull. Tu .env esta guardado en:
echo   %RESP_DIR%\env.produccion.txt
echo No se aplico ningun cambio.
endlocal
exit /b 1
