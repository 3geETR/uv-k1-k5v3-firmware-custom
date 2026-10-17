#!/usr/bin/env python3
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from app_assets import Assets

TITLE = "Sonde RS41"
UI = [
    ("T_TITLE", TITLE),
    ("T_NOPOS", "no position"),
    ("T_ALT", "ALT "),
    ("T_M", "m"),
    ("T_FRAME", "FRAME "),
    ("T_DBM", "dBm"),
    ("T_KHZ", "kHz"),
    ("T_ATT", "ATT "),
    ("T_DB", "dB"),
    ("T_BYP", "BYP"),
    ("T_BYP_PLUS", "BYP+"),
]
a = Assets("SONDE_RS41")
ui_size = 0
for name, value in UI:
    pad = -(len(value) + 1) % 4
    a.text(name, value + "\0" * pad)
    ui_size += len(value) + 1 + pad
a.const("UI_SIZE", ui_size)
a.const("T_TITLE_CHARS", len(TITLE))
a.u8("BMP_SPK", [0x1C, 0x1C, 0x3E, 0x7F, 0x00, 0x22, 0x1C, 0x41, 0x22, 0x1C])
a.const("SPK_W", 10)
a.u8("BMP_F", [0x3E, 0x7F, 0x41, 0x75, 0x75, 0x75, 0x7D, 0x7F, 0x3E])
a.u16("ATT_REG13", [0x03DF, 0x03DD, 0x03DB, 0x03D9, 0x0379, 0x0139])
a.u8("ATT_DB", [0, 6, 15, 27])
a.const("ATT_COUNT", 6)
a.const("ATT_BYP0", 4)
a.main()
