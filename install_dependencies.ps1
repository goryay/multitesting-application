# install_dependencies.ps1

$ErrorActionPreference = "Stop"

function Install-PowerShell7 {
    $pwshPath = "C:\Program Files\PowerShell\7\pwsh.exe"
    if (-Not (Test-Path $pwshPath)) {
        Write-Host "Устанавливается PowerShell 7..."
        $installer = Join-Path -Path $PSScriptRoot -ChildPath "SoftForTest\PowerShell-7.5.0.msi"
        if (-Not (Test-Path $installer)) { Write-Host "PowerShell-7.5.0.msi не найден!"; exit 1 }
        Start-Process "msiexec.exe" -ArgumentList "/i `"$installer`" /quiet /norestart" -Wait
    } else {
        Write-Host "PowerShell 7 уже установлен."
    }
}


function Install-FIO {
    $fioExe = "C:\Program Files\fio\fio.exe"
    if (-Not (Test-Path $fioExe)) {
        Write-Host "Устанавливается FIO..."
        $installer = Join-Path -Path $PSScriptRoot -ChildPath "SoftForTest\fio-3.39-x64.msi"
        if (-Not (Test-Path $installer)) { Write-Host "fio-3.39-x64.msi не найден!"; exit 1 }
        Start-Process "msiexec.exe" -ArgumentList "/i `"$installer`" /quiet /norestart" -Wait
    } else {
        Write-Host "FIO уже установлен."
    }
}


function Install-Smartmontools {
    $smartCtl = "C:\Program Files\smartmontools\bin\smartctl.exe"
    if (-Not (Test-Path $smartCtl)) {
        Write-Host "Устанавливается smartmontools..."
        $installer = Join-Path -Path $PSScriptRoot -ChildPath "SoftForTest\smartmontools-7.4-1.win32-setup.exe"
        if (-Not (Test-Path $installer)) { Write-Host "smartmontools-7.4-1.win32-setup.exe не найден!"; exit 1 }
        Start-Process $installer -ArgumentList "/SILENT" -Wait
    } else {
        Write-Host "smartmontools уже установлен."
    }
}


Install-PowerShell7
Install-FIO
Install-Smartmontools

Write-Host "Все зависимости установлены."
