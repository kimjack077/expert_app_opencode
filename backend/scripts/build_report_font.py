# -*- coding: utf-8 -*-
"""构建报告用的中文字体（backend/assets/fonts/NotoSansSC-Regular.ttf）。

背景：报告 PDF 由 reportlab 生成，需要 TrueType 中文字体。
上游 Noto Sans SC 是可变字体，reportlab 的 TTFont 不支持，
所以这里下载 → 实例化 wght=400 → 子集化 → 落到 assets/fonts/。

用法（构建期一次性执行，运行时不依赖本脚本）：
    pip install "fonttools>=4.50"
    python scripts/build_report_font.py

详见 backend/assets/fonts/README.md
"""
import os
import sys
import tempfile
import urllib.request

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SRC_URL = (
    "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/notosanssc/"
    "NotoSansSC%5Bwght%5D.ttf"
)
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "fonts",
    "NotoSansSC-Regular.ttf",
)

# 保留的码位：ASCII / 拉丁补充 / 希腊 / 常用符号 / CJK 标点 / 假名 / CJK 基本区全量 / 全角
UNICODES = (
    list(range(0x0020, 0x007F))
    + list(range(0x00A0, 0x0100))
    + list(range(0x0370, 0x0400))
    + [0x2010, 0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x2030, 0x20AC]
    + list(range(0x2100, 0x2140))
    + list(range(0x2190, 0x2200))
    + list(range(0x2460, 0x2500))
    + list(range(0x25A0, 0x2700))
    + list(range(0x3000, 0x3040))
    + list(range(0x3040, 0x30A0))
    + list(range(0x4E00, 0xA000))
    + list(range(0xFE30, 0xFE50))
    + list(range(0xFF00, 0xFFF0))
)


def main() -> int:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmpdir = tempfile.mkdtemp(prefix="noto-sc-")
    var_path = os.path.join(tmpdir, "NotoSansSC-var.ttf")
    static_path = os.path.join(tmpdir, "NotoSansSC-static.ttf")

    print("[1/3] 下载上游可变字体…")
    urllib.request.urlretrieve(SRC_URL, var_path)
    print("      %.1f MB" % (os.path.getsize(var_path) / 1024 / 1024))

    print("[2/3] 实例化 wght=400 为静态字重…")
    font = TTFont(var_path)
    instance = instancer.instantiateVariableFont(
        font, {"wght": 400}, inplace=False, updateFontNames=True
    )
    instance.save(static_path)

    print("[3/3] 子集化…")
    subset.main(
        [
            static_path,
            "--unicodes=%s" % ",".join("U+%04X" % u for u in UNICODES),
            "--layout-features=*",
            "--glyph-names",
            "--no-hinting",
            "--name-IDs=*",
            "--output-file=%s" % OUT,
        ]
    )
    print("完成：%s（%.1f MB）" % (OUT, os.path.getsize(OUT) / 1024 / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
