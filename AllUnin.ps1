<#
.SYNOPSIS
    Удаление smartmontools через uninstaller и fio любым доступным способом
#>

# Проверка прав администратора
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Требуются права администратора! Перезапуск..." -ForegroundColor Yellow
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`""
    exit
}

# 1. Удаление fio (все возможные методы)
try {
    $uninstall_reg = Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" |
                    ForEach-Object { Get-ItemProperty $_.PSPath } |
                    Where-Object { $_.DisplayName -match "fio" }

    if ($uninstall_reg) {
        Write-Host "Найдена запись в реестре:" $uninstall_reg.DisplayName -ForegroundColor Cyan
        
        # Вариант 1: Если есть UninstallString
        if ($uninstall_reg.UninstallString) {
            $uninstall_path = $uninstall_reg.UninstallString
            Write-Host "UninstallString:" $uninstall_path
            
            # Исправленный запуск для MSI
            if ($uninstall_path -match "MsiExec\.exe\s\/[IX]{1}\{([A-Z0-9-]+)\}") {
                $productCode = $matches[1]
                Write-Host "Запуск MSI деинсталлятора с кодом: $productCode"
                Start-Process "msiexec.exe" -ArgumentList "/x `{$productCode`} /quiet /norestart" -Wait
            }
            else {
                # Для обычных EXE деинсталляторов
                Start-Process -FilePath $uninstall_path -ArgumentList "/S" -Wait
            }
        }
        # Вариант 2: Если есть только ProductCode
        elseif ($uninstall_reg.PSChildName -match "\{[A-Z0-9-]+\}") {
            $productCode = $uninstall_reg.PSChildName
            Write-Host "Запуск MSI деинсталлятора с кодом: $productCode"
            Start-Process "msiexec.exe" -ArgumentList "/x $productCode /quiet /norestart" -Wait
        }
        
        Write-Host "[OK] fio удалён через деинсталлятор из реестра" -ForegroundColor Green
    }
    else {
        Write-Host "fio не найден в реестре" -ForegroundColor Yellow
    }
}
catch {
    Write-Error "Ошибка при удалении fio: $_"
}

# 2. Удаление smartmontools
$uninstallerPath = "C:\Program Files\smartmontools\uninst-smartmontools.exe"
try {
    if (Test-Path $uninstallerPath) {
        Write-Host "Запуск деинсталлятора smartmontools..." -ForegroundColor Cyan
        $process = Start-Process -FilePath $uninstallerPath -ArgumentList "/S" -Wait -PassThru
        
        if ($process.ExitCode -eq 0) {
            Write-Host "smartmontools успешно удалён." -ForegroundColor Green
        }
        else {
            Write-Error "Ошибка деинсталляции (код $($process.ExitCode))."
        }
    }
    else {
        Write-Warning "Файл деинсталлятора smartmontools не найден: $uninstallerPath"
    }
}
catch {
    Write-Error "Ошибка при удалении smartmontools: $_"
}

Write-Host "Операции завершены." -ForegroundColor Green