"""
Generate KAIRO DOT — the custom 5×7 dot-matrix display font (RFC-001 §5.1, §3.2).

Construction rules (RFC §3.2):
  - Mark lives on a 48×48 unit grid at 1x (base).
  - Gap (the "K") is 4 units wide, centered vertically.
  - Dot pitch: 2 units on-center.  Radius: 24 units.
  - The wave inside follows a sine function (period 8, amplitude 6).

The glyph set here is a 5×7 dot grid per character (uppercase A–Z, digits 0–9,
plus the punctuation KAIRO UI needs: + - % . : / , ( ) ! ? and space).
Each "on" dot becomes a filled square in TrueType outlines, preserving the
dot-matrix language. The font is built with fonttools and compressed to woff2.

Usage:  python scripts/gen_kairo_dot.py
Output: ui/brand/fonts/kairo-dot.woff2  (+ .ttf sibling for debugging)
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from fontTools.ttLib import TTFont, newTable
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.tables._g_l_y_f import Glyph
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
except ImportError:  # pragma: no cover
    sys.exit("fonttools is required: pip install fonttools brotli")

UNIT = 120          # font units per dot
GRID_W, GRID_H = 5, 7
ADVANCE = GRID_W + 2  # 2 dots of side bearing for the dot matrix rhythm
EM = UNIT * 12      # 12-dot em so the font scales like a normal display face

GLYPHS: dict[str, list[str]] = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "10001", "11001", "10101", "10011", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    "%": ["11001", "11001", "00010", "00100", "01000", "10011", "10011"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "/": ["00001", "00001", "00010", "00100", "01000", "10000", "10000"],
    ",": ["00000", "00000", "00000", "00000", "01100", "01100", "00100"],
    "(": ["00010", "00100", "01000", "01000", "01000", "00100", "00010"],
    ")": ["01000", "00100", "00010", "00010", "00010", "00100", "01000"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    "?": ["01110", "10001", "00001", "00010", "00100", "00000", "00100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def build_font() -> TTFont:
    font = TTFont()
    font.setGlyphOrder([".notdef", *GLYPHS.keys()])

    # --- cmap ---------------------------------------------------------------
    cmap = newTable("cmap")
    cmap.tableVersion = 0
    sub = CmapSubtable.newSubtable(4)
    sub.platformID, sub.platEncID, sub.language = 3, 1, 0
    sub.cmap = {ord(ch): name for name, ch in zip(GLYPHS.keys(), GLYPHS.keys())}
    cmap.tables = [sub]
    font["cmap"] = cmap

    # --- glyf ---------------------------------------------------------------
    glyf = newTable("glyf")
    glyf.glyphOrder = font.getGlyphOrder()
    glyf.glyphs = {}
    glyphs: list[Glyph] = []

    for name, bits in GLYPHS.items():
        pen = TTGlyphPen(None)
        for (x0, y0), (x1, y1) in _rects(bits):
            pen.moveTo((x0, y0))
            pen.lineTo((x1, y0))
            pen.lineTo((x1, y1))
            pen.lineTo((x0, y1))
            pen.closePath()
        glyph = pen.glyph()
        glyph.recalcBounds(glyf)
        glyf.glyphs[name] = glyph
        glyphs.append(glyph)

    # .notdef = solid square
    pen = TTGlyphPen(None)
    pen.moveTo((0, 0))
    pen.lineTo((5 * UNIT, 0))
    pen.lineTo((5 * UNIT, 7 * UNIT))
    pen.lineTo((0, 7 * UNIT))
    pen.closePath()
    g = pen.glyph()
    g.recalcBounds(glyf)
    glyf.glyphs[".notdef"] = g
    font["glyf"] = glyf

    # --- loca (auto-generated from glyf) ------------------------------------
    loca = newTable("loca")
    font["loca"] = loca

    # --- hmtx ---------------------------------------------------------------
    hmtx = newTable("hmtx")
    hmtx.metrics = {name: (ADVANCE * UNIT, 0) for name in font.getGlyphOrder()}
    font["hmtx"] = hmtx

    # --- head / hhea / maxp -------------------------------------------------
    head = newTable("head")
    head.tableVersion = 1.0
    head.fontRevision = 1.0
    head.checkSumAdjustment = 0
    head.magicNumber = 0x5F0F3CF5
    head.flags = 0x000B
    head.unitsPerEm = EM
    head.created = head.modified = 0
    head.xMin, head.yMin = 0, 0
    head.xMax, head.yMax = 5 * UNIT, 7 * UNIT
    head.macStyle = 0
    head.lowestRecPPEM = 8
    head.fontDirectionHint = 2
    head.indexToLocFormat = 0
    head.glyphDataFormat = 0
    font["head"] = head

    hhea = newTable("hhea")
    hhea.tableVersion = 0x00010000
    hhea.ascent, hhea.descent = 7 * UNIT, 0
    hhea.lineGap = UNIT
    hhea.advanceWidthMax = ADVANCE * UNIT
    hhea.minLeftSideBearing = 0
    hhea.minRightSideBearing = 0
    hhea.xMaxExtent = 5 * UNIT
    hhea.caretSlopeRise, hhea.caretSlopeRun = 1, 0
    hhea.caretOffset = 0
    hhea.reserved0, hhea.reserved1, hhea.reserved2, hhea.reserved3 = 0, 0, 0, 0
    hhea.metricDataFormat = 0
    hhea.numberOfHMetrics = len(font.getGlyphOrder())
    font["hhea"] = hhea

    maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    maxp.numGlyphs = len(font.getGlyphOrder())
    maxp.maxPoints = 5 * 4
    maxp.maxContours = 35
    maxp.maxCompositePoints = 0
    maxp.maxCompositeContours = 0
    maxp.maxZones = 1
    maxp.maxTwilightPoints = 0
    maxp.maxStorage = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 0
    maxp.maxStackElements = 0
    maxp.maxSizeOfInstructions = 0
    maxp.maxComponentElements = 0
    maxp.maxComponentDepth = 0
    font["maxp"] = maxp

    # --- name / post / OS2 ---------------------------------------------------
    from fontTools.ttLib.tables._n_a_m_e import NameRecord

    name = newTable("name")
    name.names = []
    for name_id, value in [
        (1, "KAIRO DOT"),
        (2, "Regular"),
        (4, "KAIRO DOT Regular"),
        (6, "KairoDot-Regular"),
    ]:
        rec = NameRecord()
        rec.nameID = name_id
        rec.platformID = 3
        rec.platEncID = 1
        rec.langID = 0x409
        rec.string = value
        name.names.append(rec)
    font["name"] = name

    post = newTable("post")
    post.formatType = 3.0
    post.italicAngle = 0
    post.underlinePosition, post.underlineThickness = -100, 50
    post.isFixedPitch = 1
    post.minMemType42, post.maxMemType42 = 0, 0
    post.minMemType1, post.maxMemType1 = 0, 0
    font["post"] = post

    os2 = newTable("OS/2")
    os2.version = 4
    os2.xAvgCharWidth = ADVANCE * UNIT
    os2.usWeightClass = 400
    os2.usWidthClass = 5
    os2.fsType = 0x0000
    os2.ySubscriptXSize = 650
    os2.ySubscriptYSize = 600
    os2.ySubscriptXOffset = 0
    os2.ySubscriptYOffset = 75
    os2.ySuperscriptXSize = 650
    os2.ySuperscriptYSize = 600
    os2.ySuperscriptXOffset = 0
    os2.ySuperscriptYOffset = 350
    os2.yStrikeoutSize = 50
    os2.yStrikeoutPosition = 350
    os2.sFamilyClass = 0
    from fontTools.ttLib.tables.O_S_2f_2 import Panose as _Panose

    _p = _Panose()
    _p.bFamilyType = 0  # Any
    os2.panose = _p
    os2.ulUnicodeRange1 = 1
    os2.ulUnicodeRange2 = 0
    os2.ulUnicodeRange3 = 0
    os2.ulUnicodeRange4 = 0
    os2.achVendID = "KAIRO"
    os2.fsSelection = 0x0040
    os2.usFirstCharIndex = 0x20
    os2.usLastCharIndex = 0x7E
    os2.sTypoAscender = 7 * UNIT
    os2.sTypoDescender = 0
    os2.sTypoLineGap = UNIT
    os2.usWinAscent = 7 * UNIT
    os2.usWinDescent = 0
    os2.ulCodePageRange1 = 1
    os2.ulCodePageRange2 = 0
    os2.sxHeight = 5 * UNIT
    os2.sCapHeight = 7 * UNIT
    os2.usDefaultChar = 0x20
    os2.usBreakChar = 0x20
    os2.usMaxContext = 1
    font["OS/2"] = os2

    return font


def _rects(bits: list[str]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    rects: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for row, line in enumerate(bits):
        y0 = (GRID_H - 1 - row) * UNIT
        for col, ch in enumerate(line):
            if ch == "1":
                x0 = col * UNIT
                rects.append(((x0, y0), (x0 + UNIT, y0 + UNIT)))
    return rects


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    out = root / "ui" / "brand" / "fonts"
    out.mkdir(parents=True, exist_ok=True)

    font = build_font()
    ttf_path = out / "kairo-dot.ttf"
    font.save(ttf_path)

    # woff2 needs brotli
    try:
        from fontTools.ttLib import woff2  # noqa: F401

        woff2_path = out / "kairo-dot.woff2"
        font.flavor = "woff2"
        font.save(woff2_path)
        print(f"kairo-dot: wrote {ttf_path.name} + {woff2_path.name} ({woff2_path.stat().st_size} bytes)")
    except Exception as exc:  # brotli missing
        print(f"kairo-dot: wrote {ttf_path.name} (woff2 skipped: {exc})")


if __name__ == "__main__":
    main()
