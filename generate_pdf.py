"""
generate_pdf.py
---------------
Converts project_documentation.md to a professional PDF using PyMuPDF (fitz).
All operations stay on D: drive — no C: drive temp files or Chromium downloads.

Output: D:\\real chatbot\\KAI_Chatbot_Documentation.pdf
"""

import fitz  # PyMuPDF
import os
import re
import sys
import textwrap

# ── Configuration ──────────────────────────────────────────────────────────────

MARKDOWN_PATH = r"C:\Users\kelum\.gemini\antigravity-ide\brain\344fc71e-fb42-4a24-8bdd-1dcab85223e3\project_documentation.md"
OUTPUT_DIR    = r"D:\real chatbot"
OUTPUT_PDF    = os.path.join(OUTPUT_DIR, "KAI_Chatbot_Documentation.pdf")

# Page geometry
PAGE_W, PAGE_H = fitz.paper_size("a4")   # 595 x 842 pts
MARGIN_L = 54
MARGIN_R = 54
MARGIN_T = 60
MARGIN_B = 60
TEXT_W   = PAGE_W - MARGIN_L - MARGIN_R

# ── Colour palette ─────────────────────────────────────────────────────────────

BG_DARK        = (0.05, 0.07, 0.12)
ACCENT_BLUE    = (0.28, 0.55, 1.00)
ACCENT_CYAN    = (0.25, 0.88, 0.82)
ACCENT_PURPLE  = (0.53, 0.35, 0.96)
WHITE          = (1.0, 1.0, 1.0)
LIGHT_GREY     = (0.75, 0.78, 0.85)
MID_GREY       = (0.45, 0.48, 0.55)
CODE_BG        = (0.10, 0.13, 0.20)
TABLE_HEADER   = (0.15, 0.20, 0.32)
TABLE_ROW_ALT  = (0.09, 0.11, 0.18)
TABLE_ROW_NORM = (0.07, 0.09, 0.15)

FONT_REGULAR = "helv"
FONT_BOLD    = "hebo"
FONT_ITALIC  = "heit"
FONT_MONO    = "cour"

# ── PDF builder class ──────────────────────────────────────────────────────────

