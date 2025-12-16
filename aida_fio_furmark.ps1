Push-Location -LiteralPath $PSScriptRoot
$script:__popOnExit = $true
$ErrorActionPreference = "Stop"

# ===================== ОБЩИЙ СКРИН (Python main.exe) =====================
function Start-ScreenScript {
    param(
        [string]$arg = "--screen",
        [switch]$AidaOnly = $false
    )

    $mainExe = Join-Path $PSScriptRoot "main.exe"
    $pythonScript = Join-Path $PSScriptRoot "screen.py"

    if ($AidaOnly) {
        # Специальный скриншот только AIDA64
        if (Test-Path $pythonScript) {
            # Запускаем Python скрипт напрямую для скриншота AIDA64
            $argList = @()
            if ($arg -eq "--autoscreen") {
                $argList = @("--autoscreen", "--aida-only")
            } else {
                $argList = @("--screen", "--aida-only")
            }

            # Проверяем наличие окна AIDA64
            $aidaProcess = Get-Process -Name "AIDA64Port" -ErrorAction SilentlyContinue |
                           Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -like "*System Stability Test*" }

            if ($aidaProcess) {
                Write-Host "Найдено окно AIDA64, делаем скриншот..."
                $python = "python"
                if (Test-Path "C:\Python312\python.exe") { $python = "C:\Python312\python.exe" }
                elseif (Test-Path "C:\Python311\python.exe") { $python = "C:\Python311\python.exe" }
                elseif (Test-Path "C:\Python310\python.exe") { $python = "C:\Python310\python.exe" }

                try {
                    & $python $pythonScript @argList
                } catch {
                    Write-Host "Ошибка запуска Python: $_"
                }
            } else {
                Write-Host "Окно AIDA64 не найдено для скриншота"
            }
        } else {
            Write-Host "screen.py не найден: $pythonScript"
        }
    } else {
        # Обычный скриншот всех окон
        if (Test-Path $mainExe) {
            Start-Process -FilePath $mainExe -ArgumentList $arg | Out-Null
        } else {
            Write-Host "main.exe не найден: $mainExe"
        }
    }
}

# ===================== ПРОЦЕССНЫЕ ХЕЛПЕРЫ =====================
function Close-ProcessByName {
    param(
        [Parameter(Mandatory=$true)][string]$name,
        [int]$waitSeconds = 10
    )

    $p = Get-Process -Name $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $p) { return }

    try {
        if ($p.MainWindowHandle -ne 0) { $null = $p.CloseMainWindow() }
    } catch {}

    try { $p | Wait-Process -Timeout $waitSeconds -ErrorAction SilentlyContinue } catch {}

    $p2 = Get-Process -Name $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($p2) {
        try { Stop-Process -Id $p2.Id -Force -ErrorAction SilentlyContinue } catch {}
        Start-Sleep -Seconds 2
    }
}

# ===================== ПУТИ =====================
$aida64Path  = ".\SoftForTest\AIDA64\AIDA64Port.exe"
$furMarkPath = ".\SoftForTest\FurMark\furmark.exe"
$fioPath     = "C:\Program Files\fio\fio.exe"

$scriptDir       = Split-Path -Parent $MyInvocation.MyCommand.Definition
$aida64FullPath  = Join-Path $scriptDir $aida64Path
$furMarkFullPath = Join-Path $scriptDir $furMarkPath

