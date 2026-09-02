@echo off
setlocal

cd /d "%~dp0"

echo ==========================================
echo ReActiva - Actualizacion de datos Power BI
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: No se encontro el entorno virtual en .venv
    echo.
    pause
    exit /b 1
)

echo Actualizando datos desde AWS S3...
echo.

".venv\Scripts\python.exe" "scripts\refresh_bi_data.py"

if errorlevel 1 (
    echo.
    echo ERROR: La actualizacion de datos fallo.
    echo Revise la conexion a AWS y los permisos configurados.
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Datos actualizados correctamente.
echo ==========================================
echo.

if exist "dashboard\ReActiva_EDA_Quality.pbip" (
    echo Abriendo Power BI...
    start "" "dashboard\ReActiva_EDA_Quality.pbip"
) else (
    echo ADVERTENCIA: No se encontro el proyecto Power BI.
)

echo.
echo Cuando abra Power BI, presione Actualizar.
echo.

pause
endlocal