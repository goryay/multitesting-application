# install_dependencies.ps1

# Пути к директории с установщиками
$softPath = "$env:USERPROFILE\Desktop\SoftForTest"
$logPath = "$softPath\InstallLogs"

# Пути к инсталляторам
$psInstaller = "$softPath\PowerShell-7.5.0.msi"
$fioInstaller = "$softPath\fio.msi"
$smartInstaller = "$softPath\smartmontools-7.4-1.win32-setup.exe"

# Пути для логов
$psLog = "$logPath\PowerShell_Install.log"
$fioLog = "$logPath\FIO_Install.log"
$smartLog = "$logPath\Smartmontools_Install.log"

# Создание папки для логов
if (-not (Test-Path $logPath)) {
    New-Item -ItemType Directory -Path $logPath -Force | Out-Null
}

# Функция установки через MSI
function Install-MSI($installerPath, $logFilePath) {
    Start-Process "msiexec.exe" -ArgumentList "/i `"$installerPath`" /quiet /norestart /log `"$logFilePath`"" -Wait -PassThru
}

# Функция установки через EXE (тихий режим)
function Install-EXE($installerPath, $logFilePath) {
    Start-Process $installerPath -ArgumentList "/S" -Wait -PassThru
}

Write-Host "=== Проверка необходимых программ ===" -ForegroundColor Cyan

# Проверка и установка PowerShell 7.5
if (-not (Test-Path "C:\\Program Files\\PowerShell\\7\\pwsh.exe")) {
    if (Test-Path $psInstaller) {
        Write-Host "Установка PowerShell 7.5..." -ForegroundColor Yellow
        $process = Install-MSI -installerPath $psInstaller -logFilePath $psLog
        if ($process.ExitCode -eq 0) {
            Write-Host "PowerShell 7.5 успешно установлено!" -ForegroundColor Green
        } else {
            Write-Host "Ошибка установки PowerShell 7.5 (код $($process.ExitCode)). Лог: $psLog" -ForegroundColor Red
        }
    } else {
        Write-Host "Файл PowerShell-7.5.0.msi не найден!" -ForegroundColor Red
    }
} else {
    Write-Host "PowerShell 7.5 уже установлено." -ForegroundColor Green
}

# Проверка и установка FIO
if (-not (Test-Path "C:\\Program Files\\fio\\fio.exe")) {
    if (Test-Path $fioInstaller) {
        Write-Host "Установка FIO..." -ForegroundColor Yellow
        $process = Install-MSI -installerPath $fioInstaller -logFilePath $fioLog
        if ($process.ExitCode -eq 0) {
            Write-Host "FIO успешно установлено!" -ForegroundColor Green
        } else {
            Write-Host "Ошибка установки FIO (код $($process.ExitCode)). Лог: $fioLog" -ForegroundColor Red
        }
    } else {
        Write-Host "Файл fio.msi не найден!" -ForegroundColor Red
    }
} else {
    Write-Host "FIO уже установлено." -ForegroundColor Green
}

# Проверка и установка smartmontools
if (-not (Test-Path "C:\\Program Files\\smartmontools\\bin\\smartctl.exe")) {
    if (Test-Path $smartInstaller) {
        Write-Host "Установка smartmontools..." -ForegroundColor Yellow
        $process = Install-EXE -installerPath $smartInstaller -logFilePath $smartLog
        if ($process.ExitCode -eq 0) {
            Write-Host "smartmontools успешно установлены!" -ForegroundColor Green
        } else {
            Write-Host "Ошибка установки smartmontools (код $($process.ExitCode)). Лог: $smartLog" -ForegroundColor Red
        }
    } else {
        Write-Host "Файл smartmontools-7.4-1.win32-setup.exe не найден!" -ForegroundColor Red
    }
} else {
    Write-Host "smartmontools уже установлены." -ForegroundColor Green
}

Write-Host "\n=== Проверка завершена ===" -ForegroundColor Cyan
Write-Host "Логи установки находятся в: $logPath" -ForegroundColor Yellow
