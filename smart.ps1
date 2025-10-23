# Путь к smartctl
$smartctlPath = "C:\Program Files\smartmontools\bin\smartctl.exe"

# Папка для отчётов на рабочем столе
$computerName = $env:COMPUTERNAME
$baseFolder = Join-Path $env:USERPROFILE "Desktop\$computerName"
$reportFolder = Join-Path $baseFolder "Reports"

if (-not (Test-Path $reportFolder)) {
    New-Item -ItemType Directory -Path $reportFolder -Force | Out-Null
}

# Проверка наличия smartctl
if (-not (Test-Path $smartctlPath)) {
    Write-Host "Ошибка: smartctl.exe не найден по указанному пути" -ForegroundColor Red
    exit 1
}

# Получаем список всех дисков
$disks = & $smartctlPath --scan | ForEach-Object { $_.Split()[0] }

if (-not $disks) {
    Write-Host "Не обнаружено ни одного диска для проверки" -ForegroundColor Red
    exit 1
}

# Создаём отчёт
$report = foreach ($disk in $disks) {
    $diskInfo = & $smartctlPath --all $disk | Out-String
    
    # Парсим общую информацию
    $model = ($diskInfo -split "Device Model:|Model Number:")[1] -split "`n" | Select-Object -First 1 | ForEach-Object { $_.Trim() }
    $serial = ($diskInfo -split "Serial Number:")[1] -split "`n" | Select-Object -First 1 | ForEach-Object { $_.Trim() }
    $health = ($diskInfo -split "SMART overall-health self-assessment test result:")[1] -split "`n" | Select-Object -First 1 | ForEach-Object { $_.Trim() }
    
    # Для NVMe дисков
    if ($diskInfo -match "NVME") {
        $temp = ($diskInfo -split "Temperature:")[1] -split "`n" | Select-Object -First 1 | ForEach-Object { $_.Trim() }
        $powerHours = ($diskInfo -split "Power On Hours:")[1] -split "`n" | Select-Object -First 1 | ForEach-Object { $_.Trim() }
        $mediaErrors = ($diskInfo -split "Media and Data Integrity Errors:")[1] -split "`n" | Select-Object -First 1 | ForEach-Object { $_.Trim() }
        
        [PSCustomObject]@{
            Disk = $disk
            Type = "NVMe"
            Model = $model
            Serial = $serial
            Health = $health
            Temperature = $temp
            PowerOnHours = $powerHours
            MediaErrors = $mediaErrors
            SMARTData = $diskInfo
        }
    }
    # Для SATA/HDD дисков
    else {
        $temp = ($diskInfo -split "Temperature_Celsius")[1] -split "`n" | Select-Object -First 1 | ForEach-Object { ($_ -split "-")[0].Trim() }
        $powerHours = ($diskInfo -split "Power_On_Hours")[1] -split "`n" | Select-Object -First 1 | ForEach-Object { ($_ -split "-")[0].Trim() }
        $reallocated = ($diskInfo -split "Reallocated_Sector_Ct")[1] -split "`n" | Select-Object -First 1 | ForEach-Object { ($_ -split "-")[0].Trim() }
        $pending = ($diskInfo -split "Current_Pending_Sector")[1] -split "`n" | Select-Object -First 1 | ForEach-Object { ($_ -split "-")[0].Trim() }
        
        [PSCustomObject]@{
            Disk = $disk
            Type = "SATA/HDD"
            Model = $model
            Serial = $serial
            Health = $health
            Temperature = $temp + "°C"
            PowerOnHours = $powerHours + " hours"
            ReallocatedSectors = $reallocated
            PendingSectors = $pending
            SMARTData = $diskInfo
        }
    }
}

# Сохраняем отчёты
$csvReport = "$reportFolder\SMART_Report_All_Disks_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"
$fullReport = "$reportFolder\SMART_Full_Details_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"

$report | Select-Object * -ExcludeProperty SMARTData | Export-Csv -Path $csvReport -NoTypeInformation -Encoding UTF8
$report | ForEach-Object { 
    "===== $($_.Disk) ($($_.Type)) ====="
    $_.SMARTData
    ""
} | Out-File -FilePath $fullReport

# Выводим сводную информацию
$report | Format-Table -Property `
    'Disk',
    'Type',
    @{ Label = 'Health'; Expression = {
        if ($_.Health -eq 'PASSED') { '✅' } else { '❌' }
    }},
    @{ Label = 'Temperature'; Expression = {
        if ($null -ne $_.Temperature) { '{0:N0}' -f $_.Temperature } else { '' }
    }},
    @{ Label = 'PowerOnHours'; Expression = {
        if ($null -ne $_.PowerOnHours) { '{0:N0}' -f $_.PowerOnHours } else { '' }
    }},
    @{ Label = 'Media/Realloc'; Expression = {
        $v = if ($_.Type -eq 'NVMe') { $_.MediaErrors } else { $_.ReallocatedSectors }
        $n = [int]($v)
        if ($n -gt 0) { "⚠️$n" } else { "$n" }
    }},
    @{ Label = 'PendingSec'; Expression = {
        $n = [int]$_.PendingSectors
        if ($n -gt 0) { "⚠️$n" } else { "$n" }
    }} `
    -AutoSize

Write-Host "`nОтчёты сохранены в папку: $reportFolder" -ForegroundColor Green
Write-Host "1. Краткий отчёт: $csvReport" -ForegroundColor Cyan
Write-Host "2. Полные данные: $fullReport" -ForegroundColor Cyan

sleep 120