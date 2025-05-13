# install_dependencies.ps1

$ErrorActionPreference = "Stop"

function Install-PowerShell7 {
    $pwshPath = "C:\Program Files\PowerShell\7\pwsh.exe"
    if (-Not (Test-Path $pwshPath)) {
        Write-Host "Устанавливается PowerShell 7..."
        $installer = "$env:TEMP\PowerShell-7-x64.msi"
        Invoke-WebRequest -Uri "https://github.com/PowerShell/PowerShell/releases/latest/download/PowerShell-7.4.2-win-x64.msi" -OutFile $installer
        Start-Process "msiexec.exe" -ArgumentList "/i `"$installer`" /quiet /norestart" -Wait
        Remove-Item $installer
    } else {
        Write-Host "PowerShell 7 уже установлен."
    }
}

function Install-FIO {
    $fioExe = "C:\Program Files\fio\fio.exe"
    if (-Not (Test-Path $fioExe)) {
        Write-Host "Устанавливается FIO..."
        $zipPath = "$env:TEMP\fio.zip"
        $extractPath = "C:\Program Files\fio"
        Invoke-WebRequest -Uri "https://github.com/axboe/fio/releases/download/fio-3.36/fio-3.36-x64.zip" -OutFile $zipPath
        Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force
        Remove-Item $zipPath
    } else {
        Write-Host "FIO уже установлен."
    }
}

function Install-Smartmontools {
    $smartCtl = "C:\Program Files\smartmontools\bin\smartctl.exe"
    if (-Not (Test-Path $smartCtl)) {
        Write-Host "Устанавливается smartmontools..."
        $installer = "$env:TEMP\smartmontools.exe"
        Invoke-WebRequest -Uri "https://netix.dl.sourceforge.net/project/smartmontools/smartmontools/7.3/smartmontools-7.3-1.win32-setup.exe" -OutFile $installer
        Start-Process $installer -ArgumentList "/SILENT" -Wait
        Remove-Item $installer
    } else {
        Write-Host "smartmontools уже установлен."
    }
}

Install-PowerShell7
Install-FIO
Install-Smartmontools

Write-Host "Все зависимости установлены."
