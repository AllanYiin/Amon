#!/usr/bin/env python3
"""Generate a markdown visual-elements planning table scaffold.

Usage:
  python scripts/make_visual_table.py --slides 12 > visual_table.md

This is a deterministic helper to avoid manual table formatting errors.
"""

from __future__ import annotations

import argparse


def build_table(n: int) -> str:
    if n <= 0:
        raise ValueError("--slides must be > 0")

    header = "| 頁碼 | 主題 | 關鍵視覺元素 | 色塊安排 | 視覺動線 | 特殊圖示建議 | 備註 |"
    sep = "|---:|---|---|---|---|---|---|"

    rows = []
    for i in range(1, n + 1):
        if i == 1:
            rows.append(
                "| 1 | 封面 | 主標題＋主視覺（主意象） | 左側深橙 / 右側灰 | 斜向上升（底邊→尖端） | 核心概念 icon | 封面不需資料來源 |"
            )
        elif i == n:
            rows.append(
                f"| {i} | Q&A | 問答提示模組（圖示＋留白區） | 灰底＋橙點綴 | 聚焦中央 | 問號/對話 icon | 可加聯絡資訊/下一步 |"
            )
        else:
            rows.append(
                f"| {i} | （填入） | （填入） | （填入） | （填入） | （填入） | 若含數據/新聞：註明來源需求 |"
            )

    return "\n".join(["# 視覺元素規劃表（自動骨架）", "", header, sep, *rows, ""])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slides", type=int, required=True, help="Total slides (including cover + Q&A)")
    args = ap.parse_args()

    print(build_table(args.slides))


if __name__ == "__main__":
    main()
