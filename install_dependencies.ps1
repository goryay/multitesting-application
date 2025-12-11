# install_dependencies.ps1
$ErrorActionPreference = "Stop"

# Корень с инсталляторами (лежит рядом с распакованным exe / main.py внутри _MEI...)
$SoftRoot = Join-Path $PSScriptRoot "SoftForTest"

if (-not (Test-Path $SoftRoot)) {
    Write-Host "Папка SoftForTest не найдена: $SoftRoot"
    exit 1
}

function Get-InstallerFile {
    param(
        [string]$Description,
        [string[]]$Patterns      # например: 'fio*.msi', 'PowerShell-7*.msi'
    )

    $files = @()
    foreach ($pat in $Patterns) {
        $files += Get-ChildItem -Path $SoftRoot -Filter $pat -File -ErrorAction SilentlyContinue
    }

    if (-not $files) {
        throw "Инсталлятор '$Description' не найден в $SoftRoot (шаблоны: $($Patterns -join ', '))"
    }

    # Берём самый маленький по размеру (обычно это тот самый)
    return $files | Sort-Object Length | Select-Object -First 1
}

function Install-PowerShell7 {
    $pwshPath = "C:\Program Files\PowerShell\7\pwsh.exe"
    if (Test-Path $pwshPath) {
        Write-Host "PowerShell 7 уже установлен."
        return
    }

    Write-Host "Устанавливается PowerShell 7..."

    $installerFile = Get-InstallerFile -Description "PowerShell 7" -Patterns @(
        "PowerShell-7*.msi", "*PowerShell*7*.msi"
    )
    $installer = $installerFile.FullName
    Write-Host "Найден инсталлятор PowerShell: $installer"

    Start-Process "msiexec.exe" -ArgumentList "/i `"$installer`" /quiet /norestart" -Wait

    if (Test-Path $pwshPath) {
        Write-Host "PowerShell 7 установлен: $pwshPath"
        # опционально подчистим MSI
        Remove-Item $installer -Force -ErrorAction SilentlyContinue
    } else {
        throw "После установки PowerShell 7 не найден по пути $pwshPath"
    }
}

function Install-FIO {
    $fioExe = "C:\Program Files\fio\fio.exe"
    if (Test-Path $fioExe) {
        Write-Host "FIO уже установлен."
        return
    }

    Write-Host "Устанавливается FIO..."

    # Сознательно широкие маски — главное, чтобы файл назывался fio*.msi
    $installerFile = Get-InstallerFile -Description "FIO" -Patterns @(
        "fio*.msi", "*fio*.msi"
    )
    $installer = $installerFile.FullName
    Write-Host "Найден инсталлятор FIO: $installer"

    Start-Process "msiexec.exe" -ArgumentList "/i `"$installer`" /quiet /norestart" -Wait

    if (Test-Path $fioExe) {
        Write-Host "FIO установлен: $fioExe"
        Remove-Item $installer -Force -ErrorAction SilentlyContinue
    } else {
        throw "После установки FIO не найден по пути $fioExe"
    }
}

function Install-Smartmontools {
    $smartCtl = "C:\Program Files\smartmontools\bin\smartctl.exe"
    if (Test-Path $smartCtl) {
        Write-Host "smartmontools уже установлен."
        return
    }

    Write-Host "Устанавливается smartmontools..."

    # Пытаемся найти win64, если нет — берём win32
    $installerFile = $null
    try {
        $installerFile = Get-InstallerFile -Description "smartmontools win64" -Patterns @(
            "smartmontools*win64*.exe"
        )
    } catch {
        Write-Host "win64-вариант не найден, пробуем win32..."
        $installerFile = Get-InstallerFile -Description "smartmontools win32" -Patterns @(
            "smartmontools*win32*.exe"
        )
    }

    $installer = $installerFile.FullName
    Write-Host "Найден инсталлятор smartmontools: $installer"

    # NSIS-инсталлятор, тихий ключ /S, путь задаём явно
    Start-Process $installer `
        -ArgumentList "/S", "/D=C:\Program Files\smartmontools" `
        -Wait -NoNewWindow

    if (Test-Path $smartCtl) {
        Write-Host "smartmontools установлен: $smartCtl"
        Remove-Item $installer -Force -ErrorAction SilentlyContinue
    } else {
        $smartCtlX86 = "C:\Program Files (x86)\smartmontools\bin\smartctl.exe"
        if (Test-Path $smartCtlX86) {
            Write-Warning "smartmontools поставился в Program Files (x86): $smartCtlX86"
            Write-Warning "Либо поправь путь в main.py, либо переустанови с нужным /D=..."
        } else {
            throw "Не удалось обнаружить smartctl.exe после установки."
        }
    }
}

Install-PowerShell7
Install-FIO
Install-Smartmontools

Write-Host "Все зависимости установлены."
