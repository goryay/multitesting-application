# Получаем разрешение экрана с помощью WMI
$screenWidth = (Get-WmiObject -Namespace root\cimv2 -Class Win32_VideoController).CurrentHorizontalResolution
$screenHeight = (Get-WmiObject -Namespace root\cimv2 -Class Win32_VideoController).CurrentVerticalResolution

# Выводим разрешение экрана
Write-Host "Разрешение экрана: ${screenWidth}x${screenHeight}"

# Запрашиваем время теста у пользователя
$max_time = Read-Host "Введите время теста в секундах (например, 60)"

# Путь к .bat файлу (измени на свой)
$batFilePath = "C:\Path\To\run_furmark.bat"

# Проверка, существует ли .bat файл
if (-not (Test-Path $batFilePath)) {
    Write-Host "Файл .bat не найден по указанному пути: $batFilePath"
    exit
}

# Запуск .bat файла с передачей параметров
Start-Process -FilePath $batFilePath -ArgumentList "$screenWidth $screenHeight $max_time" -NoNewWindow -Wait

Write-Host "Тест завершен. Результаты сохранены в лог."