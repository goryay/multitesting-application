# ======================= самоповышение прав (UAC) =========================
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $argsLine = @()
    foreach ($a in $args) { $argsLine += ('"{0}"' -f $a) }
    $argStr = ('-ExecutionPolicy Bypass -File "{0}" {1}' -f $PSCommandPath, ($argsLine -join ' '))
    try { Start-Process -FilePath "pwsh.exe" -ArgumentList $argStr -Verb RunAs } catch { Write-Host "UAC fail: $_" }
    exit
}
# ========================================================================

Push-Location -LiteralPath $PSScriptRoot
$script:__popOnExit = $true

# --- читаем state для путей к лаунчеру/рабочей папке ---
function Get-StatePath {
    $ld = Join-Path -Path $env:LOCALAPPDATA -ChildPath "TestLauncher\test_state.json"
    if (Test-Path $ld) { return $ld }
    $legacy = Join-Path -Path ([Environment]::GetFolderPath("Desktop")) -ChildPath "test_state.json"
    if (Test-Path $legacy) { return $legacy }
    return $null
}
function Read-State {
    $p = Get-StatePath
    if ($p -and (Test-Path $p)) {
        try { return Get-Content -Raw -Path $p | ConvertFrom-Json } catch { return $null }
    }
    return $null
}
$STATE = Read-State

function Start-ScreenScript {
    $launcher = $null
    $wd = $PSScriptRoot
    if ($STATE) {
        if ($STATE.launcher_path) { $launcher = $STATE.launcher_path }
        if ($STATE.workdir)       { $wd = $STATE.workdir }
    }
    if (-not $launcher) { $launcher = Join-Path -Path $wd -ChildPath "main.exe" }

    if (Test-Path $launcher) {
        Start-Process -FilePath $launcher -ArgumentList "--screen" -WindowStyle Hidden -WorkingDirectory $wd
    } else {
        Write-Host "Launcher not found: $launcher"
    }
}

$aida64Path  = ".\SoftForTest\AIDA64\AIDA64Port.exe"
$furMarkPath = ".\SoftForTest\FurMark\furmark.exe"
$fioPath     = "C:\Program Files\fio\fio.exe"

$scriptDir       = Split-Path -Parent $MyInvocation.MyCommand.Definition
$aida64FullPath  = Join-Path -Path $scriptDir -ChildPath $aida64Path
$furMarkFullPath = Join-Path -Path $scriptDir -ChildPath $furMarkPath

function Start-AidaTest {
    param([double]$hours, [bool]$includeGPU)
    $minutes = [math]::Round($hours * 60)
    $gpuTest = if ($includeGPU) { ",GPU" } else { "" }
    $params  = @("/SST CPU,FPU,Cache,RAM,Disk$gpuTest", "/SSTDUR $minutes")
    $cmd     = "cmd /k `"`"$aida64FullPath`" $( $params -join ' ' ) & pause`""
    $proc    = Start-Process cmd.exe -ArgumentList "/c", $cmd -PassThru
    return $proc
}

function Start-FurMarkTest {
    param([double]$hours, [int]$gpuCount)
    $seconds    = [math]::Round($hours * 3600)
    $resolution = "1920x1080"
    $demo       = "furmark-vk"
    if ($gpuCount -eq 1) {
        $params = @(
            "--demo $demo","--fullscreen",
            "--width $( $resolution.Split('x')[0] )","--height $( $resolution.Split('x')[1] )",
            "--max-time $seconds","--no-score-box","--disable-demo-options"
        )
        $cmd = "cmd /k `"`"$furMarkFullPath`" $( $params -join ' ' ) & pause`""
        Start-Process cmd.exe -ArgumentList "/c", $cmd | Out-Null
    } else {
        $params1 = @("--demo $demo","--fullscreen","--width $( $resolution.Split('x')[0] )","--height $( $resolution.Split('x')[1] )","--max-time $seconds","--no-score-box","--disable-demo-options","--gpu-index 0")
        $params2 = @("--demo $demo","--fullscreen","--width $( $resolution.Split('x')[0] )","--height $( $resolution.Split('x')[1] )","--max-time $seconds","--no-score-box","--disable-demo-options","--gpu-index 1")
        $cmd1 = "cmd /k `"`"$furMarkFullPath`" $( $params1 -join ' ' ) & pause`""
        $cmd2 = "cmd /k `"`"$furMarkFullPath`" $( $params2 -join ' ' ) & pause`""
        Start-Process cmd.exe -ArgumentList "/c", $cmd1 | Out-Null
        Start-Sleep -Seconds 3
        Start-Process cmd.exe -ArgumentList "/c", $cmd2 | Out-Null
    }
}

