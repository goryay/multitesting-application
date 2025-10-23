Push-Location -LiteralPath $PSScriptRoot
$script:__popOnExit = $true

function Start-ScreenScript {
    $mainExe = Join-Path -Path $PSScriptRoot -ChildPath "main.exe"
    if (Test-Path $mainExe) {
        Start-Process -FilePath $mainExe -ArgumentList "--screen"
    } else {
        Write-Host "main.exe не найден: $mainExe"
    }
}

$aida64Path = ".\SoftForTest\AIDA64\AIDA64Port.exe"
$furMarkPath = ".\SoftForTest\FurMark\furmark.exe"
$fioPath = "C:\Program Files\fio\fio.exe"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$aida64FullPath = Join-Path -Path $scriptDir -ChildPath $aida64Path
$furMarkFullPath = Join-Path -Path $scriptDir -ChildPath $furMarkPath

function Start-AidaTest {
    param([double]$hours, [bool]$includeGPU)
    $minutes = [math]::Round($hours * 60)
    $gpuTest = if ($includeGPU) { ",GPU" } else { "" }
    $params = @("/SST CPU,FPU,Cache,RAM,Disk$gpuTest", "/SSTDUR $minutes")
    $inner = "`"$aida64FullPath`" $( $params -join ' ' ) & pause"
    $proc  = Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $inner -PassThru
    return $proc
}

function Start-FurMarkTest {
    param([double]$hours, [int]$gpuCount)
    $seconds = [math]::Round($hours * 3600)
    $resolution = "1920x1080"
    $demo = "furmark-vk"  # Vulkan/две карты

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
        $inner = "`"$furMarkFullPath`" $( $params -join ' ' ) & pause"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $inner | Out-Null
    } else {
        $params1 = @(
            "--demo $demo", "--fullscreen",
            "--width $( $resolution.Split('x')[0] )",
            "--height $( $resolution.Split('x')[1] )",
            "--max-time $seconds", "--no-score-box", "--disable-demo-options", "--gpu-index 0"
        )
        $params2 = @(
            "--demo $demo", "--fullscreen",
            "--width $( $resolution.Split('x')[0] )",
            "--height $( $resolution.Split('x')[1] )",
            "--max-time $seconds", "--no-score-box", "--disable-demo-options", "--gpu-index 1"
        )
        $inner1 = "`"$furMarkFullPath`" $( $params1 -join ' ' ) & pause"
        $inner2 = "`"$furMarkFullPath`" $( $params2 -join ' ' ) & pause"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $inner1 | Out-Null
        Start-Sleep -Seconds 3
        Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $inner2 | Out-Null
    }
}

function Start-FioTest {
    param([double]$hours, [string[]]$selectedDrives)
    $seconds = [math]::Round($hours * 3600)
    if (-not $selectedDrives) {
        Write-Host "Диски для FIO не выбраны. Пропуск теста."
        return
    }
    foreach ($disk in $selectedDrives) {
        $testDir = "${disk}:\fio_tests"
        if (-not (Test-Path $testDir)) {
            New-Item -ItemType Directory -Path $testDir -Force | Out-Null
        }
        $testFile = "$testDir\fio_test_$([Guid]::NewGuid()).dat"
        $configPath = "$env:TEMP\fio_config_$([Guid]::NewGuid()).fio"
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
    [CmdletBinding()]
    param(
        [string]$computerName,
        [string]$aida64FullPath,   # полный путь к AIDA64Port.exe
        [string]$outputFolder      # КУДА класть отчёт (Desktop\<ПК>\Reports)
    )

    if (-not $computerName -or $computerName -eq "") {
        $computerName = $env:COMPUTERNAME
    }

    # fallback на нужную структуру, если не передали из Python
    if (-not $outputFolder -or $outputFolder -eq "") {
        $desktop = [Environment]::GetFolderPath('Desktop')
        $outputFolder = Join-Path (Join-Path $desktop $computerName) 'Reports'
    }
    New-Item -ItemType Directory -Force -Path $outputFolder | Out-Null

    if (-not (Test-Path $aida64FullPath)) {
        throw "AIDA64 не найдена: $aida64FullPath"
    }

    $ts = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
    $aidaHtml = Join-Path $outputFolder ("AIDA64_{0}_{1}.html" -f $computerName, $ts)

    # Генерация HTML из AIDA64 в наш целевой файл
    # /R <file> — путь отчёта, /HTML — формат, /SILENT — без UI
    $args = @('/R', "`"$aidaHtml`"", '/HTML', '/SILENT')
    Start-Process -FilePath $aida64FullPath -ArgumentList $args -Wait -NoNewWindow
}


# --- ОБРАБОТКА GUI АРГУМЕНТОВ ---
if ($args.Count -ge 2) {
    $selectedTests = $args[0..($args.Count - 2)]
    $duration = $args[-1]
    $hours = [double]($duration) / 60

    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
    $aida64FullPath = Join-Path -Path $scriptDir -ChildPath ".\SoftForTest\AIDA64\AIDA64Port.exe"
    $furMarkFullPath = Join-Path -Path $scriptDir -ChildPath ".\SoftForTest\FurMark\furmark.exe"
    $fioPath = "C:\Program Files\fio\fio.exe"

    $gpuCount = if ($selectedTests -contains "GPU2") { 2 } else { 1 }
    $fioDrives = @()
    foreach ($arg in $selectedTests) { if ($arg -match '^[A-Z]$') { $fioDrives += $arg } }

    # Параллельные запуски
    if ($selectedTests -contains "FIO") { Start-FioTest -hours $hours -selectedDrives $fioDrives; Start-Sleep -Seconds 1 }
    if ($selectedTests -contains "FURMARK") { Start-FurMarkTest -hours $hours -gpuCount $gpuCount; Start-Sleep -Seconds 1 }

    $aidaProc = $null
    if ($selectedTests -contains "AIDA") {
        $includeGPU = -not ($selectedTests -contains "FURMARK")
        $aidaProc = Start-AidaTest -hours $hours -includeGPU $includeGPU
    }

    $totalSeconds = [math]::Round($hours * 3600)

    if ($selectedTests -contains "AIDA") {
        # Скрин AIDA перед авто-закрытием
        $aida_delay = [math]::Max($totalSeconds - 15, 1)
        Start-Sleep -Seconds $aida_delay
        Start-ScreenScript
        Start-Sleep -Seconds 20  # дождаться финалов FurMark/FIO и оставить их окна открытыми
    } else {
        Start-Sleep -Seconds $totalSeconds
    }

    Start-ScreenScript  # Финальный общий скрин (FIO/FurMark/итоги)

    # Генерация отчёта AIDA64 (как раньше)
    $desktop = [Environment]::GetFolderPath("Desktop")
    $computerName = $env:COMPUTERNAME
    Generate-Report -computerName $computerName -desktopPath $desktop -aida64FullPath $aida64FullPath

    Write-Host "Тестирование завершено. Скриншоты и отчёт сохранены."
    exit
}

Write-Host "Режим консоли активен. GUI не использовался."
if ($script:__popOnExit) { Pop-Location }
