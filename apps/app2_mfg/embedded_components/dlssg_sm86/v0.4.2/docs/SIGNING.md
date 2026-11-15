# 代码签名（可选）

`build.ps1` 可以在打包前对这个发布里**我们自己的每一个 DLL** 做 Authenticode SHA-256 签名：

| | 文件 |
|---|---|
| 代理 | `version.dll` |
| 五个备用代理 | `alternatives\winmm.dll`、`alternatives\dbghelp.dll`、`alternatives\dinput8.dll`、`alternatives\dxgi.dll`、`alternatives\d3d12.dll` |
| 后端 | `dlssg_sm86\backend\sm86_backend.dll` |
| 帧生成内核包（`docs/PACK_FORMAT.md`；只有资源，签名在证书表里、不改任何资源字节） | `dlssg_sm86\kernels\fg_kernels.dll` |
| 超分内核包（`docs/PACK_FORMAT.md` 第三部分；同上，2026-10-11 起；按文件名签，同目录的 NVIDIA snippet 不碰） | `dlssg_sm86\sr\sr_kernels.dll` |
| XeSS-FG 模型包（`docs/PACK_FORMAT.md` 第四部分；只有资源，同上） | `dlssg_sm86\xefg\xefg_kernels.dll` |

`dlssg_sm86\runtime\`、`sr\` 下的两份 NVIDIA 运行库/snippet **不碰**（2026-10-09 前还有 `rr\` 下的光线重建 snippet）：它们是 NVIDIA 签的，重签会毁掉那个签名。

**后端能被签名，是它不再内嵌进代理、改成随包文件的主要理由之一**。在此之前后端是构建时算好 SHA-256 内嵌进代理、运行时释放到 `%LOCALAPPDATA%` 再加载的，而签名会改字节、SHA 常量在签名之前算出——两者不可能同时成立，所以那份 DLL 按构造签不了名，而"刚落盘的未签名 DLL"正是杀软与 Windows Smart App Control 拒绝的形状（`docs/COMPAT.md` C10b、公开 issue #530）。现在它是用户复制进去的文件，和代理一样。

签名发生在编译之后、CTest/安装/打包之前，作用于构建目录里的产物（`out\build-310.9.16\bundle\<配置>\`，**那棵树就是发布树**：`version.dll` 在根、备用代理在 `alternatives\`、后端在 `dlssg_sm86\backend\`、资源包在 `dlssg_sm86\kernels\`、`dlssg_sm86\sr\` 与 `dlssg_sm86\xefg\`），因此安装到 `dist\` 的那份、打进 ZIP 的那份、以及可选 GPU 验证记录哈希的那份是同一个已签名文件，哈希前后一致。签名是**可选**的：不提供证书时构建照常完成，只是 DLL 未签名。仓库里从不包含任何证书或私钥。

## 参数

| 参数 | 环境变量 | 默认 | 说明 |
|---|---|---|---|
| `-SignCert <pfx>` | `DLSSG_SIGN_CERT` | 空 | 代码签名证书（`.pfx`/PKCS#12）路径。为空则跳过签名。 |
| `-SignPass <pw>` | `DLSSG_SIGN_PASS` | 空 | 证书私钥密码（如果有）。 |
| `-SignTimestampUrl <url>` | — | `http://timestamp.digicert.com` | RFC3161 时间戳服务器。传空字符串 `''` 则不加时间戳（离线时用；未加时间戳的签名在证书过期后失效）。 |
| `-SignTool <path>` | — | 自动发现 | 显式指定 `signtool.exe`；默认在 Windows SDK（`C:\Program Files (x86)\Windows Kits\10\bin\<版本>\x64\`）和 App Certification Kit 里找最新的一个。 |

signtool 命令等价于：

```
signtool sign /fd sha256 /td sha256 /tr <SignTimestampUrl> /f <SignCert> [/p <SignPass>] <上表的每个 DLL>
```

未提供证书时，构建打印一行明确提示（DLL 未签名，以及如何签名），不报错、不自动生成证书。

## (a) 用正式证书签名

从受信任 CA 购买的代码签名证书导出为 `.pfx`（含私钥），然后：

```powershell
powershell -File build.ps1 -SignCert C:\path\to\codesign.pfx -SignPass '证书密码'
# 或用环境变量，避免密码出现在命令行历史里：
$env:DLSSG_SIGN_CERT = 'C:\path\to\codesign.pfx'; $env:DLSSG_SIGN_PASS = '证书密码'
powershell -File build.ps1
```

> **正式签名需要你自己的证书。** 本项目不附带任何证书；EV/OV 代码签名证书由 CA 签发给具体的个人或组织。

## (b) 造一个一次性自签名证书（仅供测试）

用来验证签名流水线本身（参数、时间戳、文件是否被正确签名），**不提供任何默认信任**：

```powershell
# 1. 生成自签名代码签名证书（进当前用户证书store）
$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=DLSSG Throwaway Test" `
        -CertStoreLocation Cert:\CurrentUser\My -KeyUsage DigitalSignature `
        -KeyExportPolicy Exportable -NotAfter (Get-Date).AddDays(30)

# 2. 导出成 pfx（选一个临时目录，别放进仓库）
$pw = ConvertTo-SecureString '临时密码' -AsPlainText -Force
Export-PfxCertificate -Cert $cert -FilePath $env:TEMP\dlssg_throwaway.pfx -Password $pw | Out-Null

# 3. 用它构建 + 签名
powershell -File build.ps1 -SignCert $env:TEMP\dlssg_throwaway.pfx -SignPass '临时密码'

# 4. 验证签名格式（自签名会报根不受信任，这是预期的——证明签名本身良构、参数/时间戳正确即可）
$signtool = "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe"
& $signtool verify /pa /v dist\Release-310.9.16\version.dll

# 5. 用完删证书和 pfx，别提交
Remove-Item $env:TEMP\dlssg_throwaway.pfx
Remove-Item ("Cert:\CurrentUser\My\" + $cert.Thumbprint)
```

**自签名证书只保证完整性与身份一致性（同一把私钥签的），没有 Windows 默认信任。** 用它签的 DLL 在别的机器上，SmartScreen 仍会提示"未知发布者"，`signtool verify /pa` 会报根证书不受信任。要获得默认信任必须用受信任 CA 签发的证书（见上面的 (a)）。