# ===================== ЗАПУСК AIDA64 (в cmd, чтобы окно осталось) =====================
function Start-AidaTest {
    param([double]$hours, [bool]$includeGPU)

    if (-not (Test-Path $aida64FullPath)) { throw "AIDA64 не найдена: $aida64FullPath" }

    $minutes = [math]::Round($hours * 60)
    $gpu = if ($includeGPU) { ",GPU" } else { "" }
    $params = @("/SST CPU,FPU,Cache,RAM,Disk$gpu", "/SSTDUR $minutes")

    # /k + pause => cmd не закроется, а AIDA отработает в своём окне
    $cmdLine = "`"$aida64FullPath`" $($params -join ' ')"
    $process = Start-Process -FilePath "cmd.exe" -ArgumentList @("/k", "$cmdLine") -PassThru
    return $process
}

# ===================== ЗАПУСК FURMARK (с улучшениями) =====================
function Start-FurMarkTest {
    param([double]$hours, [int]$gpuCount)

    if (-not (Test-Path $furMarkFullPath)) { throw "FurMark не найден: $furMarkFullPath" }

    $seconds    = [math]::Round($hours * 3600)
    $resolution = "1920x1080"
    $demo       = "furmark-vk"

    $w = $resolution.Split('x')[0]
    $h = $resolution.Split('x')[1]

    if ($gpuCount -le 1) {
        $params = @(
            "--demo $demo",
            "--fullscreen",
            "--width $w",
            "--height $h",
            "--max-time $seconds",
            "--no-score-box",
            "--disable-demo-options"
        )

        # УЛУЧШЕННАЯ КОМАНДА: сначала FurMark, потом пауза
        $cmdArgs = @(
            "/k",
            "echo Запуск FurMark...",
            "&",
            "`"$furMarkFullPath`" $($params -join ' ')",
            "&",
            "echo.",
            "&",
            "echo Тест FurMark завершен!",
            "&",
            "echo Для закрытия окна нажмите любую клавишу...",
            "&",
            "pause > nul"
        )

        Write-Host "Запуск FurMark..."
        Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs -WindowStyle Normal
    }
    else {
        $params1 = @(
            "--demo $demo",
            "--fullscreen",
            "--width $w",
            "--height $h",
            "--max-time $seconds",
            "--no-score-box",
            "--disable-demo-options",
            "--gpu-index 0"
        )
        $params2 = @(
            "--demo $demo",
            "--fullscreen",
            "--width $w",
            "--height $h",
            "--max-time $seconds",
            "--no-score-box",
            "--disable-demo-options",
            "--gpu-index 1"
        )

        $cmdArgs1 = @(
            "/k",
            "echo Запуск FurMark для GPU 0...",
            "&",
            "`"$furMarkFullPath`" $($params1 -join ' ')",
            "&",
            "echo.",
            "&",
            "echo Тест FurMark завершен!",
            "&",
            "pause > nul"
        )

        $cmdArgs2 = @(
            "/k",
            "echo Запуск FurMark для GPU 1...",
            "&",
            "`"$furMarkFullPath`" $($params2 -join ' ')",
            "&",
            "echo.",
            "&",
            "echo Тест FurMark завершен!",
            "&",
            "pause > nul"
        )

        Write-Host "Запуск FurMark для GPU 0..."
        Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs1 -WindowStyle Normal
        Start-Sleep -Seconds 3
        Write-Host "Запуск FurMark для GPU 1..."
        Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs2 -WindowStyle Normal
    }
}

# ===================== ЗАПУСК FIO (с улучшениями) =====================
function Start-FioTest {
    param([double]$hours, [string[]]$selectedDrives)

    # Проверяем наличие FIO
    if (-not (Test-Path $fioPath)) {
        Write-Host "FIO не найден по пути: $fioPath"
        Write-Host "Проверьте установку FIO в C:\Program Files\fio\"
        return
    }

    $seconds = [math]::Round($hours * 3600)

    if (-not $selectedDrives -or $selectedDrives.Count -eq 0) {
        Write-Host "Диски для FIO не выбраны. Пропуск теста."
        return
    }

    foreach ($disk in $selectedDrives) {
        $testDir = "${disk}:\fio_tests"
        if (-not (Test-Path $testDir)) {
            New-Item -ItemType Directory -Path $testDir -Force | Out-Null
        }

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

        # УЛУЧШЕННАЯ КОМАНДА: запуск FIO с сохранением окна
        $cmdArgs = @(
            "/k",
            "echo Запуск FIO теста для диска $disk",
            "&",
            "echo Пожалуйста, подождите...",
            "&",
            "`"$fioPath`" `"$configPath`"",
            "&",
            "echo.",
            "&",
            "echo =========================================",
            "&",
            "echo Тест FIO завершен!",
            "&",
            "echo Для закрытия окна нажмите любую клавишу...",
            "&",
            "pause > nul"
        )

        Write-Host "Запуск FIO для диска $disk..."
        Start-Process -FilePath "cmd.exe" -ArgumentList $cmdArgs -WindowStyle Normal

        Start-Sleep -Seconds 3
    }
}

