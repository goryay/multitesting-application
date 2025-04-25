# Относительные пути (относительно директории скрипта)
$aida64Path = ".\SoftForTest\AIDA64\AIDA64Port.exe"
$furMarkPath = ".\SoftForTest\FurMark\furmark.exe"
$fioPath = "C:\Program Files\fio\fio.exe"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$aida64FullPath = Join-Path -Path $scriptDir -ChildPath $aida64Path
$furMarkFullPath = Join-Path -Path $scriptDir -ChildPath $furMarkPath

# --- ФУНКЦИИ ---
function Start-AidaTest
{
    param([double]$hours, [bool]$includeGPU)
    $minutes = [math]::Round($hours * 60)
    $gpuTest = if ($includeGPU)
    {
        ",GPU"
    }
    else
    {
        ""
    }
    $params = @("/SST CPU,FPU,Cache,RAM,Disk$gpuTest", "/SSTDUR $minutes")
    Write-Host "Запуск AIDA64: $( $params -join ' ' )"
    Start-Process -FilePath $aida64FullPath -ArgumentList $params -PassThru
}

function Start-FurMarkTest
{
    param([double]$hours, [int]$gpuCount)
    $seconds = [math]::Round($hours * 3600)
    $resolution = "1920x1080"
    $demo = "furmark-gl"  # Используем стабильный OpenGL-режим

    if ($gpuCount -eq 1)
    {
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
    }
    else
    {
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


function Start-FioTest
{
    param(
        [double]$hours,
        [string[]]$selectedDrives  # <-- теперь принимаем список выбранных дисков
    )

    $seconds = [math]::Round($hours * 3600)

    if (-not $selectedDrives)
    {
        Write-Host "Диски для FIO не выбраны. Пропуск теста."
        return
    }

    Write-Host "`nЗапуск FIO на дисках: $( $selectedDrives -join ', ' )"
    foreach ($disk in $selectedDrives)
    {
        $testDir = "${disk}:\fio_tests"
        if (-not (Test-Path $testDir))
        {
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
        # Генерация отчета AIDA64 (без ожидания завершения)
        Start-Process -FilePath $aida64FullPath -ArgumentList @(
            "/R `"$ReportPath`"",
            "/ALL", "/SUM", "/HW", "/SW", "/AUDIT", "/HTML"
        ) -NoNewWindow

        Write-Host "Запущена генерация отчета AIDA64 в фоне: $ReportPath"
    }
    catch {
        Write-Host "Ошибка при запуске генерации отчета AIDA64: $_"
    }
}


# --- ОБРАБОТКА GUI АРГУМЕНТОВ ---
# === GUI-режим ===
if ($args.Count -ge 2)
{
    $selectedTests = $args[0..($args.Count - 2)]
    $duration = $args[-1]
    $hours = [double]($duration) / 60

    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
    $aida64FullPath = Join-Path -Path $scriptDir -ChildPath ".\\SoftForTest\\AIDA64\\AIDA64Port.exe"
    $furMarkFullPath = Join-Path -Path $scriptDir -ChildPath ".\\SoftForTest\\FurMark\\furmark.exe"
    $fioPath = "C:\\Program Files\\fio\\fio.exe"

    $gpuCount = if ($selectedTests -contains "GPU2")
    {
        2
    }
    else
    {
        1
    }

    # Получаем список выбранных дисков
    $fioDrives = $null
    foreach ($arg in $selectedTests)
    {
        if ($arg -match '^[A-Z]$')
        {
            if (-not $fioDrives)
            {
                $fioDrives = @()
            }
            $fioDrives += $arg
        }
    }

    if ($selectedTests -contains "FIO")
    {
        Start-FioTest -hours $hours -selectedDrives $fioDrives
    }

    if ($selectedTests -contains "FURMARK")
    {
        Start-FurMarkTest -hours $hours -gpuCount $gpuCount
    }

    if ($selectedTests -contains "AIDA")
    {
        $includeGPU = -not ($selectedTests -contains "FURMARK")
        $aidaProcess = Start-AidaTest -hours $hours -includeGPU $includeGPU
        $aidaProcess.WaitForExit()
    }

    Write-Host "Тестирование завершено. Нажмите Enter..."
    Read-Host
    exit
}


Write-Host "Режим консоли активен. GUI не использовался."
