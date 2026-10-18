# PowerShell 7 / Windows PowerShell
# 全套硬件一键还原官方真实配置脚本 (全面恢复 CPU、GPU/显存、主板、硬盘及小黑盒)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# 1. 检查并自动提升管理员权限
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[*] 正在请求系统管理员权限..." -ForegroundColor Yellow
    Start-Process powershell.exe -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"") -Verb RunAs
    exit
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "        全套硬件一键还原真实官方配置" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 2. 读取原始备份
$cpuBackupFile = "C:\CPU_Backup.cfg"
$gpuBackupFile = "C:\GPU_Backup.cfg"
$gpuPathBackupFile = "C:\GPU_Path_Backup.cfg"
$boardVendorBackup = "C:\Board_Vendor_Backup.cfg"
$boardProductBackup = "C:\Board_Product_Backup.cfg"
$diskBackupFile = "C:\Disk_Backup.cfg"
$diskPathBackupFile = "C:\Disk_Path_Backup.cfg"

$realCpu = "AMD Ryzen 5 9600X 6-Core Processor"
if (Test-Path $cpuBackupFile) { $realCpu = (Get-Content $cpuBackupFile -Raw).Trim() }

$realGpuDesc = "@oem22.inf,%nvidia_dev.2786%;NVIDIA GeForce RTX 4070"
if (Test-Path $gpuBackupFile) { $realGpuDesc = (Get-Content $gpuBackupFile -Raw).Trim() }
$realGpuName = "NVIDIA GeForce RTX 4070"
if ($realGpuDesc -match ";(.*)$") { $realGpuName = $matches[1] }

$gpuPath = "PCI\VEN_10DE&DEV_2786&SUBSYS_12017377&REV_A1\4&D0BDF66&0&0009"
if (Test-Path $gpuPathBackupFile) { $gpuPath = (Get-Content $gpuPathBackupFile -Raw).Trim() }

$realBoardVendor = "MAXSUN"
if (Test-Path $boardVendorBackup) { $realBoardVendor = (Get-Content $boardVendorBackup -Raw).Trim() }

$realBoardProduct = "MS-eSport B650ITX"
if (Test-Path $boardProductBackup) { $realBoardProduct = (Get-Content $boardProductBackup -Raw).Trim() }

$realDiskModel = "YSSDM-2TN3000"
if (Test-Path $diskBackupFile) { $realDiskModel = (Get-Content $diskBackupFile -Raw).Trim() }

$diskPath = "SCSI\DISK&VEN_NVME&PROD_YSSDM-2TN3000\5&1574F6F4&0&000000"
if (Test-Path $diskPathBackupFile) { $diskPath = (Get-Content $diskPathBackupFile -Raw).Trim() }

$realVramBytes = [int64]12593397760
$realVramDword = [uint32]4293918720

Write-Host "[1/7] 官方真实硬件信息：" -ForegroundColor Green
Write-Host "  -> 原始 CPU: $realCpu" -ForegroundColor White
Write-Host "  -> 原始 GPU: $realGpuName (12 GB 显存)" -ForegroundColor White
Write-Host "  -> 原始主板: $realBoardVendor $realBoardProduct" -ForegroundColor White
Write-Host "  -> 原始硬盘: $realDiskModel" -ForegroundColor White

# 3. 还原 CPU
Write-Host "[2/7] 正在还原 CPU 注册表..." -ForegroundColor Green
$cpuBase = "HKLM:\HARDWARE\DESCRIPTION\System\CentralProcessor"
if (Test-Path $cpuBase) {
    Get-ChildItem $cpuBase | ForEach-Object {
        if ($_.PSChildName -match "^\d+$") {
            Set-ItemProperty -Path $_.PSPath -Name "ProcessorNameString" -Value $realCpu -Type String -Force
        }
    }
}

