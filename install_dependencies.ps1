# install_dependencies.ps1

# Текущий путь скрипта
$scriptRoot = $PSScriptRoot

# Пути
$softPath = Join-Path $scriptRoot "SoftForTest"
$logPath = Join-Path $scriptRoot "InstallLogs"
$reqFile = Join-Path $scriptRoot "requirements.txt"

# Инсталляторы
$psInstaller     = Join-Path $softPath "PowerShell-7.5.0.msi"
$fioInstaller    = Join-Path $softPath "fio.msi"
$smartInstaller  = Join-Path $softPath "smartmontools-7.4-1.win32-setup.exe"

# Логи
$psLog    = Join-Path $logPath "PowerShell_Install.log"
$fioLog   = Join-Path $logPath "FIO_Install.log"
$smartLog = Join-Path $logPath "Smartmontools_Install.log"

# Создание папки для логов
if (-not (Test-Path $logPath)) {
    New-Item -ItemType Directory -Path $logPath -Force | Out-Null
}

function Install-MSI($installerPath, $logFilePath) {
    Start-Process "msiexec.exe" -ArgumentList "/i `"$installerPath`" /quiet /norestart /log `"$logFilePath`"" -Wait -PassThru
}

function Install-EXE($installerPath, $logFilePath) {
    Start-Process $installerPath -ArgumentList "/S" -Wait -PassThru
}

Write-Host "=== Проверка необходимых программ ===" -ForegroundColor Cyan

# PowerShell
if (-not (Test-Path "C:\Program Files\PowerShell\7\pwsh.exe")) {
    if (Test-Path $psInstaller) {
        Write-Host "Установка PowerShell 7.5..." -ForegroundColor Yellow
        $process = Install-MSI $psInstaller $psLog
        if ($process.ExitCode -eq 0) {
            Write-Host "PowerShell 7.5 успешно установлено!" -ForegroundColor Green
        } else {
            Write-Host "Ошибка установки PowerShell 7.5 (код $($process.ExitCode)). Лог: $psLog" -ForegroundColor Red
        }
    } else {
        Write-Host "PowerShell-7.5.0.msi не найден!" -ForegroundColor Red
    }
} else {
    Write-Host "PowerShell уже установлена." -ForegroundColor Green
}

# FIO
if (-not (Test-Path "C:\Program Files\fio\fio.exe")) {
    if (Test-Path $fioInstaller) {
        Write-Host "Установка FIO..." -ForegroundColor Yellow
        $process = Install-MSI $fioInstaller $fioLog
        if ($process.ExitCode -eq 0) {
            Write-Host "FIO успешно установлено!" -ForegroundColor Green
        } else {
            Write-Host "Ошибка установки FIO (код $($process.ExitCode)). Лог: $fioLog" -ForegroundColor Red
        }
    } else {
        Write-Host "fio.msi не найден!" -ForegroundColor Red
    }
} else {
    Write-Host "FIO уже установлено." -ForegroundColor Green
}

# smartmontools
if (-not (Test-Path "C:\Program Files\smartmontools\bin\smartctl.exe")) {
    if (Test-Path $smartInstaller) {
        Write-Host "Установка smartmontools..." -ForegroundColor Yellow
        $process = Install-EXE $smartInstaller $smartLog
        if ($process.ExitCode -eq 0) {
            Write-Host "smartmontools успешно установлены!" -ForegroundColor Green
        } else {
            Write-Host "Ошибка установки smartmontools (код $($process.ExitCode)). Лог: $smartLog" -ForegroundColor Red
        }
    } else {
        Write-Host "smartmontools-7.4-1.win32-setup.exe не найден!" -ForegroundColor Red
    }
} else {
    Write-Host "smartmontools уже установлены." -ForegroundColor Green
}

# Python зависимости
if (Test-Path $reqFile) {
    Write-Host "`nУстановка Python-зависимостей из requirements.txt..." -ForegroundColor Yellow
    try {
        python -m pip install --upgrade pip
        python -m pip install -r $reqFile
        Write-Host "Зависимости успешно установлены!" -ForegroundColor Green
    } catch {
        Write-Host "Ошибка при установке зависимостей." -ForegroundColor Red
    }
} else {
    Write-Host "requirements.txt не найден!" -ForegroundColor Red
}

Write-Host "`n=== Проверка завершена ===" -ForegroundColor Cyan
Write-Host "Логи: $logPath" -ForegroundColor Yellow
