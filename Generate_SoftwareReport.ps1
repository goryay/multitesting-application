#Requires -Version 5.1
param([switch]$IncludeSoftware)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Convert-Size {
  param([ulong]$Bytes)
  if ($Bytes -ge 1PB) { '{0:N1}P' -f ($Bytes/1PB) }
  elseif ($Bytes -ge 1TB) { '{0:N1}T' -f ($Bytes/1TB) }
  elseif ($Bytes -ge 1GB) { '{0:N1}G' -f ($Bytes/1GB) }
  elseif ($Bytes -ge 1MB) { '{0:N1}M' -f ($Bytes/1MB) }
  elseif ($Bytes -ge 1KB) { '{0:N1}K' -f ($Bytes/1KB) }
  else { "$Bytes" }
}

function Try-Dmtf {
  param([string]$Dmtf, [string]$Format = 'yyyy-MM-dd')
  if ([string]::IsNullOrWhiteSpace($Dmtf)) { return '-' }
  try {
    $dt = [System.Management.ManagementDateTimeConverter]::ToDateTime($Dmtf)
    if ($dt -is [datetime] -and $dt.Year -gt 1601) { return $dt.ToString($Format) }
    return '-'
  } catch { return '-' }
}

function Get-UptimeSpan {
  try {
    $sec = (Get-CimInstance Win32_PerfFormattedData_PerfOS_System).SystemUpTime
    if ($sec -ge 0) { return New-TimeSpan -Seconds $sec }
  } catch {}
  try {
    $os = Get-CimInstance Win32_OperatingSystem
    if ($os.LastBootUpTime) {
      $boot = [System.Management.ManagementDateTimeConverter]::ToDateTime($os.LastBootUpTime)
      return New-TimeSpan -Start $boot -End (Get-Date)
    }
  } catch {}
  return New-TimeSpan -Seconds 0
}

function Get-Text_SystemInfo {
  $os   = try { Get-CimInstance Win32_OperatingSystem -ErrorAction Stop } catch { $null }
  $ci   = try { Get-ComputerInfo -ErrorAction Stop } catch { $null }
  $cpu  = try { (Get-CimInstance Win32_Processor)[0] } catch { $null }
  $bios = try { Get-CimInstance Win32_BIOS } catch { $null }
  $upt  = Get-UptimeSpan

  $dist = "Distributor ID:`tWindows"
  $desc = "Description:`t$($os.Caption) $($os.OSArchitecture)"
  $rel  = "Release:`t$($os.Version)"
  $code = "Codename:`t$($ci.WindowsEditionId)"

  $line1 = @"
$dist
$desc
$rel
$code
"@.Trim()

  $kern = "Windows $($ci.WindowsVersion) Build $($ci.OsBuildNumber) ($($ci.OsHardwareAbstractionLayer))  $([Environment]::OSVersion.Platform) $([Environment]::Is64BitOperatingSystem ? 'x86_64' : 'x86')"
  $cpuLine = if ($cpu) { "$($cpu.Name)  Cores:$($cpu.NumberOfCores)  Logical:$($cpu.NumberOfLogicalProcessors)" } else { "-" }
  $biosLine = if ($bios) { "BIOS $($bios.SMBIOSBIOSVersion) $([string](Try-Dmtf $bios.ReleaseDate))" } else { "-" }
  $uptLine = "Uptime: {0}d {1}h {2}m" -f $upt.Days,$upt.Hours,$upt.Minutes

  $line2 = "$kern`n$cpuLine`n$biosLine`n$uptLine"
  return "<pre>$line1</pre>`n<pre>$line2</pre>"
}

