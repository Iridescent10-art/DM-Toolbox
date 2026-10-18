# PowerShell 7 / Windows PowerShell
# 全套硬件自定义配置一键深度应用脚本 (全面突破 CPU、GPU/显存、主板、内存、硬盘及小黑盒检测)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 1. 检查并自动提升管理员权限
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[*] 正在请求系统管理员权限..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"") -Verb RunAs
    exit
}

$ScriptDir = Split-Path -Parent $PSCommandPath
$ConfigFile = Join-Path $ScriptDir "config.json"

if (-not (Test-Path $ConfigFile)) {
    Write-Host "错误：未找到配置文件 config.json！" -ForegroundColor Red
    Write-Host "按任意键退出..." -ForegroundColor Gray
    [void][System.Console]::ReadKey($true)
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  电脑全套硬件配置应用工具 (CPU/显卡/主板/内存/硬盘/小黑盒)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 2. 读取配置
$config = Get-Content $ConfigFile -Raw -Encoding UTF8 | ConvertFrom-Json
$target = $config.custom_target

$cpuTarget = $target.cpu_model
$gpuTarget = $target.gpu_model
$gpuInstancePath = $target.target_gpu_instance_path
$vramGb = if ($target.gpu_vram_gb) { [int64]$target.gpu_vram_gb } else { 24 }
$vramBytes = [int64]$vramGb * 1024 * 1024 * 1024
$vramDword = if ($vramBytes -gt 4294967295) { [uint32]4294967295 } else { [uint32]$vramBytes }

$boardVendor = if ($target.motherboard_vendor) { $target.motherboard_vendor } else { "ASUSTeK COMPUTER INC." }
$boardProduct = if ($target.motherboard_product) { $target.motherboard_product } else { "ROG CROSSHAIR X870E HERO" }

$memoryVendor = if ($target.memory_vendor) { $target.memory_vendor } else { "Corsair" }
$memoryGb = if ($target.memory_size_gb) { [int]$target.memory_size_gb } else { 64 }
$memoryClock = if ($target.memory_clock_mhz) { [int]$target.memory_clock_mhz } else { 7200 }

$diskModel = if ($target.disk_model) { $target.disk_model } else { "Samsung SSD 990 PRO 2TB" }
$diskInstancePath = $target.target_disk_instance_path

Write-Host "[1/8] 目标硬件应用参数：" -ForegroundColor Green
Write-Host "  -> 目标 CPU: $cpuTarget" -ForegroundColor White
Write-Host "  -> 目标 GPU: $gpuTarget" -ForegroundColor White
Write-Host "  -> 目标显存: $vramGb GB ($vramBytes Bytes)" -ForegroundColor White
Write-Host "  -> 目标主板: $boardVendor $boardProduct" -ForegroundColor White
Write-Host "  -> 目标内存: $memoryVendor DDR5 $memoryGb GB ${memoryClock}MHz" -ForegroundColor White
Write-Host "  -> 目标硬盘: $diskModel" -ForegroundColor White

# 自动推导设备实例路径
if ([string]::IsNullOrWhiteSpace($gpuInstancePath)) {
    $gpu = Get-CimInstance Win32_VideoController | Where-Object { $_.PNPDeviceID -match "^PCI\\" } | Select-Object -First 1
    if ($gpu) {
        $gpuInstancePath = $gpu.PNPDeviceID
    }
}
if ([string]::IsNullOrWhiteSpace($diskInstancePath)) {
    $disk = Get-CimInstance Win32_DiskDrive | Where-Object { $_.PNPDeviceID -match "^SCSI\\" } | Select-Object -First 1
    if ($disk) {
        $diskInstancePath = $disk.PNPDeviceID
    }
}

# 3. 自动备份原始真实硬件
Write-Host "[2/8] 检查出厂硬件备份..." -ForegroundColor Green
$cpuBackupFile = "C:\CPU_Backup.cfg"
$gpuBackupFile = "C:\GPU_Backup.cfg"
$gpuPathBackupFile = "C:\GPU_Path_Backup.cfg"
$boardVendorBackup = "C:\Board_Vendor_Backup.cfg"
$boardProductBackup = "C:\Board_Product_Backup.cfg"
$diskBackupFile = "C:\Disk_Backup.cfg"
$diskPathBackupFile = "C:\Disk_Path_Backup.cfg"

if (-not (Test-Path $cpuBackupFile)) {
    $realCpu = (Get-ItemProperty "HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor\0" -ErrorAction SilentlyContinue).ProcessorNameString
    if ($realCpu) { [System.IO.File]::WriteAllText($cpuBackupFile, $realCpu.Trim(), [System.Text.Encoding]::ASCII) }
}
if (-not (Test-Path $gpuBackupFile) -and -not [string]::IsNullOrWhiteSpace($gpuInstancePath)) {
    $realGpu = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Enum\$gpuInstancePath" -ErrorAction SilentlyContinue).DeviceDesc
    if ($realGpu) {
        [System.IO.File]::WriteAllText($gpuBackupFile, $realGpu.Trim(), [System.Text.Encoding]::UTF8)
        [System.IO.File]::WriteAllText($gpuPathBackupFile, $gpuInstancePath.Trim(), [System.Text.Encoding]::ASCII)
    }
}
if (-not (Test-Path $boardVendorBackup)) {
    $realBV = (Get-ItemProperty "HKLM:\HARDWARE\DESCRIPTION\System\BIOS" -ErrorAction SilentlyContinue).BaseBoardManufacturer
    if ($realBV) { [System.IO.File]::WriteAllText($boardVendorBackup, $realBV.Trim(), [System.Text.Encoding]::UTF8) }
}
if (-not (Test-Path $boardProductBackup)) {
    $realBP = (Get-ItemProperty "HKLM:\HARDWARE\DESCRIPTION\System\BIOS" -ErrorAction SilentlyContinue).BaseBoardProduct
    if ($realBP) { [System.IO.File]::WriteAllText($boardProductBackup, $realBP.Trim(), [System.Text.Encoding]::UTF8) }
}
if (-not (Test-Path $diskBackupFile) -and -not [string]::IsNullOrWhiteSpace($diskInstancePath)) {
    $realDisk = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Enum\$diskInstancePath" -ErrorAction SilentlyContinue).FriendlyName
    if ($realDisk) {
        [System.IO.File]::WriteAllText($diskBackupFile, $realDisk.Trim(), [System.Text.Encoding]::UTF8)
        [System.IO.File]::WriteAllText($diskPathBackupFile, $diskInstancePath.Trim(), [System.Text.Encoding]::ASCII)
    }
}

# 4. 修改 CPU 注册表信息（针对所有逻辑核心）
Write-Host "[3/8] 正在修改 CPU 注册表..." -ForegroundColor Green
$cpuUpdatedCount = 0
$cpuBase = "HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor"
if (Test-Path $cpuBase) {
    Get-ChildItem $cpuBase | ForEach-Object {
        if ($_.PSChildName -match "^\d+$") {
            Set-ItemProperty -Path $_.PSPath -Name "ProcessorNameString" -Value $cpuTarget -Type String -Force
            $cpuUpdatedCount++
        }
    }
}

# 更新 ACPI / Enum 处理器名称（设备管理器展示项）
$acpiBase = "HKLM:\SYSTEM\CurrentControlSet\Enum\ACPI"
if (Test-Path $acpiBase) {
    Get-ChildItem $acpiBase -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "Processor|CPU" } | ForEach-Object {
        try {
            Set-ItemProperty -Path "Registry::$($_.Name)" -Name "FriendlyName" -Value $cpuTarget -Type String -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path "Registry::$($_.Name)" -Name "DeviceDesc" -Value $cpuTarget -Type String -Force -ErrorAction SilentlyContinue
            $cpuUpdatedCount++
        } catch {}
    }
}
Write-Host "  -> 已更新 $cpuUpdatedCount 处 CPU 核心注册表节点！" -ForegroundColor Cyan
[System.IO.File]::WriteAllText("C:\CPU_Config.txt", $cpuTarget.Trim(), [System.Text.Encoding]::ASCII)

