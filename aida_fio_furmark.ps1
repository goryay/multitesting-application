Push-Location -LiteralPath $PSScriptRoot
$script:__popOnExit = $true

# ===================== ОБЩИЙ СКРИН (Python) =====================
function Start-ScreenScript {
    $mainExe = Join-Path $PSScriptRoot "main.exe"
    if (Test-Path $mainExe) {
        Start-Process -FilePath $mainExe -ArgumentList "--screen"
    } else {
        Write-Host "main.exe не найден: $mainExe"
    }
}

# ===================== СКРИН AIDA64 (ОКНО) =====================
function Capture-Aida64Screenshot {
    param([bool]$isAutoScreen = $false)

    try {
        Add-Type -AssemblyName System.Drawing

        Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class Win32Cap {
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);

  [StructLayout(LayoutKind.Sequential)]
  public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
"@

        $desktop = [Environment]::GetFolderPath('Desktop')
        $pc = $env:COMPUTERNAME
        $screensDir = Join-Path $desktop "$pc\Screens"
        if (-not (Test-Path $screensDir)) {
            New-Item -ItemType Directory -Force -Path $screensDir | Out-Null
        }

        $p = Get-Process -Name "AIDA64Port" -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $p -or $p.MainWindowHandle -eq 0) {
            Write-Host "AIDA: окно не найдено"
            return $false
        }

        $hwnd = [IntPtr]$p.MainWindowHandle
        if (-not [Win32Cap]::IsWindow($hwnd) -or -not [Win32Cap]::IsWindowVisible($hwnd)) {
            Write-Host "AIDA: окно не активно/невидимо"
            return $false
        }

        $rect = New-Object Win32Cap+RECT
        if (-not [Win32Cap]::GetWindowRect($hwnd, [ref]$rect)) {
            Write-Host "AIDA: не удалось получить размеры окна"
            return $false
        }

        $w = $rect.Right - $rect.Left
        $h = $rect.Bottom - $rect.Top
        if ($w -lt 50 -or $h -lt 50) {
            Write-Host "AIDA: странные размеры окна ($w x $h)"
            return $false
        }

        $bmp = New-Object System.Drawing.Bitmap $w, $h, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
        $gfx = [System.Drawing.Graphics]::FromImage($bmp)
        $hdc = $gfx.GetHdc()

        try {
            [Win32Cap]::PrintWindow($hwnd, $hdc, 2) | Out-Null
        } finally {
            $gfx.ReleaseHdc($hdc)
            $gfx.Dispose()
        }

        $ts = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
        $tag = if ($isAutoScreen) { "auto" } else { "end" }
        $file = Join-Path $screensDir "aida_${tag}_${ts}.png"

        $bmp.Save($file, [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp.Dispose()

        Write-Host "AIDA: скрин сохранён -> $file"
        return $true
    }
    catch {
        Write-Host "AIDA: ошибка скрина: $_"
        return $false
    }
}

# ===================== ЗАПУСК ТЕСТОВ =====================
$aida64Path  = ".\SoftForTest\AIDA64\AIDA64Port.exe"
$furMarkPath = ".\SoftForTest\FurMark\furmark.exe"
$fioPath     = "C:\Program Files\fio\fio.exe"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$aida64FullPath  = Join-Path $scriptDir $aida64Path
$furMarkFullPath = Join-Path $scriptDir $furMarkPath

function Start-AidaTest {
    param([double]$hours, [bool]$includeGPU)
    $minutes = [math]::Round($hours * 60)
    $gpu = if ($includeGPU) { ",GPU" } else { "" }
    $params = @("/SST CPU,FPU,Cache,RAM,Disk$gpu", "/SSTDUR $minutes")
    $cmd = "`"$aida64FullPath`" $( $params -join ' ' )"
    Start-Process "cmd.exe" -ArgumentList "/k", $cmd | Out-Null
}

function Start-FurMarkTest {
    param([double]$hours, [int]$gpuCount)

    $seconds    = [math]::Round($hours * 3600)
    $resolution = "1920x1080"
    $demo       = "furmark-vk"

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
        if (-not (Test-Path $fioPath)) {
            Write-Host "FIO не найден по пути: $fioPath"
            continue
        }

        $inner = "`"$fioPath`" `"$configPath`" & pause"
        Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $inner | Out-Null

    }
}