# 4. 还原 DirectX / DXGI / 任务管理器显存
Write-Host "[3/7] 正在还原 DirectX / DXGI / 任务管理器显存..." -ForegroundColor Green
$dxBase = "HKLM:\SOFTWARE\Microsoft\DirectX"
if (Test-Path $dxBase) {
    Set-ItemProperty -Path $dxBase -Name "MaxDedicatedVideoMemory" -Value $realVramBytes -Type QWord -Force -ErrorAction SilentlyContinue
    Get-ChildItem $dxBase | Where-Object { $_.PSChildName -match "^\{.*\}$" } | ForEach-Object {
        $curDesc = (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).Description
        if ($curDesc -and $curDesc -notmatch "Basic|Virtual") {
            Set-ItemProperty -Path $_.PSPath -Name "Description" -Value $realGpuName -Type String -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $_.PSPath -Name "DedicatedVideoMemory" -Value $realVramBytes -Type QWord -Force -ErrorAction SilentlyContinue
        }
    }
}

# 5. 还原 Control\Video、Class 与 Enum
Write-Host "[4/7] 正在还原 Control\Video、Class 与 Enum..." -ForegroundColor Green
$videoBase = "HKLM:\SYSTEM\CurrentControlSet\Control\Video"
if (Test-Path $videoBase) {
    Get-ChildItem $videoBase | Where-Object { $_.PSChildName -match "^\{.*\}$" } | ForEach-Object {
        $guidPath = $_.PSPath
        $vidSub = Join-Path $guidPath "Video"
        if (Test-Path $vidSub) {
            $curD = (Get-ItemProperty $vidSub -ErrorAction SilentlyContinue).DeviceDesc
            if ($curD -and $curD -notmatch "Virtual|Remote") {
                Set-ItemProperty -Path $vidSub -Name "DeviceDesc" -Value $realGpuDesc -Type String -Force -ErrorAction SilentlyContinue
            }
        }

        for ($i = 0; $i -lt 8; $i++) {
            $outSub = Join-Path $guidPath ("000{0}" -f $i)
            if (Test-Path $outSub) {
                $chip = (Get-ItemProperty $outSub -ErrorAction SilentlyContinue)."HardwareInformation.ChipType"
                if ($chip -notmatch "Virtual|Remote") {
                    Set-ItemProperty -Path $outSub -Name "HardwareInformation.ChipType" -Value $realGpuName -Type String -Force -ErrorAction SilentlyContinue
                    Set-ItemProperty -Path $outSub -Name "HardwareInformation.AdapterString" -Value $realGpuName -Type String -Force -ErrorAction SilentlyContinue
                    Set-ItemProperty -Path $outSub -Name "HardwareInformation.qwMemorySize" -Value $realVramBytes -Type QWord -Force -ErrorAction SilentlyContinue
                    Set-ItemProperty -Path $outSub -Name "HardwareInformation.MemorySize" -Value $realVramDword -Type DWord -Force -ErrorAction SilentlyContinue
                    Set-ItemProperty -Path $outSub -Name "DriverDesc" -Value $realGpuName -Type String -Force -ErrorAction SilentlyContinue
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
            Set-ItemProperty -Path $_.PSPath -Name "DriverDesc" -Value $realGpuName -Type String -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $_.PSPath -Name "HardwareInformation.ChipType" -Value $realGpuName -Type String -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $_.PSPath -Name "HardwareInformation.AdapterString" -Value $realGpuName -Type String -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $_.PSPath -Name "HardwareInformation.qwMemorySize" -Value $realVramBytes -Type QWord -Force -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $_.PSPath -Name "HardwareInformation.MemorySize" -Value $realVramDword -Type DWord -Force -ErrorAction SilentlyContinue
        }
    }
}

if (-not [string]::IsNullOrWhiteSpace($gpuPath)) {
    $enumGpuReg = "HKLM:\SYSTEM\CurrentControlSet\Enum\$gpuPath"
    if (Test-Path $enumGpuReg) {
        Set-ItemProperty -Path $enumGpuReg -Name "DeviceDesc" -Value $realGpuDesc -Type String -Force -ErrorAction SilentlyContinue
        Set-ItemProperty -Path $enumGpuReg -Name "FriendlyName" -Value $realGpuName -Type String -Force -ErrorAction SilentlyContinue
    }
}

$nvVideo = "HKLM:\SYSTEM\CurrentControlSet\Services\nvlddmkm\Video"
if (Test-Path $nvVideo) {
    Set-ItemProperty -Path $nvVideo -Name "DeviceDesc" -Value $realGpuDesc -Type String -Force -ErrorAction SilentlyContinue
}

# 6. 还原主板 BIOS 与硬盘驱动器 FriendlyName
Write-Host "[5/7] 正在恢复主板 BIOS 与硬盘驱动器真实名称..." -ForegroundColor Green
$biosBase = "HKLM:\HARDWARE\DESCRIPTION\System\BIOS"
if (Test-Path $biosBase) {
    Set-ItemProperty -Path $biosBase -Name "BaseBoardManufacturer" -Value $realBoardVendor -Type String -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $biosBase -Name "BaseBoardProduct" -Value $realBoardProduct -Type String -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $biosBase -Name "SystemManufacturer" -Value $realBoardVendor -Type String -Force -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $biosBase -Name "SystemProductName" -Value $realBoardProduct -Type String -Force -ErrorAction SilentlyContinue
}

if ($diskPath -and (Test-Path "HKLM:\SYSTEM\CurrentControlSet\Enum\$diskPath")) {
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Enum\$diskPath" -Name "FriendlyName" -Value $realDiskModel -Type String -Force -ErrorAction SilentlyContinue
}

# 7. 还原小黑盒加速器拦截器
Write-Host "[6/7] 正在恢复小黑盒官方检测模块..." -ForegroundColor Green
$heyboxDir = $Config.custom_heybox_dir
if (-not $heyboxDir -or -not (Test-Path $heyboxDir)) {
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
    $bakFiles = Get-ChildItem -Path $heyboxDir -Filter "index.js.bak" -Recurse | Where-Object { $_.DirectoryName -like "*resources\app" }
    foreach ($bak in $bakFiles) {
        $origJs = Join-Path $bak.DirectoryName "index.js"
        Copy-Item $bak.FullName $origJs -Force
        Remove-Item $bak.FullName -Force
        Write-Host "  -> 已还原小黑盒原始入口: $origJs" -ForegroundColor Cyan
    }
    $webappBaks = Get-ChildItem -Path $heyboxDir -Filter "*.bak" -Recurse | Where-Object { $_.Name -like "chunk-*.js.bak" }
    foreach ($wbak in $webappBaks) {
        $origW = $wbak.FullName.Substring(0, $wbak.FullName.Length - 4)
        Copy-Item $wbak.FullName $origW -Force
        Remove-Item $wbak.FullName -Force
        Write-Host "  -> 已还原前端页面: $origW" -ForegroundColor Cyan
    }
}

# 8. 清理开机自启防还原机制
Write-Host "[7/7] 清理开机自启与临时配置..." -ForegroundColor Green
schtasks /delete /tn "CPU_Model_Fix_On_Startup" /f 2>$null | Out-Null
if (Test-Path "C:\CPU_Config.txt") { Remove-Item "C:\CPU_Config.txt" -Force -ErrorAction SilentlyContinue }
if (Test-Path "$env:TEMP\cpu_fix_startup.bat") { Remove-Item "$env:TEMP\cpu_fix_startup.bat" -Force -ErrorAction SilentlyContinue }
if (Test-Path "$env:TEMP\cpu_fix_launcher.vbs") { Remove-Item "$env:TEMP\cpu_fix_launcher.vbs" -Force -ErrorAction SilentlyContinue }
Write-Host "  -> 开机自启计划任务已清理。" -ForegroundColor Cyan

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "          已全部恢复出厂官方硬件显示！" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
[void][System.Console]::ReadKey($true)
