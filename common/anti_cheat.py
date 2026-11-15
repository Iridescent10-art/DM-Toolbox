# -*- coding: utf-8 -*-
"""反作弊游戏识别：这些游戏注入多帧生成 / DLSS 5 会被反作弊强制结束进程。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

# 上游 MFG Unlocker 文档「Games with anti-cheat」名单 + 常见反作弊模块
ANTI_CHEAT_GAME_KEYWORDS = (
    ("forza horizon 6", "Forza Horizon 6"),
    ("forzahorizon6", "Forza Horizon 6"),
    ("forza motorsport", "Forza Motorsport"),
    ("battlefield 6", "Battlefield 6 / RedSec"),
    ("battlefield6", "Battlefield 6 / RedSec"),
    ("redsec", "Battlefield 6 / RedSec"),
    ("gta v enhanced", "GTA V Enhanced"),
    ("gtav enhanced", "GTA V Enhanced"),
    ("gears of war", "Gears of War: E-Day"),
    ("zenless zone zero", "Zenless Zone Zero"),
    ("zenlesszonezero", "Zenless Zone Zero"),
    ("delta force", "Delta Force"),
    ("valorant", "VALORANT"),
    ("apex legends", "Apex Legends"),
    ("destiny 2", "Destiny 2"),
    ("rainbow six siege", "Rainbow Six Siege"),
    ("the finals", "THE FINALS"),
    ("arc raiders", "ARC Raiders"),
)

ANTI_CHEAT_MODULE_KEYWORDS = (
    "easyanticheat",
    "easyanticheat_eos",
    "battleye",
    "beclient",
    "anticheatexpert",
    "xigncode",
    "nprotect",
)


def detect_anti_cheat(game_name: str = "", exe_path: str = "",
                       target_dir: Union[str, Path, None] = None,
                       max_depth: int = 2) -> Optional[str]:
    """
    返回命中的游戏/反作弊名称；未命中返回 None。

    - 先按游戏名 / exe 名匹配已知名单（上游 MFG Unlocker 文档的 anti-cheat 列表）；
    - 再在游戏目录浅层查找 EasyAntiCheat / BattlEye 等反作弊模块目录或文件。
    """
    haystack = f"{game_name or ''} {exe_path or ''}".lower().replace("_", " ").replace("-", " ")
    compact = haystack.replace(" ", "")
    for keyword, label in ANTI_CHEAT_GAME_KEYWORDS:
        k = keyword.replace("_", " ").replace("-", " ")
        if k in haystack or k.replace(" ", "") in compact:
            return label

    if target_dir:
        td = Path(target_dir)
        if td.exists():
            base_depth = len(td.parts)
            for p in td.rglob("*"):
                try:
                    if len(p.parts) - base_depth > max_depth:
                        continue
                except Exception:
                    continue
                low = p.name.lower()
                if any(k in low for k in ANTI_CHEAT_MODULE_KEYWORDS):
                    return f"检测到反作弊模块: {p.name}"
    return None


def anti_cheat_warning_text(label: str, action: str = "注入多帧生成 / DLSS 5") -> str:
    return (
        f"检测到该游戏带反作弊：{label}\n\n"
        f"上游 MFG Unlocker 文档明确说明：反作弊游戏不受支持，{action}可能在启动时"
        f"被反作弊强制结束进程（表现为启动画面闪退、无崩溃日志）。\n\n"
        f"建议保持原版游玩。\n\n"
        f"仍要强制{action}吗？"
    )