class PDFBuilder:
    def __init__(self):
        self.doc   = fitz.open()
        self.page  = None
        self.y     = MARGIN_T
        self._new_page()

    def _new_page(self):
        self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
        self.page.draw_rect(fitz.Rect(0, 0, PAGE_W, PAGE_H),
                            color=None, fill=BG_DARK, overlay=False)
        self.y = MARGIN_T

    def _check_space(self, needed=30):
        if self.y + needed > PAGE_H - MARGIN_B:
            self._draw_footer()
            self._new_page()

    def _draw_footer(self):
        pno = len(self.doc)
        self.page.draw_line(
            fitz.Point(MARGIN_L, PAGE_H - 30),
            fitz.Point(PAGE_W - MARGIN_R, PAGE_H - 30),
            color=ACCENT_BLUE, width=0.5
        )
        self.page.insert_text(
            fitz.Point(MARGIN_L, PAGE_H - 16),
            "KAI Chatbot -- Project Documentation",
            fontname=FONT_REGULAR, fontsize=8, color=MID_GREY
        )
        self.page.insert_text(
            fitz.Point(PAGE_W - MARGIN_R - 20, PAGE_H - 16),
            str(pno),
            fontname=FONT_REGULAR, fontsize=8, color=MID_GREY
        )

    def _text_block(self, text, fontname, fontsize, color,
                    indent=0, line_height=None, max_width=None):
        if line_height is None:
            line_height = fontsize * 1.45
        width = (max_width or TEXT_W) - indent
        avg_char = fontsize * 0.55
        chars_per_line = max(1, int(width / avg_char))
        lines = []
        for raw in text.split("\n"):
            if raw.strip() == "":
                lines.append("")
            else:
                lines.extend(textwrap.wrap(raw, chars_per_line) or [""])
        for line in lines:
            self._check_space(line_height)
            if line:
                self.page.insert_text(
                    fitz.Point(MARGIN_L + indent, self.y),
                    line,
                    fontname=fontname,
                    fontsize=fontsize,
                    color=color,
                )
            self.y += line_height

    def _h1(self, text):
        self._check_space(70)
        self.y += 12
        for i, col in enumerate([ACCENT_BLUE, ACCENT_CYAN, ACCENT_PURPLE]):
            self.page.draw_rect(
                fitz.Rect(MARGIN_L + i * (TEXT_W // 3), self.y,
                           MARGIN_L + (i + 1) * (TEXT_W // 3), self.y + 3),
                color=None, fill=col
            )
        self.y += 10
        self.page.insert_text(
            fitz.Point(MARGIN_L, self.y),
            text.upper(),
            fontname=FONT_BOLD, fontsize=22, color=WHITE,
        )
        self.y += 30

    def _h2(self, text):
        self._check_space(50)
        self.y += 14
        self.page.draw_rect(
            fitz.Rect(MARGIN_L, self.y - 14, MARGIN_L + 3, self.y + 4),
            color=None, fill=ACCENT_BLUE
        )
        self.page.insert_text(
            fitz.Point(MARGIN_L + 10, self.y),
            text,
            fontname=FONT_BOLD, fontsize=15, color=ACCENT_BLUE,
        )
        self.y += 10
        self.page.draw_line(
            fitz.Point(MARGIN_L, self.y),
            fitz.Point(PAGE_W - MARGIN_R, self.y),
            color=ACCENT_BLUE, width=0.5
        )
        self.y += 8

    def _h3(self, text):
        self._check_space(35)
        self.y += 8
        self.page.insert_text(
            fitz.Point(MARGIN_L, self.y),
            text,
            fontname=FONT_BOLD, fontsize=12, color=ACCENT_CYAN,
        )
        self.y += 16

    def _paragraph(self, text, indent=0):
        self._text_block(text, FONT_REGULAR, 10, LIGHT_GREY,
                         indent=indent, line_height=15)
        self.y += 4

    def _bullet(self, text, level=0):
        indent = 16 + level * 14
        bullet_x = MARGIN_L + indent - 10
        self._check_space(16)
        col = ACCENT_CYAN if level == 0 else ACCENT_BLUE
        self.page.draw_circle(
            fitz.Point(bullet_x, self.y - 3), 2,
            color=None, fill=col
        )
        self._text_block(text, FONT_REGULAR, 10, LIGHT_GREY,
                         indent=indent, line_height=15,
                         max_width=TEXT_W - 4)

    def _code_block(self, lines):
        self._check_space(20)
        self.y += 4
        code_lines = lines.split("\n")
        block_h = len(code_lines) * 13 + 12
        self._check_space(block_h)
        rect = fitz.Rect(MARGIN_L, self.y, PAGE_W - MARGIN_R, self.y + block_h)
        self.page.draw_rect(rect, color=ACCENT_BLUE, fill=CODE_BG, width=0.5)
        self.y += 8
        for ln in code_lines:
            self._check_space(13)
            display = ln[:90] + ("..." if len(ln) > 90 else "")
            if display.strip():
                self.page.insert_text(
                    fitz.Point(MARGIN_L + 8, self.y),
                    display,
                    fontname=FONT_MONO, fontsize=8, color=ACCENT_CYAN,
                )
            self.y += 13
        self.y += 6

    def _table(self, header, rows):
        COL_COUNT = len(header)
        col_w = TEXT_W / COL_COUNT
        row_h = 16
        self._check_space(row_h * (len(rows) + 2))
        for c, hdr in enumerate(header):
            rx = MARGIN_L + c * col_w
            self.page.draw_rect(
                fitz.Rect(rx, self.y, rx + col_w, self.y + row_h),
                color=None, fill=TABLE_HEADER
            )
            txt = hdr.strip().lstrip("*:").rstrip("*:")
            self.page.insert_text(
                fitz.Point(rx + 4, self.y + 11),
                txt[:int(col_w / 5.5)],
                fontname=FONT_BOLD, fontsize=8, color=ACCENT_CYAN
            )
        self.y += row_h
        for ri, row in enumerate(rows):
            fill = TABLE_ROW_ALT if ri % 2 == 0 else TABLE_ROW_NORM
            for c, cell in enumerate(row):
                rx = MARGIN_L + c * col_w
                self.page.draw_rect(
                    fitz.Rect(rx, self.y, rx + col_w, self.y + row_h),
                    color=None, fill=fill
                )
                txt = cell.strip().strip("`*")
                self.page.insert_text(
                    fitz.Point(rx + 4, self.y + 11),
                    txt[:int(col_w / 5.5)],
                    fontname=FONT_REGULAR, fontsize=8, color=LIGHT_GREY
                )
            self.y += row_h
        self.y += 6

    def _hr(self):
        self._check_space(12)
        self.y += 4
        self.page.draw_line(
            fitz.Point(MARGIN_L, self.y),
            fitz.Point(PAGE_W - MARGIN_R, self.y),
            color=ACCENT_PURPLE, width=0.5
        )
        self.y += 8

    def cover_page(self):
        cx = PAGE_W / 2
        for r, alpha in [(200, 0.04), (150, 0.06), (90, 0.09), (50, 0.14)]:
            col = (ACCENT_BLUE[0] * alpha * 10,
                   ACCENT_CYAN[0] * alpha * 8,
                   ACCENT_PURPLE[0] * alpha * 12)
            self.page.draw_circle(fitz.Point(cx, 300), r,
                                  color=None, fill=col)
        self.page.insert_text(
            fitz.Point(cx - 145, 240),
            "KAI CHATBOT", fontname=FONT_BOLD, fontsize=36, color=WHITE
        )
        self.page.insert_text(
            fitz.Point(cx - 120, 272),
            "PROJECT DOCUMENTATION",
            fontname=FONT_REGULAR, fontsize=14, color=ACCENT_CYAN
        )
        for i, col in enumerate([ACCENT_BLUE, ACCENT_CYAN, ACCENT_PURPLE]):
            self.page.draw_rect(
                fitz.Rect(cx - 120 + i * 80, 285, cx - 40 + i * 80, 287),
                color=None, fill=col
            )
        desc = (
            "Production-grade AI Chatbot Platform\n"
            "FastAPI  LangGraph  Gemini Pro  PostgreSQL  ChromaDB  Next.js"
        )
        for i, line in enumerate(desc.split("\n")):
            self.page.insert_text(
                fitz.Point(cx - 155, 310 + i * 18),
                line, fontname=FONT_REGULAR, fontsize=11, color=LIGHT_GREY
            )
        badges = [("FastAPI", ACCENT_BLUE), ("LangGraph", ACCENT_CYAN),
                  ("Gemini Pro", ACCENT_PURPLE), ("Next.js", ACCENT_BLUE)]
        bx = cx - 130
        for label, col in badges:
            bw = len(label) * 7 + 16
            self.page.draw_rect(
                fitz.Rect(bx, 360, bx + bw, 376),
                color=col, fill=CODE_BG, width=0.8
            )
            self.page.insert_text(
                fitz.Point(bx + 8, 372),
                label, fontname=FONT_BOLD, fontsize=8, color=col
            )
            bx += bw + 10
        self.page.insert_text(
            fitz.Point(cx - 60, PAGE_H - 60),
            "Kiran Artificial Intelligence",
            fontname=FONT_REGULAR, fontsize=9, color=MID_GREY
        )
        self._draw_footer()
        self._new_page()

    def render_markdown(self, md_text):
        lines = md_text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            if line.strip().startswith("```"):
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code_lines.append(lines[i])
                    i += 1
                self._code_block("\n".join(code_lines))
                i += 1
                continue

            if re.match(r"^-{3,}$", line.strip()):
                self._hr()
                i += 1
                continue

            m = re.match(r"^# (.+)", line)
            if m:
                self._h1(m.group(1))
                i += 1
                continue

            m = re.match(r"^## (.+)", line)
            if m:
                self._h2(m.group(1))
                i += 1
                continue

            m = re.match(r"^### (.+)", line)
            if m:
                self._h3(m.group(1))
                i += 1
                continue

            if "|" in line and line.strip().startswith("|"):
                table_lines = []
                while i < len(lines) and "|" in lines[i]:
                    table_lines.append(lines[i])
                    i += 1
                header = [c.strip() for c in table_lines[0].split("|")[1:-1]]
                rows = []
                for tl in table_lines[2:]:
                    cells = [c.strip() for c in tl.split("|")[1:-1]]
                    if cells:
                        rows.append(cells)
                if header:
                    self._table(header, rows)
                continue

            m = re.match(r"^(\s*)[-*]  (.+)", line)
            if not m:
                m = re.match(r"^(\s*)[-*]\s(.+)", line)
            if m:
                level = len(m.group(1)) // 2
                text = re.sub(r"\*\*(.+?)\*\*", r"\1", m.group(2))
                text = re.sub(r"\*(.+?)\*",   r"\1", text)
                text = re.sub(r"`(.+?)`",     r"\1", text)
                self._bullet(text, level)
                i += 1
                continue

            m = re.match(r"^\s*\d+\.\s+(.+)", line)
            if m:
                text = re.sub(r"\*\*(.+?)\*\*", r"\1", m.group(1))
                text = re.sub(r"`(.+?)`",     r"\1", text)
                self._bullet(text, 0)
                i += 1
                continue

            m = re.match(r"^>\s*(.+)", line)
            if m:
                text = re.sub(r"\*\*(.+?)\*\*", r"\1", m.group(1))
                self._check_space(20)
                self.page.draw_rect(
                    fitz.Rect(MARGIN_L, self.y - 2,
                               MARGIN_L + 3, self.y + 14),
                    color=None, fill=ACCENT_PURPLE
                )
                self._text_block(text, FONT_ITALIC, 9, LIGHT_GREY,
                                 indent=10, line_height=14)
                i += 1
                continue

            if line.strip() == "":
                self.y += 4
                i += 1
                continue

            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            text = re.sub(r"\*(.+?)\*",   r"\1", text)
            text = re.sub(r"`(.+?)`",     r"\1", text)
            text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
            if text.strip():
                self._paragraph(text)
            i += 1

    def save(self, path):
        self._draw_footer()
        self.doc.save(path, garbage=4, deflate=True)
        self.doc.close()
        print(f"PDF saved: {path}")


def main():
    if not os.path.exists(MARKDOWN_PATH):
        print(f"ERROR: Source markdown not found: {MARKDOWN_PATH}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Reading documentation...")
    with open(MARKDOWN_PATH, "r", encoding="utf-8") as f:
        md = f.read()

    print("Building PDF (PyMuPDF - no Chromium, no C: drive temp files)...")
    builder = PDFBuilder()
    builder.cover_page()
    builder.render_markdown(md)
    builder.save(OUTPUT_PDF)

    size_kb = os.path.getsize(OUTPUT_PDF) // 1024
    print(f"File size: {size_kb} KB")
    print(f"Location:  {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
