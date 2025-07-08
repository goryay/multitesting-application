function Start-ScreenScript {
    $pythonExe = Join-Path -Path $PSScriptRoot -ChildPath "main.exe"
    if (Test-Path $pythonExe) {
        Start-Process -FilePath $pythonExe -ArgumentList "--screen"
    } else {
        Write-Host "main.exe не найден: $pythonExe"
    }
}

# --- Пути к утилитам (относительно папки скрипта) ---
$aida64Path = ".\SoftForTest\AIDA64\AIDA64Port.exe"
$furMarkPath = ".\SoftForTest\FurMark\furmark.exe"
$fioPath = "C:\Program Files\fio\fio.exe"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$aida64FullPath = Join-Path -Path $scriptDir -ChildPath $aida64Path
$furMarkFullPath = Join-Path -Path $scriptDir -ChildPath $furMarkPath

# --- ФУНКЦИИ ---

function Start-AidaTest {
    param([double]$hours, [bool]$includeGPU)
    $minutes = [math]::Round($hours * 60)
    $gpuTest = if ($includeGPU) { ",GPU" } else { "" }
    $params = @("/SST CPU,FPU,Cache,RAM,Disk$gpuTest", "/SSTDUR $minutes")
    Write-Host "Запуск AIDA64: $( $params -join ' ' )"
    Start-Process -FilePath $aida64FullPath -ArgumentList $params -PassThru
}

function Start-FurMarkTest {
    param([double]$hours, [int]$gpuCount)
    $seconds = [math]::Round($hours * 3600)
    $resolution = "1920x1080"
    $demo = "furmark-gl"  # OpenGL-режим

    if ($gpuCount -eq 1) {
        $params = @(
            "--demo $demo",
            "--fullscreen",
            "--width $( $resolution.Split('x')[0] )",
            "--height $( $resolution.Split('x')[1] )",
            "--max-time $seconds",
            "--no-score-box",
            "--disable-demo-options"
        )
        $cmd = "cmd /k `"`"$furMarkFullPath`" $( $params -join ' ' ) & pause`""
        Start-Process cmd.exe -ArgumentList "/c", $cmd
    } else {
        $params1 = @(
            "--demo $demo",
            "--fullscreen",
            "--width $( $resolution.Split('x')[0] )",
            "--height $( $resolution.Split('x')[1] )",
            "--max-time $seconds",
            "--no-score-box",
            "--disable-demo-options",
            "--gpu-index 0"
        )
        $params2 = @(
            "--demo $demo",
            "--fullscreen",
            "--width $( $resolution.Split('x')[0] )",
            "--height $( $resolution.Split('x')[1] )",
            "--max-time $seconds",
            "--no-score-box",
            "--disable-demo-options",
            "--gpu-index 1"
        )
        $cmd = "cmd /k `"start `"FurMark GPU 0`" `"$furMarkFullPath`" $( $params1 -join ' ' ) & start `"FurMark GPU 1`" `"$furMarkFullPath`" $( $params2 -join ' ' ) & pause`""
        Start-Process cmd.exe -ArgumentList "/c", $cmd
    }
}

function Start-FioTest {
    param(
        [double]$hours,
        [string[]]$selectedDrives
    )
    $seconds = [math]::Round($hours * 3600)
    if (-not $selectedDrives) {
        Write-Host "Диски для FIO не выбраны. Пропуск теста."
        return
    }
    Write-Host "`nЗапуск FIO на дисках: $( $selectedDrives -join ', ' )"
    foreach ($disk in $selectedDrives) {
        $testDir = "${disk}:\fio_tests"
        if (-not (Test-Path $testDir)) { New-Item -ItemType Directory -Path $testDir -Force | Out-Null }
        $testFile = "$testDir\fio_test_$([Guid]::NewGuid() ).dat"
        $configPath = "$env:TEMP\fio_config_$([Guid]::NewGuid() ).fio"
        $config = @"
[global]
ioengine=windowsaio
filename=$testFile
size=1g
direct=1
time_based
runtime=$seconds
loops=1
thread
stonewall

[Read-Write-test]
startdelay=0
iodepth=28
numjobs=14
bs=896k
rw=rw
"@
        Set-Content -Path $configPath -Value $config
        $cmd = "cmd /k `"`"$fioPath`" `"$configPath`" & pause`""
        Start-Process cmd.exe -ArgumentList "/c", $cmd
    }
}