# ===================== ОТЧЁТ AIDA64 (после завершения тестов) =====================
function Generate-AidaReport {
    [CmdletBinding()]
    param(
        [string]$computerName,
        [string]$aida64FullPath,
        [string]$outputFolder
    )

    if (-not $computerName) { $computerName = $env:COMPUTERNAME }
    if (-not $outputFolder -or $outputFolder -eq "") {
        $desktop = [Environment]::GetFolderPath("Desktop")
        $outputFolder = Join-Path (Join-Path $desktop $computerName) "Reports"
    }
    New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null

    $reportPath = Join-Path $outputFolder "SystemReport.html"

    # Чтобы не было "программа уже запущена" — закрываем стресс-экземпляр AIDA64 перед отчётом
    Close-ProcessByName -name "AIDA64Port" -waitSeconds 20

    # Генерим отчёт и ЖДЁМ (так надёжнее)
    Start-Process -FilePath $aida64FullPath -ArgumentList @(
        "/R `"$reportPath`"",
        "/ALL", "/SUM", "/HW", "/SW", "/AUDIT", "/HTML"
    ) -Wait -NoNewWindow

    Write-Host "AIDA64: отчёт готов -> $reportPath"
    return $reportPath
}

# ===================== ОЖИДАНИЕ ОТ СТАРТА AIDA =====================
function Sleep-Until {
    param([int]$targetSec, [datetime]$start)
    $elapsed = [int]((Get-Date) - $start).TotalSeconds
    $remain = $targetSec - $elapsed
    if ($remain -gt 0) { Start-Sleep -Seconds $remain }
}

# ===================== ОСНОВНАЯ ЛОГИКА (аргументы от GUI) =====================
if ($args.Count -ge 2) {

    $tests = $args[0..($args.Count - 2)]
    $durationMin = [double]$args[-1]
    $hours = $durationMin / 60
    $totalSeconds = [int][math]::Round($hours * 3600)

    $gpuCount  = if ($tests -contains "GPU2") { 2 } else { 1 }
    $fioDrives = @($tests | Where-Object { $_ -match '^[A-Z]$' })

    $desktop = [Environment]::GetFolderPath("Desktop")
    $pc = $env:COMPUTERNAME
    $reportsDir = Join-Path (Join-Path $desktop $pc) "Reports"

    $aidaStart = $null
    $aidaProcess = $null
    $allProcesses = @()

    # ===== ПОСЛЕДОВАТЕЛЬНЫЙ ЗАПУСК (как ты хочешь) =====
    if ($tests -contains "AIDA") {
        $aidaStart = Get-Date
        $includeGPU = -not ($tests -contains "FURMARK")
        Write-Host "Запуск AIDA64..."

        # Запускаем AIDA64 и сохраняем процесс
        $aidaProcess = Start-AidaTest -hours $hours -includeGPU $includeGPU
        Write-Host "AIDA64 запущена (PID: $($aidaProcess.Id))"
        $allProcesses += $aidaProcess
        Start-Sleep -Seconds 120
    }

    if ($tests -contains "FURMARK") {
        Write-Host "Запуск FurMark..."
        Start-FurMarkTest -hours $hours -gpuCount $gpuCount
        Start-Sleep -Seconds 60
    }

    if ($tests -contains "FIO") {
        Write-Host "Запуск FIO (диски: $($fioDrives -join ', '))..."
        Start-FioTest -hours $hours -selectedDrives $fioDrives
        Start-Sleep -Seconds 45
    }
    # ===== КОНЕЦ ПОСЛЕДОВАТЕЛЬНОГО ЗАПУСКА =====

    # ----- AIDA: 2 скрина окна до конца теста -----
    if ($aidaStart) {
        # УПРОЩЕННАЯ ЛОГИКА:
        # 1. Первый скрин за 2 минуты до конца (или за 30 секунд для коротких тестов)
        # 2. Второй скрин за 15 секунд до конца

        $first_screen_delay = if ($totalSeconds -gt 300) { $totalSeconds - 120 } else { $totalSeconds - 30 }
        if ($first_screen_delay -lt 10) { $first_screen_delay = 10 }

        Write-Host "Первый скрин AIDA через $first_screen_delay секунд"
        Sleep-Until -targetSec $first_screen_delay -start $aidaStart
        # Используем общий скриншотер вместо неработающей функции
        Start-ScreenScript -arg "--autoscreen" -AidaOnly
        Start-Sleep -Seconds 2

        # Второй скрин за 15 секунд до конца
        $second_screen_delay = $totalSeconds - 15
        if ($second_screen_delay -lt 5) { $second_screen_delay = 5 }

        Write-Host "Второй скрин AIDA через $second_screen_delay секунд"
        Sleep-Until -targetSec $second_screen_delay -start $aidaStart
        # Используем общий скриншотер вместо неработающей функции
        Start-ScreenScript -arg "--screen" -AidaOnly
        Start-Sleep -Seconds 2

        # Дожидаемся конца таймера
        Sleep-Until -targetSec $totalSeconds -start $aidaStart

        # ЖДЁМ ЗАВЕРШЕНИЯ AIDA64
        Write-Host "Ожидание завершения AIDA64..."
        if ($aidaProcess) {
            try {
                $aidaProcess | Wait-Process -Timeout 30 -ErrorAction SilentlyContinue
                Write-Host "AIDA64 завершена"

                # СДЕЛАТЬ СКРИНШОТ AIDA64 СРАЗУ ПОСЛЕ ЗАВЕРШЕНИЯ
                Write-Host "Делаем скриншот AIDA64 сразу после завершения..."
                Start-ScreenScript -arg "--screen" -AidaOnly
                Start-Sleep -Seconds 5

            } catch {
                Write-Host "AIDA64 не завершилась за 30 секунд, продолжаем"
            }
        }
    } else {
        # Если AIDA не запускалась — просто ждём общий таймер
        Write-Host "Ожидание завершения теста ($totalSeconds секунд)..."
        Start-Sleep -Seconds $totalSeconds

        # После завершения AIDA64 сделай специальный скриншот
        Write-Host "Делаем ФИНАЛЬНЫЙ скриншот AIDA64 перед закрытием..."
        Start-ScreenScript -arg "--screen" -AidaOnly
        Start-Sleep -Seconds 3
    }

    # ----- ЖДЁМ ЗАВЕРШЕНИЯ ВСЕХ ПРОЦЕССОВ -----
    Write-Host "Ожидание завершения всех тестов..."

    # Ждём процессы AIDA64
    if ($aidaProcess) {
        try {
            $aidaProcess | Wait-Process -Timeout 60 -ErrorAction SilentlyContinue
            Write-Host "AIDA64 завершилась"
        } catch {
            Write-Host "AIDA64 ещё работает, продолжаем"
        }
    }

    # Даём дополнительное время на завершение
    Start-Sleep -Seconds 30

    # ----- ФИНАЛ: общий скрин (тут должны попасть FIO/FurMark в состоянии "pause") -----
    Write-Host "Финальный общий скрин"

    # ЖДЁМ чтобы окна точно появились
    Write-Host "Ожидание появления финальных окон (10 секунд)..."
    Start-Sleep -Seconds 10

    # Делаем скрин несколько раз для надёжности
    for ($i = 1; $i -le 3; $i++) {
        Write-Host "Попытка скрина #$i"
        Start-ScreenScript -arg "--screen" -AidaOnly
        Start-Sleep -Seconds 5
    }

    Write-Host "Тестирование завершено"
    exit
}

Write-Host "GUI не использовался"
if ($script:__popOnExit) { Pop-Location }