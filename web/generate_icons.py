#!/usr/bin/env python3
"""
Professional 64x64 icon generator for Cinema 4D plugins.
Style: Clean geometric, flat design, cyan accent on transparent background.
All icons fill the full 64x64 canvas properly.
"""
import os, math, base64, io
from PIL import Image, ImageDraw

SIZE = 64
SCALE = 4
CANVAS = SIZE * SCALE
ICO_NEW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ico")
B64_DATA = []  # (name, base64_string)

# Colors
BG     = (0,0,0,0)
CYAN   = (0,200,255,255)
CYAN_L = (100,220,255,255)
CYAN_D = (0,140,200,255)
WHITE  = (230,235,240,255)
ORANGE = (255,160,50,255)
GREEN  = (80,220,130,255)
RED_L  = (255,100,100,255)
YELLOW = (255,210,60,255)
GRAY   = (120,130,145,255)
GRAY_L = (170,180,195,255)
GRAY_D = (70,75,85,255)

def s(v):
    return int(v * SCALE)

def make():
    return Image.new("RGBA", (CANVAS, CANVAS), BG)

def fin(img):
    return img.resize((SIZE, SIZE), Image.LANCZOS)

def save(img, rel):
    p = os.path.join(ICO_NEW, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    final = fin(img)
    final.save(p, "PNG")
    # Collect base64
    buf = io.BytesIO()
    final.save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    name = os.path.splitext(os.path.basename(rel))[0]
    B64_DATA.append((name, b64))
    print(f"  OK {rel}")

# ─── MAIN PLUGINS ──────────────────────────────────────────────

def icon_camera_resolution():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(30)
    # Camera body - big
    bw, bh = s(52), s(30)
    bx, by = cx - bw//2, cy - bh//2
    d.rounded_rectangle([bx, by, bx+bw, by+bh], radius=s(4), fill=None, outline=CYAN, width=s(3))
    # Lens - big
    lr = s(11)
    d.ellipse([cx-lr, cy-lr, cx+lr, cy+lr], fill=None, outline=CYAN, width=s(3))
    d.ellipse([cx-s(4), cy-s(4), cx+s(4), cy+s(4)], fill=CYAN)
    # Flash
    d.rectangle([bx+s(4), by-s(6), bx+s(14), by], fill=ORANGE)
    # Resolution grid
    for i in range(3):
        lx = bx + s(10) + i * s(11)
        d.line([(lx, by+s(4)), (lx, by+bh-s(4))], fill=CYAN_L, width=s(1))
    for i in range(2):
        ly = by + s(8) + i * s(7)
        d.line([(bx+s(3), ly), (bx+bw-s(3), ly)], fill=CYAN_L, width=s(1))
    save(img, "CameraResolution.png")

def icon_cloud_wizard():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(34)
    # Big cloud
    for c, r in [((cx-s(12), cy+s(4)), s(16)), ((cx+s(12), cy+s(4)), s(14)),
                  ((cx, cy-s(4)), s(14)), ((cx-s(4), cy+s(14)), s(12))]:
        d.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=CYAN_D, outline=CYAN, width=s(3))
    # Bottom flat
    d.line([(cx-s(24), cy+s(12)), (cx+s(24), cy+s(12))], fill=CYAN, width=s(3))
    # Stars
    for sx, sy, sz, col in [(cx+s(18), cy-s(18), 5, ORANGE), (cx-s(20), cy-s(14), 4, YELLOW), (cx+s(8), cy-s(24), 3, YELLOW)]:
        draw_star(d, sx, sy, sz, col)
    save(img, "CloudWizard.png")

def draw_star(d, cx, cy, r, color):
    pts = []
    for i in range(5):
        a = math.radians(-90 + i * 72)
        pts.append((cx + r*SCALE*math.cos(a), cy + r*SCALE*math.sin(a)))
        a2 = math.radians(-90 + i*72 + 36)
        pts.append((cx + r*SCALE*0.4*math.cos(a2), cy + r*SCALE*0.4*math.sin(a2)))
    d.polygon(pts, fill=color)