function Generate-Report {
    param(
        [string]$computerName,
        [string]$desktopPath,
        [string]$aida64FullPath
    )
    $reportDirectory = Join-Path -Path $desktopPath -ChildPath "Report\$computerName"
    $ReportPath = Join-Path -Path $reportDirectory -ChildPath "SystemReport.html"
    if (-Not (Test-Path -Path $reportDirectory)) {
        New-Item -ItemType Directory -Path $reportDirectory | Out-Null
    }
    try {
        Start-Process -FilePath $aida64FullPath -ArgumentList @(
            "/R `"$ReportPath`"",
            "/ALL", "/SUM", "/HW", "/SW", "/AUDIT", "/HTML"
        ) -NoNewWindow
        Write-Host "Запущена генерация отчета AIDA64 в фоне: $ReportPath"
    } catch {
        Write-Host "Ошибка при запуске генерации отчета AIDA64: $_"
    }
}

# === GUI-режим (запуск из main.py) ===
if ($args.Count -ge 2) {
    $selectedTests = $args[0..($args.Count - 2)]
    $duration = $args[-1]
    $hours = [double]($duration) / 60

    $gpuCount = if ($selectedTests -contains "GPU2") { 2 } else { 1 }

    # Диски для FIO, если выбраны
    $fioDrives = @()
    foreach ($arg in $selectedTests) {
        if ($arg -match '^[A-Z]$') { $fioDrives += $arg }
    }

    if ($selectedTests -contains "FIO") {
        Start-FioTest -hours $hours -selectedDrives $fioDrives
    }
    if ($selectedTests -contains "FURMARK") {
        Start-FurMarkTest -hours $hours -gpuCount $gpuCount
    }
    if ($selectedTests -contains "AIDA") {
        $includeGPU = -not ($selectedTests -contains "FURMARK")
        $aidaProcess = Start-AidaTest -hours $hours -includeGPU $includeGPU

        Start-Sleep -Seconds 5
        Start-ScreenScript

        $aidaProcess.WaitForExit()

        Start-Sleep -Seconds 5
        Start-ScreenScript

        $exePath = Join-Path $PSScriptRoot "main.exe"
        Start-Process -FilePath $exePath -ArgumentList "--screen"
        Start-Sleep -Seconds 7
    }
    Write-Host "Тестирование завершено. Нажмите Enter..."
    Read-Host
    Start-Sleep -Seconds 5
    exit
}

# === Ручной режим (интерактив) ===
function Show-MainMenu {
    Clear-Host
    Write-Host "=== МЕНЮ ТЕСТИРОВАНИЯ ===" -ForegroundColor Cyan
    Write-Host "1) Только AIDA64"
    Write-Host "2) AIDA64 + FurMark"
    Write-Host "3) AIDA64 + FurMark + FIO"
    Write-Host "4) AIDA64 + FIO"
    $choice = Read-Host "`nВыберите тест (1-4)"
    while ($choice -notmatch "^[1-4]$") {
        $choice = Read-Host "Некорректный ввод. Введите число от 1 до 4"
    }
    Write-Host "`nВыберите длительность теста:"
    Write-Host "1) 10 минут"
    Write-Host "2) 30 минут"
    Write-Host "3) 1 час"
    Write-Host "4) 8 часов"
    Write-Host "5) 12 часов"
    Write-Host "6) Ввести свое значение"
    $timeChoice = Read-Host "Ваш выбор (1-6)"
    switch ($timeChoice) {
        1 { $hours = 10 / 60 }
        2 { $hours = 30 / 60 }
        3 { $hours = 1 }
        4 { $hours = 8 }
        5 { $hours = 12 }
        6 {
            $hours = Read-Host "Введите время теста в часах"
            while (-not ($hours -match '^\d*\.?\d+$') -or [double]$hours -le 0) {
                $hours = Read-Host "Некорректное значение. Введите время в часах"
            }
            $hours = [double]$hours
        }
        Default {
            Write-Host "Некорректный выбор. Установлено значение по умолчанию: 1 час."
            $hours = 1
        }
    }
    return $choice, $hours
}

try {
    if ($args.Count -lt 2) {
        $choice, $hours = Show-MainMenu
        if ($choice -in "3","4") {
            # Список дисков подбирай по твоей старой логике
            # ... (см. твой старый вариант)
            Write-Host "Диск для FIO ввести вручную или через Get-Volume"
        }
        if ($choice -in "2","3") {
            Write-Host "`nКоличество видеокарт:"
            Write-Host "1) Одна видеокарта"
            Write-Host "2) Две видеокарты"
            $gpuChoice = Read-Host "Ваш выбор (1-2)"
            $gpuCount = if ($gpuChoice -eq "2") { 2 } else { 1 }
            Start-FurMarkTest -hours $hours -gpuCount $gpuCount
        }
        $includeGPUinAIDA = $choice -eq 1
        $aidaProcess = Start-AidaTest -hours $hours -includeGPU $includeGPUinAIDA
        Write-Host "`nВсе тесты успешно запущены!" -ForegroundColor Green
        $aidaProcess.WaitForExit()
        $computerName = $env:COMPUTERNAME
        $desktopPath = [Environment]::GetFolderPath("Desktop")
        Generate-Report -computerName $computerName -desktopPath $desktopPath -aida64FullPath $aida64FullPath
    }
} catch {
    Write-Host "`nОшибка: $_" -ForegroundColor Red
} finally {
    Write-Host "`nНажмите любую клавишу для выхода..." -ForegroundColor Magenta
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
