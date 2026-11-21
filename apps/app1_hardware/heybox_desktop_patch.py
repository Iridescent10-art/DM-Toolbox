# -*- coding: utf-8 -*-
"""小黑盒桌面版（HeyboxDesktop 2.x）硬件伪装 Hook。

新版小黑盒不再用 resources/app/index.js，而是把硬件采集放在扩展：
  versions/<ver>/resources/extensions/internal/ai-desktop.hardware-detect/services/hardware.mjs
这里在模块尾部注入一层包装，覆盖 getInventory / getReportInfo 返回的硬件信息。
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import List, Optional

MARKER = "/* TBX_HEYBOX_DESKTOP_HOOK_V1 */"

DESKTOP_CANDIDATES = [
    r"C:\Program Files (x86)\Qingfeng\HeyboxDesktop",
    r"C:\Program Files\Qingfeng\HeyboxDesktop",
    r"D:\Program Files (x86)\Qingfeng\HeyboxDesktop",
    r"D:\Program Files\Qingfeng\HeyboxDesktop",
]

HOOK_JS = r"""

/* TBX_HEYBOX_DESKTOP_HOOK_V1 */
import { readFileSync as __tbxReadFile, existsSync as __tbxExists } from "node:fs";
import { join as __tbxJoinPath } from "node:path";
const __tbxOrigCreate = Ct;
function __tbxReadCfg() {
  try {
    const candidates = [];
    if (process.env.APPDATA) candidates.push(__tbxJoinPath(process.env.APPDATA, 'ToolboxMaster', 'config', 'app1_hardware', 'config.json'));
    if (process.env.LOCALAPPDATA) candidates.push(__tbxJoinPath(process.env.LOCALAPPDATA, 'ToolboxMaster', 'config', 'app1_hardware', 'config.json'));
    candidates.push('C:\\Users\\Public\\Hardware_Config.json');
    candidates.push('C:\\ToolboxData\\config\\app1_hardware\\config.json');
    if (process.env.ProgramFiles) candidates.push(__tbxJoinPath(process.env.ProgramFiles, 'DMBOX', 'apps', 'app1_hardware', 'config.json'));
    if (process.env['ProgramFiles(x86)']) candidates.push(__tbxJoinPath(process.env['ProgramFiles(x86)'], 'DMBOX', 'apps', 'app1_hardware', 'config.json'));
    candidates.push('D:\\AI\\整合包\\apps\\app1_hardware\\config.json');
    for (const p of candidates) {
      try {
        if (!__tbxExists(p)) continue;
        const data = JSON.parse(__tbxReadFile(p, 'utf8'));
        if (data && data.custom_target) return data.custom_target;
      } catch (e) {}
    }
  } catch (e) {}
  return null;
}
function __tbxNum(v) { const n = Number(v); return Number.isFinite(n) && n > 0 ? n : undefined; }
function __tbxBytes(gb) { const n = __tbxNum(gb); return n ? Math.round(n * 1024 * 1024 * 1024) : undefined; }
function __tbxDiskBytes(model) {
  if (!model) return undefined;
  let m = /(\d+(?:\.\d+)?)\s*TB/i.exec(model);
  if (m) return Math.round(Number(m[1]) * 1024 ** 4);
  m = /(\d+(?:\.\d+)?)\s*GB/i.exec(model);
  if (m) return Math.round(Number(m[1]) * 1024 ** 3);
  return undefined;
}
function __tbxApplyInventory(inv, cfg) {
  if (!inv || typeof inv !== 'object' || !cfg) return inv;
  const out = { ...inv };
  if (cfg.cpu_model && out.cpu) out.cpu = { ...out.cpu, name: String(cfg.cpu_model) };
  if (Array.isArray(out.gpus) && out.gpus.length && cfg.gpu_model) {
    out.gpus = out.gpus.map((g, i) => i === 0 ? { ...g, name: String(cfg.gpu_model), ...(__tbxBytes(cfg.gpu_vram_gb) ? { memoryBytes: __tbxBytes(cfg.gpu_vram_gb) } : {}) } : g);
  }
  if (out.memory && (cfg.memory_size_gb || cfg.memory_vendor || cfg.memory_clock_mhz || cfg.memory_type)) {
    const mem = { ...out.memory };
    const bytes = __tbxBytes(cfg.memory_size_gb);
    if (bytes) { mem.totalBytes = bytes; mem.moduleCount = mem.moduleCount || 1; }
    if (cfg.memory_vendor) mem.vendor = String(cfg.memory_vendor);
    if (__tbxNum(cfg.memory_clock_mhz)) mem.speedMhz = Number(cfg.memory_clock_mhz);
    if (cfg.memory_type) mem.type = String(cfg.memory_type);
    if (cfg.memory_part_number) mem.partNumber = String(cfg.memory_part_number);
    out.memory = mem;
  }
  if (out.board && (cfg.motherboard_product || cfg.motherboard_vendor)) {
    out.board = { ...out.board, ...(cfg.motherboard_product ? { name: String(cfg.motherboard_product), product: String(cfg.motherboard_product) } : {}), ...(cfg.motherboard_vendor ? { vendor: String(cfg.motherboard_vendor) } : {}) };
  }
  if (Array.isArray(out.disks) && out.disks.length && cfg.disk_model) {
    const size = __tbxDiskBytes(cfg.disk_model);
    out.disks = out.disks.map((d, i) => i === 0 ? { ...d, name: String(cfg.disk_model), ...(size ? { sizeBytes: size } : {}) } : d);
  }
  return out;
}
function __tbxApplyReport(rep, cfg) {
  if (!rep || typeof rep !== 'object' || !cfg) return rep;
  const out = { ...rep };
  if (cfg.cpu_model && out.cpu) out.cpu = { ...out.cpu, name: String(cfg.cpu_model) };
  if (out.memory) {
    const mem = { ...out.memory };
    const gb = __tbxNum(cfg.memory_size_gb);
    if (gb) mem.memory_size = gb;
    if (cfg.memory_vendor) mem.vendor = String(cfg.memory_vendor);
    if (__tbxNum(cfg.memory_clock_mhz)) mem.clock_speed = Number(cfg.memory_clock_mhz);
    if (cfg.memory_type) mem.type_name = String(cfg.memory_type);
    out.memory = mem;
  }
  if (Array.isArray(out.gpus) && out.gpus.length) {
    out.gpus = out.gpus.map((g, i) => i === 0 ? { ...g, ...(cfg.gpu_model ? { name: String(cfg.gpu_model) } : {}), ...(__tbxNum(cfg.gpu_vram_gb) ? { memory_size: __tbxNum(cfg.gpu_vram_gb) } : {}) } : g);
  }
  if (Array.isArray(out.disks) && out.disks.length && cfg.disk_model) {
    const size = __tbxDiskBytes(cfg.disk_model);
    out.disks = out.disks.map((d, i) => i === 0 ? { ...d, name: String(cfg.disk_model), ...(size ? { size: size } : {}) } : d);
  }
  if (out.board) out.board = { ...out.board, ...(cfg.motherboard_product ? { name: String(cfg.motherboard_product), product: String(cfg.motherboard_product) } : {}), ...(cfg.motherboard_vendor ? { vendor: String(cfg.motherboard_vendor) } : {}) };
  if (out.computer && cfg.motherboard_product) out.computer = { ...out.computer, model: String(cfg.motherboard_product) };
  return out;
}
function __tbxWrapService(svc) {
  if (!svc || typeof svc !== 'object') return svc;
  return new Proxy(svc, {
    get(target, prop, receiver) {
      const orig = Reflect.get(target, prop, receiver);
      if (typeof orig !== 'function') return orig;
      if (prop === 'getInventory') {
        return async (...args) => {
          const res = await orig.apply(target, args);
          const cfg = __tbxReadCfg();
          if (!cfg || !res || typeof res !== 'object') return res;
          if (res.snapshot) return { ...res, snapshot: __tbxApplyInventory(res.snapshot, cfg) };
          return __tbxApplyInventory(res, cfg);
        };
      }
      if (prop === 'getReportInfo') {
        return async (...args) => __tbxApplyReport(await orig.apply(target, args), __tbxReadCfg());
      }
      return orig.bind(target);
    }
  });
}
function __tbxCreate(e) { return __tbxWrapService(__tbxOrigCreate(e)); }
export { __tbxCreate as create, Pt as dispose };
"""


def find_desktop_dirs() -> List[Path]:
    dirs: List[Path] = []
    for c in DESKTOP_CANDIDATES:
        p = Path(c)
        if p.exists():
            dirs.append(p)
    # 注册表
    try:
        import winreg
        for hkey, sub in (
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ):
            with winreg.OpenKey(hkey, sub) as parent:
                for i in range(winreg.QueryInfoKey(parent)[0]):
                    try:
                        k = winreg.EnumKey(parent, i)
                        with winreg.OpenKey(parent, k) as app:
                            name = winreg.QueryValueEx(app, "DisplayName")[0]
                            if "小黑盒" in name and ("Desktop" in name or "桌面" in name):
                                loc = winreg.QueryValueEx(app, "InstallLocation")[0].strip('"')
                                if os.path.isdir(loc):
                                    dirs.append(Path(loc))
                    except Exception:
                        continue
    except Exception:
        pass
    # 去重
    out, seen = [], set()
    for d in dirs:
        k = str(d).lower()
        if k not in seen:
            seen.add(k)
            out.append(d)
    return out


def find_hardware_modules(base: Path) -> List[Path]:
    versions = base / "versions"
    if not versions.is_dir():
        return []
    found = []
    for v in versions.iterdir():
        p = v / "resources" / "extensions" / "internal" / "ai-desktop.hardware-detect" / "services" / "hardware.mjs"
        if p.exists():
            found.append(p)
    return found


def is_patched(path: Path) -> bool:
    try:
        return MARKER in path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False


def _inject(content: str) -> str:
    # 去掉旧 export，改成包装后的 create
    old_export = "export{Ct as create,Pt as dispose};"
    if old_export not in content:
        raise RuntimeError("未找到预期的 export 语句，无法注入（小黑盒版本可能已变化）")
    return content.replace(old_export, HOOK_JS.strip(), 1)


def patch_hardware_module(path: Path, dry_run: bool = False) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if MARKER in text:
        return False
    new_text = _inject(text)
    if dry_run:
        return True
    bak = path.with_suffix(path.suffix + ".tbx_bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(new_text, encoding="utf-8")
    return True


def restore_hardware_module(path: Path) -> bool:
    bak = path.with_suffix(path.suffix + ".tbx_bak")
    if bak.exists():
        shutil.copy2(bak, path)
        return True
    return False


def apply_heybox_desktop_hook() -> List[str]:
    """返回已处理的 hardware.mjs 路径列表。"""
    done = []
    for base in find_desktop_dirs():
        for mod in find_hardware_modules(base):
            try:
                if patch_hardware_module(mod):
                    done.append(str(mod))
            except Exception:
                continue
    return done


if __name__ == "__main__":
    for p in apply_heybox_desktop_hook():
        print("patched:", p)