function Start-FioTest {
    param([double]$hours, [string[]]$selectedDrives)
    $seconds = [math]::Round($hours * 3600)
    if (-not $selectedDrives) { Write-Host "FIO: диски не выбраны"; return }
    foreach ($disk in $selectedDrives) {
        $testDir = "${disk}:\fio_tests"
        if (-not (Test-Path $testDir)) { New-Item -ItemType Directory -Path $testDir -Force | Out-Null }
        $testFile   = "$testDir\fio_test_$([Guid]::NewGuid()).dat"
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
        Set-Content -Path $configPath -Value $config -Encoding ASCII
        $cmd = "cmd /k `"`"$fioPath`" `"$configPath`" & pause`""
        Start-Process cmd.exe -ArgumentList "/c", $cmd | Out-Null
    }
}

function Generate-Report {
    param([string]$computerName,[string]$desktopPath,[string]$aida64FullPath)
    $reportDirectory = Join-Path -Path $desktopPath -ChildPath "Report\$computerName"
    $ReportPath      = Join-Path -Path $reportDirectory -ChildPath "SystemReport.html"
    if (-Not (Test-Path -Path $reportDirectory)) { New-Item -ItemType Directory -Path $reportDirectory | Out-Null }
    try {
        Start-Process -FilePath $aida64FullPath -ArgumentList @("/R `"$ReportPath`"","/ALL","/SUM","/HW","/SW","/AUDIT","/HTML") -NoNewWindow
        Write-Host "AIDA64 report started: $ReportPath"
    } catch { Write-Host "AIDA64 report error: $_" }
}

# -------- обработка аргументов от GUI/headless --------
if ($args.Count -ge 2) {
    $selectedTests = $args[0..($args.Count - 2)]
    $duration      = $args[-1]
    $hours         = [double]($duration) / 60

    $scriptDir       = Split-Path -Parent $MyInvocation.MyCommand.Definition
    $aida64FullPath  = Join-Path -Path $scriptDir -ChildPath ".\SoftForTest\AIDA64\AIDA64Port.exe"
    $furMarkFullPath = Join-Path -Path $scriptDir -ChildPath ".\SoftForTest\FurMark\furmark.exe"
    $fioPath         = "C:\Program Files\fio\fio.exe"

    $gpuCount  = if ($selectedTests -contains "GPU2") { 2 } else { 1 }
    $fioDrives = @(); foreach ($arg in $selectedTests) { if ($arg -match '^[A-Z]$') { $fioDrives += $arg } }

    if ($selectedTests -contains "FIO")     { Start-FioTest     -hours $hours -selectedDrives $fioDrives; Start-Sleep -Seconds 1 }
    if ($selectedTests -contains "FURMARK") { Start-FurMarkTest -hours $hours -gpuCount $gpuCount;      Start-Sleep -Seconds 1 }

    $aidaProc = $null
    if ($selectedTests -contains "AIDA") {
        $includeGPU = -not ($selectedTests -contains "FURMARK")
        $aidaProc   = Start-AidaTest -hours $hours -includeGPU $includeGPU
    }

    $totalSeconds = [math]::Round($hours * 3600)
    $preEndShot   = 3

    if ($selectedTests -contains "AIDA") {
        Start-Sleep -Seconds ([math]::Max($totalSeconds - $preEndShot, 1))
        Start-ScreenScript
        if ($aidaProc) { [void]$aidaProc.WaitForExit(20000) }

        $othersRunning = ($selectedTests -contains "FURMARK") -or ($selectedTests -contains "FIO")
        if ($othersRunning) {
            Start-Sleep -Seconds $preEndShot
            Start-ScreenScript
        }
    } else {
        Start-Sleep -Seconds $totalSeconds
        Start-ScreenScript
    }

    $desktop      = [Environment]::GetFolderPath("Desktop")
    $computerName = $env:COMPUTERNAME
    Generate-Report -computerName $computerName -desktopPath $desktop -aida64FullPath $aida64FullPath

    Write-Host "Тестирование завершено. Скриншоты и отчёт сохранены."
    if ($script:__popOnExit) { Pop-Location }
    exit
}

Write-Host "Режим консоли активен. GUI не использовался."
if ($script:__popOnExit) { Pop-Location }
