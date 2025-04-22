@echo off
cd "C:\Users\Admin\Desktop\SoftForTest\FurMark\"
chcp 1251
setlocal enabledelayedexpansion

echo Выберите разрешение экрана:
echo 1) 1280x720
echo 2) 1920x1080
echo 3) 2560x1440
echo 4) 3840x2160
set /p resolution_choice="Введите номер выбранного разрешения: "

if "%resolution_choice%"=="1" (
    set width=1280
    set height=720
) else if "%resolution_choice%"=="2" (
    set width=1920
    set height=1080
) else if "%resolution_choice%"=="3" (
    set width=2560
    set height=1440
) else if "%resolution_choice%"=="4" (
    set width=3840
    set height=2160
) else (
    echo Неверный выбор разрешения. Используется разрешение по умолчанию 1920x1080.
    set width=1920
    set height=1080
)

set /p duration="Введите время теста в секундах: "

echo Выберите количество видеокарт для тестирования:
echo 1) 1 видеокарта
echo 2) 2 видеокарты
set /p gpu_count_choice="Введите номер выбранного количества видеокарт: "

if "%gpu_count_choice%"=="2" (
    set gpu_count=2
) else (
    set gpu_count=1
)

for /L %%i in (0,1,%gpu_count%) do (
    echo Запуск бенчмарка на видеокарте GPU:%%i с разрешением %width%x%height% на %duration% секунд...
    furmark --demo furmark-gl --benchmark --width %width% --height %height% --max-time %duration% --gpu %%i
)

echo Получение температуры видеокарты...
set valid_temp=false
for /f "tokens=2 delims==" %%a in ('"wmic /namespace:\\root\wmi PATH MSAcpi_ThermalZoneTemperature GET CurrentTemperature /value"') do (
    set /a temp=%%a/10-273
    if !temp! gtr -100 (
        echo Текущая температура видеокарты: !temp! °C
        set valid_temp=true
    )
)

if "!valid_temp!"=="false" (
    echo Не удалось получить температуру видеокарты.
)

pause