function Generate-Report {
    [CmdletBinding()]
    param(
        [string]$computerName,
        [string]$desktopPath,
        [string]$aida64FullPath,
        [string]$outputFolder
    )

    if (-not $computerName) { $computerName = $env:COMPUTERNAME }

    if (-not $desktopPath) {
        $desktopPath = [Environment]::GetFolderPath("Desktop")
    }

    # ✅ По умолчанию — как в старом коде: Desktop\Report\<PC>\SystemReport.html
    if (-not $outputFolder) {
        $reportDirectory = Join-Path -Path $desktopPath -ChildPath ("Report\{0}" -f $computerName)
    } else {
        # ✅ Если передали outputFolder (как делает main.py) — кладём туда, чтобы было "вместе с остальными"
        $reportDirectory = $outputFolder
    }

    if (-not (Test-Path $reportDirectory)) {
        New-Item -ItemType Directory -Force -Path $reportDirectory | Out-Null
    }

    $ReportPath = Join-Path -Path $reportDirectory -ChildPath "SystemReport.html"

    try {
        # ✅ Как раньше: в фоне, НЕ ждём завершения
        Start-Process -FilePath $aida64FullPath -ArgumentList @(
            "/R `"$ReportPath`"",
            "/ALL", "/SUM", "/HW", "/SW", "/AUDIT", "/HTML"
        ) -NoNewWindow

        Write-Host "AIDA64: запущена генерация отчёта (в фоне): $ReportPath"
        return $ReportPath
    }
    catch {
        Write-Host "AIDA64: ошибка запуска отчёта: $_"
        return $null
    }
}

# ===================== ОЖИДАНИЕ ОТ СТАРТА AIDA =====================
function Sleep-UntilAida {
    param([int]$targetSec, [datetime]$start)
    $elapsed = [int]((Get-Date) - $start).TotalSeconds
    $remain = $targetSec - $elapsed
    if ($remain -gt 0) { Start-Sleep -Seconds $remain }
}

# ===================== ОСНОВНАЯ ЛОГИКА =====================
if ($args.Count -ge 2) {

    $tests = $args[0..($args.Count - 2)]
    $hours = [double]$args[-1] / 60
    $aidaSeconds = [int]($hours * 3600)

    $aidaStart = $null

    if ($tests -contains "AIDA") {
        $aidaStart = Get-Date
        Start-AidaTest -hours $hours -includeGPU (-not ($tests -contains "FURMARK"))
        Start-Sleep -Seconds 120
    }

    if ($tests -contains "FURMARK") {
        Start-FurMarkTest -hours $hours
        Start-Sleep -Seconds 60
    }

    if ($tests -contains "FIO") {
        $drives = $tests | Where-Object { $_ -match '^[A-Z]$' }
        Start-FioTest -hours $hours -selectedDrives $drives
        Start-Sleep -Seconds 45
    }

    if ($aidaStart) {
        # T-10 минут
        Sleep-UntilAida -targetSec ([math]::Max($aidaSeconds - 600, 60)) -start $aidaStart
        Capture-Aida64Screenshot -isAutoScreen $true | Out-Null

        # T-1 минута
        Sleep-UntilAida -targetSec ([math]::Max($aidaSeconds - 60, 60)) -start $aidaStart
        Capture-Aida64Screenshot -isAutoScreen $false | Out-Null

        # Дожидаемся конца
        Sleep-UntilAida -targetSec $aidaSeconds -start $aidaStart
    }

    Write-Host "Финальный общий скрин"
    Start-ScreenScript

    # ✅ Авто-отчёт AIDA ПОСЛЕ завершения тестов (как раньше)
    $computerName = $env:COMPUTERNAME
    $desktop = [Environment]::GetFolderPath("Desktop")

    # Если хочешь "как раньше" — оставь outputFolder пустым (уйдёт в Desktop\Report\<PC>)
    # Если хочешь "вместе с остальными" — укажи Desktop\<PC>\Reports
    $outputFolder = Join-Path (Join-Path $desktop $computerName) "Reports"

    Generate-Report -computerName $computerName -desktopPath $desktop -aida64FullPath $aida64FullPath -outputFolder $outputFolder | Out-Null

    Write-Host "Тестирование завершено"
    exit
}

Write-Host "GUI не использовался"
if ($script:__popOnExit) { Pop-Location }
