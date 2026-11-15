# 备用代理 DLL（alternatives/）

代理 DLL 靠"游戏会加载一个和它同名的系统 DLL"来进入进程。默认的 `version.dll` 放在发布根目录，是首选。只有目标游戏不加载 `version.dll` 时，才从本目录按下表的顺序换一个游戏确实会加载的名字，放到渲染 EXE 旁边。

**任何时候只放一个代理。** 六个名字是同一份加载器：读同一个 `dlssg_sm86.ini`，从同一个 `dlssg_sm86\` 加载同一个后端、内核包与运行库，区别只在于文件名和转发的目标系统 DLL。每个代理都会把自己全部导出转发给 `C:\Windows\System32\` 里的同名真实 DLL，只拦截 `nvngx_dlssg.dll` 等 NVIDIA DLSS 文件的加载——所以换名字不改变行为。

## 试的顺序

| 顺序 | 名字 | 放置位置 | 说明 |
|---|---|---|---|
| 1 | `version.dll` | 发布根目录 | 首选。绝大多数游戏都会加载 `version.dll`。 |
| 2 | `alternatives/winmm.dll` | EXE 旁 | 多媒体计时 API，几乎所有游戏都导入。 |
| 3 | `alternatives/dbghelp.dll` | EXE 旁 | 崩溃/符号处理库。游戏或反作弊常加载。 |
| 4 | `alternatives/dinput8.dll` | EXE 旁 | DirectInput8。老一些的输入栈会加载。 |
| 5 | `alternatives/dxgi.dll` | EXE 旁 | 渲染路径代理，见下。 |
| 6 | `alternatives/d3d12.dll` | EXE 旁 | 同上；与 `dxgi.dll` 二选一，不要同时放。 |

前四个是工具类 DLL，不在 D3D12 渲染热路径上，转发开销可以忽略。

## 渲染路径代理（可用，但风险更高）

`dxgi.dll` 和 `d3d12.dll` 是 D3D12 渲染管线本身的入口，游戏每帧都密集调用它们，而且加载顺序敏感（游戏可能在我们的代理就位之前就已按系统路径解析了真实 DLL）。转发是完整的，功能正确，但只在前四个都无法被目标加载时才用，最后手段，两者只放一个。Vulkan 游戏根本不加载这两个，只能用前四个名字。

## 使用步骤

1. 先用根目录的 `version.dll`：把它、`dlssg_sm86.ini` 和 `dlssg_sm86\` 文件夹一起复制到渲染 EXE 所在目录（代理按自己所在目录找 `dlssg_sm86\`，只复制 DLL 什么都不会发生）。
2. 启动游戏，打开 DLSS 帧生成。要确认代理在工作，把 INI 的 `[Logging] Level` 临时改成 `2`：日志 `dlssg_sm86\logs\dlssg_sm86.log` 里这个游戏 EXE 名的行中出现 `runtime_redirect` 即代理已生效，`configuration` 记录的 `proxies.active` 写明是哪一个代理。
3. `Level=2` 下开了帧生成，日志里也没有这个 EXE 名的行，最常见的原因是这个代理没被游戏加载：退出游戏，**先删掉它**，再按上表顺序把下一个从本目录复制到 EXE 旁，再试。
4. 确认 EXE 旁只有一个本项目的代理 DLL。

同目录里万一有好几个本项目的代理（例如 0.3.1 起那几版的四代理安装留下的 `winmm.dll` / `dbghelp.dll` / `dinput8.dll`）：进程里第一个被加载的那个运行本 mod，其余只转发、不装钩子、不读 INI、不写日志（列在 `configuration.proxies.standby` 里）。谁是第一个取决于游戏的加载顺序，抢到的若是旧版本的代理，跑的就是那个旧版本，所以升级时把多余的删掉，只留一个。

签名与信任见 `docs/SIGNING.md`。一步一步的安装手册见根目录 `MANUAL.html`，版本说明见根目录 `README.md`，全部 INI 键见 `docs/INSTALL.md`。
