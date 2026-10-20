"""
Generate enhanced academic conference PowerPoint for MIC 2026
Paper: A Biased Random-Key Genetic Algorithm with Rolling Horizon for the MDRP
Enhancements: pseudocode slides + decision flowchart
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree

# ── Color palette ─────────────────────────────────────────────────────────────
DARK_BLUE  = RGBColor(0x1F, 0x38, 0x64)
MID_BLUE   = RGBColor(0x2E, 0x54, 0x96)
LIGHT_BLUE = RGBColor(0xBD, 0xD7, 0xEE)
LIGHT_GRAY = RGBColor(0xF2, 0xF2, 0xF2)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
BLACK      = RGBColor(0x00, 0x00, 0x00)
ACCENT_ORG = RGBColor(0xED, 0x7D, 0x31)
ACCENT_GRN = RGBColor(0x70, 0xAD, 0x47)
DARK_GRAY  = RGBColor(0x40, 0x40, 0x40)
CODE_BG    = RGBColor(0x1E, 0x1E, 0x2E)   # dark background for code blocks
CODE_KW    = RGBColor(0xFF, 0x79, 0xC6)   # keywords (pink)
CODE_CMT   = RGBColor(0x6A, 0x99, 0x55)   # comments (green)
CODE_VAR   = RGBColor(0x8B, 0xE9, 0xFD)   # variables (cyan)
CODE_NUM   = RGBColor(0xBD, 0x93, 0xF9)   # numbers/indices (purple)
CODE_TXT   = RGBColor(0xF8, 0xF8, 0xF2)   # normal text (off-white)
YELLOW_HL  = RGBColor(0xFF, 0xD7, 0x00)

W = Inches(13.33)
H = Inches(7.5)

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H
BLANK = prs.slide_layouts[6]

# ─────────────────────────── helpers ──────────────────────────────────────────

def add_rect(slide, l, t, w, h, fill_rgb=None, line_rgb=None, line_width=Pt(0)):
    shape = slide.shapes.add_shape(1, l, t, w, h)
    if fill_rgb:
        shape.fill.solid(); shape.fill.fore_color.rgb = fill_rgb
    else:
        shape.fill.background()
    if line_rgb:
        shape.line.color.rgb = line_rgb; shape.line.width = line_width
    else:
        shape.line.fill.background()
    return shape

def add_text(slide, text, l, t, w, h,
             font="Calibri", size=Pt(14), bold=False, italic=False,
             color=BLACK, align=PP_ALIGN.LEFT, wrap=True):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame; tf.word_wrap = wrap
    p = tf.paragraphs[0]; p.alignment = align
    run = p.add_run(); run.text = text
    run.font.name = font; run.font.size = size
    run.font.bold = bold; run.font.italic = italic
    run.font.color.rgb = color
    return tb

def title_bar(slide, title, subtitle=None):
    bar_h = Inches(1.1)
    add_rect(slide, 0, 0, W, bar_h, fill_rgb=DARK_BLUE)
    add_rect(slide, 0, 0, Inches(0.12), bar_h, fill_rgb=ACCENT_ORG)
    add_text(slide, title, Inches(0.25), Inches(0.1), W-Inches(0.5), Inches(0.72),
             size=Pt(24), bold=True, color=WHITE)
    if subtitle:
        add_text(slide, subtitle, Inches(0.25), Inches(0.76), W-Inches(0.5), Inches(0.32),
                 size=Pt(12), color=LIGHT_BLUE)

def footer(slide, num):
    ft = H - Inches(0.36)
    add_rect(slide, 0, ft, W, Inches(0.36), fill_rgb=DARK_BLUE)
    add_text(slide, "Daniel Giraldo-Herrera & David Alvarez-Martinez  |  Universidad de los Andes  |  MIC 2026",
             Inches(0.25), ft, Inches(11), Inches(0.36), size=Pt(9), color=LIGHT_BLUE)
    add_text(slide, str(num), W-Inches(0.65), ft, Inches(0.55), Inches(0.36),
             size=Pt(10), bold=True, color=WHITE, align=PP_ALIGN.RIGHT)

def bg(slide):
    add_rect(slide, 0, Inches(1.1), W, H-Inches(1.46), fill_rgb=LIGHT_GRAY)

def bullets(slide, items, l, t, w, h, size=Pt(14), color=DARK_GRAY):
    tb = slide.shapes.add_textbox(l, t, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    first = True
    for lvl, txt in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_before = Pt(5 if lvl==0 else 2)
        p.text = ("•  " if lvl==0 else "    –  ") + txt
        for run in p.runs:
            run.font.name = "Calibri"
            run.font.size = size if lvl==0 else size-Pt(1.5)
            run.font.color.rgb = color

# ── Code block helper ──────────────────────────────────────────────────────────

def code_block(slide, lines, l, t, w, h, font_size=Pt(10.5)):
    """
    lines: list of (indent_level, text, style)
    style: 'normal' | 'keyword' | 'comment' | 'highlight'
    Renders a dark-background monospace code block.
    """
    add_rect(slide, l, t, w, h, fill_rgb=CODE_BG,
             line_rgb=ACCENT_ORG, line_width=Pt(1.0))

    tb = slide.shapes.add_textbox(l+Inches(0.12), t+Inches(0.1),
                                   w-Inches(0.24), h-Inches(0.2))
    tf = tb.text_frame; tf.word_wrap = False
    INDENT = "    "
    first = True
    for (indent, text, style) in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_before = Pt(0); p.space_after = Pt(0)
        run = p.add_run()
        run.text = INDENT*indent + text
        run.font.name = "Courier New"
        run.font.size = font_size
        if style == 'keyword':
            run.font.color.rgb = CODE_KW; run.font.bold = True
        elif style == 'comment':
            run.font.color.rgb = CODE_CMT; run.font.italic = True
        elif style == 'highlight':
            run.font.color.rgb = YELLOW_HL; run.font.bold = True
        elif style == 'var':
            run.font.color.rgb = CODE_VAR
        else:
            run.font.color.rgb = CODE_TXT

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 1 — Title
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
add_rect(slide, 0, 0, W, H, fill_rgb=DARK_BLUE)
add_rect(slide, 0, 0, Inches(0.18), H, fill_rgb=ACCENT_ORG)
add_rect(slide, Inches(0.35), Inches(1.4), W-Inches(0.55), Inches(4.5), fill_rgb=WHITE)
add_rect(slide, Inches(0.35), Inches(5.85), W-Inches(0.55), Inches(0.08), fill_rgb=ACCENT_ORG)

add_text(slide,
    "A Biased Random-Key Genetic Algorithm\nwith Rolling Horizon for the\nMeal Delivery Routing Problem",
    Inches(0.6), Inches(1.55), W-Inches(1.0), Inches(2.5),
    size=Pt(30), bold=True, color=DARK_BLUE)
add_text(slide, "Daniel Giraldo-Herrera  ·  David Alvarez-Martinez",
    Inches(0.6), Inches(4.2), W-Inches(1.0), Inches(0.45),
    size=Pt(17), color=DARK_GRAY)
add_text(slide, "Department of Industrial Engineering · Universidad de los Andes · Bogotá, Colombia",
    Inches(0.6), Inches(4.65), W-Inches(1.0), Inches(0.4),
    size=Pt(13), italic=True, color=DARK_GRAY)
add_text(slide, "MIC 2026  |  Metaheuristics International Conference",
    Inches(0.6), Inches(6.3), W-Inches(1.0), Inches(0.4),
    size=Pt(13), bold=True, color=LIGHT_BLUE)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 2 — Agenda
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Presentation Outline", ""); footer(slide, 2)

agenda_items = [
    ("1", "Introduction",          "MDRP in Latin America — operational context & logistics challenges",           MID_BLUE),
    ("2", "Literature Review",     "Prior work on MDRP, rolling-horizon methods, and metaheuristics",              ACCENT_ORG),
    ("3", "Problem Definition",    "Sets, parameters, and rolling-horizon decision structure",                     MID_BLUE),
    ("4", "Solution Methods",      "Business Model (BM/BML) and two BRKGA variants (Coverage & Travel)",          ACCENT_ORG),
    ("5", "BRKGA Deep Dive",       "Chromosome encoding, evolutionary cycle, biased crossover, decoder",           MID_BLUE),
    ("6", "Experimental Results",  "24 real-world instances — coverage rate, execution time, travel efficiency",   ACCENT_ORG),
    ("7", "Conclusions",           "Practical deployment guide and future research directions",                    DARK_BLUE),
]

item_h = Inches(0.72); item_w = W - Inches(0.7); ix = Inches(0.35); iy0 = Inches(1.22)
for i,(num,title,desc,col) in enumerate(agenda_items):
    iy = iy0 + i*(item_h + Inches(0.04))
    # number badge
    add_rect(slide, ix, iy, Inches(0.6), item_h, fill_rgb=col)
    add_text(slide, num, ix, iy, Inches(0.6), item_h,
             size=Pt(22), bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    # title block
    add_rect(slide, ix+Inches(0.6), iy, Inches(2.8), item_h, fill_rgb=col,
             line_rgb=WHITE, line_width=Pt(0.3))
    add_text(slide, title, ix+Inches(0.65), iy+Inches(0.12), Inches(2.7), item_h-Inches(0.24),
             size=Pt(13), bold=True, color=WHITE, align=PP_ALIGN.LEFT)
    # description block
    add_rect(slide, ix+Inches(3.4), iy, item_w-Inches(3.4), item_h, fill_rgb=WHITE,
             line_rgb=col, line_width=Pt(1.0))
    add_text(slide, desc, ix+Inches(3.55), iy+Inches(0.12),
             item_w-Inches(3.7), item_h-Inches(0.24),
             size=Pt(12), color=DARK_GRAY, wrap=True)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 3 — Introduction: MDRP in Latin America
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Introduction — Meal Delivery in Latin America",
                     "A rapidly growing sector with unique urban logistics challenges"); footer(slide, 3)

# ── Left column: context stats ───────────────────────────────────────────────
lw = Inches(4.3); lx = Inches(0.35); ly = Inches(1.22)

add_rect(slide, lx, ly, lw, Inches(0.42), fill_rgb=DARK_BLUE)
add_text(slide, "MARKET CONTEXT", lx+Inches(0.1), ly+Inches(0.05), lw-Inches(0.2), Inches(0.32),
         size=Pt(12), bold=True, color=WHITE)

stats = [
    (ACCENT_ORG, "$29B+",  "Projected Latin American\nonline food delivery market by 2026"),
    (MID_BLUE,   "4×",     "Growth in platform orders\npost-pandemic (2019–2024)"),
    (ACCENT_GRN, "60%+",   "Market share concentrated in\nUber Eats, Rappi & iFood"),
    (DARK_BLUE,  "15 min", "Average customer expected\ndelivery time in major LATAM cities"),
]
for i,(col,val,desc) in enumerate(stats):
    sx = lx + (i%2)*Inches(2.15); sy = ly + Inches(0.5) + (i//2)*Inches(1.45)
    add_rect(slide, sx, sy, Inches(2.05), Inches(1.32), fill_rgb=WHITE,
             line_rgb=col, line_width=Pt(2))
    add_rect(slide, sx, sy, Inches(2.05), Inches(0.5), fill_rgb=col)
    add_text(slide, val, sx, sy+Inches(0.03), Inches(2.05), Inches(0.44),
             size=Pt(22), bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, desc, sx+Inches(0.08), sy+Inches(0.54), Inches(1.9), Inches(0.72),
             size=Pt(10.5), color=DARK_GRAY, wrap=True, align=PP_ALIGN.CENTER)

# ── Center column: LATAM urban challenges ────────────────────────────────────
cx2 = lx + lw + Inches(0.25); cw2 = Inches(4.15)

add_rect(slide, cx2, ly, cw2, Inches(0.42), fill_rgb=RGBColor(0x8B,0,0))
add_text(slide, "URBAN LOGISTICS CHALLENGES", cx2+Inches(0.1), ly+Inches(0.05),
         cw2-Inches(0.2), Inches(0.32), size=Pt(12), bold=True, color=WHITE)

challenges_la = [
    (RGBColor(0x8B,0,0),  "Traffic Congestion",
     "Bogotá, Mexico City, São Paulo rank among world's worst congestion cities — unpredictable travel times"),
    (RGBColor(0x8B,0,0),  "Informal Urban Layout",
     "Many neighborhoods lack standardized addressing; routing algorithms fail without real GPS traces"),
    (RGBColor(0x8B,0,0),  "Heterogeneous Fleet",
     "Motorcycles, bicycles, walkers operate in the same city — different speeds, costs, and range constraints"),
    (RGBColor(0x8B,0,0),  "Demand Volatility",
     "Lunch & dinner peaks create 5–10× demand surges; weekday vs. weekend patterns differ widely"),
    (RGBColor(0x8B,0,0),  "Courier Informality",
     "Gig-economy workers have irregular shift patterns; real-time availability is highly stochastic"),
]
for i,(col,title,desc) in enumerate(challenges_la):
    cy2i = ly + Inches(0.5) + i*Inches(0.95)
    add_rect(slide, cx2, cy2i, Inches(0.08), Inches(0.85), fill_rgb=col)
    add_rect(slide, cx2+Inches(0.08), cy2i, cw2-Inches(0.08), Inches(0.85),
             fill_rgb=LIGHT_GRAY if i%2==0 else WHITE,
             line_rgb=col, line_width=Pt(0.5))
    add_text(slide, title, cx2+Inches(0.18), cy2i+Inches(0.05), cw2-Inches(0.28), Inches(0.3),
             size=Pt(11), bold=True, color=RGBColor(0x8B,0,0))
    add_text(slide, desc, cx2+Inches(0.18), cy2i+Inches(0.35), cw2-Inches(0.28), Inches(0.46),
             size=Pt(10), color=DARK_GRAY, wrap=True)

# ── Right column: why this is hard (NP-hard + real data) ─────────────────────
rx2 = cx2 + cw2 + Inches(0.25); rw2 = W - rx2 - Inches(0.2)

add_rect(slide, rx2, ly, rw2, Inches(0.42), fill_rgb=ACCENT_ORG)
add_text(slide, "WHY IT IS HARD", rx2+Inches(0.1), ly+Inches(0.05),
         rw2-Inches(0.2), Inches(0.32), size=Pt(12), bold=True, color=WHITE)

hard_pts = [
    ("NP-hard", "Even small instances require exponential search without heuristics"),
    ("Real-Time", "Dispatch decisions must complete in < 2 min per window"),
    ("Stochastic", "Orders arrive dynamically; future demand is unknown"),
    ("Multi-constraint", "Time windows + vehicle capacity + courier shifts + K≤3 orders/route"),
    ("Scale", "Up to 59,167 orders/day on real LATAM data used in this work"),
]
for i,(tag,txt) in enumerate(hard_pts):
    hy = ly + Inches(0.5) + i*Inches(0.95)
    add_rect(slide, rx2, hy, rw2, Inches(0.85), fill_rgb=WHITE,
             line_rgb=ACCENT_ORG, line_width=Pt(1.0))
    add_rect(slide, rx2, hy, rw2, Inches(0.35), fill_rgb=RGBColor(0xFF,0xEE,0xE0))
    add_text(slide, tag, rx2+Inches(0.08), hy+Inches(0.04), rw2-Inches(0.16), Inches(0.28),
             size=Pt(11), bold=True, color=ACCENT_ORG)
    add_text(slide, txt, rx2+Inches(0.08), hy+Inches(0.37), rw2-Inches(0.16), Inches(0.44),
             size=Pt(10), color=DARK_GRAY, wrap=True)

# Bottom research question box
add_rect(slide, Inches(0.35), Inches(6.55), W-Inches(0.5), Inches(0.52),
         fill_rgb=DARK_BLUE, line_rgb=YELLOW_HL, line_width=Pt(1.5))
add_text(slide,
    "Research Question:  Can a population-based metaheuristic (BRKGA) outperform greedy dispatching "
    "within a rolling-horizon framework on real large-scale LATAM meal-delivery data?",
    Inches(0.5), Inches(6.58), W-Inches(0.8), Inches(0.46),
    size=Pt(11.5), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 4 — Motivation
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Motivation", "On-demand food delivery: a growing operational challenge"); footer(slide, 4)

# Icon boxes for platforms
platforms = ["Uber Eats", "Rappi", "DoorDash", "Glovo", "Just Eat"]
cols = [ACCENT_ORG, MID_BLUE, ACCENT_GRN, RGBColor(0xE0,0x30,0x70), RGBColor(0x8B,0x00,0x8B)]
for i,(p,c) in enumerate(zip(platforms,cols)):
    px = Inches(0.4) + i*Inches(2.55)
    add_rect(slide, px, Inches(1.2), Inches(2.3), Inches(0.5), fill_rgb=c)
    add_text(slide, p, px, Inches(1.2), Inches(2.3), Inches(0.5),
             size=Pt(13), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# Challenge arrows with shapes
challenges = [
    ("Stochastic\nDemand", "Orders arrive unpredictably throughout the day"),
    ("Tight Time\nWindows", "Customers expect delivery within minutes"),
    ("Heterogeneous\nFleet", "Motorcycles, bikes, walkers — different speeds"),
    ("Real-Time\nDecisions", "Must assign & route in < 2 minutes per epoch"),
]
for i,(title,desc) in enumerate(challenges):
    bx = Inches(0.4) + i*Inches(3.2)
    by = Inches(1.95)
    add_rect(slide, bx, by, Inches(2.9), Inches(1.7), fill_rgb=WHITE,
             line_rgb=DARK_BLUE, line_width=Pt(1.5))
    add_rect(slide, bx, by, Inches(2.9), Inches(0.55), fill_rgb=DARK_BLUE)
    add_text(slide, title, bx, by+Inches(0.02), Inches(2.9), Inches(0.5),
             size=Pt(12), bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, desc, bx+Inches(0.1), by+Inches(0.6), Inches(2.7), Inches(1.0),
             size=Pt(12), color=DARK_GRAY, wrap=True)

# MDRP definition box
add_rect(slide, Inches(0.4), Inches(3.8), W-Inches(0.6), Inches(0.7),
         fill_rgb=DARK_BLUE, line_rgb=ACCENT_ORG, line_width=Pt(2))
add_text(slide,
    "MDRP: Assign couriers to order batches and compute delivery routes in real time — NP-hard, dynamic, stochastic",
    Inches(0.55), Inches(3.85), W-Inches(0.9), Inches(0.62),
    size=Pt(14), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

bullets(slide, [
    (0, "Rolling-horizon policy: decisions re-made every Δ = 2 minutes using newly observed information"),
    (0, "Performance metric: coverage rate ρ = |orders delivered| / |orders placed|"),
    (0, "Real data from a Colombian delivery app — 24 instances, up to 59,167 orders/day"),
], Inches(0.45), Inches(4.65), W-Inches(0.6), Inches(2.0), size=Pt(14))

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 3 — Literature Review
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Literature Review",
                     "MDRP, planning horizons, metaheuristics, and the research gap"); footer(slide, 5)

lit_cols = [
    ("The MDRP", MID_BLUE, [
        "Formally defined by Reyes et al. (2018) — stochastic orders, time-window constraints, rolling-horizon framework",
        "Ulmer et al. (2021) — Anticipative Customer Assignment (ACA) to avoid premature courier–order matching",
        "Extensions: multi-objective (Dusadeerungsikul 2023), ghost kitchens (Neria 2024), shared logistics (Bi 2023)",
    ]),
    ("Planning Horizons", ACCENT_ORG, [
        "Static: full info assumed; high quality but no real-time reactivity",
        "Rolling-Horizon (RH): re-solve each window → incorporates new arrivals (Reyes 2018; Auad 2023)",
        "Fully dynamic: event-driven replanning (Steever 2019) or probabilistic forecasts (Ulmer 2021)",
    ]),
    ("Metaheuristics", ACCENT_GRN, [
        "NSGA-II for green delivery (Liao 2020); GA with fairness constraints (Xie 2024)",
        "Hybrid GA + local search for VRPTW — elite preservation, diversity (Bañós 2013)",
        "RL (DDQN, deep RL) — promising but needs training data; limited interpretability",
        "GRASP on same LA dataset — direct methodological baseline (Giraldo-Herrera 2024)",
    ]),
    ("Research Gap", DARK_BLUE, [
        "RH inner solvers are almost exclusively greedy constructive heuristics",
        "Population-based search inside each rolling window has NOT been studied for MDRP",
        "Quality–speed trade-off rarely quantified across heterogeneous instance sizes",
        "→ We embed BRKGA inside RH and compare 2 fitness variants on 24 real instances",
    ]),
]

cw3 = Inches(3.1); ch3_base = Inches(4.95); cx0 = Inches(0.35); gap3 = Inches(0.18)
for i,(title,col,pts) in enumerate(lit_cols):
    bx = cx0 + i*(cw3+gap3)
    # header
    add_rect(slide, bx, Inches(1.18), cw3, Inches(0.5), fill_rgb=col)
    add_text(slide, title, bx+Inches(0.05), Inches(1.2), cw3-Inches(0.1), Inches(0.44),
             size=Pt(13), bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    # body
    add_rect(slide, bx, Inches(1.68), cw3, ch3_base, fill_rgb=WHITE,
             line_rgb=col, line_width=Pt(1.2))
    tb = slide.shapes.add_textbox(bx+Inches(0.1), Inches(1.74), cw3-Inches(0.2), ch3_base-Inches(0.12))
    tf = tb.text_frame; tf.word_wrap = True
    first3 = True
    for pt in pts:
        p3 = tf.paragraphs[0] if first3 else tf.add_paragraph()
        first3 = False
        p3.space_before = Pt(5)
        run3 = p3.add_run(); run3.text = "• " + pt
        run3.font.name = "Calibri"; run3.font.size = Pt(11.5)
        run3.font.color.rgb = DARK_GRAY

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 4 — Table 1: Positioning of the present work
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Positioning of the Present Work in the Literature",
                     "RH: rolling horizon  ·  Cov: coverage  ·  TT: travel time  ·  ✓: yes  ·  — : no"); footer(slide, 6)

# Table data
tbl_headers = ["Study", "Method", "RH", "Objective", "Dynamic", "Real data", "Instance size"]
tbl_rows = [
    ["Reyes et al. (2018)",              "Greedy",      "✓", "TT",       "✓", "✓", "Small–Med"],
    ["Ulmer et al. (2021)",              "DP / ACA",    "✓", "TT",       "✓", "✓", "Small–Med"],
    ["Steever et al. (2019)",            "Greedy",      "✓", "TT",       "✓", "✓", "Med"],
    ["Yildiz & Savelsbergh (2019)",      "Exact",       "—", "Cost",     "—", "✓", "Small–Med"],
    ["Liao et al. (2020)",               "NSGA-II",     "—", "Multi",    "—", "Synth.", "Small"],
    ["Bozanta et al. (2022)",            "RL (DDQN)",   "✓", "TT",       "✓", "✓", "Small"],
    ["Auad et al. (2023)",               "Greedy RH",   "✓", "Fairness", "✓", "✓", "Med"],
    ["Giraldo-Herrera & Álvarez (2024)", "GRASP",       "—", "Cov",      "—", "✓", "Small–Large"],
    ["Martínez-Sykora et al. (2024)",    "RH sched.",   "✓", "Fairness", "✓", "✓", "Small–Med"],
    ["This work",                        "BRKGA",       "✓", "Cov / TT", "✓", "✓", "Small–Large"],
]

# Column widths
col_ws_t = [Inches(3.1), Inches(1.35), Inches(0.58), Inches(1.1), Inches(1.05), Inches(1.05), Inches(1.4)]
rh_t = Inches(0.47); tx_t = Inches(0.35); ty_t = Inches(1.18)

# Header row
for ci, hdr in enumerate(tbl_headers):
    cx_t = tx_t + sum(col_ws_t[:ci])
    add_rect(slide, cx_t, ty_t, col_ws_t[ci], rh_t, fill_rgb=DARK_BLUE,
             line_rgb=WHITE, line_width=Pt(0.75))
    add_text(slide, hdr, cx_t+Inches(0.04), ty_t+Inches(0.05),
             col_ws_t[ci]-Inches(0.08), rh_t-Inches(0.1),
             size=Pt(11.5), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# Data rows
for ri, row in enumerate(tbl_rows):
    is_this = (ri == len(tbl_rows)-1)
    for ci, cell in enumerate(row):
        cx_t = tx_t + sum(col_ws_t[:ci]); cy_t = ty_t + (ri+1)*rh_t
        if is_this:
            bg_c = RGBColor(0xFF, 0xE6, 0xCC)  # highlight last row
        elif ri % 2 == 0:
            bg_c = LIGHT_BLUE
        else:
            bg_c = WHITE
        line_c = ACCENT_ORG if is_this else DARK_BLUE
        lw_t = Pt(1.2) if is_this else Pt(0.5)
        add_rect(slide, cx_t, cy_t, col_ws_t[ci], rh_t, fill_rgb=bg_c,
                 line_rgb=line_c, line_width=lw_t)
        # checkmark and "—" in green/red
        txt_col = DARK_GRAY
        if cell == "✓":
            txt_col = ACCENT_GRN
        elif cell == "—":
            txt_col = RGBColor(0xA0, 0xA0, 0xA0)
        if is_this:
            txt_col = RGBColor(0xC0, 0x50, 0x00)
        add_text(slide, cell, cx_t+Inches(0.04), cy_t+Inches(0.05),
                 col_ws_t[ci]-Inches(0.08), rh_t-Inches(0.1),
                 size=Pt(11) if ci == 0 else Pt(12),
                 bold=is_this,
                 color=txt_col,
                 align=PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER)

# Caption note
add_rect(slide, tx_t, ty_t+11*rh_t+Inches(0.06), W-Inches(0.5), Inches(0.38),
         fill_rgb=CODE_BG, line_rgb=YELLOW_HL, line_width=Pt(1))
add_text(slide,
    "BRKGA-RH is the first population-based metaheuristic integrated with rolling-horizon dispatch for the MDRP — "
    "covering both Coverage and Travel Time objectives on real Large-scale instances.",
    tx_t+Inches(0.1), ty_t+11*rh_t+Inches(0.09), W-Inches(0.7), Inches(0.32),
    size=Pt(10), bold=True, color=YELLOW_HL, align=PP_ALIGN.CENTER)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 5 — Problem Definition + Rolling Horizon
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Problem Definition", "Sets, parameters, and rolling-horizon decision structure"); footer(slide, 7)

# Left: sets & params table
sets = [("U","Customers","geo-located delivery points"),
        ("R","Restaurants","order pickup locations"),
        ("O","Orders","(restaurant, customer, time window) tuples"),
        ("C","Couriers","heterogeneous: speed, shift, location"),
        ("S","Routes","feasible pickup+delivery sequences")]
add_text(slide,"SETS & NOTATION", Inches(0.35), Inches(1.15), Inches(6.2), Inches(0.35),
         size=Pt(12), bold=True, color=DARK_BLUE)
for i,(sym,name,desc) in enumerate(sets):
    row_y = Inches(1.5) + i*Inches(0.52)
    bg_c = LIGHT_BLUE if i%2==0 else WHITE
    add_rect(slide, Inches(0.35), row_y, Inches(6.2), Inches(0.5), fill_rgb=bg_c,
             line_rgb=MID_BLUE, line_width=Pt(0.5))
    add_text(slide, sym, Inches(0.4), row_y+Inches(0.06), Inches(0.4), Inches(0.42),
             size=Pt(14), bold=True, color=DARK_BLUE, align=PP_ALIGN.CENTER)
    add_text(slide, f"{name} — {desc}", Inches(0.85), row_y+Inches(0.06), Inches(5.6), Inches(0.42),
             size=Pt(12), color=DARK_GRAY)

params = [("Δ","2 min","Rolling-horizon window"),
          ("K","≤ 3","Max orders per route"),
          ("D_max","10 km","Max courier-to-store distance"),
          ("ρ","Coverage rate","Primary objective: |Ō|/|O|")]
add_text(slide,"KEY PARAMETERS", Inches(0.35), Inches(4.25), Inches(6.2), Inches(0.35),
         size=Pt(12), bold=True, color=DARK_BLUE)
for i,(sym,val,desc) in enumerate(params):
    row_y = Inches(4.6) + i*Inches(0.48)
    bg_c = RGBColor(0xFF,0xE6,0xCC) if i%2==0 else WHITE
    add_rect(slide, Inches(0.35), row_y, Inches(6.2), Inches(0.46), fill_rgb=bg_c,
             line_rgb=ACCENT_ORG, line_width=Pt(0.5))
    add_text(slide, f"{sym} = {val}", Inches(0.4), row_y+Inches(0.04), Inches(1.8), Inches(0.4),
             size=Pt(13), bold=True, color=ACCENT_ORG)
    add_text(slide, desc, Inches(2.25), row_y+Inches(0.04), Inches(4.2), Inches(0.4),
             size=Pt(12), color=DARK_GRAY)

# Right: rolling horizon visual
rx = Inches(6.8)
add_text(slide, "ROLLING HORIZON STRUCTURE", rx, Inches(1.15), Inches(6.35), Inches(0.35),
         size=Pt(12), bold=True, color=DARK_BLUE)

# Timeline
tl_y = Inches(1.58); tl_h = Inches(0.22)
add_rect(slide, rx, tl_y, Inches(6.2), tl_h, fill_rgb=MID_BLUE)
add_text(slide, "← Operational Day (1 440 min) →", rx, tl_y+Inches(0.22),
         Inches(6.2), Inches(0.28), size=Pt(10), italic=True, color=DARK_GRAY, align=PP_ALIGN.CENTER)

# Epoch blocks
epoch_labels = ["w=0\n(t=0)", "w=1\n(t=2)", "w=2\n(t=4)", "…", "w=720\n(t=1440)"]
epoch_colors = [ACCENT_ORG, MID_BLUE, MID_BLUE, LIGHT_GRAY, DARK_BLUE]
ew = Inches(1.1); eg = Inches(0.08)
for i,(lbl,ec) in enumerate(zip(epoch_labels,epoch_colors)):
    ex = rx + i*(ew+eg)
    add_rect(slide, ex, tl_y+Inches(0.55), ew, Inches(0.65), fill_rgb=ec)
    add_text(slide, lbl, ex, tl_y+Inches(0.55), ew, Inches(0.65),
             size=Pt(9.5), bold=(i!=3), color=WHITE if ec!=LIGHT_GRAY else DARK_GRAY,
             align=PP_ALIGN.CENTER)

# Step-by-step inside each epoch
steps = [
    ("①", ACCENT_ORG, "Observe O^w (pending orders) and C^w (idle couriers)"),
    ("②", MID_BLUE,   "(BML only) Forecast demand → defer marginal stores"),
    ("③", MID_BLUE,   "Generate candidate routes S^w for each courier"),
    ("④", DARK_BLUE,  "Solve assignment: select conflict-free subset A^w"),
    ("⑤", ACCENT_GRN, "Dispatch A^w → couriers depart; advance to w+1"),
]
sy = tl_y + Inches(1.35)
for num,(icon,col,text) in enumerate(steps):
    add_rect(slide, rx, sy+num*Inches(0.72), Inches(0.45), Inches(0.65), fill_rgb=col)
    add_text(slide, icon, rx, sy+num*Inches(0.72), Inches(0.45), Inches(0.65),
             size=Pt(14), bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_rect(slide, rx+Inches(0.45), sy+num*Inches(0.72), Inches(5.75), Inches(0.65),
             fill_rgb=WHITE, line_rgb=col, line_width=Pt(0.75))
    add_text(slide, text, rx+Inches(0.55), sy+num*Inches(0.72)+Inches(0.07),
             Inches(5.55), Inches(0.55), size=Pt(12), color=DARK_GRAY)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 4 — Four Methods Overview
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Four Dispatching Policies", "All share the same rolling-horizon architecture (Δ = 2 min)"); footer(slide, 8)

methods = [
    ("BM", "Business\nModel", MID_BLUE,
     ["Score-based candidate\ngeneration",
      "Greedy conflict-free\nselection",
      "No future information",
      "Fast & deterministic"]),
    ("BML", "Business Model\nLookahead", RGBColor(0x2E,0x75,0xB6),
     ["Phase 0: demand-forecast\ndeferral filter",
      "Phases 1+2 same as BM",
      "Defers orders likely to\nbatch with future arrivals",
      "Best for large instances"]),
    ("BRKGA-C", "BRKGA\nCoverage", ACCENT_ORG,
     ["Genetic algorithm with\nrandom-key encoding",
      "Tiered fitness: maximize\ncoverage ≥ 60% first",
      "10 pop × 10 generations\nper window",
      "Best for small/medium"]),
    ("BRKGA-T", "BRKGA\nTravel", ACCENT_GRN,
     ["Same framework as\nBRKGA-Coverage",
      "Softer penalties allow\ntravel-time tradeoffs",
      "~25% faster execution",
      "Preferred in practice"]),
]
bw = Inches(2.9); bh = Inches(5.2); gap = Inches(0.35)
x0 = Inches(0.45)
for i,(abbr,name,col,blist) in enumerate(methods):
    bx = x0 + i*(bw+gap); by = Inches(1.2)
    add_rect(slide, bx, by, bw, bh, fill_rgb=WHITE, line_rgb=col, line_width=Pt(2))
    add_rect(slide, bx, by, bw, Inches(1.1), fill_rgb=col)
    add_text(slide, abbr, bx, by+Inches(0.04), bw, Inches(0.55),
             size=Pt(22), bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, name, bx, by+Inches(0.58), bw, Inches(0.5),
             size=Pt(11), color=WHITE, align=PP_ALIGN.CENTER)
    for j,b in enumerate(blist):
        add_rect(slide, bx+Inches(0.12), by+Inches(1.18)+j*Inches(0.95),
                 bw-Inches(0.24), Inches(0.88), fill_rgb=LIGHT_GRAY)
        add_text(slide, b, bx+Inches(0.2), by+Inches(1.22)+j*Inches(0.95),
                 bw-Inches(0.4), Inches(0.84), size=Pt(12), color=DARK_GRAY, wrap=True)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 5 — Algorithm 1: Business Model Lookahead (pseudocode)
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Algorithm 1 — Business Model Lookahead",
                     "Three-phase dispatch: forecast filter → candidate generation → conflict-free selection"); footer(slide, 9)

# Phase annotation boxes on left
phases_info = [
    (Inches(1.2),  Inches(0.65), MID_BLUE,   "Phase 0\n(BML only)\nLookahead\nFilter"),
    (Inches(2.55), Inches(1.15), DARK_BLUE,  "Phase 1\nCandidate\nGeneration"),
    (Inches(1.1),  Inches(0.5),  ACCENT_ORG, "Phase 2\nConflict-Free\nSelection"),
]
px_ann = Inches(0.25); py_starts = [Inches(1.55), Inches(3.15), Inches(5.6)]
for (pw,ph,col,txt),(py_s) in zip(phases_info, py_starts):
    add_rect(slide, px_ann, py_s, pw, ph, fill_rgb=col)
    add_text(slide, txt, px_ann+Inches(0.03), py_s+Inches(0.04), pw-Inches(0.06), ph-Inches(0.08),
             size=Pt(9), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# Code block
code_lines = [
    (0, "Algorithm 1: Business Model Lookahead — window w",      'highlight'),
    (0, "Require: O^w, C^w, current time t_w, order history",    'comment'),
    (0, "Ensure:  Conflict-free assignment set A^w",              'comment'),
    (0, "",                                                        'normal'),
    (0, "1:  Compute f_hat(r, t_w) for all stores r              ▷ demand forecast", 'normal'),
    (0, "2:  Λ^w ← ∅",                                            'var'),
    (0, "",                                                        'normal'),
    (0, "3:  for all store r with O^w_r ≠ ∅ do",                 'keyword'),
    (1, "4:    if |O^w_r| ≤ 2  AND  f_hat ≥ 3  AND  min_deadline > 25 min then", 'keyword'),
    (2, "5:        continue                                        ▷ Phase 0 defer", 'comment'),
    (1, "6:    end if",                                            'keyword'),
    (1, "7:    Sort O^w_r by deadline; partition → batches s_1…s_Bmax  ▷ Phase 1", 'normal'),
    (1, "8:    for all batch s_j, courier c in top-N_max nearby couriers do", 'keyword'),
    (2, "9:        τ_cs ← best feasible route via 3-heuristic ensemble", 'var'),
    (2, "10:       if route feasible then",                        'keyword'),
    (3, "11:           Λ^w ← Λ^w ∪ { (c, s_j, score(c, s_j)) }", 'var'),
    (2, "12:       end if",                                        'keyword'),
    (1, "13:   end for",                                           'keyword'),
    (0, "14: end for",                                             'keyword'),
    (0, "",                                                        'normal'),
    (0, "15: Sort Λ^w by score (descending)                       ▷ Phase 2", 'highlight'),
    (0, "16: A^w ← ∅;  U_C ← ∅;  U_O ← ∅",                      'var'),
    (0, "17: for all (c, s, ·) ∈ Λ^w do",                        'keyword'),
    (1, "18:   if c ∉ U_C  AND  s ∩ U_O = ∅ then",               'keyword'),
    (2, "19:       A^w ← A^w ∪ {(c,s)};  U_C ← U_C∪{c};  U_O ← U_O∪s", 'var'),
    (1, "20:   end if",                                            'keyword'),
    (0, "21: end for",                                             'keyword'),
    (0, "22: return A^w",                                          'highlight'),
]
code_block(slide, code_lines, Inches(1.65), Inches(1.18), Inches(11.45), Inches(5.85),
           font_size=Pt(10))

# score formula callout
add_rect(slide, Inches(1.65), Inches(6.65), Inches(11.45), Inches(0.42),
         fill_rgb=RGBColor(0x2A,0x2A,0x3E), line_rgb=ACCENT_ORG, line_width=Pt(0.75))
add_text(slide,
    "score(c,s) = k × 10,000 + u(s) × 10 − τ_cs      where  u(s) = max(0, 100 − min_deadline_remaining)",
    Inches(1.75), Inches(6.67), Inches(11.2), Inches(0.38),
    font="Courier New", size=Pt(10.5), color=YELLOW_HL, align=PP_ALIGN.CENTER)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 6 — BRKGA Chromosome Encoding (visual)
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "BRKGA — Chromosome Encoding & Decoder",
                     "Random-key vectors → feasible courier-order assignments without repair operators"); footer(slide, 10)

# Chromosome visual
add_text(slide, "CHROMOSOME  x  (length = |O^w| + |C^w|)",
         Inches(0.4), Inches(1.18), Inches(12.7), Inches(0.35),
         size=Pt(13), bold=True, color=DARK_BLUE)

# Order keys segment
ok_colors = [ACCENT_ORG, ACCENT_ORG, ACCENT_ORG, ACCENT_ORG, ACCENT_ORG]
ok_vals   = ["0.91", "0.34", "0.77", "0.55", "0.12"]
ok_labels = ["o₁", "o₂", "o₃", "o₄", "o₅"]
ck_colors = [ACCENT_GRN, ACCENT_GRN, ACCENT_GRN]
ck_vals   = ["0.82", "0.47", "0.63"]
ck_labels = ["c₁", "c₂", "c₃"]

cell_w = Inches(1.1); cell_h = Inches(0.7)
start_ok = Inches(0.4)

# bracket label
add_rect(slide, start_ok, Inches(1.6), Inches(5.5)+Inches(0.2), Inches(0.08), fill_rgb=ACCENT_ORG)
add_text(slide, "Order Keys", start_ok, Inches(1.55), Inches(5.5), Inches(0.25),
         size=Pt(11), bold=True, color=ACCENT_ORG)

for i,(col,val,lbl) in enumerate(zip(ok_colors,ok_vals,ok_labels)):
    cx = start_ok + i*(cell_w+Inches(0.04))
    add_rect(slide, cx, Inches(1.88), cell_w, cell_h, fill_rgb=col)
    add_text(slide, lbl, cx, Inches(1.88), cell_w, Inches(0.3),
             size=Pt(11), bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, val, cx, Inches(2.18), cell_w, Inches(0.38),
             size=Pt(13), color=WHITE, align=PP_ALIGN.CENTER)

# separator
sep_x = start_ok + len(ok_vals)*(cell_w+Inches(0.04)) + Inches(0.05)
add_rect(slide, sep_x, Inches(1.78), Inches(0.06), cell_h+Inches(0.2), fill_rgb=DARK_GRAY)
add_text(slide, "|", sep_x-Inches(0.05), Inches(1.85), Inches(0.2), Inches(0.5),
         size=Pt(20), bold=True, color=DARK_GRAY, align=PP_ALIGN.CENTER)

start_ck = sep_x + Inches(0.12)
add_rect(slide, start_ck, Inches(1.6), Inches(3.3)+Inches(0.2), Inches(0.08), fill_rgb=ACCENT_GRN)
add_text(slide, "Courier Keys", start_ck, Inches(1.55), Inches(3.5), Inches(0.25),
         size=Pt(11), bold=True, color=ACCENT_GRN)

for i,(col,val,lbl) in enumerate(zip(ck_colors,ck_vals,ck_labels)):
    cx = start_ck + i*(cell_w+Inches(0.04))
    add_rect(slide, cx, Inches(1.88), cell_w, cell_h, fill_rgb=col)
    add_text(slide, lbl, cx, Inches(1.88), cell_w, Inches(0.3),
             size=Pt(11), bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, val, cx, Inches(2.18), cell_w, Inches(0.38),
             size=Pt(13), color=WHITE, align=PP_ALIGN.CENTER)

# Sorted priorities
add_text(slide, "↓  Sort descending by key value",
         Inches(0.4), Inches(2.68), Inches(12.7), Inches(0.3),
         size=Pt(12), italic=True, color=DARK_GRAY)

add_rect(slide, Inches(0.4), Inches(3.0), Inches(5.5), Inches(0.5), fill_rgb=DARK_BLUE)
add_text(slide, "Order priority:  o₁ (0.91)  ≻  o₃ (0.77)  ≻  o₄ (0.55)  ≻  o₂ (0.34)  ≻  o₅ (0.12)",
         Inches(0.55), Inches(3.02), Inches(5.2), Inches(0.46),
         size=Pt(11), color=WHITE, font="Courier New")

add_rect(slide, Inches(6.1), Inches(3.0), Inches(3.5), Inches(0.5), fill_rgb=ACCENT_GRN)
add_text(slide, "Courier preference:  c₁ (0.82)  ≻  c₃ (0.63)  ≻  c₂ (0.47)",
         Inches(6.2), Inches(3.02), Inches(3.3), Inches(0.46),
         size=Pt(11), color=WHITE, font="Courier New")

# Parameters table (right side, bottom)
params_brkga = [
    ("Nₚ = 10","Population size"),
    ("Gₘₐₓ = 10","Generations / window"),
    ("Nₑ = 2","Elite individuals"),
    ("Nₘ = 2","Mutant individuals"),
    ("pₑ = 0.7","Elite crossover bias"),
    ("K = 3","Couriers eval / batch"),
]
add_text(slide, "HYPER-PARAMETERS", Inches(9.8), Inches(1.18), Inches(3.3), Inches(0.35),
         size=Pt(12), bold=True, color=DARK_BLUE)
for i,(sym,desc) in enumerate(params_brkga):
    ry = Inches(1.56) + i*Inches(0.48)
    bg_c = LIGHT_BLUE if i%2==0 else WHITE
    add_rect(slide, Inches(9.8), ry, Inches(3.3), Inches(0.46), fill_rgb=bg_c,
             line_rgb=DARK_BLUE, line_width=Pt(0.5))
    add_text(slide, sym, Inches(9.85), ry+Inches(0.05), Inches(1.1), Inches(0.38),
             size=Pt(12), bold=True, color=DARK_BLUE, font="Courier New")
    add_text(slide, desc, Inches(11.0), ry+Inches(0.05), Inches(2.0), Inches(0.38),
             size=Pt(11), color=DARK_GRAY)

# Genetic operators visual
add_text(slide, "GENETIC OPERATORS", Inches(0.4), Inches(3.65), Inches(9.2), Inches(0.35),
         size=Pt(12), bold=True, color=DARK_BLUE)
ops = [
    (DARK_BLUE,  "ELITE  (Nₑ=2)", "Top-2 solutions copied unchanged"),
    (ACCENT_ORG, "CROSSOVER  (Nₒ=6)", "Each gene: x_elite w.p. 0.7, x_non-elite w.p. 0.3"),
    (ACCENT_GRN, "MUTANTS  (Nₘ=2)", "Drawn from U[0,1] — maintains diversity"),
]
for i,(col,title,desc) in enumerate(ops):
    ox = Inches(0.4) + i*Inches(3.1)
    add_rect(slide, ox, Inches(4.05), Inches(2.9), Inches(0.42), fill_rgb=col)
    add_text(slide, title, ox, Inches(4.05), Inches(2.9), Inches(0.42),
             size=Pt(11), bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_rect(slide, ox, Inches(4.47), Inches(2.9), Inches(0.6), fill_rgb=WHITE,
             line_rgb=col, line_width=Pt(1))
    add_text(slide, desc, ox+Inches(0.08), Inches(4.5), Inches(2.76), Inches(0.55),
             size=Pt(11), color=DARK_GRAY, wrap=True)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 7 — BRKGA Evolutionary Cycle (visual)
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "BRKGA — Evolutionary Cycle per Window",
                     "Inside each Δ=2 min epoch: Nₚ=10 chromosomes evolved for Gₘₐₓ=10 generations"); footer(slide, 11)

ELITE_COL   = RGBColor(0xFF, 0xC0, 0x00)
MUTANT_COL  = RGBColor(0xA0, 0xA0, 0xA0)

def con(slide, x1, y1, x2, y2, col=DARK_GRAY, w=Pt(1.5)):
    ln = slide.shapes.add_connector(1, x1, y1, x2, y2)
    ln.line.color.rgb = col; ln.line.width = w

def flow_box(slide, label, sublabel, l, t, w, h, fill, text_color=WHITE, sub_color=None):
    add_rect(slide, l, t, w, h, fill_rgb=fill, line_rgb=DARK_GRAY, line_width=Pt(1.2))
    lh = Inches(0.42) if sublabel else h
    add_text(slide, label, l+Inches(0.04), t+Inches(0.04), w-Inches(0.08), lh-Inches(0.08),
             size=Pt(11), bold=True, color=text_color, align=PP_ALIGN.CENTER, wrap=True)
    if sublabel:
        add_text(slide, sublabel, l+Inches(0.04), t+lh, w-Inches(0.08), h-lh-Inches(0.04),
                 size=Pt(9.5), color=sub_color or text_color, align=PP_ALIGN.CENTER, wrap=True)

# ── banner ──
add_rect(slide, Inches(0.35), Inches(1.2), W-Inches(0.5), Inches(0.38), fill_rgb=DARK_BLUE)
add_text(slide,
    "Each window w:  observe O^w and C^w  →  run BRKGA  →  dispatch best assignment A*",
    Inches(0.5), Inches(1.22), W-Inches(0.8), Inches(0.34),
    size=Pt(12), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# ── Row 1: pipeline (top) ─────────────────────────────────────────────────────
r1y = Inches(1.75); bh = Inches(0.9); bw_p = Inches(1.95); gap_p = Inches(0.28)
pipeline = [
    ("INITIALIZE", "Nₚ=10 random\nchromosomes", MID_BLUE),
    ("DECODE ALL", "Run Alg.2\nfor each x", ACCENT_ORG),
    ("EVALUATE", "Compute f_cov\nor f_trav", ACCENT_ORG),
    ("RANK", "Sort by\nfitness ↑", ACCENT_ORG),
    ("DONE?\ng = Gₘₐₓ?", "", DARK_BLUE),
]
box_xs = []
for i,(lbl,sub,col) in enumerate(pipeline):
    bx = Inches(0.35) + i*(bw_p+gap_p)
    box_xs.append(bx)
    flow_box(slide, lbl, sub, bx, r1y, bw_p, bh, fill=col)
    if i < len(pipeline)-1:
        ax = bx + bw_p
        ay = r1y + bh/2
        con(slide, ax, ay, ax+gap_p, ay, col=MID_BLUE, w=Pt(2))

# ── YES path (right of DONE? box) → DISPATCH ──
done_bx = box_xs[-1]
done_cx = done_bx + bw_p
done_cy = r1y + bh/2
dispatch_x = done_cx + Inches(0.32)
dispatch_y = r1y
flow_box(slide, "DISPATCH\nBEST  A*", "Couriers depart\noptimal routes",
         dispatch_x, dispatch_y, Inches(1.82), bh, fill=ACCENT_GRN)
con(slide, done_cx, done_cy, dispatch_x, done_cy, col=ACCENT_GRN, w=Pt(2))
add_text(slide, "YES  g=10", done_cx+Inches(0.04), done_cy-Inches(0.32),
         Inches(1.2), Inches(0.28), size=Pt(10), bold=True, color=ACCENT_GRN)

# ── NO path (down from DONE?) → Row 2 ────────────────────────────────────────
r2y = Inches(3.15); bw_op = Inches(2.1); gap_op = Inches(0.32)
ops = [
    ("SELECT ELITE",  "Nₑ=2 best\nchromosomes",   ELITE_COL,  BLACK),
    ("CROSSOVER",     "Nₒ=6 offspring\npₑ=0.7 bias", ACCENT_ORG, WHITE),
    ("MUTANTS",       "Nₘ=2 random\nfrom U[0,1]", MUTANT_COL, WHITE),
]
no_down_x = done_bx + bw_p/2
con(slide, no_down_x, r1y+bh, no_down_x, r2y, col=DARK_GRAY, w=Pt(2))
add_text(slide, "NO  g<10", no_down_x+Inches(0.06), r1y+bh+Inches(0.05),
         Inches(1.1), Inches(0.28), size=Pt(10), bold=True, color=DARK_GRAY)

op_xs = []
for i,(lbl,sub,col,tc) in enumerate(ops):
    ox = Inches(1.9) + i*(bw_op+gap_op)
    op_xs.append(ox)
    flow_box(slide, lbl, sub, ox, r2y, bw_op, bh, fill=col, text_color=tc)
    if i < len(ops)-1:
        con(slide, ox+bw_op, r2y+bh/2, ox+bw_op+gap_op, r2y+bh/2, col=DARK_GRAY, w=Pt(2))

# MERGE banner
merge_x = Inches(1.9); merge_y = r2y + bh + Inches(0.22)
merge_w = bw_op*3 + gap_op*2
add_rect(slide, merge_x, merge_y, merge_w, Inches(0.48), fill_rgb=DARK_BLUE,
         line_rgb=ACCENT_ORG, line_width=Pt(1.5))
add_text(slide, "MERGE  →  New Population  (elite ∪ offspring ∪ mutants)  →  repeat DECODE",
         merge_x+Inches(0.1), merge_y+Inches(0.05), merge_w-Inches(0.2), Inches(0.38),
         size=Pt(11), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# Connect ops to merge
for ox in op_xs:
    con(slide, ox+bw_op/2, r2y+bh, ox+bw_op/2, merge_y, col=DARK_GRAY, w=Pt(1.2))

# Arrow from MERGE back up-left to DECODE ALL
merge_left = merge_x
merge_mid_y = merge_y + Inches(0.24)
decode_bx = box_xs[1]; decode_top = r1y
con(slide, merge_left, merge_mid_y, Inches(0.6), merge_mid_y, col=ACCENT_ORG, w=Pt(2))
con(slide, Inches(0.6), merge_mid_y, Inches(0.6), decode_top+bh/2, col=ACCENT_ORG, w=Pt(2))
con(slide, Inches(0.6), decode_top+bh/2, decode_bx, decode_top+bh/2, col=ACCENT_ORG, w=Pt(2))
add_text(slide, "← next\ngeneration", Inches(0.0), r2y+Inches(0.05), Inches(0.75), Inches(0.6),
         size=Pt(9), italic=True, color=ACCENT_ORG, align=PP_ALIGN.CENTER)

# key note
add_rect(slide, Inches(0.35), Inches(6.1), W-Inches(0.5), Inches(0.42),
         fill_rgb=CODE_BG, line_rgb=YELLOW_HL, line_width=Pt(1))
add_text(slide,
    "KEY: The entire loop (10 chromosomes × 10 generations = 100 decoder calls) must finish within Δ=2 min budget",
    Inches(0.5), Inches(6.13), W-Inches(0.8), Inches(0.36),
    size=Pt(11), bold=True, color=YELLOW_HL, align=PP_ALIGN.CENTER)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 8 — BRKGA Biased Crossover (visual)
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "BRKGA — Biased Crossover Explained",
                     "How offspring inherit mostly from elite parents — gene by gene"); footer(slide, 12)

# ── Left panel: Population structure ─────────────────────────────────────────
add_text(slide, "POPULATION STRUCTURE  (Nₚ=10)",
         Inches(0.35), Inches(1.18), Inches(4.2), Inches(0.35),
         size=Pt(12), bold=True, color=DARK_BLUE)

pop_rows = [
    ("#1", "Elite",     ELITE_COL,  BLACK),
    ("#2", "Elite",     ELITE_COL,  BLACK),
    ("#3", "Offspring", ACCENT_ORG, WHITE),
    ("#4", "Offspring", ACCENT_ORG, WHITE),
    ("#5", "Offspring", ACCENT_ORG, WHITE),
    ("#6", "Offspring", ACCENT_ORG, WHITE),
    ("#7", "Offspring", ACCENT_ORG, WHITE),
    ("#8", "Offspring", ACCENT_ORG, WHITE),
    ("#9", "Mutant",    MUTANT_COL, WHITE),
    ("#10","Mutant",    MUTANT_COL, WHITE),
]
pr_h = Inches(0.48); pr_w1 = Inches(0.55); pr_w2 = Inches(1.6)
for i,(num,role,col,tc) in enumerate(pop_rows):
    ry = Inches(1.58) + i*pr_h
    add_rect(slide, Inches(0.35), ry, pr_w1, pr_h, fill_rgb=col,
             line_rgb=WHITE, line_width=Pt(0.5))
    add_text(slide, num, Inches(0.35), ry+Inches(0.05), pr_w1, pr_h-Inches(0.1),
             size=Pt(11), bold=True, color=tc, align=PP_ALIGN.CENTER)
    add_rect(slide, Inches(0.35)+pr_w1, ry, pr_w2, pr_h,
             fill_rgb=RGBColor(0xFF,0xF8,0xDC) if col==ELITE_COL else
                      RGBColor(0xFF,0xEE,0xE0) if col==ACCENT_ORG else LIGHT_GRAY,
             line_rgb=col, line_width=Pt(0.5))
    add_text(slide, role, Inches(0.35)+pr_w1+Inches(0.05), ry+Inches(0.05),
             pr_w2-Inches(0.1), pr_h-Inches(0.1), size=Pt(11), color=DARK_GRAY)

# legend chips
legend_items = [("Elite (Nₑ=2)", ELITE_COL, BLACK),
                ("Offspring (Nₒ=6)", ACCENT_ORG, WHITE),
                ("Mutants (Nₘ=2)", MUTANT_COL, WHITE)]
for i,(lbl,col,tc) in enumerate(legend_items):
    lx = Inches(0.35) + i*Inches(1.45)
    ly = Inches(6.55)
    add_rect(slide, lx, ly, Inches(1.35), Inches(0.3), fill_rgb=col,
             line_rgb=DARK_GRAY, line_width=Pt(0.5))
    add_text(slide, lbl, lx+Inches(0.04), ly+Inches(0.03), Inches(1.28), Inches(0.24),
             size=Pt(9), bold=True, color=tc, align=PP_ALIGN.CENTER)

# ── Right panel: Gene-by-gene crossover ──────────────────────────────────────
rx = Inches(4.55)
add_text(slide, "GENE-BY-GENE CROSSOVER  (pₑ=0.7 bias toward elite)",
         rx, Inches(1.18), W-rx-Inches(0.2), Inches(0.35),
         size=Pt(12), bold=True, color=DARK_BLUE)

# 7 genes shown
genes = ["o₁\n.91", "o₂\n.34", "o₃\n.77", "o₄\n.55", "o₅\n.12", "c₁\n.82", "c₂\n.47"]
probs = [0.7,      0.3,       0.7,       0.7,       0.3,        0.7,       0.3]
elites = [True,    False,     True,      True,      False,      True,      False]

ncols = len(genes); gw2 = Inches(1.1); gg2 = Inches(0.12)
total_w = ncols*gw2 + (ncols-1)*gg2
start_x = rx + (W - rx - Inches(0.2) - total_w) / 2

row_labels = ["Elite\nParent", "Non-Elite\nParent", "Prob.", "↓", "Offspring", "Source"]
row_ys     = [Inches(1.62), Inches(2.35), Inches(3.08), Inches(3.62), Inches(3.98), Inches(4.62)]
row_hs     = [Inches(0.65), Inches(0.65), Inches(0.45), Inches(0.28), Inches(0.56), Inches(0.3)]

# row labels on left
lbl_x = rx
for lbl, ry2, rh2 in zip(row_labels, row_ys, row_hs):
    add_rect(slide, lbl_x, ry2, Inches(0.9), rh2,
             fill_rgb=DARK_BLUE if lbl not in ("↓","Source") else
                      RGBColor(0xEE,0xEE,0xEE),
             line_rgb=DARK_GRAY, line_width=Pt(0.5))
    add_text(slide, lbl, lbl_x+Inches(0.02), ry2+Inches(0.02), Inches(0.86), rh2-Inches(0.04),
             size=Pt(9), bold=True,
             color=WHITE if lbl not in ("↓","Source") else DARK_GRAY,
             align=PP_ALIGN.CENTER, wrap=True)

# gene columns
for gi, (val_e, prob, from_elite) in enumerate(
        zip(genes, probs, elites)):
    gx = start_x + gi*(gw2+gg2)

    # Elite parent cell (gold)
    parts = val_e.split("\n")
    add_rect(slide, gx, row_ys[0], gw2, row_hs[0], fill_rgb=ELITE_COL,
             line_rgb=WHITE, line_width=Pt(0.5))
    add_text(slide, parts[0], gx, row_ys[0]+Inches(0.03), gw2, Inches(0.28),
             size=Pt(10), bold=True, color=BLACK, align=PP_ALIGN.CENTER)
    add_text(slide, parts[1], gx, row_ys[0]+Inches(0.31), gw2, Inches(0.3),
             size=Pt(12), bold=True, color=DARK_BLUE, align=PP_ALIGN.CENTER)

    # Non-elite parent cell (blue)
    ne_val = ["0.23","0.88","0.41","0.19","0.73","0.35","0.91"][gi]
    add_rect(slide, gx, row_ys[1], gw2, row_hs[1], fill_rgb=MID_BLUE,
             line_rgb=WHITE, line_width=Pt(0.5))
    add_text(slide, parts[0], gx, row_ys[1]+Inches(0.03), gw2, Inches(0.28),
             size=Pt(10), bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(slide, ne_val, gx, row_ys[1]+Inches(0.31), gw2, Inches(0.3),
             size=Pt(12), bold=True, color=LIGHT_BLUE, align=PP_ALIGN.CENTER)

    # Probability cell
    prob_col = ACCENT_GRN if prob == 0.7 else ACCENT_ORG
    add_rect(slide, gx, row_ys[2], gw2, row_hs[2], fill_rgb=prob_col,
             line_rgb=WHITE, line_width=Pt(0.5))
    add_text(slide, f"{prob:.1f}", gx, row_ys[2]+Inches(0.05), gw2, row_hs[2]-Inches(0.1),
             size=Pt(11), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

    # Arrow
    add_text(slide, "↓", gx, row_ys[3], gw2, row_hs[3],
             size=Pt(14), bold=True,
             color=ELITE_COL if from_elite else MID_BLUE,
             align=PP_ALIGN.CENTER)

    # Offspring cell
    off_val = parts[1] if from_elite else ne_val
    off_col = ELITE_COL if from_elite else MID_BLUE
    off_tc  = BLACK if from_elite else WHITE
    add_rect(slide, gx, row_ys[4], gw2, row_hs[4], fill_rgb=off_col,
             line_rgb=WHITE, line_width=Pt(0.5))
    add_text(slide, off_val, gx, row_ys[4]+Inches(0.08), gw2, row_hs[4]-Inches(0.12),
             size=Pt(13), bold=True, color=off_tc, align=PP_ALIGN.CENTER)

    # Source label
    src_lbl = "elite" if from_elite else "non-e"
    src_col = ELITE_COL if from_elite else MID_BLUE
    add_rect(slide, gx, row_ys[5], gw2, row_hs[5], fill_rgb=src_col,
             line_rgb=WHITE, line_width=Pt(0.4))
    add_text(slide, src_lbl, gx, row_ys[5]+Inches(0.02), gw2, row_hs[5]-Inches(0.04),
             size=Pt(8.5), bold=True,
             color=BLACK if from_elite else WHITE,
             align=PP_ALIGN.CENTER)

# Prob legend
add_text(slide, "Green = 0.7 (elite gene wins)   Orange = 0.3 (non-elite gene wins)",
         rx, Inches(5.05), W-rx-Inches(0.2), Inches(0.28),
         size=Pt(10), italic=True, color=DARK_GRAY, align=PP_ALIGN.CENTER)

# KEY INSIGHT box
add_rect(slide, rx, Inches(5.4), W-rx-Inches(0.2), Inches(0.9),
         fill_rgb=CODE_BG, line_rgb=YELLOW_HL, line_width=Pt(1.5))
add_text(slide,
    "KEY INSIGHT:  Each gene independently drawn from Elite with p=0.7, Non-Elite with p=0.3.\n"
    "Result: offspring inherit ~70% elite genes → exploit good solutions while preserving diversity.",
    rx+Inches(0.12), Inches(5.44), W-rx-Inches(0.44), Inches(0.82),
    size=Pt(11), color=YELLOW_HL, wrap=True)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 9 — Algorithm 2: Chromosome Decoder (pseudocode)
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Algorithm 2 — Chromosome Decoder",
                     "Translates a random-key chromosome into a feasible assignment set A^w"); footer(slide, 13)

code_lines2 = [
    (0, "Algorithm 2: Chromosome Decoder for window w",           'highlight'),
    (0, "Require: chromosome x, O^w, C^w",                        'comment'),
    (0, "Ensure:  Assignment set A and fitness f",                 'comment'),
    (0, "",                                                        'normal'),
    (0, "1:  Extract order keys x[1..|O^w|] and courier keys x[|O^w|+1..|O^w|+|C^w|]", 'normal'),
    (0, "2:  Sort O^w by order key (desc)  → priority list π_O",  'var'),
    (0, "3:  Sort C^w by courier key (desc) → priority list π_C", 'var'),
    (0, "4:  Group π_O by store: { O^w_r }_{r∈R}",                'normal'),
    (0, "5:  A ← ∅;  assigned ← ∅",                               'var'),
    (0, "",                                                        'normal'),
    (0, "6:  for all store r (ordered by first pending order in π_O) do", 'keyword'),
    (1, "7:    avail ← C^w \\ assigned couriers, sorted by π_C",   'var'),
    (1, "8:    while O^w_r ≠ ∅  AND  avail ≠ ∅ do",               'keyword'),
    (2, "9:        best ← None",                                   'var'),
    (2, "10:       for all batch size k = 1 … K do",               'keyword'),
    (3, "11:           s ← first k unassigned orders of O^w_r",    'normal'),
    (3, "12:           for all c in top-K couriers of avail do",   'keyword'),
    (4, "13:               route ← nearest-neighbor(c, r, s)",     'var'),
    (4, "14:               if feasible AND finish_time < best do",  'keyword'),
    (5, "15:                   best ← (c, s, route)",              'highlight'),
    (3, "16:           end for",                                    'keyword'),
    (2, "17:       end for",                                        'keyword'),
    (2, "18:       if best ≠ None then",                            'keyword'),
    (3, "19:           A ← A ∪ {(best.c, best.s)};  mark assigned",'var'),
    (2, "20:       else  break",                                    'keyword'),
    (1, "21:   end while",                                          'keyword'),
    (0, "22: end for",                                              'keyword'),
    (0, "23: Compute ρ = |A|/|O^w|,  τ̄ = avg travel time from A;  evaluate f", 'highlight'),
    (0, "24: return A, f",                                          'highlight'),
]
code_block(slide, code_lines2, Inches(0.35), Inches(1.18), Inches(8.5), Inches(5.9),
           font_size=Pt(10))

# Right: decoder step illustration
rx = Inches(9.05)
add_text(slide, "DECODER EXAMPLE", rx, Inches(1.18), Inches(4.1), Inches(0.35),
         size=Pt(12), bold=True, color=DARK_BLUE)
example_steps = [
    (ACCENT_ORG, "Input chromosome", 'x = [0.91, 0.34, 0.77 | 0.82, 0.47]'),
    (MID_BLUE,   "Order priority",   "o₁ ≻ o₃ ≻ o₂"),
    (ACCENT_GRN, "Courier priority", "c₁ ≻ c₂"),
    (DARK_BLUE,  "Assign o₁",        "Try c₁ first → route(c₁,r,{o₁}) feasible ✓"),
    (DARK_BLUE,  "Batch o₁+o₃",      "k=2 batch → route(c₁,r,{o₁,o₃}) feasible ✓"),
    (ACCENT_ORG, "Assign o₂",        "c₁ used → try c₂ → route(c₂,r,{o₂}) ✓"),
    (ACCENT_GRN, "Result A",          "A = {(c₁,{o₁,o₃}), (c₂,{o₂})}   ρ=1.0"),
]
for i,(col,title,desc) in enumerate(example_steps):
    ey = Inches(1.58) + i*Inches(0.75)
    add_rect(slide, rx, ey, Inches(1.25), Inches(0.65), fill_rgb=col)
    add_text(slide, title, rx+Inches(0.03), ey+Inches(0.05), Inches(1.2), Inches(0.58),
             size=Pt(9), bold=True, color=WHITE, align=PP_ALIGN.CENTER, wrap=True)
    add_rect(slide, rx+Inches(1.25), ey, Inches(2.8), Inches(0.65), fill_rgb=WHITE,
             line_rgb=col, line_width=Pt(0.75))
    add_text(slide, desc, rx+Inches(1.35), ey+Inches(0.08), Inches(2.65), Inches(0.55),
             size=Pt(10), color=DARK_GRAY, font="Courier New", wrap=True)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 8 — Algorithm 3: BRKGA Rolling Horizon main loop (pseudocode)
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Algorithm 3 — BRKGA Rolling-Horizon Main Loop",
                     "Full evolutionary cycle executed once every Δ = 2 minutes"); footer(slide, 14)

code_lines3 = [
    (0, "Algorithm 3: BRKGA Rolling-Horizon main loop",           'highlight'),
    (0, "Require: Orders O, Couriers C, window length Δ",          'comment'),
    (0, "",                                                         'normal'),
    (0, "1:  Initialise; assigned ← ∅",                            'var'),
    (0, "2:  for w = 0, Δ, 2Δ, …, 1440 do                         ▷ 720 dispatch epochs", 'keyword'),
    (1, "3:    Release couriers whose routes finished ≤ w",         'normal'),
    (1, "4:    O^w ← { o ∈ O \\ assigned : s^r_o ≤ w }",           'var'),
    (1, "5:    C^w ← idle couriers at time w",                      'var'),
    (1, "6:    if O^w = ∅ or C^w = ∅ then continue end if",        'keyword'),
    (0, "",                                                         'normal'),
    (1, "// ─── BRKGA must complete within Δ = 2 minutes ───",     'comment'),
    (1, "7:    Initialise population P ~ U[0,1]^{Nₚ × (|O^w|+|C^w|)}", 'var'),
    (1, "8:    f* ← ∞;  A* ← ∅",                                   'var'),
    (0, "",                                                         'normal'),
    (1, "9:    for g = 1 … Gₘₐₓ (= 10) do                         ▷ evolutionary loop", 'keyword'),
    (2, "10:       for all x ∈ P do",                               'keyword'),
    (3, "11:           (A, f) ← Decode(x, O^w, C^w)               ▷ Algorithm 2", 'normal'),
    (3, "12:           if f < f* then  f* ← f;  A* ← A",           'highlight'),
    (2, "13:       end for",                                         'keyword'),
    (2, "14:       Select Nₑ=2 elite; generate Nₒ=6 offspring + Nₘ=2 mutants", 'normal'),
    (2, "15:       P ← elite ∪ offspring ∪ mutants",                'var'),
    (1, "16:   end for",                                             'keyword'),
    (0, "",                                                         'normal'),
    (1, "17:   Dispatch A*;  update state and assigned",             'highlight'),
    (0, "18: end for",                                               'keyword'),
]
code_block(slide, code_lines3, Inches(0.35), Inches(1.18), Inches(8.5), Inches(5.88),
           font_size=Pt(10.2))

# Right: Fitness function comparison
rx = Inches(9.05)
add_text(slide, "FITNESS FUNCTIONS", rx, Inches(1.18), Inches(4.1), Inches(0.35),
         size=Pt(12), bold=True, color=DARK_BLUE)

add_rect(slide, rx, Inches(1.58), Inches(4.1), Inches(2.5), fill_rgb=WHITE,
         line_rgb=ACCENT_ORG, line_width=Pt(1.5))
add_rect(slide, rx, Inches(1.58), Inches(4.1), Inches(0.42), fill_rgb=ACCENT_ORG)
add_text(slide, "f_cov  (BRKGA-Coverage)", rx+Inches(0.08), Inches(1.6), Inches(3.95), Inches(0.38),
         size=Pt(11), bold=True, color=WHITE)
cov_eqs = [
    "ρ < 0.50  →  10⁹(1-ρ) + τ̄/20",
    "ρ < 0.60  →  10⁷(1-ρ) + τ̄/20",
    "ρ ≥ 0.60  →  10⁵(1-ρ) + τ̄/20",
    "Priority: coverage first, travel second",
]
for j,eq in enumerate(cov_eqs):
    add_text(slide, ("  " if j<3 else "→ ") + eq,
             rx+Inches(0.1), Inches(2.05)+j*Inches(0.47), Inches(3.9), Inches(0.45),
             size=Pt(10.5), color=DARK_GRAY, font="Courier New" if j<3 else "Calibri")

add_rect(slide, rx, Inches(4.25), Inches(4.1), Inches(2.5), fill_rgb=WHITE,
         line_rgb=ACCENT_GRN, line_width=Pt(1.5))
add_rect(slide, rx, Inches(4.25), Inches(4.1), Inches(0.42), fill_rgb=ACCENT_GRN)
add_text(slide, "f_trav  (BRKGA-Travel)", rx+Inches(0.08), Inches(4.27), Inches(3.95), Inches(0.38),
         size=Pt(11), bold=True, color=WHITE)
trav_eqs = [
    "ρ < 0.50  →  10⁶(1-ρ) + τ̄",
    "ρ ≥ 0.50  →  10⁴(1-ρ) + τ̄",
    "Softer penalty → allows coverage/",
    "  travel tradeoffs (~25% faster)",
]
for j,eq in enumerate(trav_eqs):
    add_text(slide, "  " + eq,
             rx+Inches(0.1), Inches(4.72)+j*Inches(0.47), Inches(3.9), Inches(0.45),
             size=Pt(10.5), color=DARK_GRAY, font="Courier New" if j<2 else "Calibri")

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 9 — Experimental Setup
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Experimental Setup",
                     "24 real-world instances from a Latin American food-delivery platform"); footer(slide, 15)

bullets(slide, [
    (0, "DATA SOURCE"),
    (1, "Anonymized operational data from a Colombian delivery app — one full day per instance"),
    (1, "Dispatch interval Δ = 2 min → 720 decision epochs; planning horizon = 1,440 min"),
    (0, "INSTANCE TIERS"),
    (1, "Small   (S): |O| < 5,000   — 13 instances    avg |O| = 2,423    avg |C| ≈ 1,200"),
    (1, "Medium  (M): 5,000–20,000  —  5 instances    avg |O| = 10,210   avg |C| ≈ 3,800"),
    (1, "Large   (L): |O| > 20,000  —  6 instances    avg |O| = 37,518   avg |C| ≈ 11,200"),
    (0, "EVALUATION METRICS"),
    (1, "Coverage rate ρ = |Ō|/|O|  (orders delivered / orders placed)"),
    (1, "Average travel time τ̄ per delivered order (min/order)"),
    (1, "Total daily execution time T (seconds, sum over all windows)"),
    (0, "HARDWARE / SOFTWARE"),
    (1, "Python 3.7 · Intel Core i9-12900H · 16 GB RAM · Windows 11"),
    (1, "All four methods run under identical rolling-horizon conditions"),
], Inches(0.4), Inches(1.18), Inches(7.8), H-Inches(1.7), size=Pt(14))

# Instance distribution visual (right)
rx = Inches(8.3)
add_text(slide, "INSTANCE DISTRIBUTION", rx, Inches(1.18), Inches(4.8), Inches(0.35),
         size=Pt(12), bold=True, color=DARK_BLUE)
tiers = [("Small\n13 inst.", 13, MID_BLUE, "avg 2,423 orders"),
         ("Medium\n5 inst.",   5, ACCENT_ORG, "avg 10,210 orders"),
         ("Large\n6 inst.",    6, ACCENT_GRN, "avg 37,518 orders")]
max_c = 13; bw2 = Inches(1.3); bg2 = Inches(0.25); barea = Inches(4.2)
bar_top2 = Inches(1.6)
for i,(lbl,cnt,col,sub) in enumerate(tiers):
    bx2 = rx+Inches(0.1)+i*(bw2+bg2)
    bh2 = barea*(cnt/max_c)
    by2 = bar_top2+barea-bh2
    add_rect(slide, bx2, by2, bw2, bh2, fill_rgb=col)
    add_text(slide, str(cnt), bx2, by2-Inches(0.38), bw2, Inches(0.36),
             size=Pt(18), bold=True, color=col, align=PP_ALIGN.CENTER)
    add_text(slide, lbl, bx2, bar_top2+barea+Inches(0.05), bw2, Inches(0.55),
             size=Pt(11), color=DARK_GRAY, align=PP_ALIGN.CENTER)
    add_text(slide, sub, bx2, bar_top2+barea+Inches(0.6), bw2, Inches(0.4),
             size=Pt(9), italic=True, color=DARK_GRAY, align=PP_ALIGN.CENTER)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 10 — Results: Coverage Rate
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Results — Coverage Rate (ρ)",
                     "Percentage of orders successfully delivered by end of day"); footer(slide, 16)

# Results table
headers = ["Size", "#", "BRKGA-Cov", "BRKGA-Trav", "BML", "BM"]
rows = [
    ["Small",  "13", "64.8%", "64.8%", "53.6%", "46.0%"],
    ["Medium", " 5", "59.1%", "59.1%", "46.0%", "38.4%"],
    ["Large",  " 6", "47.2%", "47.3%", "51.1%*","44.8%"],
    ["All",    "24", "59.2%", "59.2%", "51.4%", "44.1%"],
]
col_ws = [Inches(1.5),Inches(0.6),Inches(1.6),Inches(1.6),Inches(1.55),Inches(1.55)]
rh = Inches(0.52); tx = Inches(0.35); ty = Inches(1.22)

for ci,hdr in enumerate(headers):
    cx = tx+sum(col_ws[:ci])
    add_rect(slide, cx, ty, col_ws[ci], rh, fill_rgb=DARK_BLUE,
             line_rgb=WHITE, line_width=Pt(0.75))
    add_text(slide, hdr, cx+Inches(0.04), ty+Inches(0.07), col_ws[ci]-Inches(0.08), rh-Inches(0.1),
             size=Pt(13), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

# highlight winners: small/med → BRKGA; large → BML; all → BRKGA
winners = {(0,2),(0,3),(1,2),(1,3),(2,4),(3,2),(3,3)}
for ri,row in enumerate(rows):
    for ci,cell in enumerate(row):
        cx = tx+sum(col_ws[:ci]); cy = ty+(ri+1)*rh
        win = (ri,ci) in winners
        total = ri==3
        bg_c = RGBColor(0xFF,0xE6,0xCC) if win else \
               (RGBColor(0xD6,0xE4,0xF0) if total else (LIGHT_BLUE if ri%2==0 else WHITE))
        add_rect(slide, cx, cy, col_ws[ci], rh, fill_rgb=bg_c,
                 line_rgb=DARK_BLUE, line_width=Pt(0.5))
        add_text(slide, cell, cx+Inches(0.04), cy+Inches(0.07), col_ws[ci]-Inches(0.08), rh-Inches(0.1),
                 size=Pt(13.5), bold=win or total,
                 color=RGBColor(0xC0,0x50,0x00) if win else DARK_GRAY,
                 align=PP_ALIGN.CENTER)

add_text(slide,
    "* BML outperforms BRKGA on all 6 large instances — deterministic lookahead scales better under fixed generation budget",
    tx, ty+5*rh+Inches(0.06), Inches(9.1), Inches(0.38),
    size=Pt(10.5), italic=True, color=DARK_GRAY)

# Bar chart
chart_x = Inches(9.6); chart_y = Inches(1.22)
add_text(slide, "Coverage by Instance Size", chart_x, chart_y, Inches(3.55), Inches(0.35),
         size=Pt(11), bold=True, color=DARK_BLUE, align=PP_ALIGN.CENTER)
bar_colors = [ACCENT_ORG, ACCENT_GRN, MID_BLUE, RGBColor(0xA0,0xA0,0xA0)]
ml = ["BRKGA-C","BRKGA-T","BML","BM"]
vals_by_size = [[64.8,64.8,53.6,46.0],[59.1,59.1,46.0,38.4],[47.2,47.3,51.1,44.8]]
sz_lbl = ["Small","Medium","Large"]
gw = Inches(0.95); bw3 = Inches(0.19); bg3 = Inches(0.02); gg = Inches(0.08)
maxv = 70; avh = Inches(4.0)
for gi,(sz,vals) in enumerate(zip(sz_lbl,vals_by_size)):
    gx = chart_x+Inches(0.1)+gi*(gw+gg)
    for bi,(v,col) in enumerate(zip(vals,bar_colors)):
        bx3 = gx+bi*(bw3+bg3)
        bh3 = avh*(v/maxv)
        by3 = chart_y+Inches(0.45)+avh-bh3
        add_rect(slide, bx3, by3, bw3, bh3, fill_rgb=col)
    add_text(slide, sz, gx, chart_y+Inches(0.45)+avh+Inches(0.04), gw, Inches(0.28),
             size=Pt(10), color=DARK_GRAY, align=PP_ALIGN.CENTER)
legend_y = chart_y+Inches(4.95)
for bi,(lbl,col) in enumerate(zip(ml,bar_colors)):
    lx = chart_x+Inches(0.1)+bi*Inches(0.88)
    add_rect(slide, lx, legend_y, Inches(0.18), Inches(0.18), fill_rgb=col)
    add_text(slide, lbl, lx+Inches(0.22), legend_y-Inches(0.02), Inches(0.66), Inches(0.25),
             size=Pt(9), color=DARK_GRAY)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 11 — Results: Execution Time
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Results — Execution Time & Travel Efficiency",
                     "BRKGA-Travel faster than Coverage; BML slowest on large instances"); footer(slide, 17)

bullets(slide, [
    (0, "EXECUTION TIME  (total over all windows)"),
    (1, "BRKGA-Travel ~25% faster than BRKGA-Coverage — softer fitness → faster convergence"),
    (1, "BML dramatically slower on large instances (demand-forecast computation overhead)"),
    (1, "Instance 6 (Large, 59k orders): T_BML = 6,738 s   vs   T_BC = 490 s  → 13.7× difference"),
    (0, "TRAVEL TIME PER DELIVERED ORDER"),
    (1, "BRKGA-Coverage:  27.90 min/order   vs   BRKGA-Travel:  27.86 min/order  (< 0.2% diff)"),
    (1, "Nearest-neighbor decoder dominates route quality — fitness function barely differentiates"),
    (1, "Small instances: τ̄ ≈ 25 min/order   vs   Large: τ̄ ≈ 33 min/order  (wider geographic spread)"),
    (0, "KEY TAKEAWAY"),
    (1, "BRKGA-Travel strictly dominates BRKGA-Coverage: same coverage, lower runtime"),
    (1, "No free lunch — BML's lookahead pays off only for very large instances (|O| > 20k)"),
], Inches(0.4), Inches(1.18), Inches(8.0), H-Inches(1.7), size=Pt(14))

# Horizontal bar chart (relative time)
rx = Inches(8.5); ry = Inches(1.22)
add_text(slide, "Relative Exec. Time (Large Instances)", rx, ry, Inches(4.6), Inches(0.35),
         size=Pt(11), bold=True, color=DARK_BLUE, align=PP_ALIGN.CENTER)
mt = [("BM",1.0,MID_BLUE),("BML",13.7,RGBColor(0x8B,0,0)),("BRKGA-C",1.0,ACCENT_ORG),("BRKGA-T",0.75,ACCENT_GRN)]
maxT = 14.0; barea2 = Inches(3.6); bh4 = Inches(0.5); bg4 = Inches(0.14)
for mi,(name,val,col) in enumerate(mt):
    by4 = ry+Inches(0.45)+mi*(bh4+bg4)
    bw4 = barea2*(val/maxT)
    add_text(slide, name, rx, by4, Inches(0.9), bh4,
             size=Pt(12), bold=True, color=DARK_GRAY)
    add_rect(slide, rx+Inches(0.95), by4, bw4, bh4, fill_rgb=col)
    add_text(slide, f"{val:.1f}×", rx+Inches(0.95)+bw4+Inches(0.06), by4+Inches(0.06),
             Inches(0.8), bh4-Inches(0.12), size=Pt(12), bold=True,
             color=RGBColor(0x8B,0,0) if val>5 else DARK_GRAY)
add_text(slide, "(relative to BM execution time on large instances)", rx, ry+Inches(4.0),
         Inches(4.6), Inches(0.3), size=Pt(10), italic=True, color=DARK_GRAY, align=PP_ALIGN.CENTER)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 12 — Decision Guide (flowchart)
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Practical Decision Guide",
                     "Which dispatching method to deploy? — A flowchart based on our results"); footer(slide, 18)

def diamond(slide, text, cx, cy, hw, hh, fill, text_color=WHITE, font_size=Pt(11)):
    """Draw a diamond shape using a rotated rectangle placeholder via add_shape type=4 (diamond)."""
    shape = slide.shapes.add_shape(4, cx-hw, cy-hh, hw*2, hh*2)
    shape.fill.solid(); shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = DARK_GRAY; shape.line.width = Pt(1)
    tf = shape.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    run = p.add_run(); run.text = text
    run.font.name = "Calibri"; run.font.size = font_size
    run.font.bold = True; run.font.color.rgb = text_color
    return shape

def arrow(slide, x1,y1,x2,y2):
    """Draw a simple line connector."""
    from pptx.util import Emu
    line = slide.shapes.add_connector(1, x1, y1, x2, y2)
    line.line.color.rgb = DARK_GRAY; line.line.width = Pt(1.5)

def box(slide, text, l, t, w, h, fill, text_color=WHITE, font_size=Pt(12), border=DARK_GRAY):
    add_rect(slide, l, t, w, h, fill_rgb=fill, line_rgb=border, line_width=Pt(1.5))
    add_text(slide, text, l+Inches(0.08), t+Inches(0.06), w-Inches(0.16), h-Inches(0.12),
             size=font_size, bold=True, color=text_color, align=PP_ALIGN.CENTER, wrap=True)

# Start node
box(slide, "START\nNew dispatching day",
    Inches(5.35), Inches(1.18), Inches(2.65), Inches(0.7), fill=DARK_BLUE, font_size=Pt(13))
arrow(slide, Inches(6.68), Inches(1.88), Inches(6.68), Inches(2.2))

# Q1: instance size
diamond(slide, "Daily order\nvolume |O|?",
        Inches(6.68), Inches(2.75), Inches(1.55), Inches(0.58), fill=MID_BLUE, font_size=Pt(12))

# Labels on branches
add_text(slide, "|O| < 20k", Inches(3.6), Inches(2.55), Inches(1.5), Inches(0.3),
         size=Pt(11), bold=True, color=MID_BLUE)
add_text(slide, "|O| > 20k", Inches(7.65), Inches(2.55), Inches(1.5), Inches(0.3),
         size=Pt(11), bold=True, color=RGBColor(0x8B,0,0))

# Left branch: small/medium → Q2
arrow(slide, Inches(5.13), Inches(2.75), Inches(3.8), Inches(2.75))
arrow(slide, Inches(3.8), Inches(2.75), Inches(3.8), Inches(3.35))

diamond(slide, "Is exec. time\ncritical?",
        Inches(3.8), Inches(3.9), Inches(1.35), Inches(0.58), fill=MID_BLUE, font_size=Pt(12))
arrow(slide, Inches(3.8), Inches(4.48), Inches(3.8), Inches(5.05))
arrow(slide, Inches(5.15), Inches(3.9), Inches(6.3), Inches(3.9))

# YES time critical → BRKGA-Travel
box(slide, "BRKGA-Travel\n✓ Same coverage\n✓ 25% faster",
    Inches(2.35), Inches(5.05), Inches(2.9), Inches(1.0),
    fill=ACCENT_GRN, font_size=Pt(12))
add_text(slide, "YES", Inches(3.1), Inches(4.7), Inches(1.0), Inches(0.3),
         size=Pt(11), bold=True, color=ACCENT_GRN)

# NO → BRKGA-Coverage
box(slide, "BRKGA-Coverage\n✓ Max coverage\n(slight overhead)",
    Inches(6.3), Inches(3.3), Inches(2.9), Inches(1.0),
    fill=ACCENT_ORG, font_size=Pt(12))
add_text(slide, "NO", Inches(5.7), Inches(3.72), Inches(0.8), Inches(0.3),
         size=Pt(11), bold=True, color=ACCENT_ORG)

# Right branch: large → BML
arrow(slide, Inches(8.23), Inches(2.75), Inches(10.0), Inches(2.75))
arrow(slide, Inches(10.0), Inches(2.75), Inches(10.0), Inches(3.35))

box(slide, "Business Model\nLookahead (BML)\n✓ Best coverage at scale",
    Inches(8.6), Inches(3.35), Inches(2.8), Inches(1.0),
    fill=RGBColor(0x8B,0,0), font_size=Pt(12))

# Hybrid box at bottom
box(slide, "HYBRID STRATEGY: Monitor daily |O| → switch method automatically",
    Inches(3.35), Inches(6.22), Inches(6.65), Inches(0.62),
    fill=DARK_BLUE, font_size=Pt(12), border=ACCENT_ORG)

# Connect recommendation boxes to hybrid
arrow(slide, Inches(3.8), Inches(6.05), Inches(3.8), Inches(6.22))
arrow(slide, Inches(7.75), Inches(3.9), Inches(6.68), Inches(6.22))
arrow(slide, Inches(10.0), Inches(4.35), Inches(10.0), Inches(6.53))
arrow(slide, Inches(10.0), Inches(6.53), Inches(10.0), Inches(6.84))

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 13 — Conclusions
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Conclusions",
                     "BRKGA-RH advances the state of practice for real-time meal delivery dispatching"); footer(slide, 19)

col1 = Inches(0.35); col2 = Inches(6.85); cw = Inches(6.25)

add_text(slide, "MAIN FINDINGS", col1, Inches(1.18), cw, Inches(0.35),
         size=Pt(13), bold=True, color=DARK_BLUE)
bullets(slide, [
    (0, "BRKGA variants outperform BM/BML on small & medium instances"),
    (1, "+11 to +20 pp coverage gain over BML   |   +19 to +27 pp over BM"),
    (0, "BML competitive on large instances (|O| > 20k)"),
    (1, "Demand-forecast deferral consolidates larger batches at scale"),
    (1, "BRKGA's fixed Gmax=10 limits exploration on high-volume days"),
    (0, "BRKGA-Travel preferred over BRKGA-Coverage"),
    (1, "Same or better coverage across all instance sizes"),
    (1, "~25% faster — critical advantage in real-time dispatch (2-min budget)"),
    (0, "Travel time nearly identical across BRKGA variants (27.9 min/order)"),
    (1, "Nearest-neighbor decoder dominates route quality regardless of fitness"),
], col1, Inches(1.58), cw, H-Inches(2.1), size=Pt(14))

add_rect(slide, col2-Inches(0.18), Inches(1.18), Inches(0.04), H-Inches(1.62), fill_rgb=MID_BLUE)

add_text(slide, "CONTRIBUTIONS", col2, Inches(1.18), cw, Inches(0.35),
         size=Pt(13), bold=True, color=DARK_BLUE)
bullets(slide, [
    (0, "First BRKGA integration with rolling-horizon for online MDRP"),
    (0, "Chromosome encoding guaranteeing feasibility without repair operators"),
    (0, "Two fitness variants targeting coverage vs. travel-time efficiency"),
    (0, "Systematic benchmark on 24 real-world heterogeneous instances"),
    (0, "Empirical evidence that travel-time fitness dominates coverage-only fitness"),
    (0, "Recommended hybrid deployment strategy based on instance size"),
    (0, "Open-source implementation available on GitHub"),
], col2, Inches(1.58), cw, H-Inches(2.1), size=Pt(14))

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE 14 — Future Work
# ─────────────────────────────────────────────────────────────────────────────
slide = prs.slides.add_slide(BLANK)
bg(slide); title_bar(slide, "Future Work",
                     "Extending the BRKGA-Rolling Horizon framework"); footer(slide, 20)

fw = [
    (ACCENT_ORG, "Adaptive Generation Budget",
     "Dynamically adjust Gmax and Np based on available time budget and instance density — eliminate the large-instance scalability gap"),
    (MID_BLUE, "Courier Fairness Objectives",
     "Multi-objective BRKGA: Pareto frontier between coverage rate ρ and courier workload equity (min/max order distribution)"),
    (ACCENT_GRN, "Online Demand-Forecast Learning",
     "Replace static BML heuristic weights with RL demand predictor that adapts during the operating day using streaming order data"),
    (DARK_BLUE, "Ghost Kitchens & Multi-Platform",
     "Extend formulation to virtual kitchens (dynamic pickup locations) and cooperative logistics across competing platforms"),
    (RGBColor(0x8B,0,0), "Live Field Trial",
     "Deploy BRKGA-Travel in A/B test on real platform — measure customer satisfaction, courier income, and platform profit metrics"),
]
for i,(col,title,desc) in enumerate(fw):
    iy = Inches(1.22) + i*Inches(1.08)
    add_rect(slide, Inches(0.35), iy, Inches(2.0), Inches(0.95), fill_rgb=col)
    add_text(slide, title, Inches(0.4), iy+Inches(0.08), Inches(1.92), Inches(0.85),
             size=Pt(12), bold=True, color=WHITE, align=PP_ALIGN.CENTER, wrap=True)
    add_rect(slide, Inches(2.35), iy, W-Inches(2.5), Inches(0.95), fill_rgb=WHITE,
             line_rgb=col, line_width=Pt(1.5))
    add_text(slide, desc, Inches(2.5), iy+Inches(0.12), W-Inches(2.8), Inches(0.78),
             size=Pt(13), color=DARK_GRAY, wrap=True)

# ─────────────────────────────────────────────────────────────────────────────
# Save
# ─────────────────────────────────────────────────────────────────────────────
out = r"C:\Users\danie\OneDrive - Universidad de los andes\Doctorado\articulo MDRP\presentacion_MIC2026.pptx"
prs.save(out)
print(f"Saved: {out}")
