# DLSSG for SM86 (proxy build) - 0.4.0

[中文](README.md) · **English**

Enables NVIDIA DLSS Frame Generation (DLSS-G) on RTX 30-series (SM86) and RTX 20-series (SM75), and accelerates DLSS Super Resolution with INT8 on RTX 30 / 20. Windows x64 / D3D12; the runtime files are `version.dll`, `dlssg_sm86.ini` and the `dlssg_sm86\` directory.

> **Upgrading from 0.3.x? Read this first: 0.4.0 is a major upgrade. The file layout and the install steps changed; do not copy it over the old version.**
>
> 1. Remove the old version completely: quit the game, then delete every proxy DLL of this project from the game directory (0.3.1–0.3.6 had you copy four, `version.dll`, `winmm.dll`, `dbghelp.dll` and `dinput8.dll`; delete all four), `dlssg_sm86.ini`, and the whole `dlssg_sm86\` directory.
> 2. Copy the three items of the new version: `version.dll`, `dlssg_sm86.ini` and the whole `dlssg_sm86\` directory. The runtime, backend, kernel pack, XeSS model pack and super-resolution files all live in `dlssg_sm86\`; copying only the DLL does nothing.
> 3. Only one proxy at any time: the root has only `version.dll`; if the game does not load it, swap in one from `alternatives\` (swap, do not add).
> 4. Use the new `dlssg_sm86.ini`: keys moved (`Optimized` and `Preset` are now in `[DLSSG]`, `[XeSSFG]` is new) and `[Runtime] Mode=Auto` was removed. An old INI is still read, but every old key logs a warning; redo your changes in the new INI.
>
> Step-by-step: "Install & upgrade" below and the manual `MANUAL.en.html`.

## Changes in this release

### 0.4.0

- Super-resolution INT8 (RTX 30 / 20 only): with `[SuperResolution] Mode=On`, the super-resolution modes the game runs with preset L or M (Performance and Ultra Performance in most games) use this project's INT8 kernels; no preset is changed. On an RTX 3070 one super-resolution evaluate takes L −6..−16 %, M −9..−22 % GPU time against the same preset in FP16. Factory `Mode=Off`.
- DLSS-G preset C (FG Lite, optional): `[DLSSG] Preset=C`. Each generated frame skips the second network and its post-processing; on RTX 3070 real captures the GPU time per generated frame is −29..−34 % at 2X and about −45 % at 4X, with slightly lower image quality (mostly on the HUD and at occlusion edges). Factory is still `Preset=Auto`.
- XeSS-FG engine (optional): `[FrameGeneration] Engine=XeSS` generates frames with Intel's XeSS-FG model, 2X only; `[XeSSFG] FlowResolution` (`Coarse` / `Middle` / `Fine`) and `UseHudless`. Intel's `libxess_fg.dll` is neither shipped nor loaded: the model runs on this project's own D3D12 runner. On RTX 30 it is slower than DLSS-G, see "Known issues". Factory is still `Engine=DLSS`.
- The bundled runtime is now `nvngx_dlssg.dll` 310.9.16 (bit-identical output to 310.9.1 under the default preset). The version the game ships does not matter.
- New INI layout: the DLSS-G-only `Optimized` and `Preset` moved to `[DLSSG]`, the XeSS-only keys are in `[XeSSFG]`; the old locations still work and log one `configuration_warning`. `[Runtime] Mode=Auto` was removed: written, it runs as `Bundled` with one warning.
- The release root carries a single proxy, `version.dll`; the other five are in `alternatives\`, one at a time (0.3.1–0.3.6 had you copy four; delete the extra ones when upgrading, see "Install & upgrade").
- RTX 40 / 50: frame generation also runs this project's kernels (PTX, compiled by the driver); `[Compatibility] AccelerateNewerGpus=0` switches back to NVIDIA's own kernels. Not yet run on real hardware.
- `[Logging] FrameTiming=1`: one line per real frame in the log directory (frame interval, super-resolution and frame-generation GPU time), for performance reports.
- New installation manual `MANUAL.en.html` (Chinese `MANUAL.html`).

### 0.3.6

- New option `[FrameGeneration] CatmullRomWarp=1` (default 0): the two motion-compensated samples taken for a generated frame switch from bilinear to Catmull-Rom, so fine structure (railings, text, distant window panes) is somewhat clearer in generated frames, at a cost of about +3% per generated frame (1080p / 1440p) to +4% (4K); with it on the image is no longer bit-identical to the official runtime. Measured offline on 11 real captures from 6 games, fine-structure energy rises by about 5 percentage points and the flicker metric improves along with it; the visible improvement is slight. It is not part of any `Optimized` tier, and the 310.1 build does not support it. There are also experimental `DetailRestore` keys (modes C and D); the measured gain is small or comes with side effects, so enabling them is not recommended - see `docs/INSTALL.md`.
- The log now records the version, hash and generation of the DLSS-G runtime the game itself ships (`runtime_redirect` / `game_runtime_generation`). Games on an early Streamline (1.x–2.4, shipping DLSS-G 3.x) can only do 2X: that generation of the plugin never writes a generated-frame count to the runtime, which no setting of this project can change; the log now says so directly. Streamline 1.x versions used to be recorded as 1.0.0.0 throughout; fixed.
- With NVIDIA App's DLSS override enabled, the frame-generation component is supplied by the NGX model store, and this project takes it over as usual; the new `ngx_override_active` record marks that case. The over-the-air Streamline plugin in the model store is now recognised as well (`ForcePluginFrames` used to be silently ineffective in such processes).
- The release package now carries all four proxies (`version` / `winmm` / `dbghelp` / `dinput8`) and the INI at its root, as `alternatives/README.md` describes; `310.1\` carries an INI too.
- Removed an NVAPI stub that was never called (`SetRawScgPriority`, present in none of the runtimes, in the NGX core or in Streamline).
- `docs/INSTALL.md` additions: what `Preset` means and when it takes effect, why `Optimized=2/3` "looks no different", how to attribute image artefacts, and the order in which to rule out full-screen flicker.

### 0.3.5

- Fixes a defect present since 0.3.0: when the game re-creates the frame-generation feature (menu changes, a resolution or settings change, toggling frame generation — some games re-create it often while running), the driver recycles kernel handles, and a recycled handle could still be bound to the previous kernel's optimized variant, so the wrong kernel could be launched afterwards — seen as corrupted generated frames, or a random crash / display-driver reset after playing for a while (`Optimized=0` is not affected). In an offline test with 15 re-creations on a 3070, the old build produced wrong frames in three runs out of four; the new build is bit-identical every time.
- Logging: `fg_gate_exit` is new (written when the process exits normally); a log without it means the game was killed or crashed.

### 0.3.4

- Fixes the 0.3.3 crash on RTX 30 (the display driver resets when the game starts or when DLSS is switched on; Forza Horizon 6 reports it as FHC01). Cause: when the NVIDIA App's DLSS override or an NGX online update is in effect, the DLSS super-resolution model is loaded from the NGX model directory, and it also received the GPU-architecture rewrite this project makes for Streamline, so on RTX 30 it took kernel paths that do not belong to this card and hung the GPU. NVIDIA's own components (the NGX model directory, the driver modules) now always get the real architecture; the rewrite applies to Streamline and the game only.
- Logging: `arch_spoof_applied` is now one record per calling module, with the full path, and `arch_spoof_excluded` is new; three small fixes (a missing system export no longer makes the proxy fail to load #10 / #65, `backend_install -100` now says which reason it was, and hardware-accelerated GPU scheduling being off is reported on its own #513).

### 0.3.3 (preview)

- `[FrameGeneration] Optimized=1` no longer turns on `SkipRepeatedRealCopy`, and no tier does; write `SkipRepeatedRealCopy=1` yourself if you want it. It is bit-identical in synthetic scenes and offline replays, but its exactness rests on an assumption outside our kernels (how the game's own plugin submits the Evaluates of one group), it had never been validated in a live game, and a flicker report on 0.3.2 followed (Zenless Zone Zero, public issue #532). Tier `1` remains bit-identical to the official runtime.
- RTX 20-series (Turing): the NVAPI GPU-architecture rewrite shown to the game is now armed at game start (our own `DllMain`, or when `nvapi64.dll` loads). Streamline 2.x decides "this GPU does not support DLSS-G" inside `slInit`, before the DLSS-G runtime is loaded and before earlier versions had armed the rewrite, which is why a 2080 Ti in Final Fantasy VII Rebirth (Streamline 2.8) lost the frame-generation plugin. RTX 30 needs it too: an RTX 3060 Laptop shows exactly the same symptom in the same game (public issue #509; the 0.2.4 native build reported Ada to every GPU, which is why that version worked), so a Turing or an Ampere answer is now rewritten to Blackwell (RTX 50: both builds do multi-frame generation, and games and Streamline unlock the 3X / 4X / 6X options on that architecture) while Ada / Blackwell are left alone.
- Diagnostics: the log field `arch_spoof_installed.trigger` gained the values `dllmain` / `nvapi_load` / `dependency_load`.

### 0.3.2

- Part of the inference kernels rewritten (310.9 build): the generated image now matches the official DLSS-G exactly (bit-identical in tests on an RTX 3080 Ti and an RTX 5070; an RTX 2080 Ti's output is bit-identical to the 3080 Ti's), no longer lossy, with a small speed-up (0–8% on the 3080 Ti).
- Optimization levels reworked: `[FrameGeneration] Optimized` is now `0`–`3`. `0` stock kernels, no acceleration; `1` every acceleration, image bit-identical to the official one (factory default); `2` adds lossy image kernels, faster, about 50 dB PSNR or better against the official image (310.9 build only); `3` everything lossy, fastest. See [`docs/INSTALL.en.md`](docs/INSTALL.en.md).

### 0.3.1

- Simpler install: the package root now ships four proxies (`version.dll`, `winmm.dll`, `dbghelp.dll`, `dinput8.dll`) — **copy all of them next to the game EXE, there is nothing to pick**. Whichever one the game loads first runs the mod; the others go on standby and only forward their exports to the matching system DLL, so frame generation is never installed twice. Only if none of the four is loaded, take `dxgi.dll` or `d3d12.dll` (one of them) from `alternatives\`.
- The factory `MaxGeneratedFrames` changes from `5` to `3` (4X). A game with dynamic MFG runs at whatever ceiling is written here by default, and `5` turned out to be too high for most people (public issues #497 / #499). For 6X use the 310.9 build and set this line to `5` yourself; a game whose own Streamline plugin is 4X stays at 4X either way.
- A bad value in the INI no longer switches the whole mod off: that key falls back to its own default and logs one `configuration_warning` (visible at `Level=1`), every other key keeps working. The same for a switch the backend cannot do (for example `Preset=B` on the 310.1 build): those flags are **stripped and the install goes ahead**, logging `kernel_selection_unsupported{stripped_flags}` instead of refusing outright.
- RTX 20-series (Turing) works again, with the factory `dlssg_sm86.ini` and no edits: the kernel family is selected from the physical GPU and resolves to the SM75 family. Confirmed on an RTX 2080 Ti in The Witcher 3 next-gen DX12 at 2X (that game's own Streamline plugin caps at 2X); 4X / 6X are decided by the game's own plugin, as on RTX 30. Driver R580+ recommended, roughly R555 minimum (PTX is used automatically, costing one extra JIT on first load).
- 0.3.0 could not enable frame generation on any RTX 20: the GPU architecture it reported to the NGX core was not the card's real architecture, so the core refused the frame-generation feature (public issues #491 / #492). Nothing about RTX 30 numerics or performance changes with this fix.
- The two RTX 20-related keys, `SM75Family` and `SpoofArchToGame`, are not in the factory INI; their defaults are the right values. See [`docs/INSTALL.en.md`](docs/INSTALL.en.md) if you need them.
- Diagnostics for "frame generation will not turn on": at `[Logging] Level=2` the log now records which gate refused it — hardware-accelerated GPU scheduling (HAGS), driver version, the NGX core's answer to the capability query, and the `CreateFeature` result. These records are named `fg_gate_*`.
- Image quality and performance on RTX 20 are not yet measured: this release only shows that frame generation runs there (thousands of Evaluates with no failure and no fallback). There are no FPS numbers and no image comparison against RTX 30.

### 0.3.0

- Reverted from the native build to the proxy build. The native approach (a self-built NGX host) had game-compatibility problems that were hard to fix; this build uses a proxy DLL around the unmodified factory runtime, leaving the game's calls to NGX unchanged, which is more compatible.
- The 310.9 runtime adds 6X (`MaxGeneratedFrames` ceiling raised from 3 to 5). On games that themselves support Dynamic MFG, selecting "Dynamic / Auto" frame generation reaches 6X.
- Optimized kernel set (~19–32% in the offline benchmark), a two-switch factory INI, capture/replay, and diagnostic logging — see below and `docs/`.

## Statement & roadmap

- Kernel-level work on frame generation (DLSS-G) has essentially reached its best at this stage and kernel optimization is paused; later releases focus on compatibility and bug fixes.
- INT8 for the super-resolution presets L / M ships in this release (RTX 30 / 20).
- The XeSS-FG engine is functional only in this release (2X, no performance work); performance and HDR (RGBA16F) back buffers are listed under "Known issues".
- Vulkan support is hard to continue in the project's current state: the wrapper layer's own game compatibility is not good enough yet, test coverage is thin, and Vulkan only adds more compatibility problems. Users who need it can use the community patch versions.

## Requirements

- OS and games: Windows 10/11 x64, D3D12.
- GPU: RTX 30-series (SM86) or RTX 20-series (Turing / SM75). Development validation and all in-game tests on an RTX 3070; the full 0.4.0 test kit also ran on an RTX 3080 Ti; RTX 20 was tested on a 2080 Ti for frame generation (0.3.x) and one super-resolution INT8 smoke run. RTX 40 / 50 work too: frame generation takes this project's PTX route, not yet run on real hardware.
- Driver: an NVIDIA driver with the NGX / NVAPI / CUDA interfaces; tested on 591.86, 610.74, 610.88 and 617.14. The cubins need roughly R580+; older drivers fall back to PTX automatically (one extra JIT on the first frame only).
- No CUDA Toolkit and no Python.

| Release zip | Packaged runtime | Ceiling | `version.dll` size | SHA-256 |
|---|---|---|---|---|
| `dlssg-release-0.4.0-x64.zip` | 310.9.16.0 | 6X | 853,280 | `7b3f90435be4f94348bf8d128c84871c7f904c704f7690601a263277c327a7b2` |

The proxy DLL is about 0.85 MB; the runtime, the backend and the packs are files under `dlssg_sm86\`: the backend `backend\sm86_backend.dll` 2.1 MB (no kernels in it), the frame-generation kernel pack `kernels\fg_kernels.dll` 18.3 MB (required), the runtime `runtime\nvngx_dlssg.dll` 7.5 MB, the XeSS model pack `xefg\xefg_kernels.dll` 5.4 MB, and super resolution's `sr\nvngx_dlss.dll` 74.2 MB and `sr\sr_kernels.dll` 106.6 MB (a pair, used only with `[SuperResolution] Mode=On`).

## Extra VRAM by configuration

Frame generation's own local VRAM delta (after warm-up minus before feature creation, rounded up to 10 MiB, 310.9 build, optimized, measured with 0.3.x). It tracks the output resolution only and is independent of the multiplier: 2X and 6X use the same amount; the multiplier costs no extra VRAM.

| Aspect | Output resolution | Extra VRAM |
|---|---|---|
| 16:9 | 720p | ~230 MiB |
| 16:9 | 1080p | ~350 MiB |
| 16:9 | 1440p | ~540 MiB |
| 16:9 | 4K / 3840×2160 | ~810 MiB |
| 21:9 | 2560×1080 | ~440 MiB |
| 21:9 | 3440×1440 | ~700 MiB |
| 21:9 | 5120×2160 | ~1050 MiB |
| 32:9 | 3840×1080 | ~610 MiB |
| 32:9 | 5120×1440 | ~990 MiB |
| 4:3 | 1920×1440 | ~430 MiB |

The same height at different widths is similar (it tracks output pixel count). This is frame generation's own increment, excluding the game itself and the synthetic inputs. With `Engine=XeSS` the dedicated VRAM in use is about 410–530 MiB higher than with DLSS-G (RTX 3070, 4K output, five games).

## Install & upgrade

New to mods? Follow the installation manual at the package root step by step: `MANUAL.en.html` (Chinese: `MANUAL.html`; double-click it to open it in a browser). The short version:

1. Exit the game completely.
2. Go to the directory of the EXE the game actually renders with (e.g. Black Myth: Wukong is `...\b1\Binaries\Win64\`). If you are not sure which one it is: while the game runs, open Task Manager's Details page, right-click the game's process → "Open file location".
3. Copy `version.dll`, `dlssg_sm86.ini` and the `dlssg_sm86\` folder from the package root into it; back up any same-named DLL that is already there. The runtime, the backend, the kernel packs, the XeSS model pack and the super-resolution snippet live in `dlssg_sm86\` and the proxy itself is under a megabyte, so **copying the DLL without the folder does nothing at all**. `alternatives\` is not copied normally.
4. Launch the game, enable DLSS Frame Generation in the graphics settings, and select 2X / 3X / 4X (for 6X see "6X" below: it needs `MaxGeneratedFrames` set to `5` by hand). On RTX 20 / 30, a frame-generation option that used to be grayed out and can now be turned on means it is installed.
5. To confirm that the proxy is loaded (the only way on RTX 40 / 50, where frame generation was available anyway): set `[Logging] Level` to `2`, play a little with frame generation on and exit; a `loader_<PID>.jsonl` in `dlssg_sm86\logs\` means it was loaded. The factory `Level=1` writes a log only on errors, so an empty `logs`, or none at all, is normal.
6. If the game does not load `version.dll` (no `loader_*.jsonl` at `Level=2` with frame generation on): exit the game, delete it and put the proxies from `alternatives\` next to the EXE one at a time, in the order `winmm.dll` → `dbghelp.dll` → `dinput8.dll` → `dxgi.dll` → `d3d12.dll`, trying each. Only ever one at a time; `dxgi.dll` and `d3d12.dll` sit on the render path, so they come last and never together. See `alternatives\README.md`.
7. Upgrade: exit the game, delete the old proxy DLL, `dlssg_sm86.ini` and the `dlssg_sm86\` folder first, then copy the three new items; make the settings you had changed again in the new INI. Releases 0.3.1–0.3.6 had you copy four proxies (`version.dll`, `winmm.dll`, `dbghelp.dll`, `dinput8.dll`); delete all four when upgrading: when several of this project's proxies sit in one folder, the first one the process loads runs the mod, and if that is an old one, the old version runs. Coming from 0.3.x you can also delete `%LOCALAPPDATA%\DlssgSm86` — nothing is written there any more.
8. Uninstall: delete `version.dll` (or the alternative you switched to), `dlssg_sm86.ini` and the `dlssg_sm86\` folder, and put back any DLL you backed up.

Switches in the factory `dlssg_sm86.ini` a player may change:

- `[DLSSG] Optimized`: consistency tier `0`–`3`. Factory `2` = every acceleration plus the lossy image kernels: no longer bit-identical to the official image, with no visible difference from `1` side by side against ground truth; `1` = every acceleration that stays bit-identical; `0` = stock numerics; `3` = every lossy acceleration. In `[FrameGeneration]` before 2026-10-14; the old place still works.
- `[DLSSG] Preset`: factory `Auto`; `C` = FG Lite (faster, slightly lower quality), also runs this project's accelerated kernels (per the `Optimized` tier) whatever DLSS-G version the game ships.
- `[FrameGeneration] MaxGeneratedFrames`: factory `3` = 4X; `5` = 6X; the actual count is requested by the game and clamped to the runtime's ceiling.
- `[FrameGeneration] Engine`: factory `DLSS`; `XeSS` = Intel's XeSS-FG model, 2X only. `[XeSSFG] FlowResolution` (factory `Middle`; finer is slower) and `UseHudless` (factory `1`) apply to XeSS only.
- `[SuperResolution] Mode`: factory `Off`; set it to `On` on RTX 30 / 20 and the super-resolution modes the game runs with preset L or M use this project's INT8 kernels, with no preset changed; within one run of the game only the first of those modes you use is accelerated; no effect on RTX 40 / 50.

The other entries in the factory file (`Enabled`, logging, the runtime source `[Runtime] Mode=Bundled`) are normally left alone; further diagnostic/compatibility keys are not in the file and take safe defaults — the full list is in [`docs/INSTALL.en.md`](docs/INSTALL.en.md). A key written wrongly only costs that key — it falls back to its default and logs one `configuration_warning` instead of switching the mod off.

## Antivirus & signing

Every DLL of this project in the package is code-signed: `version.dll` at the root, the five alternative proxies in `alternatives\`, and under `dlssg_sm86\` the backend and three resource packs (frame-generation kernels `fg_kernels.dll`, super-resolution kernels `sr_kernels.dll`, XeSS model `xefg_kernels.dll`), 10 in total (NVIDIA's runtime and super-resolution snippet in `dlssg_sm86\runtime\` and `dlssg_sm86\sr\` keep NVIDIA's own signature and are not touched). A self-signed certificate only verifies the signer's identity and file integrity; it gives no default Windows trust, so Windows SmartScreen may still prompt "unknown publisher" on first run — that is a reputation prompt, not an antivirus detection. The certificate is self-signed as `CN=DLSSG for SM86 (self-signed)`, SHA-1 thumbprint `85BA66762F851E49148D706915D09026281418E6`; verify the signer and thumbprint via the file's Properties → Digital Signatures tab or `signtool verify /pa`.

## Performance

Every number below comes from this project's own timing (a D3D12 timestamp before and after each Evaluate, or the `[Logging] FrameTiming` log). Offline GPU milliseconds measure the cost of frame generation / super resolution itself; they are not an in-game frame-rate gain.

### Frame generation: real game captures (RTX 3070, offline replay)

RTX 3070, driver 617.14, the 0.4.0 test kit's full run (run_all). Inputs recorded in the games (Cyberpunk 2077, Black Myth: Wukong) replayed through the whole route (proxy → backend → NVIDIA runtime 310.9.16 or the XeSS engine); the first 4 real frames of each run dropped, median over all frames of 4 rounds. GPU milliseconds per generated frame; in brackets the change against DLSS default (negative = faster). DLSS default = the factory INI (`Optimized=2`, `Preset=Auto`); stock kernels = `Optimized=0`.

**2X**

| Capture | DLSS default | Preset C | XeSS Middle | XeSS Coarse | XeSS Fine | Stock kernels |
|---|---:|---:|---:|---:|---:|---:|
| Cyberpunk 2077 1440p | 2.554 | 1.694 (−33.7 %) | 2.974 (+16.4 %) | 2.344 (−8.2 %) | 3.828 (+49.9 %) | 3.639 (+42.4 %) |
| Black Myth: Wukong 1440p | 2.581 | 1.745 (−32.4 %) | 3.266 (+26.5 %) | 2.634 (+2.0 %) | 4.164 (+61.3 %) | 3.657 (+41.7 %) |
| Cyberpunk 2077 4K | 3.557 | 2.499 (−29.7 %) | 6.379 (+79.3 %) | 5.059 (+42.2 %) | 8.296 (+133.2 %) | 4.407 (+23.9 %) |
| Black Myth: Wukong 4K | 3.756 | 2.679 (−28.7 %) | 6.974 (+85.7 %) | 5.682 (+51.3 %) | 9.025 (+140.3 %) | 4.560 (+21.4 %) |

**4X** (per generated frame = the sum of a real frame's 3 Evaluates ÷ 3): Cyberpunk 2077 4K default 2.532 ms, preset C 1.392 ms (−45.0 %); Black Myth: Wukong 4K default 2.733 ms, preset C 1.517 ms (−44.5 %).

### Frame generation: real game captures (RTX 3080 Ti, offline replay)

RTX 3080 Ti, driver 610.88, a full run of the same test kit (a tester's machine); method as above. During these two timing stages the GPU held 1665 MHz (below the 1950 MHz of the synthetic timing), so the absolute values are conservative; the comparisons hold.

**2X**

| Capture | DLSS default | Preset C | XeSS Middle | XeSS Coarse | XeSS Fine | Stock kernels |
|---|---:|---:|---:|---:|---:|---:|
| Cyberpunk 2077 1440p | 1.651 | 1.032 (−37.5 %) | 2.235 (+35.4 %) | 1.786 (+8.2 %) | 2.791 (+69.1 %) | 2.381 (+44.2 %) |
| Black Myth: Wukong 1440p | 1.663 | 1.062 (−36.1 %) | 2.359 (+41.9 %) | 1.911 (+14.9 %) | 2.936 (+76.6 %) | 2.391 (+43.8 %) |
| Cyberpunk 2077 4K | 2.171 | 1.473 (−32.2 %) | 4.640 (+113.7 %) | 3.668 (+68.9 %) | 5.908 (+172.1 %) | 2.860 (+31.7 %) |
| Black Myth: Wukong 4K | 2.275 | 1.577 (−30.7 %) | 4.763 (+109.3 %) | 3.822 (+68.0 %) | 6.060 (+166.3 %) | 2.935 (+29.0 %) |

**4X**: Cyberpunk 2077 4K default 1.567 ms, preset C 0.822 ms (−47.5 %); Black Myth: Wukong 4K default 1.666 ms, preset C 0.897 ms (−46.2 %).

### Super-resolution INT8 against the same preset in FP16 (RTX 3070, offline)

Same test kit. GPU time of one super-resolution Evaluate in ms: median of 64 measured frames per run, median of 3 rounds. Same runtime (310.7.129), same preset; only INT8 against FP16. The two kernel families correspond to The Witcher 3 / Resonance / Forza Horizon 6 / Spider-Man (mvlo) and Black Myth: Wukong / Hogwarts Legacy (mvhi).

| Family | Output | Mode | L FP16 | L INT8 | L change | M FP16 | M INT8 | M change |
|---|---|---|---:|---:|---:|---:|---:|---:|
| mvlo | 3840×2160 | Performance | 7.443 | 6.459 | −13.2 % | 6.065 | 4.905 | −19.1 % |
| mvlo | 2560×1440 | Performance | 3.415 | 2.993 | −12.4 % | 2.787 | 2.294 | −17.7 % |
| mvlo | 1920×1080 | Performance | 1.965 | 1.736 | −11.7 % | 1.615 | 1.353 | −16.2 % |
| mvlo | 1920×1080 | Ultra Performance | 1.258 | 1.179 | −6.3 % | 1.066 | 0.967 | −9.3 % |
| mvhi | 3840×2160 | Performance | 7.305 | 6.127 | −16.1 % | 5.914 | 4.623 | −21.8 % |
| mvhi | 2560×1440 | Performance | 3.346 | 2.845 | −15.0 % | 2.719 | 2.171 | −20.2 % |
| mvhi | 1920×1080 | Performance | 1.934 | 1.656 | −14.4 % | 1.581 | 1.278 | −19.2 % |
| mvhi | 1920×1080 | Ultra Performance | 1.235 | 1.106 | −10.4 % | 1.057 | 0.914 | −13.5 % |

### Super-resolution INT8 against the same preset in FP16 (RTX 3080 Ti, offline)

Same test kit and method, GPU at 1665 MHz.

| Family | Output | Mode | L FP16 | L INT8 | L change | M FP16 | M INT8 | M change |
|---|---|---|---:|---:|---:|---:|---:|---:|
| mvlo | 3840×2160 | Performance | 5.338 | 4.578 | −14.2 % | 4.341 | 3.455 | −20.4 % |
| mvlo | 2560×1440 | Performance | 2.484 | 2.151 | −13.4 % | 2.028 | 1.644 | −18.9 % |
| mvlo | 1920×1080 | Performance | 1.465 | 1.333 | −9.0 % | 1.208 | 1.047 | −13.4 % |
| mvlo | 1920×1080 | Ultra Performance | 1.000 | 0.948 | −5.2 % | 0.849 | 0.791 | −6.9 % |
| mvhi | 3840×2160 | Performance | 5.262 | 4.355 | −17.2 % | 4.252 | 3.239 | −23.8 % |
| mvhi | 2560×1440 | Performance | 2.437 | 2.045 | −16.1 % | 1.991 | 1.545 | −22.4 % |
| mvhi | 1920×1080 | Performance | 1.441 | 1.272 | −11.8 % | 1.186 | 0.994 | −16.1 % |
| mvhi | 1920×1080 | Ultra Performance | 0.979 | 0.892 | −8.9 % | 0.848 | 0.746 | −12.0 % |

### In game (RTX 3070, 4K output, 2X)

RTX 3070, driver 617.14, logs of `[Logging] FrameTiming=1`, median of a 60 s still window after entering the world, tier 2, XeSS at `Middle`. Per generated frame = frame-generation GPU time; real frame rate = frames the game renders (the displayed rate is twice that).

| Game | DLSS default (ms) | XeSS (ms) | XeSS real fps | Preset C (ms) | Preset C real fps |
|---|---:|---:|---:|---:|---:|
| Cyberpunk 2077 | 3.755 | 6.733 (+79 %) | −8.6..−9.7 % | 2.748 (−27 %) | +3.6 % |
| Black Myth: Wukong | 4.035 | 7.308 (+81 %) | −11.0 % | 3.085 (−24 %) | +4.3 % |
| The Witcher 3 | 3.973 | 7.166 (+80 %) | −15.0 % | 2.974 (−25 %) | −0.8 % |
| A Plague Tale: Resonance | 3.943 | 6.968 (+77 %) | −28.1 % | 2.947 (−25 %) | +9.5 % |
| Forza Horizon 6 | 3.856 | 6.847 (+78 %) | −8.0 % | 2.803 (−27 %) | +7.4 % |

Cyberpunk 2077: path tracing + ray reconstruction, DLSS Ultra Performance; Black Myth: Wukong: DLSS 50 %. How the real frame rate moves depends on the game's bottleneck: in The Witcher 3 preset C saves 1 ms per generated frame and the frame rate does not change.

### Whole generation group GPU time (RTX 3080 Ti, synthetic scene)

RTX 3080 Ti, driver 610.88, the 0.4.0 test kit (a tester's machine). GPU milliseconds of the whole frame-generation group per real frame (the span of one group's Evaluates in one submission): median of 256 groups per run, median of 4 rounds; reduction = (tier0 − current) / tier0. tier0 = stock kernels (`Optimized=0`), tier1 = bit-identical acceleration (`1`), tier2 = factory default (`2`). The same kit's consistency checks match the RTX 3070 reference bit for bit: frame generation 18/18, real captures 28/28, super resolution 32/32, super resolution `Mode=On` 4/4.

| Resolution | Multiplier | tier0 (ms) | tier1 (ms) | Reduction | tier2 (ms) | Reduction |
|---|---|---:|---:|---:|---:|---:|
| 1080p | 2X | 1.364 | 0.926 | 32.1 % | 0.917 | 32.8 % |
| 1080p | 3X | 1.942 | 1.423 | 26.7 % | 1.400 | 27.9 % |
| 1080p | 4X | 2.520 | 1.914 | 24.0 % | 1.888 | 25.1 % |
| 1080p | 5X | 3.089 | 2.411 | 21.9 % | 2.375 | 23.1 % |
| 1080p | 6X | 3.677 | 2.911 | 20.8 % | 2.867 | 22.0 % |
| 1440p | 2X | 2.094 | 1.459 | 30.3 % | 1.443 | 31.1 % |
| 1440p | 3X | 3.030 | 2.238 | 26.1 % | 2.205 | 27.2 % |
| 1440p | 4X | 3.963 | 3.008 | 24.1 % | 2.960 | 25.3 % |
| 1440p | 5X | 4.900 | 3.786 | 22.7 % | 3.719 | 24.1 % |
| 1440p | 6X | 5.841 | 4.558 | 22.0 % | 4.472 | 23.4 % |
| 4K | 2X | 2.472 | 1.901 | 23.1 % | 1.864 | 24.6 % |
| 4K | 3X | 3.792 | 3.002 | 20.8 % | 2.924 | 22.9 % |
| 4K | 4X | 5.112 | 4.106 | 19.7 % | 3.987 | 22.0 % |
| 4K | 5X | 6.437 | 5.212 | 19.0 % | 5.054 | 21.5 % |
| 4K | 6X | 7.760 | 6.319 | 18.6 % | 6.123 | 21.1 % |

The gain is larger at lower resolution and lower multiplier (closer to launch/latency bound).

## Estimating FPS after frame generation

First, in the same scene, output resolution, DLSS upscaling mode, and quality settings, turn frame generation off and read the frame rate `F_off`. Convert to a base frame time with `1000 / F_off`, then take the whole-group generation time `T_FG` (ms) from the table above for that resolution, multiplier, and kernel setting.

```text
base frame time    T_base (ms) = 1000 / F_off
group time         T_group (ms) ≈ T_base + T_FG
real-frame/group rate G (grp/s) ≈ 1000 / T_group
output frame rate  F_out (FPS)  ≈ G × M = 1000 × M / (1000 / F_off + T_FG)
```

`M` is the multiplier (2X…6X → 2…6). A group is one real frame plus `M − 1` generated frames; `T_FG` already covers the whole group and the shared preprocessing, so do not multiply it by `M − 1`. With generation on, the real-frame/group rate `G` is lower than `F_off`.

Example: with frame generation off, ~**50 FPS** (20 ms base frame time), using the RTX 3080 Ti **4K 4X** `T_FG` from the table:

| Kernels | T_FG (ms) | group time (ms) | group rate (grp/s) | estimated FPS |
|---|---|---|---|---|
| Stock (tier0) | 5.112 | 25.112 | 39.8 | 159.3 FPS |
| Factory default (tier2) | 3.987 | 23.987 | 41.7 | 166.8 FPS |

For other resolutions/multipliers use the matching row and your own measured `F_off` for that setting. This is a rough estimate — the base render time plus the generation-group cost; GPU contention, synchronization, CPU overhead, frame caps, and the monitor refresh rate all affect the real result, and the estimate is not guaranteed to equal a counter reading or the actual displayed rate.

## 6X

6X (5 generated frames per real frame) is NVIDIA's DLSS 4.5 Dynamic Multi Frame Generation. The bundled runtime supports it and this project makes it run on Ampere (with `Engine=DLSS` only).

**The factory `MaxGeneratedFrames` is `3` (4X); 6X is a manual edit.** A game with dynamic MFG runs at whatever ceiling is written there by default, and `5` was too high for most people (public issues #497 / #499); setting it back to `5` gets 6X at any time. Whether you actually get 6X still depends on the game:

- The game itself supports 6X (ships a newer Streamline frame-gen plugin and offers 6X or Dynamic MFG in its menu): set `MaxGeneratedFrames=5`; 6X runs stably in testing.
- The game only supports 4X (ships an older 4X plugin, as most current games do): the ceiling is set by the game's plugin and this project cannot raise it to 6X. That plugin sizes its internal present queue for 4X at init, so forcing extra frames overruns it and disables frame generation or crashes. Use 4X for these games.

## Real-world feedback

Black Myth: Wukong, Cyberpunk 2077, and Forza Horizon 6 run 4X normally in testing; A Plague Tale: Resonance runs 6X by default with "Dynamic / Auto" frame generation. 0.4.0 ran DLSS default, preset C and XeSS (2X, 4K output) in these four games and The Witcher 3 on an RTX 3070 with no crash, TDR or device removal, and the HUD intact in screenshots. Image quality depends on the base frame rate: at a low base rate, generated frames can show breakup and edge artifacts, more so at higher multipliers, and some games need graphics settings lowered, to raise the base rate, even at 4X for a good result. This is inherent to frame generation when there is little frame-rate headroom, not a defect of this project.

## Known issues

- XeSS-FG (`Engine=XeSS`) is optional; the default is still DLSS-G. On RTX 30 it is much slower per generated frame than DLSS-G (4K: RTX 3070 +77..+86 %, about +3 ms; RTX 3080 Ti offline +109..+114 %), the real frame rate is 8..15 % lower, and 28 % lower in A Plague Tale: Resonance (the cause of the extra wait is not yet found); it uses about 0.4–0.5 GB more VRAM; 2X only (a higher `MaxGeneratedFrames` still gives 2X and logs one `xefg_multiplier_clamped`). The image-quality difference between HUD-less on / off has not been compared frame by frame. `[Debug] Capture` records nothing under XeSS.
- In these cases a game does not use XeSS and runs DLSS-G instead, with one `xefg_fallback` record (at the factory log level) naming the reason: a back buffer that is not R8G8B8A8 / B8G8R8A8 / R10G10B10A2 (e.g. RGBA16F, common for HDR; Intel's own XeSS-FG does not accept that format either); no back buffer, depth, motion vectors or interpolation output from the game; motion vectors and depth of different sizes; an interpolation output whose size differs from the back buffer's; failure to create XeSS's device objects. A HUD-less image or UI plane whose size differs from the back buffer's does not cause a fallback: those frames run without the HUD-less image (`xefg_hudless_unused`).
- `[DLSSG] Preset=B` (UI recomposition forced on) only takes effect when the game provides both a HUD-less image and a UI plane, which most games do not; then the log (at the factory level) has one `preset_ineffective` record naming what is missing, and the image is the same as without `Preset=B`.
- Preset C has no comparison against the official preset C on RTX 40 / 50; in The Witcher 3 preset C saves 1 ms per generated frame but the frame rate does not change (the bottleneck is elsewhere).
- `[FrameGeneration] DetailRestore` / `CatmullRomWarp` have no effect on the 310.9.16 package (logged as `detail_restore_row_unknown`).
- Super resolution `Mode=On`: within one run of the game only the first L / M mode used is accelerated; switching to the other needs a game restart (logged as `sr_route_preset_refused`).
- RTX 20: frame generation and XeSS were verified on the RTX 3070 by forward JIT of the sm_75 kernels only, and 310.9.16's three new kernels have not run on a real Turing card; super-resolution INT8 had one smoke run on a 2080 Ti. RTX 40 / 50: the frame-generation PTX route has not run on real hardware.
- When a game exits abnormally (e.g. force-closed), the backend writes no XeSS summary record (`xefg_summary`; diagnostics only).

## Diagnostics & boundaries

- Logs go to `dlssg_sm86\logs\` in the game directory (`loader_<PID>.jsonl` / `backend_<PID>.jsonl`, plus `frames_<PID>.jsonl` with `FrameTiming=1`). `[Logging] Level=1` (default) records errors only; use `2` or `3` when investigating.
- If frame generation does nothing, check `backend_*.jsonl` for an `install` line with `route active=true`; if it is absent, the driver/runtime usually did not match — the reason is logged and the factory path is used.
- Do not read an offline time reduction as an in-game FPS gain — the real frame-rate change depends on the game and where the bottleneck is.
- All INI keys, log fields, and capture/replay are in [`docs/INSTALL.en.md`](docs/INSTALL.en.md) and [`docs/CAPTURE.md`](docs/CAPTURE.md).

## SM75 source & credits

- Coldwood1026 for the RTX 20-series / SM75 adaptation (the source of the SM75 kernel family — see `THIRD_PARTY_NOTICES.txt`).
- NVIDIA for the DLSS-G runtime, the DLSS super-resolution snippet, models, and pre/post-processing (bundled, unmodified).
- Intel for the XeSS-FG model (shaders and weights, MIT license, see `THIRD_PARTY_NOTICES.txt`).

## Source & building

- The C++ source of the proxies, the backend, the tests and the tools is in the source repository and builds with
  `build.ps1` (default runtime model 310.9.16: `-Runtime310916` for the runtime, `-RuntimeModel 310.9` with `-Runtime3109` for the developer alternative; `-KernelPack` for the kernel pack); the steps,
  tests and rules are in that repository's `CONTRIBUTING.en.md`.
- The kernel pack `dlssg_sm86\kernels\fg_kernels.dll`, the super-resolution kernel pack, the XeSS model pack and the NVIDIA runtimes are not in the source; take them from the
  release of the same version. Without the kernel pack, frame generation stands aside on RTX 30 / 20 (logged as
  `kernel_pack_missing`); everything else works as usual. Without the XeSS model pack, `Engine=XeSS` runs DLSS (`xefg_unavailable`).

## License & third-party

- The project's C++ source is released under the MIT license (`LICENSE.md`, Copyright (c) 2026 sdli1995). The kernel images shipped with it are provided in binary form only and are not covered by the MIT license.
- The bundled `nvngx_dlssg.dll` (310.9.16, SHA prefix `cadee1aa…`) ships unmodified as a file under `dlssg_sm86\runtime\`, and the super-resolution snippet `nvngx_dlss.dll` (310.7.129) under `dlssg_sm86\sr\`. The kernel images in `dlssg_sm86\kernels\fg_kernels.dll` and `dlssg_sm86\sr\sr_kernels.dll` are extracted, recompiled or rewritten from NVIDIA's kernels (the sm_75 family imported from Coldwood1026), are provided in binary form only and are not covered by the MIT license. All of these are NVIDIA and upstream third-party material, not re-licensed with the project source — see `THIRD_PARTY_NOTICES.txt`.
- The shaders and weights in `dlssg_sm86\xefg\xefg_kernels.dll` come from Intel XeSS-FG and ship under Intel's MIT license; the notice is in `THIRD_PARTY_NOTICES.txt`. Intel's `libxess_fg.dll` is not included.
