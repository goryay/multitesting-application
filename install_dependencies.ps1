$ErrorActionPreference = "Stop"

# Абсолютный путь к папке SoftForTest внутри dist
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$softPath = Join-Path $scriptDir "SoftForTest"

# Пути к локальным установщикам
$pwshInstaller = Join-Path $softPath "PowerShell-7.5.0.msi"
$fioInstaller = Join-Path $softPath "fio-3.36-x64.msi"
$smartInstaller = Join-Path $softPath "smartmontools-7.4-1.win32-setup.exe"

# Установка PowerShell
if (-not (Test-Path "C:\Program Files\PowerShell\7\pwsh.exe")) {
    if (Test-Path $pwshInstaller) {
        Write-Host "Устанавливается PowerShell 7..."
        Start-Process "msiexec.exe" -ArgumentList "/i `"$pwshInstaller`" /quiet /norestart" -Wait
    } else {
        Write-Host "❌ Установщик PowerShell не найден: $pwshInstaller" -ForegroundColor Red
    }
} else {
    Write-Host "✔ PowerShell 7 уже установлен."
}

# Установка FIO
if (-not (Test-Path "C:\Program Files\fio\fio.exe")) {
    if (Test-Path $fioInstaller) {
        Write-Host "Устанавливается FIO..."
        Start-Process "msiexec.exe" -ArgumentList "/i `"$fioInstaller`" /quiet /norestart" -Wait
    } else {
        Write-Host "❌ Установщик FIO не найден: $fioInstaller" -ForegroundColor Red
    }
} else {
    Write-Host "✔ FIO уже установлен."
}

# Установка smartmontools
if (-not (Test-Path "C:\Program Files\smartmontools\bin\smartctl.exe")) {
    if (Test-Path $smartInstaller) {
        Write-Host "Устанавливается smartmontools..."
        Start-Process $smartInstaller -ArgumentList "/SILENT" -Wait
    } else {
        Write-Host "❌ Установщик smartmontools не найден: $smartInstaller" -ForegroundColor Red
    }
} else {
    Write-Host "✔ smartmontools уже установлен."
}

Write-Host "✅ Все зависимости проверены и установлены."
