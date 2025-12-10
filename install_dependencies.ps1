# install_dependencies.ps1

$ErrorActionPreference = "Stop"

function Install-PowerShell7 {
    $pwshPath = "C:\Program Files\PowerShell\7\pwsh.exe"
    if (-Not (Test-Path $pwshPath)) {
        Write-Host "Устанавливается PowerShell 7..."
        $installer = Join-Path -Path $PSScriptRoot -ChildPath "SoftForTest\PowerShell-7.5.0.msi"
        if (-Not (Test-Path $installer)) {
            Write-Host "PowerShell-7.5.0.msi не найден!"
            exit 1
        }

        Start-Process "msiexec.exe" -ArgumentList "/i `"$installer`" /quiet /norestart" -Wait

        # опционально: подчистить MSI после успешной установки
        if (Test-Path $pwshPath -and (Test-Path $installer)) {
            Remove-Item $installer -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "PowerShell 7 уже установлен."
    }
}


function Install-FIO {
    $fioExe = "C:\Program Files\fio\fio.exe"
    if (-Not (Test-Path $fioExe)) {
        Write-Host "Устанавливается FIO..."
        $installer = Join-Path -Path $PSScriptRoot -ChildPath "SoftForTest\fio-3.39-x64.msi"
        if (-Not (Test-Path $installer)) {
            Write-Host "fio-3.39-x64.msi не найден!"
            exit 1
        }

        Start-Process "msiexec.exe" -ArgumentList "/i `"$installer`" /quiet /norestart" -Wait

        # подчистка MSI после успешной установки
        if (Test-Path $fioExe -and (Test-Path $installer)) {
            Remove-Item $installer -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "FIO уже установлен."
    }
}


function Install-Smartmontools {
    $smartCtl = "C:\Program Files\smartmontools\bin\smartctl.exe"

    if (-Not (Test-Path $smartCtl)) {
        Write-Host "Устанавливается smartmontools..."

        # пробуем сначала win64, потом win32 — вдруг у тебя поменяется инсталлятор
        $win64 = Join-Path -Path $PSScriptRoot -ChildPath "SoftForTest\smartmontools-7.4-1.win64-setup.exe"
        $win32 = Join-Path -Path $PSScriptRoot -ChildPath "SoftForTest\smartmontools-7.4-1.win32-setup.exe"

        if (Test-Path $win64) {
            $installer = $win64
        } elseif (Test-Path $win32) {
            $installer = $win32
        } else {
            Write-Host "Инсталлятор smartmontools не найден (ни win64, ни win32)!"
            exit 1
        }

        # ВАЖНО:
        # smartmontools использует NSIS, у него тихий ключ /S, а /SILENT не работает.
        # Также задаём каталог установки явно, чтобы smartctl оказался там, где его ждёт main.py.
        #
        # Пример из доки:
        #   smartmontools-x.y-z.win32-setup.exe /S /D=C:\smartmontools
        #
        # Здесь устанавливаем в C:\Program Files\smartmontools
        Start-Process $installer `
            -ArgumentList "/S", "/D=C:\Program Files\smartmontools" `
            -Wait -NoNewWindow

        if (Test-Path $smartCtl) {
            Write-Host "smartmontools установлен: $smartCtl"
        } else {
            # fallback: вдруг инсталлятор всё равно ушёл в Program Files (x86)
            $smartCtlX86 = "C:\Program Files (x86)\smartmontools\bin\smartctl.exe"
            if (Test-Path $smartCtlX86) {
                Write-Warning "smartmontools установился в Program Files (x86). main.py его там не ищет!"
                Write-Warning "Либо поправь путь в main.py, либо переустанови smartmontools с нужным /D=..."
            } else
            {
                Write-Warning "Не удалось обнаружить smartctl.exe после установки. Проверь инсталлятор."
            }
        }

        # Если всё ок — можно удалить exe инсталлятора
        if (Test-Path $smartCtl -and (Test-Path $installer)) {
            Remove-Item $installer -Force -ErrorAction SilentlyContinue
        }

    } else {
        Write-Host "smartmontools уже установлен."
    }
}


Install-PowerShell7
Install-FIO
Install-Smartmontools

Write-Host "Все зависимости установлены."
