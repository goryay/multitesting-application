# Пути к файлам
$softPath = "$env:USERPROFILE\Desktop\SoftForTest"
$psInstaller = "$softPath\PowerShell-7.5.0.msi"
$fioInstaller = "$softPath\fio-3.39-x64.msi"
$smartmontoolsInstaller = "$softPath\smartmontools-7.4-1.win32-setup.exe"
$logPath = "$softPath\InstallLogs"
$psLog = "$logPath\PowerShell_Install.log"
$fioLog = "$logPath\FIO_Install.log"
$smartmontoolsLog = "$logPath\Smartmontools_Install.log"

# Создаем папку для логов
if (-not (Test-Path $logPath)) {
    New-Item -ItemType Directory -Path $logPath -Force | Out-Null
}

# Удаляем предыдущую версию PowerShell 7 (если есть)
if (Test-Path "$env:ProgramFiles\PowerShell\7\pwsh.exe") {
    Write-Host "Удаление предыдущей версии PowerShell 7..." -ForegroundColor Yellow
    Start-Process "msiexec.exe" -ArgumentList "/x `"$psInstaller`" /quiet /norestart /log `"$logPath\PowerShell_Uninstall.log`"" -Wait
}

# Устанавливаем PowerShell 7.5
if (Test-Path $psInstaller) {
    Write-Host "Установка PowerShell 7.5..." -ForegroundColor Cyan
    $arguments = "/i `"$psInstaller`" /quiet /norestart /log `"$psLog`""
    $process = Start-Process "msiexec.exe" -ArgumentList $arguments -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        Write-Host "PowerShell 7.5 успешно установлено!" -ForegroundColor Green
    } else {
        Write-Host "Ошибка установки PowerShell 7.5 (код $($process.ExitCode)). Проверьте лог: $psLog" -ForegroundColor Red
    }
} else {
    Write-Host "Файл PowerShell-7.5.0.msi не найден!" -ForegroundColor Red
}

# Устанавливаем FIO
if (Test-Path $fioInstaller) {
    Write-Host "Установка FIO..." -ForegroundColor Cyan
    $arguments = "/i `"$fioInstaller`" /quiet /norestart /log `"$fioLog`""
    $process = Start-Process "msiexec.exe" -ArgumentList $arguments -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        Write-Host "FIO успешно установлено!" -ForegroundColor Green
    } else {
        Write-Host "Ошибка установки FIO (код $($process.ExitCode)). Проверьте лог: $fioLog" -ForegroundColor Red
    }
} else {
    Write-Host "Файл fio-3.39-x64.msi не найден!" -ForegroundColor Red
}

# Устанавливаем Smartmontools
if (Test-Path $smartmontoolsInstaller) {
    Write-Host "Установка Smartmontools..." -ForegroundColor Cyan
    $process = Start-Process -FilePath $smartmontoolsInstaller -ArgumentList "/S" -Wait -PassThru
    
    if ($process.ExitCode -eq 0) {
        Write-Host "Smartmontools успешно установлен!" -ForegroundColor Green
        # Записываем успешную установку в лог
        "Установка завершена успешно. Код выхода: $($process.ExitCode)" | Out-File -FilePath $smartmontoolsLog -Encoding UTF8
    } else {
        Write-Host "Ошибка установки Smartmontools (код $($process.ExitCode))" -ForegroundColor Red
        "Ошибка установки. Код выхода: $($process.ExitCode)" | Out-File -FilePath $smartmontoolsLog -Encoding UTF8
    }
} else {
    Write-Host "Файл smartmontools-7.4-1.win32-setup.exe не найден!" -ForegroundColor Red
}

Write-Host "Логи сохранены: $psLog, $fioLog, $smartmontoolsLog" -ForegroundColor Yellow