function Get-Text_Disks {
  # Блок 1: Сводка устройств (NAME LABEL SIZE SERIAL / GUID)
  $header = "NAME        LABEL      SIZE SERIAL/GUID"
  $rows = @()

  # Физические
  $phys = try { Get-CimInstance Win32_DiskDrive -ErrorAction Stop } catch { @() }
  foreach ($d in $phys) {
    $name = "Disk{0}" -f $d.Index
    $size = if ($d.Size) { Convert-Size ([uint64]$d.Size) } else { "-" }
    $ser  = ($d.SerialNumber -replace '\s+$','')
    if (-not $ser) { $ser = $d.PNPDeviceID }
    $rows += ("{0,-12}{1,-11}{2,-5} {3}" -f $name,'',"$size",$ser)
    # Разделы/тома этого диска
    try {
      $parts = Get-CimAssociatedInstance -InputObject $d -Association Win32_DiskDriveToDiskPartition
    } catch { $parts = @() }
    foreach ($p in $parts) {
      try {
        $vols = Get-CimAssociatedInstance -InputObject $p -Association Win32_LogicalDiskToPartition
      } catch { $vols = @() }
      foreach ($v in $vols) {
        $volInfo = try { Get-CimInstance Win32_Volume -Filter "DriveLetter='$($v.DeviceID)'" } catch { $null }
        $label = if ($volInfo) { $volInfo.Label } else { '' }
        $vsize = if ($volInfo -and $volInfo.Capacity) { Convert-Size ([uint64]$volInfo.Capacity) } else { '-' }
        $guid  = if ($volInfo -and $volInfo.DeviceID -match '\\\\\?\\Volume\{[0-9a-fA-F-]+\}\\') {
          ($volInfo.DeviceID -replace '^.*Volume\{','' -replace '\}\\$','')
        } else { '' }
        $rows += ("└─{0,-10}{1,-11}{2,-5} {3}" -f $v.DeviceID,$label,$vsize,$guid)
      }
    }
  }

  # Блок 2: псевдо-`blkid` — тип ФС, серийник, GUID
  $blk = @()
  $volumes = try { Get-CimInstance Win32_Volume } catch { @() }
  foreach ($v in $volumes) {
    if (-not $v.DriveLetter -and -not $v.DeviceID) { continue }
    $id = if ($v.DriveLetter) { $v.DriveLetter } else { $v.DeviceID }
    $fs = $v.FileSystem
    $lbl = $v.Label
    $ser = $v.SerialNumber
    $guid = if ($v.DeviceID -match '\\\\\?\\Volume\{[0-9a-fA-F-]+\}\\') {
      ($v.DeviceID -replace '^.*Volume\{','' -replace '\}\\$','')
    } else { '' }
    $blk += ("{0}: LABEL=""{1}"" FS=""{2}"" SERIAL=""{3}"" GUID=""{4}""" -f $id,$lbl,$fs,$ser,$guid)
  }

  # Блок 3: аналог `df -h`
  $dfHead = "Файл.система   Размер Использовано  Дост Использовано% Cмонтировано в"
  $dfRows = @()
  $ld = try { Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3 OR DriveType=2 OR DriveType=5" } catch { @() }
  foreach ($d in $ld) {
    $size = [uint64]($d.Size  -as [uint64])
    $free = [uint64]($d.FreeSpace -as [uint64])
    $used = if ($size -ge $free) { $size - $free } else { 0 }
    $pct  = if ($size) { [math]::Round(100 * ($used / $size)) } else { 0 }
    $fs   = if ($d.FileSystem) { $d.FileSystem } else { '-' }
    $mnt  = $d.DeviceID
    $dfRows += ("{0,-14}{1,6} {2,11} {3,6} {4,11}% {5}" -f $fs, (Convert-Size $size), (Convert-Size $used), (Convert-Size $free), $pct, $mnt)
  }

  $out1 = "<pre>$header`n$($rows -join "`n")</pre>"
  $out2 = "<pre>$($blk -join "`n")</pre>"
  $out3 = "<pre>$dfHead`n$($dfRows -join "`n")</pre>"
  return "$out1`n$out2`n$out3"
}

function Get-Text_DocFlash {
  # «Информация о флешке с документацией и дистрибутивами»
  # Ищем том с меткой IPDROM (как в вашем отчёте). Если нет — просто показываем все флешки (DriveType=2).
  $rem = try { Get-CimInstance Win32_LogicalDisk -Filter "DriveType=2" } catch { @() }
  $doc = $rem | Where-Object { $_.VolumeName -eq 'IPDROM' } | Select-Object -First 1
  if ($null -eq $doc) { $doc = $rem | Select-Object -First 1 }

  if ($null -eq $doc) {
    return "<pre>Флешка не обнаружена</pre>"
  }

  $root = $doc.DeviceID + '\'
  # Подсчёт файлов/директорий поверхностно (можно глубоко, но дольше)
  try {
    $dirs = (Get-ChildItem -Path $root -Directory -Force -ErrorAction Stop).Count
  } catch { $dirs = 0 }
  try {
    $files = (Get-ChildItem -Path $root -File -Force -ErrorAction Stop).Count
  } catch { $files = 0 }

  return "<pre>$root`n`n$dirs directories, $files files</pre>"
}

function Get-Text_Memory {
  try {
    $cs = Get-CimInstance Win32_ComputerSystem
    $os = Get-CimInstance Win32_OperatingSystem
  } catch {}
  $total = if ($cs.TotalPhysicalMemory) { [uint64]$cs.TotalPhysicalMemory } else { 0 }
  $free  = if ($os.FreePhysicalMemory) { [uint64]$os.FreePhysicalMemory * 1KB } else { 0 }
  $used  = if ($total -ge $free) { $total - $free } else { 0 }

  $swapT = if ($os.TotalVirtualMemorySize) { [uint64]$os.TotalVirtualMemorySize * 1KB } else { 0 }
  $swapF = if ($os.FreeVirtualMemory) { [uint64]$os.FreeVirtualMemory * 1KB } else { 0 }
  $swapU = if ($swapT -ge $swapF) { $swapT - $swapF } else { 0 }

  $lines = @(
    ('{0,-14}{1,12}{2,12}{3,12}{4,12}{5,12}' -f '', 'total','used','free','shared','buff/cache') -replace 'shared|buff/cache',''
    ('{0,-14}{1,12}{2,12}{3,12}{4,12}{5,12}' -f 'Память:', (Convert-Size $total), (Convert-Size $used), (Convert-Size $free),'','')
    ('{0,-14}{1,12}{2,12}{3,12}' -f 'Подкачка:', (Convert-Size $swapT), (Convert-Size $swapU), (Convert-Size $swapF))
  )
  return "<pre>$($lines -join "`n")</pre>"
}

function Get-Text_Network {
  $rows = @()
  $adapters = try { Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" } catch { @() }
  foreach ($a in $adapters) {
    $name = $a.Description
    $ipv4 = ($a.IPAddress | Where-Object { $_ -match '^\d{1,3}(\.\d{1,3}){3}$' }) -join ', '
    $mac  = $a.MACAddress
    $gw   = $a.DefaultIPGateway -join ', '
    $rows += @"
${name}: flags=<UP>  mtu $($a.IPConnectionMetric)
        inet $ipv4
        ether $mac
        gateway $gw
"@
  }
  if ($rows.Count -eq 0) { $rows = @('Сетевые адаптеры не обнаружены / нет IPv4') }
  return "<pre>$($rows -join "`n`n")</pre>"
}

function Get-UninstallEntries
{
    param(
        [switch]$IncludeSystemComponents = $false
    )

    $views = @(
        [Microsoft.Win32.RegistryView]::Registry64,
        [Microsoft.Win32.RegistryView]::Registry32
    )
    $hives = @(
        @{ Hive = [Microsoft.Win32.RegistryHive]::LocalMachine; Paths = @('Software\Microsoft\Windows\CurrentVersion\Uninstall') },
        @{ Hive = [Microsoft.Win32.RegistryHive]::CurrentUser; Paths = @('Software\Microsoft\Windows\CurrentVersion\Uninstall') }
    )

    $results = @()

    foreach ($view in $views)
    {
        foreach ($h in $hives)
        {
            try
            {
                $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey($h.Hive, $view)
                foreach ($relPath in $h.Paths)
                {
                    try
                    {
                        $key = $base.OpenSubKey($relPath)
                        if (-not $key)
                        {
                            continue
                        }
                        foreach ($subName in $key.GetSubKeyNames())
                        {
                            try
                            {
                                $sk = $key.OpenSubKey($subName)
                                if (-not $sk)
                                {
                                    continue
                                }

                                $name = $sk.GetValue('DisplayName')
                                if ( [string]::IsNullOrWhiteSpace($name))
                                {
                                    continue
                                }
                                $ver = $sk.GetValue('DisplayVersion')
                                $pub = $sk.GetValue('Publisher')
                                $rtype = $sk.GetValue('ReleaseType')
                                $scomp = $sk.GetValue('SystemComponent')
                                $instDt = $sk.GetValue('InstallDate')
                                $uninst = $sk.GetValue('UninstallString')

                                if (-not $IncludeSystemComponents)
                                {
                                    if ($scomp -eq 1)
                                    {
                                        continue
                                    }
                                    if ($rtype -match 'Update|Hotfix')
                                    {
                                        continue
                                    }
                                    if ($name -match '^(Security Update|Update for|KB\d+)')
                                    {
                                        continue
                                    }
                                }

                                $results += [pscustomobject]@{
                                    Name        = $name
                                    Version     = $ver
                                    Publisher   = $pub
                                    InstallDate = $instDt
                                    Uninstall   = $uninst
                                    Scope       = ($h.Hive -eq [Microsoft.Win32.RegistryHive]::CurrentUser) ? 'User' : 'Machine'
                                    View        = ($view -eq [Microsoft.Win32.RegistryView]::Registry64) ? 'x64' : 'x86'
                                }
                            }
                            catch
                            {
                            }
                        }
                    }
                    catch
                    {
                    }
                }
            }
            catch
            {
            }
        }
    }

    $results
}

function Get-Text_Packages {
  param([switch]$IncludeSoftware)

  # --- Сбор ПО из реестра (HKLM/HKCU, 32/64) ---
  $soft = @()
  if ($IncludeSoftware) {
    $soft = @( Get-UninstallEntries )  # уже отфильтрованы обновления/системные по умолчанию
    # Нормализовать дату
    $soft = $soft | ForEach-Object {
      $id = $_.InstallDate
      $fmt = if ($id -is [string] -and $id -match '^\d{8}$') {
        "{0}-{1}-{2}" -f $id.Substring(0,4), $id.Substring(4,2), $id.Substring(6,2)
      } else { "$id" }
      [pscustomobject]@{
        Name        = $_.Name
        Ver         = $_.Version
        Pub         = $_.Publisher
        InstallDate = $fmt
        Uninstall   = $_.Uninstall
        Scope       = $_.Scope
        View        = $_.View
      }
    }
  }

  # --- Appx/UWP (Store) для текущего пользователя ---
  $appx = @()
  if ($IncludeSoftware) {
    try {
      $appx = @( Get-AppxPackage | Select-Object Name, Publisher, Version )
    } catch {}
  }

  # --- Интеллект / Интеллект X ---
  $intel = @()
  if ($IncludeSoftware -and $soft.Count -gt 0) {
    $intel = @(
      $soft | Where-Object {
        $_.Name -match '(?i)\bIntellect\b' -or
        $_.Name -match '(?i)\bIntellect\s*X\b' -or
        $_.Name -match '(?i)Axxon.*Intellect'
      } | Sort-Object Name, Ver
    )
  }

  # --- Guardant ---
  $guardSrv = $null
  try { $guardSrv = Get-Service aksusbd -ErrorAction Stop } catch {}
  $guardDev = @()
  try { $guardDev = @( Get-PnpDevice -FriendlyName '*Guardant*','*Sentinel*HASP*','*SafeNet*HASP*' -ErrorAction SilentlyContinue ) } catch {}
  $guardDrv = @()
  try { $guardDrv = @( Get-WmiObject Win32_SystemDriver | Where-Object { $_.Name -match 'aksusbd|hasp' } ) } catch {}

  # --- Вывод текста ---
  $lines = @()

  $lines += '== Интеллект/Интеллект X =='
  if ($intel -and $intel.Count -gt 0) {
    foreach ($i in $intel) {
      $lines += ("{0}  {1}  {2}" -f ($i.Name ?? '-'), ($i.Ver ?? '-'), ($i.Pub ?? '-'))
    }
  } else {
    $lines += 'Не найдено'
  }

  $lines += "`n== Guardant =="
  $status = if ($guardSrv) { "$($guardSrv.Status)" } else { "не найдена" }
  $lines += "Служба aksusbd: $status"
  if ($guardDev -and $guardDev.Count -gt 0) {
    foreach ($d in $guardDev) {
      $fn = $d.FriendlyName; if ([string]::IsNullOrEmpty($fn)) { $fn = $d.InstanceId }
      $st = if ($d.Status) { $d.Status } else { '-' }
      $lines += ("Устройство: {0} [{1}]" -f $fn, $st)
    }
  } else {
    $lines += 'Устройства Guardant/Sentinel не найдены'
  }
  if ($guardDrv -and $guardDrv.Count -gt 0) {
    foreach ($d in $guardDrv) {
      $dn = if ($d.DisplayName) { $d.DisplayName } else { '-' }
      $nm = if ($d.Name)        { $d.Name }        else { '-' }
      $st = if ($d.State)       { $d.State }       else { '-' }
      $lines += ("Драйвер: {0} ({1}) {2}" -f $dn, $nm, $st)
    }
  }

  if ($IncludeSoftware) {
    $lines += "`n== Установленные пакеты (MSI/EXE из реестра) =="
    if ($soft.Count -gt 0) {
      foreach ($s in ($soft | Sort-Object Name, Ver, Pub, Scope, View)) {
        $nm = $s.Name ?? '-'; $vr = $s.Ver ?? '-'; $pb = $s.Pub ?? '-'
        $sc = $s.Scope ?? '-'; $vw = $s.View ?? '-'
        $lines += ("{0}  {1}  {2}  [{3}/{4}]" -f $nm, $vr, $pb, $sc, $vw)
      }
    } else {
      $lines += 'Нет данных'
    }

    $lines += "`n== UWP/Store (Appx) текущего пользователя =="
    if ($appx.Count -gt 0) {
      foreach ($a in ($appx | Sort-Object Name, Version)) {
        $lines += ("{0}  {1}  {2}" -f $a.Name, $a.Version, ($a.Publisher ?? '-'))
      }
    } else {
      $lines += 'Нет данных'
    }
  }

  return "<pre>$($lines -join "`n")</pre>"
}

# ---------- Сбор и рендер ----------
$now = Get-Date
$computer = $env:COMPUTERNAME
$title = "Отчёт о системе $computer от $($now.ToString('yyyy-MM-dd_HH-mm'))"

$section1 = Get-Text_SystemInfo
$section2 = Get-Text_Disks
$section3 = Get-Text_DocFlash
$section4 = Get-Text_Memory
$section5 = Get-Text_Network
$section6 = Get-Text_Packages -IncludeSoftware:$IncludeSoftware

# ---------- Вывод HTML (минималистично, как в Linux-файле) ----------
$desk = [Environment]::GetFolderPath('Desktop')
$dir = Join-Path $desk ("Report{0}" -f $computer)
New-Item -Force -ItemType Directory -Path $dir | Out-Null
$fname = "Software_Report_{0}.html" -f (Get-Date -Format "yyyy-MM-dd_HH-mm")
$path = Join-Path $dir $fname

$html = @"
<html>
  <head><title>Отчёт о системе</title></head>
  <body>
  <h1>$title</h1>

  <h2>Информация о системе :</h2>
  $section1

  <h2>Информация о дисках:</h2>
  $section2

  <h2>Информация о флешке с документацией и дистрибутивами:</h2>
  $section3

  <h2>Информация о памяти:</h2>
  $section4

  <h2>Сетевая информация:</h2>
  $section5

  <h2>Установленные пакеты:</h2>
  $section6
  </body>
</html>
"@

Set-Content -LiteralPath $path -Value $html -Encoding UTF8
Write-Host "✅ Готово: $path"