# 5. 【核心突破】DirectX / DXGI / 任务管理器专用显存
Write-Host "[4/8] 正在修改 DirectX / DXGI / 任务管理器显存注册表..." -ForegroundColor Green
$dxBase = "HKLM:\SOFTWARE\Microsoft\DirectX"
if (Test-Path $dxBase) {
    Set-ItemProperty -Path $dxBase -Name "MaxDedicatedVideoMemory" -Value $vramBytes -Type QWord -Force -ErrorAction SilentlyContinue
    Get-ChildItem $dxBase | Where-Object { $_.PSChildName -match "^\{.*\}$" } | ForEach-Object {
        $curDesc = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).Description
        if ($curDesc -and $curDesc -notmatch "Basic|Virtual") {
            Set-ItemProperty -Path $_.PSPath -Name "Description" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $_.PSPath -Name "DedicatedVideoMemory" -Value $vramBytes -Type QWord -Force -ErrorAction SilentlyContinue
            Write-Host "  -> 已更新 DirectX 适配器描述与显存 ($($_.PSChildName)): $gpuTarget / $vramGb GB" -ForegroundColor Cyan
        }
    }
}

# 6. 【核心突破】Control\Video、Class、Enum 穿透
Write-Host "[5/8] 正在穿透底层 Control\Video、Class、Enum 显卡描述..." -ForegroundColor Green
$videoBase = "HKLM:\SYSTEM\CurrentControlSet\Control\Video"
if (Test-Path $videoBase) {
    Get-ChildItem $videoBase | Where-Object { $_.PSChildName -match "^\{.*\}$" } | ForEach-Object {
        $guidPath = $_.PSPath
        $vidSub = Join-Path $guidPath "Video"
        if (Test-Path $vidSub) {
            $curD = (Get-ItemProperty $vidSub -ErrorAction SilentlyContinue).DeviceDesc
            if ($curD -and $curD -notmatch "Virtual|Remote") {
                Set-ItemProperty -Path $vidSub -Name "DeviceDesc" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
            }
        }

        for ($i = 0; $i -lt 8; $i++) {
            $outSub = Join-Path $guidPath ("000{0}" -f $i)
            if (Test-Path $outSub) {
                $chip = (Get-ItemProperty $outSub -ErrorAction SilentlyContinue)."HardwareInformation.ChipType"
                if ($chip -notmatch "Virtual|Remote") {
                    Set-ItemProperty -Path $outSub -Name "HardwareInformation.ChipType" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
                    Set-ItemProperty -Path $outSub -Name "HardwareInformation.AdapterString" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
                    Set-ItemProperty -Path $outSub -Name "HardwareInformation.qwMemorySize" -Value $vramBytes -Type QWord -Force -ErrorAction SilentlyContinue
                    Set-ItemProperty -Path $outSub -Name "HardwareInformation.MemorySize" -Value $vramDword -Type DWord -Force -ErrorAction SilentlyContinue
                    Set-ItemProperty -Path $outSub -Name "DriverDesc" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }
}

$classBase = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
if (Test-Path $classBase) {
    Get-ChildItem $classBase | Where-Object { $_.PSChildName -match "^\d{4}$" } | ForEach-Object {
        $driverDesc = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DriverDesc
        if ($driverDesc -and $driverDesc -notmatch "Virtual|Remote") {
            Set-ItemProperty -Path $_.PSPath -Name "DriverDesc" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $_.PSPath -Name "HardwareInformation.ChipType" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $_.PSPath -Name "HardwareInformation.AdapterString" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $_.PSPath -Name "HardwareInformation.qwMemorySize" -Value $vramBytes -Type QWord -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $_.PSPath -Name "HardwareInformation.MemorySize" -Value $vramDword -Type DWord -Force -ErrorAction SilentlyContinue
        }
    }
}

if (-not [string]::IsNullOrWhiteSpace($gpuInstancePath)) {
    $enumGpuReg = "HKLM:\SYSTEM\CurrentControlSet\Enum\$gpuInstancePath"
    if (Test-Path $enumGpuReg) {
        Set-ItemProperty -Path $enumGpuReg -Name "DeviceDesc" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
        Set-ItemProperty -Path $enumGpuReg -Name "FriendlyName" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
    }
}

$nvVideo = "HKLM:\SYSTEM\CurrentControlSet\Services\nvlddmkm\Video"
if (Test-Path $nvVideo) {
    Set-ItemProperty -Path $nvVideo -Name "DeviceDesc" -Value $gpuTarget -Type String -Force -ErrorAction SilentlyContinue
}

# 7. 修改主板 BIOS 与硬盘驱动器 FriendlyName
Write-Host "[6/8] 正在修改主板 BIOS 与硬盘设备名称..." -ForegroundColor Green
$biosBase = "HKLM:\HARDWARE\DESCRIPTION\System\BIOS"
if (Test-Path $biosBase) {
    $cleanProduct = $boardProduct
    if ($boardVendor -and $cleanProduct.StartsWith($boardVendor)) {
        $cleanProduct = $cleanProduct.Substring($boardVendor.Length).Trim()
    }
    Set-ItemProperty -Path $biosBase -Name "BaseBoardManufacturer" -Value $boardVendor -Type String -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $biosBase -Name "BaseBoardProduct" -Value $cleanProduct -Type String -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $biosBase -Name "SystemManufacturer" -Value $boardVendor -Type String -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $biosBase -Name "SystemProductName" -Value $cleanProduct -Type String -Force -ErrorAction SilentlyContinue
    Write-Host "  -> 主板已修改为: $boardVendor $cleanProduct" -ForegroundColor Cyan
}

if ($diskModel) {
    if ($diskInstancePath -and (Test-Path "HKLM:\SYSTEM\CurrentControlSet\Enum\$diskInstancePath")) {
        Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Enum\$diskInstancePath" -Name "FriendlyName" -Value $diskModel -Type String -Force -ErrorAction SilentlyContinue
    }
    Get-ChildItem "HKLM:\SYSTEM\CurrentControlSet\Enum\SCSI" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Property -contains "FriendlyName" } | ForEach-Object {
        $curFN = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).FriendlyName
        if ($curFN -and $curFN -notmatch "Virtual|Remote") {
            Set-ItemProperty -Path $_.PSPath -Name "FriendlyName" -Value $diskModel -Type String -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "  -> 硬盘驱动器已修改为: $diskModel" -ForegroundColor Cyan
}

# 8. 小黑盒加速器 (HeyboxAccelerator) 全硬件拦截器注入与前端实时渲染补丁
Write-Host "[7/8] 正在检查并更新小黑盒全套硬件拦截器及前端渲染补丁..." -ForegroundColor Green
$publicCfg = "C:\Users\Public\Hardware_Config.json"
Copy-Item $ConfigFile $publicCfg -Force -ErrorAction SilentlyContinue

$heyboxDir = $target.custom_heybox_dir
if (-not $heyboxDir -or -not (Test-Path $heyboxDir)) {
    $heyboxDir = $Config.custom_heybox_dir
}
if (-not $heyboxDir -or -not (Test-Path $heyboxDir)) {
    # 尝试从注册表自动读取
    $regInst = (Get-ItemProperty "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like "*小黑盒*" -or $_.DisplayName -like "*Heybox*" } | Select-Object -First 1)
    if ($regInst.InstallLocation -and (Test-Path $regInst.InstallLocation)) {
        $heyboxDir = $regInst.InstallLocation
    } elseif ($regInst.DisplayIcon -and (Test-Path $regInst.DisplayIcon)) {
        $heyboxDir = Split-Path $regInst.DisplayIcon
    }
}
if (-not $heyboxDir -or -not (Test-Path $heyboxDir)) {
    $candidates = @(
        "C:\Program Files (x86)\Qingfeng\HeyboxAccelerator",
        "D:\Program Files (x86)\Qingfeng\HeyboxAccelerator",
        "D:\Qingfeng\HeyboxAccelerator",
        "D:\HeyboxAccelerator",
        "E:\Qingfeng\HeyboxAccelerator",
        "E:\HeyboxAccelerator"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $heyboxDir = $c; break }
    }
}

if ($heyboxDir -and (Test-Path $heyboxDir)) {
    Write-Host "  -> 锁定小黑盒安装目录: $heyboxDir" -ForegroundColor Cyan
    $indexFiles = Get-ChildItem -Path $heyboxDir -Filter "index.js" -Recurse | Where-Object { $_.DirectoryName -like "*resources\app" }
    foreach ($idx in $indexFiles) {
        $bak = "$($idx.FullName).bak"
        if (-not (Test-Path $bak)) {
            Copy-Item $idx.FullName $bak -Force
        }
        $hookTemplate = Join-Path $ScriptDir "xiaoheihe_index.js"
        if (Test-Path $hookTemplate) {
            Copy-Item $hookTemplate $idx.FullName -Force
            Write-Host "  -> 已向小黑盒注入最新全硬件拦截器 ($($idx.FullName))" -ForegroundColor Cyan
        }
    }
    $patchScript = Join-Path $ScriptDir "patch_webapp.py"
    if (Test-Path $patchScript) {
        python $patchScript "$heyboxDir" 2>$null | Out-Null
        Write-Host "  -> 已应用小黑盒前端 UI 实时同步渲染补丁！" -ForegroundColor Cyan
    }
}

# 9. 开机自启防还原机制（计划任务）
Write-Host "[8/8] 配置开机防还原机制..." -ForegroundColor Green
$taskName = "CPU_Model_Fix_On_Startup"
if ($target.enable_startup_fix) {
    $batPath = Join-Path $env:TEMP "cpu_fix_startup.bat"
    $vbsPath = Join-Path $env:TEMP "cpu_fix_launcher.vbs"

    $batLines = New-Object System.Collections.Generic.List[string]
    $batLines.Add("@echo off")
    for ($i = 0; $i -lt 64; $i++) {
        $batLines.Add('reg add "HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\' + $i + '" /v "ProcessorNameString" /t REG_SZ /d "' + $cpuTarget + '" /f >nul 2>&1')
    }
    $batLines.Add('reg add "HKLM\SOFTWARE\Microsoft\DirectX" /v "MaxDedicatedVideoMemory" /t REG_QWORD /d "' + $vramBytes + '" /f >nul 2>&1')
    $batLines.Add('reg add "HKLM\HARDWARE\DESCRIPTION\System\BIOS" /v "BaseBoardManufacturer" /t REG_SZ /d "' + $boardVendor + '" /f >nul 2>&1')
    $batLines.Add('reg add "HKLM\HARDWARE\DESCRIPTION\System\BIOS" /v "BaseBoardProduct" /t REG_SZ /d "' + $boardProduct + '" /f >nul 2>&1')
    $batLines.Add('reg add "HKLM\HARDWARE\DESCRIPTION\System\BIOS" /v "SystemManufacturer" /t REG_SZ /d "' + $boardVendor + '" /f >nul 2>&1')
    $batLines.Add('reg add "HKLM\HARDWARE\DESCRIPTION\System\BIOS" /v "SystemProductName" /t REG_SZ /d "' + $boardProduct + '" /f >nul 2>&1')
    if ($diskInstancePath) {
        $batLines.Add('reg add "HKLM\SYSTEM\CurrentControlSet\Enum\' + $diskInstancePath + '" /v "FriendlyName" /t REG_SZ /d "' + $diskModel + '" /f >nul 2>&1')
    }
    [System.IO.File]::WriteAllLines($batPath, $batLines, [System.Text.Encoding]::GetEncoding("GBK"))

    $vbsLines = New-Object System.Collections.Generic.List[string]
    $vbsLines.Add('Set WshShell = CreateObject("WScript.Shell")')
    $vbsLines.Add('WshShell.Run Chr(34) & "' + $batPath + '" & Chr(34), 0, False')
    $vbsLines.Add('Set WshShell = Nothing')
    [System.IO.File]::WriteAllLines($vbsPath, $vbsLines, [System.Text.Encoding]::ASCII)

    schtasks /create /tn $taskName /tr "wscript.exe `"$vbsPath`"" /sc onlogon /rl highest /delay 0000:05 /f | Out-Null
    Write-Host "  -> 已启用开机静默修复计划任务 [$taskName]！" -ForegroundColor Cyan
} else {
    schtasks /delete /tn $taskName /f 2>$null | Out-Null
    Write-Host "  -> 未启用开机自启防还原。" -ForegroundColor Gray
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "          全部硬件自定义配置已深度生效！" -ForegroundColor Green
Write-Host "  CPU、显卡/显存、主板、内存及硬盘已同步注入！" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "[温馨生效提醒]：" -ForegroundColor Yellow
Write-Host "  1. 任务管理器：请彻底关闭并重新打开任务管理器查看全新硬件；" -ForegroundColor White
Write-Host "  2. 小黑盒加速器：请在右下角系统托盘彻底退出小黑盒后重新打开即可！" -ForegroundColor White
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
[void][System.Console]::ReadKey($true)