def icon_floor_generator():
    img = make(); d = ImageDraw.Draw(img)
    size = s(6)
    hx = int(size * 1.5)
    hy = int(size * math.sqrt(3))
    margin = s(6)
    orange_count = 0
    orange_cells = {(2, 1), (0, 3), (4, 2)}
    for col in range(-1, CANVAS // hx + 2):
        for row in range(-1, CANVAS // hy + 2):
            cx = col * hx
            cy = row * hy + (col % 2) * (hy // 2)
            if cx < margin or cx > CANVAS - margin or cy < margin or cy > CANVAS - margin:
                continue
            pts = []
            for i in range(6):
                a = math.radians(60 * i)
                pts.append((cx + size * math.cos(a), cy + size * math.sin(a)))
            color = ORANGE if (col, row) in orange_cells else CYAN
            d.polygon(pts, fill=color, outline=WHITE, width=s(1))
    save(img, "FloorGenerator.png")

def icon_object_renamer():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(30)
    # Big document
    dw, dh = s(40), s(48)
    d.rounded_rectangle([cx-dw//2, cy-dh//2, cx+dw//2, cy+dh//2], radius=s(4), fill=None, outline=CYAN, width=s(3))
    # Text lines
    for i, w in enumerate([s(28), s(20), s(26), s(16)]):
        y = cy - s(14) + i * s(9)
        d.rounded_rectangle([cx-s(12), y, cx-s(12)+w, y+s(4)], radius=s(1), fill=CYAN)
    # Pencil bottom-right
    px, py = cx+s(14), cy+s(12)
    d.line([(px, py), (px+s(12), py-s(12))], fill=ORANGE, width=s(3))
    d.line([(px+s(12), py-s(12)), (px+s(12), py-s(7))], fill=ORANGE, width=s(2))
    d.line([(px+s(12), py-s(12)), (px+s(7), py-s(12))], fill=ORANGE, width=s(2))
    save(img, "ObjectRenamerPRO.png")

def icon_snapshot():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Camera body
    bw, bh = s(52), s(28)
    bx, by = cx-bw//2, cy-bh//2
    d.rounded_rectangle([bx, by, bx+bw, by+bh], radius=s(4), fill=None, outline=CYAN, width=s(3))
    # Lens
    lr = s(10)
    d.ellipse([cx-lr, cy-lr, cx+lr, cy+lr], fill=None, outline=CYAN, width=s(3))
    d.ellipse([cx-s(5), cy-s(5), cx+s(5), cy+s(5)], fill=CYAN)
    # Flash
    d.rectangle([bx+s(3), by-s(5), bx+s(12), by], fill=ORANGE)
    # Snowflake/frozen effect
    for angle in [0, 60, 120]:
        a = math.radians(angle)
        for sign in [1, -1]:
            x1 = cx + sign*s(8)*math.cos(a)
            y1 = by - s(8) + sign*s(8)*math.sin(a)
            x2 = cx + sign*s(5)*math.cos(a+30)
            y2 = by - s(8) + sign*s(5)*math.sin(a+30)
            d.line([(cx, by-s(8)), (x1, y1)], fill=CYAN_L, width=s(2))
            d.line([(x1, y1), (x2, y2)], fill=CYAN_L, width=s(1))
    save(img, "Snapshot.png")

# ─── SELECTION SET ─────────────────────────────────────────────

def icon_selection_set_plugin():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Three large overlapping squares
    for dx, dy, color in [(-s(8), -s(8), CYAN_D), (s(0), s(0), CYAN), (s(8), s(8), ORANGE)]:
        x, y = cx+dx-s(16), cy+dy-s(16)
        d.rounded_rectangle([x, y, x+s(32), y+s(32)], radius=s(3), fill=None, outline=color, width=s(3))
    # Checkmark
    d.line([(cx-s(6), cy+s(2)), (cx-s(2), cy+s(8)), (cx+s(8), cy-s(6))], fill=GREEN, width=s(4))
    save(img, "SelectionSet/icon_plugin.png")

def icon_selection_set_tag():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Selection set = list of items with checkmarks showing they are selected
    for i, dy in enumerate([-s(14), s(0), s(14)]):
        y = cy + dy - s(5)
        # Item background
        d.rounded_rectangle([cx-s(22), y, cx+s(22), y+s(10)], radius=s(2), fill=CYAN_D, outline=CYAN, width=s(2))
        # Checkmark
        d.line([(cx-s(16), y+s(5)), (cx-s(12), y+s(8)), (cx-s(6), y+s(1))], fill=GREEN if i != 1 else ORANGE, width=s(3))
    save(img, "SelectionSet/icon_tag.png")

# ─── VAR TOOLS ─────────────────────────────────────────────────

def icon_var_tools():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Big gear
    draw_gear(d, cx, cy, s(26), s(18), 8, CYAN, CYAN_D)
    # Wrench
    d.line([(cx-s(8), cy+s(8)), (cx+s(8), cy-s(8))], fill=ORANGE, width=s(4))
    d.ellipse([cx+s(5)-s(5), cy-s(5)-s(5), cx+s(5)+s(5), cy-s(5)+s(5)], fill=None, outline=ORANGE, width=s(3))
    save(img, "Var_tools/varp_tools.png")

def draw_gear(d, cx, cy, outer_r, inner_r, teeth, outline_color, fill_color):
    pts = []
    for i in range(teeth):
        a1 = 2*math.pi*i/teeth
        a2 = 2*math.pi*(i+0.3)/teeth
        a3 = 2*math.pi*(i+0.5)/teeth
        a4 = 2*math.pi*(i+0.8)/teeth
        pts.extend([(cx+outer_r*math.cos(a1), cy+outer_r*math.sin(a1)),
                     (cx+outer_r*math.cos(a2), cy+outer_r*math.sin(a2)),
                     (cx+inner_r*math.cos(a3), cy+inner_r*math.sin(a3)),
                     (cx+inner_r*math.cos(a4), cy+inner_r*math.sin(a4))])
    d.polygon(pts, fill=fill_color, outline=outline_color)
    hr = s(6)
    d.ellipse([cx-hr, cy-hr, cx+hr, cy+hr], fill=BG, outline=outline_color, width=s(3))

def icon_about():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    r = s(28)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=None, outline=CYAN, width=s(3))
    d.rounded_rectangle([cx-s(3), cy-s(14), cx+s(3), cy+s(3)], radius=s(2), fill=CYAN)
    d.ellipse([cx-s(3), cy+s(8), cx+s(3), cy+s(14)], fill=ORANGE)
    save(img, "Var_tools/About.png")

# ─── ANIMATION ─────────────────────────────────────────────────

def icon_shift_anim():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Big timeline
    d.rounded_rectangle([s(4), cy-s(6), s(60), cy+s(6)], radius=s(3), fill=GRAY_D, outline=CYAN, width=s(2))
    for x in [s(12), s(22), s(34), s(46)]:
        d.rectangle([x-s(2), cy-s(3), x+s(2), cy+s(3)], fill=CYAN_L)
    # Arrow to start
    d.line([(s(32), cy-s(18)), (s(10), cy-s(18))], fill=ORANGE, width=s(3))
    d.polygon([(s(10), cy-s(18)), (s(16), cy-s(24)), (s(16), cy-s(12))], fill=ORANGE)
    # Frame 0 line
    d.line([(s(10), cy-s(24)), (s(10), cy+s(24))], fill=ORANGE, width=s(2))
    save(img, "Var_tools/Animation/shift_anim_to_zero.png")

def icon_scale_anim():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Timeline
    d.rounded_rectangle([s(8), cy-s(6), s(56), cy+s(6)], radius=s(3), fill=GRAY_D, outline=CYAN, width=s(2))
    for x in [s(16), s(26), s(36), s(46)]:
        d.rectangle([x-s(2), cy-s(3), x+s(2), cy+s(3)], fill=CYAN_L)
    # Scale arrows both ends
    for ax, direction in [(s(8), -1), (s(56), 1)]:
        d.line([(ax, cy-s(18)), (ax, cy+s(18))], fill=ORANGE, width=s(3))
        d.polygon([(ax, cy-s(18)), (ax-direction*s(6), cy-s(12)), (ax+direction*s(6), cy-s(12))], fill=ORANGE)
        d.polygon([(ax, cy+s(18)), (ax-direction*s(6), cy+s(12)), (ax+direction*s(6), cy+s(12))], fill=ORANGE)
    d.text((cx, cy+s(14)), "x2", fill=ORANGE, anchor="mt")
    save(img, "Var_tools/Animation/scale_anim_timeline.png")

# ─── OBJECTS / PRIMITIVES ──────────────────────────────────────

def icon_tri_cube():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(34)
    hw = s(22)
    # Front face
    front = [(cx-hw, cy-hw), (cx+hw, cy-hw), (cx+hw, cy+hw), (cx-hw, cy+hw)]
    d.polygon(front, fill=None, outline=CYAN, width=s(3))
    # Triangle subdivisions
    d.line([(cx-hw, cy-hw), (cx+hw, cy+hw)], fill=CYAN_L, width=s(2))
    d.line([(cx+hw, cy-hw), (cx-hw, cy+hw)], fill=CYAN_L, width=s(2))
    d.line([(cx, cy-hw), (cx, cy+hw)], fill=CYAN_L, width=s(1))
    d.line([(cx-hw, cy), (cx+hw, cy)], fill=CYAN_L, width=s(1))
    # Top face
    off = s(10)
    d.polygon([(cx-hw, cy-hw), (cx-hw+off, cy-hw-off), (cx+hw+off, cy-hw-off), (cx+hw, cy-hw)], fill=None, outline=ORANGE, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/TriCube.png")

def icon_hex_sphere():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    r = s(28)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=None, outline=CYAN, width=s(3))
    for i in range(6):
        a = math.radians(i*60)
        d.line([(cx, cy), (cx+r*math.cos(a), cy+r*math.sin(a))], fill=CYAN_L, width=s(2))
    ri = s(16)
    hex_pts = [(cx+ri*math.cos(math.radians(i*60-30)), cy+ri*math.sin(math.radians(i*60-30))) for i in range(6)]
    d.polygon(hex_pts, fill=None, outline=ORANGE, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/HexSphere.png")

def icon_diamond_cylinder():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Wireframe cylinder with zigzag pattern - no fill
    ew, eh = s(22), s(8)
    top_y = cy - s(22)
    bot_y = cy + s(22)
    # Side walls
    d.line([(cx-ew, top_y), (cx-ew, bot_y)], fill=CYAN, width=s(3))
    d.line([(cx+ew, top_y), (cx+ew, bot_y)], fill=CYAN, width=s(3))
    # Top ellipse
    d.ellipse([cx-ew, top_y-eh, cx+ew, top_y+eh], fill=None, outline=CYAN, width=s(3))
    # Bottom ellipse
    d.ellipse([cx-ew, bot_y-eh, cx+ew, bot_y+eh], fill=None, outline=ORANGE, width=s(3))
    # Zigzag on the body surface
    n = 5
    step = (ew * 2) // n
    for i in range(n + 1):
        x = cx - ew + step * i
        if i % 2 == 0:
            d.line([(x, top_y + s(4)), (x, bot_y - s(4))], fill=CYAN_L, width=s(1))
        else:
            d.line([(x, top_y + s(4)), (x, bot_y - s(4))], fill=CYAN_L, width=s(1))
    # Horizontal zigzag lines
    for i in range(3):
        y = top_y + s(4) + i * s(6)
        for j in range(n):
            x1 = cx - ew + step * j
            x2 = cx - ew + step * (j + 1)
            if j % 2 == 0:
                d.line([(x1, y), (x2, y + s(3))], fill=CYAN_L, width=s(2))
            else:
                d.line([(x1, y + s(3)), (x2, y)], fill=CYAN_L, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/DiamondCylinder.png")

def icon_tri_torus():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    ro_x, ro_y = s(28), s(22)
    d.ellipse([cx-ro_x, cy-ro_y, cx+ro_x, cy+ro_y], fill=None, outline=CYAN, width=s(3))
    ri_x, ri_y = s(12), s(8)
    d.ellipse([cx-ri_x, cy-ri_y, cx+ri_x, cy+ri_y], fill=None, outline=ORANGE, width=s(3))
    mid_r = (ro_x+ri_x)//2
    mid_ry = (ro_y+ri_y)//2
    for i in range(8):
        a = math.radians(i*45)
        x1 = cx+mid_r*math.cos(a)
        y1 = cy+mid_ry*math.sin(a)
        a2 = math.radians(i*45+22)
        x2 = cx+mid_r*math.cos(a2)
        y2 = cy+mid_ry*math.sin(a2)
        a3 = math.radians(i*45+45)
        x3 = cx+mid_r*math.cos(a3)
        y3 = cy+mid_ry*math.sin(a3)
        d.line([(x1,y1),(x2,y2),(x3,y3)], fill=CYAN_L, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/TriTorus.png")

def icon_brick_plane():
    img = make(); d = ImageDraw.Draw(img)
    bw, bh = s(14), s(7)
    for row in range(5):
        offset = (row%2)*s(7)
        for col in range(5):
            x = s(1)+col*s(14)+offset
            y = s(1)+row*s(12)
            if x+bw < CANVAS-s(1):
                brick_col = ORANGE if row % 2 == 0 else CYAN
                d.rectangle([x, y, x+bw, y+bh], fill=None, outline=brick_col, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/BrickPlane.png")

def icon_molecular_hex_lattice():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    nodes = [(cx+s(20)*math.cos(math.radians(i*60)), cy+s(20)*math.sin(math.radians(i*60))) for i in range(6)]
    nodes.append((cx, cy))
    for i in range(6):
        d.line([nodes[i], nodes[(i+1)%6]], fill=CYAN_D, width=s(3))
        d.line([nodes[i], nodes[6]], fill=CYAN_D, width=s(2))
    for idx, (x, y) in enumerate(nodes):
        r = s(6)
        node_col = ORANGE if idx == 6 else CYAN
        d.ellipse([x-r, y-r, x+r, y+r], fill=node_col, outline=WHITE, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/MolecularHexLattice.png")

def icon_tesseract():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    c30 = math.cos(math.pi / 6)
    s30 = 0.5
    def iso(x, y, z):
        return (cx + (x - z) * c30, cy + (y - x * s30 - z * s30))
    def cube3d(ox, oy, sz):
        v = []
        for i in range(8):
            x = ((i & 1) * 2 - 1) * sz
            y = (((i >> 1) & 1) * 2 - 1) * sz
            z = (((i >> 2) & 1) * 2 - 1) * sz
            v.append(iso(x + ox, y + oy, z))
        return v
    edges_cube = [(0,1),(2,3),(4,5),(6,7),(0,2),(1,3),(4,6),(5,7),(0,4),(1,5),(2,6),(3,7)]
    S = s(14)
    outer = cube3d(0, 0, S)
    inner = cube3d(s(3), s(3), s(7))
    back_edges = [(0,2),(2,6),(6,4),(4,0)]
    side_edges = [(0,1),(2,3),(6,7),(4,5)]
    front_edges = [(1,3),(3,7),(7,5),(5,1)]
    for fi, col in [(back_edges, CYAN_D), (side_edges, CYAN), (front_edges, CYAN_L)]:
        for i, j in fi:
            d.line([outer[i], outer[j]], fill=col, width=s(3))
            d.line([inner[i], inner[j]], fill=ORANGE, width=s(2))
    for j in range(4):
        wt = (j + 2) % 4
        w_avg = (outer[wt][1] + inner[wt][1]) / 2.0
        t = (w_avg - (cy - s(28))) / s(56)
        t = max(0.0, min(1.0, t))
        r = int(CYAN_D[0] * (1 - t) + CYAN_L[0] * t)
        g = int(CYAN_D[1] * (1 - t) + CYAN_L[1] * t)
        b = int(CYAN_D[2] * (1 - t) + CYAN_L[2] * t)
        d.line([outer[wt], inner[wt]], fill=(r, g, b, 255), width=s(2))
    for v in outer:
        r = s(3)
        d.ellipse([v[0]-r, v[1]-r, v[0]+r, v[1]+r], fill=CYAN, outline=WHITE, width=s(1))
    for v in inner:
        r = s(2)
        d.ellipse([v[0]-r, v[1]-r, v[0]+r, v[1]+r], fill=ORANGE, outline=WHITE, width=s(1))
    save(img, "Var_tools/Objects/Primitivs/Tesseract.png")

def icon_diamond():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Diamond top view - octagonal brilliant cut
    r = s(26)
    # Outer octagon
    pts = []
    for i in range(8):
        a = math.radians(i * 45 - 22.5)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=None, outline=CYAN, width=s(4))
    # Inner star facets
    ri = s(14)
    for i in range(8):
        a = math.radians(i * 45)
        d.line([(cx + ri * math.cos(a), cy + ri * math.sin(a)),
                (cx + r * math.cos(a - math.radians(22.5)), cy + r * math.sin(a - math.radians(22.5)))],
               fill=CYAN_L, width=s(2))
        d.line([(cx + ri * math.cos(a), cy + ri * math.sin(a)),
                (cx + r * math.cos(a + math.radians(22.5)), cy + r * math.sin(a + math.radians(22.5)))],
               fill=CYAN_L, width=s(2))
    # Center table
    d.ellipse([cx-s(6), cy-s(6), cx+s(6), cy+s(6)], fill=None, outline=ORANGE, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/Diamond.png")

def icon_terrain():
    img = make(); d = ImageDraw.Draw(img)
    step = s(11)
    for gy in range(5):
        for gx in range(6):
            x = s(1)+gx*step
            y = s(1)+gy*step
            h = math.sin(gx*0.8)*math.cos(gy*0.6)*s(4)
            if x+s(10) < CANVAS and y+step+h < CANVAS:
                d.rectangle([x, y+h, x+s(10), y+step+h], fill=None, outline=CYAN, width=s(1))
    d.line([(s(4), s(36)), (s(16), s(12)), (s(28), s(28)), (s(40), s(4)), (s(56), s(20))], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Objects/Primitivs/Terrain.png")

def icon_pipe_network():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    pw = s(5)
    d.line([(s(8), cy), (s(56), cy)], fill=CYAN, width=pw)
    d.line([(cx, s(8)), (cx, s(56))], fill=CYAN, width=pw)
    d.line([(s(12), s(12)), (s(52), s(12))], fill=CYAN_D, width=s(4))
    d.line([(s(12), s(52)), (s(52), s(52))], fill=CYAN_D, width=s(4))
    for x, y in [(cx, cy), (s(12), s(12)), (s(52), s(12)), (s(12), s(52)), (s(52), s(52))]:
        r = s(5)
        joint_col = ORANGE if x == cx and y == cy else CYAN_L
        d.ellipse([x-r, y-r, x+r, y+r], fill=joint_col, outline=CYAN, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/PipeNetwork.png")

def icon_spring_coil():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    coils = 5
    w, h = s(16), s(28)
    points = []
    for i in range(coils*30+1):
        t = i/(coils*30)
        x = cx + w*math.cos(t*coils*2*math.pi)
        y = cy - h + t*2*h
        points.append((x, y))
    for i in range(len(points)-1):
        t = i/len(points)
        r = int(CYAN[0]*(1-t)+CYAN_L[0]*t)
        g = int(CYAN[1]*(1-t)+CYAN_L[1]*t)
        b = int(CYAN[2]*(1-t)+CYAN_L[2]*t)
        d.line([points[i], points[i+1]], fill=(r,g,b,255), width=s(3))
    save(img, "Var_tools/Objects/Primitivs/SpringCoil.png")

def icon_wireframe_cube():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    fs = s(20)
    front = [(cx-fs, cy-fs), (cx+fs, cy-fs), (cx+fs, cy+fs), (cx-fs, cy+fs)]
    d.polygon(front, fill=None, outline=CYAN, width=s(3))
    off = s(10)
    back = [(x+off, y-off) for x, y in front]
    d.polygon(back, fill=None, outline=ORANGE, width=s(3))
    for i in range(4):
        d.line([front[i], back[i]], fill=CYAN_L, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/WireframeCube.png")

def icon_torus_knot():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    points = []
    for i in range(300):
        t = 2*math.pi*i/300
        r = s(22)+s(8)*math.cos(3*t)
        x = cx + r*math.cos(t)
        y = cy + r*math.sin(t)*0.7
        points.append((x, y))
    for i in range(len(points)-1):
        t = i/len(points)
        alpha = int(180+75*math.sin(t*4*math.pi))
        seg_col = ORANGE if i % 30 < 10 else (CYAN[0], CYAN[1], CYAN[2], alpha)
        d.line([points[i], points[i+1]], fill=seg_col, width=s(4))
    save(img, "Var_tools/Objects/Primitivs/TorusKnot.png")

def icon_archimedean_solid():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    r = s(26)
    n = 12
    pts = [(cx+r*math.cos(math.radians(i*360/n)), cy+r*math.sin(math.radians(i*360/n))) for i in range(n)]
    d.polygon(pts, fill=None, outline=CYAN, width=s(3))
    for i in range(0, n, 2):
        d.line([pts[i], pts[(i+3)%n]], fill=CYAN_L, width=s(2))
    for i in range(1, n, 2):
        d.line([pts[i], pts[(i+3)%n]], fill=ORANGE, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/ArchimedeanSolid.png")

def icon_geodesic_dome():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(36)
    r = s(28)
    d.arc([cx-r, cy-r, cx+r, cy+r], 0, 360, fill=CYAN, width=s(3))
    for i in range(1, 4):
        ry = r*i//4
        rx = int(math.sqrt(max(1, r*r-ry*ry)))
        d.arc([cx-rx, cy-ry, cx+rx, cy+ry], 0, 180, fill=CYAN_L, width=s(2))
    for i in range(-2, 3):
        offset = i*s(10)
        d.line([(cx+offset, cy), (cx+offset//2, cy-r)], fill=CYAN_D, width=s(2))
    d.line([(cx-r, cy), (cx+r, cy)], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Objects/Primitivs/GeodesicDome.png")

def icon_sierpinski_carpet():
    img = make(); d = ImageDraw.Draw(img)
    def draw_carpet(x, y, size, depth):
        if depth == 0:
            d.rectangle([x, y, x+size, y+size], fill=None, outline=CYAN, width=s(1))
            return
        third = size // 3
        for i in range(3):
            for j in range(3):
                if i == 1 and j == 1:
                    d.rectangle([x+third, y+third, x+2*third, y+2*third], fill=ORANGE, outline=CYAN, width=s(1))
                else:
                    draw_carpet(x+i*third, y+j*third, third, depth-1)
    draw_carpet(s(2), s(2), s(60), 2)
    save(img, "Var_tools/Objects/Primitivs/SierpinskiCarpet.png")

def icon_sierpinski_tetrahedron():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    def draw_tri(x1, y1, x2, y2, x3, y3, depth):
        if depth == 0:
            tri_col = ORANGE if y1 < cy - s(10) else CYAN
            d.polygon([(x1,y1),(x2,y2),(x3,y3)], fill=None, outline=tri_col, width=s(2))
            return
        mx1,my1 = (x1+x2)//2,(y1+y2)//2
        mx2,my2 = (x2+x3)//2,(y2+y3)//2
        mx3,my3 = (x1+x3)//2,(y1+y3)//2
        draw_tri(x1,y1,mx1,my1,mx3,my3,depth-1)
        draw_tri(mx1,my1,x2,y2,mx2,my2,depth-1)
        draw_tri(mx3,my3,mx2,my2,x3,y3,depth-1)
    h = s(56)
    draw_tri(cx, cy-h//2, cx-h//2, cy+h//2, cx+h//2, cy+h//2, 3)
    save(img, "Var_tools/Objects/Primitivs/SierpinskiTetrahedron.png")

def icon_menger_sponge():
    img = make(); d = ImageDraw.Draw(img)
    def draw_menger(x, y, size, depth):
        if depth == 0:
            d.rectangle([x, y, x+size, y+size], fill=CYAN_D, outline=CYAN, width=s(1))
            return
        third = size // 3
        for i in range(3):
            for j in range(3):
                if i == 1 and j == 1:
                    d.rectangle([x+third, y+third, x+2*third, y+2*third], fill=BG, outline=ORANGE, width=s(1))
                else:
                    draw_menger(x+i*third, y+j*third, third, depth-1)
    draw_menger(s(2), s(2), s(60), 2)
    save(img, "Var_tools/Objects/Primitivs/MengerSponge.png")

def icon_crystal_lattice():
    img = make(); d = ImageDraw.Draw(img)
    step = s(18)
    for i in range(4):
        for j in range(4):
            x = s(2)+i*step
            y = s(2)+j*step
            r = s(3)
            d.ellipse([x-r, y-r, x+r, y+r], fill=CYAN)
            if i < 3:
                d.line([(x, y), (x+step, y)], fill=CYAN_D, width=s(2))
            if j < 3:
                d.line([(x, y), (x, y+step)], fill=CYAN_D, width=s(2))
            if i < 3 and j < 3:
                d.line([(x, y), (x+step, y+step)], fill=ORANGE, width=s(1))
    save(img, "Var_tools/Objects/Primitivs/CrystalLattice.png")

def icon_helicoid():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    for i in range(50):
        t = i/50*2*math.pi
        y = cy-s(28)+i*s(1)
        r = s(22)*abs(math.sin(t))
        x_off = s(22)*math.cos(t)
        d.line([(cx-r, y), (cx+r, y)], fill=CYAN, width=s(2))
        d.line([(cx+x_off, y), (cx+x_off, y+s(1))], fill=ORANGE, width=s(1))
    save(img, "Var_tools/Objects/Primitivs/Helicoid.png")

def icon_enneper_surface():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    for i in range(-10, 11):
        points = []
        for j in range(-10, 11):
            u, v = i*0.25, j*0.25
            x = cx + s(2)*(u - u**3/3 + u*v**2)
            y = cy + s(2)*(v - v**3/3 + v*u**2)
            points.append((x, y))
        for k in range(len(points)-1):
            t = (i+10)/20
            alpha = int(120+135*t)
            line_col = ORANGE if i == 0 else (CYAN[0],CYAN[1],CYAN[2],alpha)
            d.line([points[k], points[k+1]], fill=line_col, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/EnneperSurface.png")

def icon_klein_bottle():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    points = []
    for i in range(300):
        t = 2*math.pi*i/300
        x = cx + s(22)*(2*math.cos(t)+math.cos(2*t))
        y = cy + s(16)*math.sin(2*t)
        points.append((x, y))
    for i in range(len(points)-1):
        t = i/len(points)
        alpha = int(150+105*math.sin(t*2*math.pi))
        seg_col = ORANGE if 0.2 < t < 0.4 else (CYAN[0],CYAN[1],CYAN[2],alpha)
        d.line([points[i], points[i+1]], fill=seg_col, width=s(3))
    save(img, "Var_tools/Objects/Primitivs/KleinBottle.png")

def icon_mobius_strip():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    top, bot = [], []
    for i in range(300):
        t = 2*math.pi*i/300
        r = s(24)
        twist = t/2
        x = cx + r*math.cos(t)
        y = cy + r*math.sin(t)*0.5
        w = s(6)*math.cos(twist)
        top.append((x+w*math.cos(t), y+w*math.sin(t)*0.5))
        bot.append((x-w*math.cos(t), y-w*math.sin(t)*0.5))
    for i in range(len(top)-1):
        t = i/len(top)
        alpha = int(150+105*math.sin(t*2*math.pi))
        twist_col = ORANGE if 0.4 < t < 0.6 else (CYAN[0],CYAN[1],CYAN[2],alpha)
        d.line([top[i], top[i+1]], fill=twist_col, width=s(2))
        d.line([bot[i], bot[i+1]], fill=(CYAN_D[0],CYAN_D[1],CYAN_D[2],alpha), width=s(2))
    save(img, "Var_tools/Objects/Primitivs/MobiusStrip.png")

def icon_penrose_tiling():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    size = s(16)
    for row in range(-2, 3):
        for col in range(-2, 3):
            x = cx + col*size + (row%2)*size//2
            y = cy + row*int(size*0.85)
            color = ORANGE if (row+col)%3 == 0 else CYAN_D
            pts = [(x, y-size//2), (x+size//2, y), (x, y+size//2), (x-size//2, y)]
            d.polygon(pts, fill=None, outline=color, width=s(2))
    save(img, "Var_tools/Objects/Primitivs/PenroseTiling3D.png")

# ─── XPRESSO ───────────────────────────────────────────────────

def icon_hierarchy_filter():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(28)
    nodes = [(cx, s(6)), (cx-s(18), s(22)), (cx+s(18), s(22)),
             (cx-s(26), s(38)), (cx-s(10), s(38)), (cx+s(10), s(38)), (cx+s(26), s(38))]
    lines = [(0,1),(0,2),(1,3),(1,4),(2,5),(2,6)]
    for a, b in lines:
        d.line([nodes[a], nodes[b]], fill=CYAN_D, width=s(2))
    for x, y in nodes:
        r = s(5)
        d.ellipse([x-r, y-r, x+r, y+r], fill=CYAN, outline=WHITE, width=s(2))
    fx, fy, fr = cx+s(20), cy+s(22), s(8)
    d.ellipse([fx-fr, fy-fr, fx+fr, fy+fr], fill=None, outline=ORANGE, width=s(3))
    d.line([(fx+fr, fy+fr), (fx+fr*2, fy+fr*2)], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Objects/XPressos_objects/HierarchyFilter.png")

# ─── TAGS ──────────────────────────────────────────────────────

def icon_child_selector_tag():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Dropdown selector - clean professional look
    # Main box
    d.rounded_rectangle([s(4), s(4), s(60), s(24)], radius=s(4), fill=CYAN_D, outline=CYAN, width=s(3))
    # Dropdown arrow (chevron down)
    d.line([(cx-s(4), s(12)), (cx, s(18))], fill=ORANGE, width=s(3))
    d.line([(cx, s(18)), (cx+s(4), s(12))], fill=ORANGE, width=s(3))
    # List items below
    for i, y in enumerate([s(30), s(42), s(54)]):
        d.rounded_rectangle([s(8), y-s(4), s(56), y+s(4)], radius=s(2), fill=None, outline=CYAN_L, width=s(2))
        # Dot indicators
        d.ellipse([s(14)-s(2), y-s(2), s(14)+s(2), y+s(2)], fill=CYAN_L)
    save(img, "Var_tools/Tegs/ChildSelectorTeg.png")

def icon_target_camera():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Camera body - classic DSLR shape
    bw, bh = s(48), s(30)
    bx, by = cx - bw//2, cy - bh//2
    d.rounded_rectangle([bx, by, bx+bw, by+bh], radius=s(5), fill=CYAN_D, outline=CYAN, width=s(3))
    # Grip on right side
    d.rounded_rectangle([bx+bw-s(10), by+s(4), bx+bw+s(2), by+bh-s(4)], radius=s(3), fill=CYAN_D, outline=CYAN, width=s(2))
    # Lens barrel - multiple concentric circles for depth
    lx = bx + s(18)
    for ri, ro, col in [(s(14), s(16), CYAN), (s(11), s(13), CYAN_L), (s(8), s(10), CYAN)]:
        d.ellipse([lx-ro, cy-ro, lx+ro, cy+ro], fill=None, outline=col, width=s(2))
    # Lens glass - filled
    d.ellipse([lx-s(7), cy-s(7), lx+s(7), cy+s(7)], fill=CYAN_D, outline=CYAN_L, width=s(2))
    d.ellipse([lx-s(4), cy-s(4), lx+s(4), cy+s(4)], fill=CYAN_L)
    d.ellipse([lx-s(2), cy-s(2), lx+s(2), cy+s(2)], fill=WHITE)
    # Viewfinder hump on top
    d.rounded_rectangle([bx+s(10), by-s(8), bx+s(26), by+s(2)], radius=s(3), fill=CYAN_D, outline=CYAN, width=s(2))
    # Flash hot shoe on top
    d.rectangle([bx+s(12), by-s(10), bx+s(24), by-s(8)], fill=CYAN)
    # Shutter button
    d.ellipse([bx+bw-s(14), by-s(4), bx+bw-s(8), by+s(2)], fill=ORANGE, outline=WHITE, width=s(2))
    save(img, "Var_tools/Tegs/TargetCamera.png")

def icon_target_camera_tag():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Crosshair/target - fills entire canvas
    r = s(26)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=None, outline=CYAN, width=s(3))
    ri = s(18)
    d.ellipse([cx-ri, cy-ri, cx+ri, cy+ri], fill=None, outline=CYAN_L, width=s(2))
    rii = s(10)
    d.ellipse([cx-rii, cy-rii, cx+rii, cy+rii], fill=None, outline=CYAN_D, width=s(2))
    # Cross lines
    d.line([(cx, cy-r), (cx, cy+r)], fill=CYAN, width=s(2))
    d.line([(cx-r, cy), (cx+r, cy)], fill=CYAN, width=s(2))
    # Center dot
    d.ellipse([cx-s(3), cy-s(3), cx+s(3), cy+s(3)], fill=ORANGE)
    save(img, "Var_tools/Tegs/TargetCameraTag.png")

def icon_camera_visibility_tag():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Eye with visibility toggle
    # Eye shape
    ew, eh = s(26), s(16)
    d.ellipse([cx-ew, cy-eh, cx+ew, cy+eh], fill=None, outline=CYAN, width=s(3))
    # Iris
    ir = s(10)
    d.ellipse([cx-ir, cy-ir, cx+ir, cy+ir], fill=None, outline=CYAN_L, width=s(3))
    # Pupil
    pr = s(4)
    d.ellipse([cx-pr, cy-pr, cx+pr, cy+pr], fill=ORANGE)
    # Slash (visibility off)
    d.line([(cx-ew-s(2), cy+eh+s(2)), (cx+ew+s(2), cy-eh-s(2))], fill=RED_L, width=s(3))
    save(img, "Var_tools/Tegs/CameraVisibilityTag.png")

# ─── DEFORMERS ─────────────────────────────────────────────────

def icon_poly_subdivide():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Large polygon being subdivided into smaller pieces
    # Main polygon - large quad
    pts = [(cx-s(26), cy-s(20)), (cx+s(26), cy-s(14)), (cx+s(22), cy+s(20)), (cx-s(22), cy+s(16))]
    d.polygon(pts, fill=None, outline=CYAN, width=s(3))
    # Subdivision lines - dividing into 4 sub-polygons
    mx1 = ((pts[0][0]+pts[1][0])//2, (pts[0][1]+pts[1][1])//2)
    mx2 = ((pts[2][0]+pts[3][0])//2, (pts[2][1]+pts[3][1])//2)
    my1 = ((pts[0][0]+pts[3][0])//2, (pts[0][1]+pts[3][1])//2)
    my2 = ((pts[1][0]+pts[2][0])//2, (pts[1][1]+pts[2][1])//2)
    d.line([mx1, mx2], fill=CYAN_L, width=s(2))
    d.line([my1, my2], fill=CYAN_L, width=s(2))
    # Diagonal subdivision lines
    center = (cx, cy)
    for p in pts:
        d.line([center, p], fill=ORANGE, width=s(1))
    save(img, "Var_tools/Deformers/PolySubdivide.png")

# ─── AXIS ──────────────────────────────────────────────────────

def icon_axis2bottom():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(26)
    s2 = s(18)
    d.rectangle([cx-s2, cy-s2, cx+s2, cy+s2], fill=None, outline=CYAN, width=s(3))
    d.line([(cx, cy-s(22)), (cx, cy)], fill=GRAY_L, width=s(2))
    d.line([(cx, cy-s(22)), (cx+s(22), cy-s(22))], fill=GRAY_L, width=s(2))
    new_y = cy+s2
    d.line([(cx, new_y), (cx, new_y+s(12))], fill=ORANGE, width=s(3))
    d.line([(cx, new_y), (cx+s(12), new_y)], fill=ORANGE, width=s(3))
    d.polygon([(cx, new_y+s(12)), (cx-s(4), new_y+s(6)), (cx+s(4), new_y+s(6))], fill=ORANGE)
    save(img, "Var_tools/Tools/Axis/Axis2Bottom.png")

def icon_axis2center():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    s2 = s(18)
    d.rectangle([cx-s2, cy-s2, cx+s2, cy+s2], fill=None, outline=CYAN, width=s(3))
    d.line([(cx, cy-s(22)), (cx, cy+s(22))], fill=ORANGE, width=s(3))
    d.line([(cx-s(22), cy), (cx+s(22), cy)], fill=ORANGE, width=s(3))
    d.ellipse([cx-s(4), cy-s(4), cx+s(4), cy+s(4)], fill=ORANGE)
    save(img, "Var_tools/Tools/Axis/Axis2Center.png")

def icon_axis_drop():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(26)
    s2 = s(18)
    d.rectangle([cx-s2, cy-s2, cx+s2, cy+s2], fill=None, outline=CYAN, width=s(3))
    d.line([(cx, cy-s(22)), (cx, cy)], fill=GRAY_L, width=s(2))
    d.line([(cx, cy-s(22)), (cx+s(22), cy-s(22))], fill=GRAY_L, width=s(2))
    d.line([(cx, cy-s(6)), (cx, cy+s2+s(8))], fill=ORANGE, width=s(3))
    d.polygon([(cx, cy+s2+s(8)), (cx-s(4), cy+s2+s(2)), (cx+s(4), cy+s2+s(2))], fill=ORANGE)
    save(img, "Var_tools/Tools/Axis/Axis_Droppng.png")

# ─── LOCATION ──────────────────────────────────────────────────

def icon_drop2floor():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(22)
    s2 = s(14)
    d.rectangle([cx-s2, cy-s2, cx+s2, cy+s2], fill=None, outline=CYAN, width=s(3))
    floor_y = cy+s2+s(10)
    d.line([(s(4), floor_y), (s(60), floor_y)], fill=GREEN, width=s(3))
    d.line([(cx, cy+s2+s(2)), (cx, floor_y-s(3))], fill=ORANGE, width=s(3))
    d.polygon([(cx, floor_y-s(3)), (cx-s(4), floor_y-s(9)), (cx+s(4), floor_y-s(9))], fill=ORANGE)
    save(img, "Var_tools/Tools/Location/Drop2Floor.png")

def icon_drop2floor_0():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(22)
    s2 = s(14)
    d.rectangle([cx+s(6)-s2, cy-s2, cx+s(6)+s2, cy+s2], fill=None, outline=CYAN, width=s(3))
    floor_y = cy+s2+s(10)
    d.line([(s(4), floor_y), (s(60), floor_y)], fill=GREEN, width=s(3))
    d.line([(cx+s(6), cy+s2+s(2)), (cx+s(6), floor_y-s(3))], fill=ORANGE, width=s(3))
    d.polygon([(cx+s(6), floor_y-s(3)), (cx+s(2), floor_y-s(9)), (cx+s(10), floor_y-s(9))], fill=ORANGE)
    d.line([(s(22), floor_y-s(12)), (s(22), floor_y+s(8))], fill=YELLOW, width=s(2))
    d.line([(s(42), floor_y-s(12)), (s(42), floor_y+s(8))], fill=YELLOW, width=s(2))
    save(img, "Var_tools/Tools/Location/Drop2Floor_0.png")

def icon_center2parent():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    ps = s(24)
    d.rectangle([cx-ps, cy-ps, cx+ps, cy+ps], fill=None, outline=CYAN_D, width=s(3))
    cs = s(12)
    ccx, ccy = cx+s(12), cy+s(12)
    d.rectangle([ccx-cs, ccy-cs, ccx+cs, ccy+cs], fill=None, outline=CYAN, width=s(3))
    d.line([(ccx, ccy), (cx, cy)], fill=ORANGE, width=s(3))
    d.ellipse([cx-s(4), cy-s(4), cx+s(4), cy+s(4)], fill=ORANGE)
    save(img, "Var_tools/Tools/Location/Center2Parent.png")

def icon_center2world():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    s2 = s(14)
    d.rectangle([cx+s(6)-s2, cy-s2, cx+s(6)+s2, cy+s2], fill=None, outline=CYAN, width=s(3))
    d.line([(s(4), cy), (s(60), cy)], fill=GRAY, width=s(2))
    d.line([(cx, s(4)), (cx, s(60))], fill=GRAY, width=s(2))
    d.line([(cx+s(6), cy), (cx, cy)], fill=ORANGE, width=s(3))
    d.ellipse([cx-s(3), cy-s(3), cx+s(3), cy+s(3)], fill=ORANGE)
    d.line([(s(6), s(6)), (s(14), s(6))], fill=RED_L, width=s(3))
    d.line([(s(6), s(6)), (s(6), s(14))], fill=GREEN, width=s(3))
    save(img, "Var_tools/Tools/Location/Center2World.png")

# ─── CLEAN ─────────────────────────────────────────────────────

def _draw_mat_sphere(d, cx, cy, r, filled=True):
    """Draw C4D-style material sphere with gradient effect."""
    if filled:
        # Gradient sphere - concentric circles getting lighter toward center
        colors = [CYAN_D, CYAN_D, CYAN, CYAN, CYAN_L]
        for i, c in enumerate(colors):
            ri = r - i * s(2)
            if ri > 0:
                d.ellipse([cx-ri, cy-ri, cx+ri, cy+ri], fill=c)
        # Highlight
        d.ellipse([cx-s(6), cy-s(8), cx+s(2), cy-s(2)], fill=CYAN_L)
    else:
        # Empty sphere outline
        d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=None, outline=CYAN, width=s(3))
        d.arc([cx-r, cy-r, cx+r, cy+r], 200, 340, fill=CYAN_L, width=s(2))

def _draw_polygon_c4d(d, cx, cy, size, fill=None, outline=CYAN, width=3):
    """Draw C4D-style polygon: triangle with 3 node circles at vertices."""
    h = size
    pts = [(cx, cy - h*2//3), (cx - h//2, cy + h//3), (cx + h//2, cy + h//3)]
    d.polygon(pts, fill=fill, outline=outline, width=s(width))
    # Node circles at vertices
    for px, py in pts:
        r = s(4)
        d.ellipse([px-r, py-r, px+r, py+r], fill=CYAN, outline=WHITE, width=s(1))

def icon_clean_nulls():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(30)
    # Null = filled dot. Multiple nulls with X = delete all nulls
    # Draw 3 null dots (small filled circles)
    for dx, dy in [(-s(12), -s(8)), (s(0), s(8)), (s(12), -s(8))]:
        r = s(7)
        d.ellipse([cx+dx-r, cy+dy-r, cx+dx+r, cy+dy+r], fill=CYAN, outline=CYAN, width=s(2))
    # Small X bottom-right
    xk, yk = s(50), s(52)
    d.line([(xk-s(8), yk-s(8)), (xk+s(8), yk+s(8))], fill=ORANGE, width=s(3))
    d.line([(xk+s(8), yk-s(8)), (xk-s(8), yk+s(8))], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Tools/Clean/Clean_Nulls.png")

def icon_clean_empty_nulls():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(30)
    # Empty nulls = hollow circles (no children, no tags)
    for dx, dy in [(-s(12), -s(8)), (s(0), s(8)), (s(12), -s(8))]:
        r = s(7)
        d.ellipse([cx+dx-r, cy+dy-r, cx+dx+r, cy+dy+r], fill=None, outline=CYAN, width=s(2))
    # Small X bottom-right
    xk, yk = s(50), s(52)
    d.line([(xk-s(8), yk-s(8)), (xk+s(8), yk+s(8))], fill=ORANGE, width=s(3))
    d.line([(xk+s(8), yk-s(8)), (xk-s(8), yk+s(8))], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Tools/Clean/Clean_EmptyNulls.png")

def icon_clean_objects():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Big polygon (triangle with nodes)
    _draw_polygon_c4d(d, cx, cy, s(26), fill=CYAN_D)
    # Small X bottom-right
    xk, yk = s(52), s(52)
    d.line([(xk-s(8), yk-s(8)), (xk+s(8), yk+s(8))], fill=ORANGE, width=s(3))
    d.line([(xk+s(8), yk-s(8)), (xk-s(8), yk+s(8))], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Tools/Clean/Clean_Objects.png")

def icon_clean_empty_objects():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Big polygon outline (no fill = empty)
    _draw_polygon_c4d(d, cx, cy, s(26), fill=None, outline=CYAN_D, width=2)
    # Small X bottom-right
    xk, yk = s(52), s(52)
    d.line([(xk-s(8), yk-s(8)), (xk+s(8), yk+s(8))], fill=ORANGE, width=s(3))
    d.line([(xk+s(8), yk-s(8)), (xk-s(8), yk+s(8))], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Tools/Clean/Clean_EmptyObjects.png")

def icon_clean_all_tags():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Multiple tags (rounded rects)
    for i, dy in enumerate([-s(10), s(0), s(10)]):
        x, y = cx-s(20), cy+dy-s(5)
        d.rounded_rectangle([x, y, x+s(36), y+s(10)], radius=s(2), fill=CYAN_D, outline=CYAN, width=s(2))
    # Small X bottom-right
    xk, yk = s(52), s(52)
    d.line([(xk-s(8), yk-s(8)), (xk+s(8), yk+s(8))], fill=ORANGE, width=s(3))
    d.line([(xk+s(8), yk-s(8)), (xk-s(8), yk+s(8))], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Tools/Clean/Clean_allTags.png")

def icon_clean_select_tags():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Single tag type with arrow (select matching type)
    x, y = cx-s(22), cy-s(8)
    d.rounded_rectangle([x, y, x+s(36), y+s(16)], radius=s(3), fill=CYAN_D, outline=CYAN, width=s(3))
    # Arrow right
    d.line([(cx+s(18), cy), (cx+s(28), cy)], fill=ORANGE, width=s(3))
    d.polygon([(cx+s(24), cy-s(4)), (cx+s(24), cy+s(4)), (cx+s(30), cy)], fill=ORANGE)
    save(img, "Var_tools/Tools/Clean/Clean_SelectTags.png")

def icon_clean_empty_mat_tags():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Empty material sphere (no material)
    r = s(22)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=None, outline=CYAN, width=s(3))
    # Highlight arc
    d.arc([cx-r, cy-r, cx+r, cy+r], 200, 340, fill=CYAN_L, width=s(2))
    # Small X bottom-right
    xk, yk = s(52), s(52)
    d.line([(xk-s(8), yk-s(8)), (xk+s(8), yk+s(8))], fill=ORANGE, width=s(3))
    d.line([(xk+s(8), yk-s(8)), (xk-s(8), yk+s(8))], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Tools/Clean/Clean_Empty_MatTags.png")

def icon_clean_select_mat_tags():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Filled material sphere
    _draw_mat_sphere(d, cx, cy, s(22), filled=True)
    # Small X bottom-right
    xk, yk = s(52), s(52)
    d.line([(xk-s(8), yk-s(8)), (xk+s(8), yk+s(8))], fill=ORANGE, width=s(3))
    d.line([(xk+s(8), yk-s(8)), (xk-s(8), yk+s(8))], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Tools/Clean/Clean_Select_MatTags.png")

def icon_clean_empty_polys():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(32)
    # Polygon mesh grid with a hole in the center (empty polys = polygon object with no polygons)
    # Draw a grid of small quads representing a mesh
    step = s(10)
    for gy in range(5):
        for gx in range(5):
            x = s(4) + gx * step
            y = s(4) + gy * step
            # Skip center area to show the "empty" hole
            if gx in [2] and gy in [2]:
                continue
            d.rectangle([x, y, x+step-s(1), y+step-s(1)], fill=None, outline=CYAN_D, width=s(1))
    # Small orange X bottom-right
    xk, yk = s(52), s(52)
    d.line([(xk-s(8), yk-s(8)), (xk+s(8), yk+s(8))], fill=ORANGE, width=s(3))
    d.line([(xk+s(8), yk-s(8)), (xk-s(8), yk+s(8))], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Tools/Clean/CleanEmptyPolys.png")

def icon_clean_animation_keys():
    img = make(); d = ImageDraw.Draw(img)
    cx, cy = s(32), s(30)
    # Timeline bar
    d.rounded_rectangle([s(4), cy-s(6), s(56), cy+s(6)], radius=s(3), fill=GRAY_D, outline=CYAN, width=s(2))
    # Keyframes (diamond shapes) on the timeline
    for x in [s(14), s(26), s(38)]:
        pts = [(x, cy-s(5)), (x+s(3), cy), (x, cy+s(5)), (x-s(3), cy)]
        d.polygon(pts, fill=ORANGE, outline=ORANGE, width=s(1))
    # Small X bottom-right
    xk, yk = s(52), s(52)
    d.line([(xk-s(8), yk-s(8)), (xk+s(8), yk+s(8))], fill=ORANGE, width=s(3))
    d.line([(xk+s(8), yk-s(8)), (xk-s(8), yk+s(8))], fill=ORANGE, width=s(3))
    save(img, "Var_tools/Tools/Clean/Clean_AnimationKeys.png")

# ─── MAIN ──────────────────────────────────────────────────────

def main():
    print("Generating 64x64 icons -> ico/ ...")
    funcs = [
        icon_camera_resolution, icon_cloud_wizard, icon_floor_generator,
        icon_object_renamer, icon_snapshot, icon_selection_set_plugin,
        icon_selection_set_tag, icon_var_tools, icon_about,
        icon_shift_anim, icon_scale_anim, icon_tri_cube, icon_hex_sphere,
        icon_diamond_cylinder, icon_tri_torus, icon_brick_plane,
        icon_molecular_hex_lattice, icon_tesseract, icon_diamond, icon_terrain,
        icon_pipe_network, icon_spring_coil, icon_wireframe_cube, icon_torus_knot,
        icon_archimedean_solid, icon_geodesic_dome, icon_sierpinski_carpet,
        icon_sierpinski_tetrahedron, icon_menger_sponge, icon_crystal_lattice,
        icon_helicoid, icon_enneper_surface, icon_klein_bottle, icon_mobius_strip,
        icon_penrose_tiling, icon_hierarchy_filter, icon_child_selector_tag,
        icon_target_camera, icon_target_camera_tag, icon_camera_visibility_tag,
        icon_poly_subdivide, icon_axis2bottom, icon_axis2center, icon_axis_drop,
        icon_drop2floor, icon_drop2floor_0, icon_center2parent, icon_center2world,
        icon_clean_nulls, icon_clean_empty_nulls, icon_clean_objects,
        icon_clean_empty_objects, icon_clean_all_tags, icon_clean_select_tags,
        icon_clean_empty_mat_tags, icon_clean_select_mat_tags, icon_clean_empty_polys,
        icon_clean_animation_keys,
    ]
    for fn in funcs:
        fn()

    # Write base64.txt
    b64_path = os.path.join(ICO_NEW, "base64.txt")
    with open(b64_path, "w", encoding="utf-8") as f:
        for i, (name, b64) in enumerate(B64_DATA):
            if i > 0:
                f.write("\n")
            f.write(f'{name}:\n{b64}\n')
    print(f"\nDone! {len(funcs)} icons + base64.txt generated in {ICO_NEW}")

if __name__ == "__main__":
    main()
