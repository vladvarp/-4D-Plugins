# -*- coding: utf-8 -*-
"""
Tessera — Cinema 4D ObjectData Plugin v1.0.1
============================================
Процедурная облицовка любой плоскости: пол, стена, потолок.
Работает без дочернего объекта (свой размер). Дочерний полигон —
опциональный контур с отверстиями.

Не копия Floor Generator / 3ds Max Floor Generator:
  • 13 раскладок, включая plank с рандомной длиной, english bond,
    basket, windmill, versailles, chevron, fish scale
  • режим Keep Intact — резать плитки по контуру или отбрасывать обрезанные
  • подложка (substrate) + зазор шва как реальная конструкция
  • jitter высоты/угла, N групп материалов (теги MAT_1..)
  • рамка (border) по периметру

ID плагина: 1071751
"""
import c4d  # type: ignore
import math
import random
import os
import base64
import tempfile

PLUGIN_ID = 1071751
PLUGIN_VER = "v1.0.1"
PLUGIN_NAME = "Tessera"
PLUGIN_HELP = "Процедурная облицовка: пол, стена, потолок — 13 раскладок, подложка, материалы"

MAX_TILES = 14000

# ── Паттерны ──────────────────────────────────────────────────────────────────
PAT_PLANK      = 0
PAT_RUNNING    = 1
PAT_STACK      = 2
PAT_THIRD      = 3
PAT_ENGLISH    = 4
PAT_HERRING    = 5
PAT_CHEVRON    = 6
PAT_BASKET     = 7
PAT_WINDMILL   = 8
PAT_VERSAILLES = 9
PAT_HEX        = 10
PAT_DIAMOND    = 11
PAT_SCALE      = 12

PAT_NAMES = [
    "Plank (рандом длина)",
    "Running Bond",
    "Stack Bond",
    "1/3 Bond",
    "English Bond",
    "Herringbone 90",
    "Chevron",
    "Basket Weave",
    "Windmill",
    "Versailles",
    "Hex",
    "Diamond",
    "Fish Scale",
]

SURF_FLOOR   = 0
SURF_WALL    = 1
SURF_CEILING = 2

# ── Description IDs ───────────────────────────────────────────────────────────
G_SURF, G_PAT, G_GEO, G_VAR, G_UV, G_MAT = 2000, 2001, 2002, 2003, 2004, 2005

TS_SURFACE  = 2100
TS_SIZE_A   = 2101
TS_SIZE_B   = 2102
TS_USE_CHILD = 2103

TS_PATTERN  = 2200
TS_LEN      = 2201
TS_WID      = 2202
TS_ANGLE    = 2203
TS_OFF_U    = 2204
TS_OFF_V    = 2205
TS_BOND     = 2206
TS_LEN_VAR  = 2207
TS_SEED     = 2208
TS_KEEP     = 2209
TS_BORDER   = 2210

TS_THICK    = 2300
TS_BEVEL    = 2301
TS_SEAM     = 2302
TS_UNDERLAY = 2303

TS_H_JIT    = 2400
TS_YAW_JIT  = 2401

TS_UV_U     = 2500
TS_UV_V     = 2501
TS_UV_ROT   = 2502
TS_UV_RAND  = 2503
TS_UV_RANDR = 2504

TS_MAT_N    = 2600


# ══════════════════════════════════════════════════════════════════════════════
#  Геометрия 2D
# ══════════════════════════════════════════════════════════════════════════════

def _area(poly):
    n = len(poly)
    a = 0.0
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a * 0.5


def _bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), max(xs), min(ys), max(ys)


def _rot(p, cx, cy, a):
    dx, dy = p[0] - cx, p[1] - cy
    c, s = math.cos(a), math.sin(a)
    return dx * c - dy * s + cx, dx * s + dy * c + cy


def _rect(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def _inside_edge(p, a, b):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-10


def _intersect(p, q, a, b):
    dx, dy = q[0] - p[0], q[1] - p[1]
    ex, ey = b[0] - a[0], b[1] - a[1]
    det = dx * ey - dy * ex
    if abs(det) < 1e-14:
        return q
    t = ((a[0] - p[0]) * ey - (a[1] - p[1]) * ex) / det
    return p[0] + t * dx, p[1] + t * dy


def _clip_sh(subject, clip):
    """Sutherland–Hodgman. clip — CCW."""
    if not subject or len(clip) < 3:
        return []
    output = list(subject)
    n = len(clip)
    for i in range(n):
        a, b = clip[i], clip[(i + 1) % n]
        inp = output
        output = []
        if not inp:
            break
        prev = inp[-1]
        for cur in inp:
            if _inside_edge(cur, a, b):
                if not _inside_edge(prev, a, b):
                    output.append(_intersect(prev, cur, a, b))
                output.append(cur)
            elif _inside_edge(prev, a, b):
                output.append(_intersect(prev, cur, a, b))
            prev = cur
    return output if len(output) >= 3 else []


def _pip(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-30) + xi):
            inside = not inside
        j = i
    return inside


def _ensure_ccw(poly):
    return list(poly) if _area(poly) >= 0 else list(reversed(poly))


def _is_convex(poly):
    n = len(poly)
    pos = neg = False
    for i in range(n):
        a, b, c = poly[i], poly[(i + 1) % n], poly[(i + 2) % n]
        cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if cr > 1e-10:
            pos = True
        elif cr < -1e-10:
            neg = True
        if pos and neg:
            return False
    return True


def _pt_in_tri(p, a, b, c):
    d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
    d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
    d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
    has_neg = (d1 < -1e-12) or (d2 < -1e-12) or (d3 < -1e-12)
    has_pos = (d1 > 1e-12) or (d2 > 1e-12) or (d3 > 1e-12)
    return not (has_neg and has_pos)


def _pt_key(p):
    return (round(p[0], 6), round(p[1], 6))


def _remove_collinear(poly):
    n = len(poly)
    if n < 4:
        return poly
    result = []
    for i in range(n):
        prev_p, cur_p, next_p = poly[i - 1], poly[i], poly[(i + 1) % n]
        dx1, dy1 = cur_p[0] - prev_p[0], cur_p[1] - prev_p[1]
        dx2, dy2 = next_p[0] - cur_p[0], next_p[1] - cur_p[1]
        len1, len2 = math.hypot(dx1, dy1), math.hypot(dx2, dy2)
        if len1 < 1e-9 or len2 < 1e-9:
            continue
        if abs(dx1 * dy2 - dy1 * dx2) / (len1 * len2) < 1e-6:
            continue
        result.append(cur_p)
    return result if len(result) >= 3 else poly


def _merge_fragments(fragments):
    """Склеивает куски, разрезанные только диагоналями триангуляции вогнутого контура."""
    if not fragments:
        return []
    if len(fragments) == 1:
        return [_remove_collinear(fragments[0])]

    edge_owner = {}
    for fi, frag in enumerate(fragments):
        n = len(frag)
        for i in range(n):
            a = _pt_key(frag[i])
            b = _pt_key(frag[(i + 1) % n])
            edge_owner.setdefault((a, b), []).append(fi)

    shared = set()
    for (a, b), owners in edge_owner.items():
        if (b, a) in edge_owner:
            for fi in owners:
                for fj in edge_owner[(b, a)]:
                    if fi != fj:
                        shared.add((a, b))
                        shared.add((b, a))
    if not shared:
        return [_remove_collinear(f) for f in fragments]

    parent = list(range(len(fragments)))

    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(x, y):
        rx, ry = _find(x), _find(y)
        if rx != ry:
            parent[rx] = ry

    for (a, b), owners in edge_owner.items():
        if (b, a) not in edge_owner:
            continue
        for fi in owners:
            for fj in edge_owner[(b, a)]:
                if fi != fj:
                    _union(fi, fj)

    groups = {}
    for fi in range(len(fragments)):
        groups.setdefault(_find(fi), []).append(fi)

    merged = []
    for group in groups.values():
        if len(group) == 1:
            merged.append(fragments[group[0]])
            continue
        adj = {}
        for fi in group:
            frag = fragments[fi]
            n = len(frag)
            for i in range(n):
                a_pt, b_pt = frag[i], frag[(i + 1) % n]
                a, b = _pt_key(a_pt), _pt_key(b_pt)
                if (a, b) in shared:
                    continue
                adj.setdefault(a, []).append((b, b_pt, a_pt))
        if not adj:
            merged.extend(fragments[fi] for fi in group)
            continue
        start = next(iter(adj))
        loop, cur, ok = [], start, True
        max_steps = sum(len(v) for v in adj.values()) + 1
        steps = 0
        while True:
            steps += 1
            opts = adj.get(cur)
            if steps > max_steps or not opts:
                ok = False
                break
            nxt_key, nxt_pt, cur_pt = opts[0]
            loop.append(cur_pt)
            opts.pop(0)
            if not opts:
                del adj[cur]
            cur = nxt_key
            if cur == start and len(loop) >= 3:
                break
            if len(loop) > 5000:
                ok = False
                break
        if ok and len(loop) >= 3:
            merged.append(loop)
        else:
            merged.extend(fragments[fi] for fi in group)
    return [_remove_collinear(p) for p in merged]


def _triangulate(poly):
    n = len(poly)
    if n < 3:
        return []
    if n == 3:
        return [list(poly)]
    pts = _ensure_ccw(poly)
    idx = list(range(len(pts)))
    tris = []
    guard = len(idx) * 4
    while len(idx) > 2 and guard:
        guard -= 1
        m = len(idx)
        clipped = False
        for i in range(m):
            i0, i1, i2 = idx[(i - 1) % m], idx[i], idx[(i + 1) % m]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) <= 1e-12:
                continue
            ear = True
            for k in idx:
                if k in (i0, i1, i2):
                    continue
                if _pt_in_tri(pts[k], a, b, c):
                    ear = False
                    break
            if ear:
                tris.append([a, b, c])
                del idx[i]
                clipped = True
                break
        if not clipped:
            break
    return tris


def _triangulate_idx(pts_2d):
    """Ear-clip: треугольники как локальные индексы. Не веер от вершины 0."""
    n = len(pts_2d)
    if n < 3:
        return []
    if n == 3:
        return [(0, 1, 2)]
    ccw = _area(pts_2d) >= 0
    indices = list(range(n)) if ccw else list(range(n - 1, -1, -1))
    triangles = []
    max_iter = n * 4
    while len(indices) > 2 and max_iter > 0:
        max_iter -= 1
        m = len(indices)
        found = False
        for i in range(m):
            i0, i1, i2 = indices[(i - 1) % m], indices[i], indices[(i + 1) % m]
            a, b, c = pts_2d[i0], pts_2d[i1], pts_2d[i2]
            if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) <= 1e-12:
                continue
            is_ear = True
            for jdx in indices:
                if jdx in (i0, i1, i2):
                    continue
                if _pt_in_tri(pts_2d[jdx], a, b, c):
                    is_ear = False
                    break
            if is_ear:
                triangles.append((i0, i1, i2))
                indices.pop(i)
                found = True
                break
        if not found:
            break
    return triangles


def _clip_to(subject, boundary):
    if not subject or len(boundary) < 3:
        return []
    if _is_convex(boundary):
        c = _clip_sh(subject, _ensure_ccw(boundary))
        return [c] if c else []
    out = []
    for tri in _triangulate(boundary):
        c = _clip_sh(subject, _ensure_ccw(tri))
        if c:
            out.append(c)
    return _merge_fragments(out)


def _subtract_convex(poly, hole_ccw):
    remaining = list(poly)
    outside = []
    n = len(hole_ccw)
    for i in range(n):
        if not remaining:
            break
        a, b = hole_ccw[i], hole_ccw[(i + 1) % n]
        out_p, in_p = [], []
        m = len(remaining)
        for j in range(m):
            cur = remaining[j]
            prev = remaining[j - 1]
            sc = (b[0] - a[0]) * (cur[1] - a[1]) - (b[1] - a[1]) * (cur[0] - a[0])
            sp = (b[0] - a[0]) * (prev[1] - a[1]) - (b[1] - a[1]) * (prev[0] - a[0])
            cin, pin = sc >= 0, sp >= 0
            if cin != pin:
                hit = _intersect(prev, cur, a, b)
                out_p.append(hit)
                in_p.append(hit)
            (in_p if cin else out_p).append(cur)
        if len(out_p) >= 3:
            outside.append(out_p)
        remaining = in_p if len(in_p) >= 3 else []
    return outside


def _punch_holes(polys, holes):
    current = polys
    for hole in holes:
        if len(hole) < 3:
            continue
        ccw = _ensure_ccw(hole)
        pieces = [ccw] if _is_convex(ccw) else [_ensure_ccw(t) for t in _triangulate(ccw)]
        nxt = []
        for poly in current:
            acc = [poly]
            for piece in pieces:
                tmp = []
                for p in acc:
                    tmp.extend(_subtract_convex(p, piece))
                acc = tmp
            nxt.extend(_merge_fragments(acc) if acc else [])
        current = nxt
    return current


def _inset(poly, amount):
    n = len(poly)
    if n < 3 or amount <= 0:
        return list(poly) if n >= 3 else None
    nrm = []
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        nrm.append((0.0, 0.0) if L < 1e-12 else (-dy / L, dx / L))
    out = []
    for i in range(n):
        prev = (i - 1) % n
        p1x = poly[prev][0] + nrm[prev][0] * amount
        p1y = poly[prev][1] + nrm[prev][1] * amount
        d1x = poly[i][0] - poly[prev][0]
        d1y = poly[i][1] - poly[prev][1]
        p2x = poly[i][0] + nrm[i][0] * amount
        p2y = poly[i][1] + nrm[i][1] * amount
        d2x = poly[(i + 1) % n][0] - poly[i][0]
        d2y = poly[(i + 1) % n][1] - poly[i][1]
        det = -d1x * d2y + d1y * d2x
        if abs(det) < 1e-10:
            out.append(((p1x + p2x) * 0.5, (p1y + p2y) * 0.5))
            continue
        t = (-d2y * (p2x - p1x) + d2x * (p2y - p1y)) / det
        out.append((p1x + t * d1x, p1y + t * d1y))
    if min(math.hypot(p[0] - sum(q[0] for q in out) / n,
                      p[1] - sum(q[1] for q in out) / n) for p in out) < 1e-4:
        return None
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  Раскладки
# ══════════════════════════════════════════════════════════════════════════════

def _expand_bbox(b, m):
    mu, Mu, mv, Mv = b
    return mu - m, Mu + m, mv - m, Mv + m


def _gen_plank(tw, th, var, bond, bbox, rng):
    mu, Mu, mv, Mv = bbox
    tiles = []
    y = mv
    row = 0
    vmin, vmax = max(th * 0.4, tw * (1.0 - var)), tw * (1.0 + var)
    vmin = max(th, vmin)
    while y < Mv + th * 0.5:
        x = mu + (row % 2) * tw * bond
        while x < Mu + tw:
            L = rng.uniform(vmin, vmax) if var > 1e-6 else tw
            tiles.append(_rect(x, y, L, th))
            x += L
        y += th
        row += 1
    return tiles


def _gen_running(tw, th, bond, bbox, third=False):
    mu, Mu, mv, Mv = bbox
    tiles = []
    rows = int(math.ceil((Mv - mv) / th)) + 2
    cols = int(math.ceil((Mu - mu) / tw)) + 3
    frac = 1.0 / 3.0 if third else bond
    for r in range(-1, rows):
        shift = (r * tw * frac) % tw
        for c in range(-1, cols):
            tiles.append(_rect(mu + c * tw + shift, mv + r * th, tw, th))
    return tiles


def _gen_stack(tw, th, bbox):
    mu, Mu, mv, Mv = bbox
    tiles = []
    rows = int(math.ceil((Mv - mv) / th)) + 2
    cols = int(math.ceil((Mu - mu) / tw)) + 2
    for r in range(-1, rows):
        for c in range(-1, cols):
            tiles.append(_rect(mu + c * tw, mv + r * th, tw, th))
    return tiles


def _gen_english(tw, th, bbox):
    mu, Mu, mv, Mv = bbox
    tiles = []
    y, row = mv, 0
    while y < Mv + th:
        if row % 2 == 0:
            x = mu
            while x < Mu + tw:
                tiles.append(_rect(x, y, tw, th))
                x += tw
        else:
            x = mu
            while x < Mu + th:
                tiles.append(_rect(x, y, th, th))
                x += th
        y += th
        row += 1
    return tiles


def _gen_herring(tw, th, bbox):
    mu, Mu, mv, Mv = bbox
    cell = tw + th
    tiles = []
    cols = int(math.ceil((Mu - mu) / cell)) + 2
    rows = int(math.ceil((Mv - mv) / cell)) + 2
    for r in range(-1, rows):
        for c in range(-1, cols):
            ux, uy = mu + c * cell, mv + r * cell
            tiles.append(_rect(ux, uy, tw, th))
            tiles.append(_rect(ux + tw, uy + th, th, tw))
    return tiles


def _gen_chevron(tw, th, bbox):
    """Параллелограммы ±45° — настоящий шеврон, не ёлка 90°."""
    mu, Mu, mv, Mv = bbox
    tiles = []
    step_u = tw * math.cos(math.pi / 4.0)
    step_v = th
    cols = int(math.ceil((Mu - mu) / max(step_u, 1.0))) + 3
    rows = int(math.ceil((Mv - mv) / th)) + 3
    s2 = math.sin(math.pi / 4.0)
    c2 = math.cos(math.pi / 4.0)
    for r in range(-1, rows):
        for c in range(-1, cols):
            x = mu + c * (tw * c2)
            y = mv + r * th + (c % 2) * th * 0.0
            # левый луч
            w, h = tw, th
            p = [(0, 0), (w * c2, w * s2), (w * c2, w * s2 + h), (0, h)]
            tiles.append([(x + px, y + py) for px, py in p])
            # правый луч
            q = [(0, 0), (w * c2, -w * s2), (w * c2, -w * s2 + h), (0, h)]
            tiles.append([(x + tw * c2 + px, y + py) for px, py in q])
    return tiles


def _gen_basket(tw, th, bbox):
    mu, Mu, mv, Mv = bbox
    tiles = []
    cell_w, cell_h = tw + th, tw + th
    cols = int(math.ceil((Mu - mu) / cell_w)) + 2
    rows = int(math.ceil((Mv - mv) / cell_h)) + 2
    for r in range(-1, rows):
        for c in range(-1, cols):
            x, y = mu + c * cell_w, mv + r * cell_h
            if (r + c) % 2 == 0:
                tiles.append(_rect(x, y, th, tw))
                tiles.append(_rect(x + th, y, th, tw))
            else:
                tiles.append(_rect(x, y, tw, th))
                tiles.append(_rect(x, y + th, tw, th))
    return tiles


def _gen_windmill(tw, th, bbox):
    mu, Mu, mv, Mv = bbox
    s = tw
    tiles = []
    cols = int(math.ceil((Mu - mu) / s)) + 2
    rows = int(math.ceil((Mv - mv) / s)) + 2
    hole = max(th, s * 0.22)
    arm = (s - hole) * 0.5
    for r in range(-1, rows):
        for c in range(-1, cols):
            x, y = mu + c * s, mv + r * s
            tiles.append(_rect(x + arm, y + arm, hole, hole))
            tiles.append(_rect(x, y + arm, arm, hole))
            tiles.append(_rect(x + arm + hole, y + arm, arm, hole))
            tiles.append(_rect(x + arm, y, hole, arm))
            tiles.append(_rect(x + arm, y + arm + hole, hole, arm))
    return tiles


def _gen_versailles(L, S, bbox):
    """Модуль из квадрата L, квадрата S и двух прямоугольников — не 4 одинаковых плитки."""
    mu, Mu, mv, Mv = bbox
    mod = L + S
    tiles = []
    cols = int(math.ceil((Mu - mu) / mod)) + 2
    rows = int(math.ceil((Mv - mv) / mod)) + 2
    for r in range(-1, rows):
        for c in range(-1, cols):
            x, y = mu + c * mod, mv + r * mod
            tiles.append(_rect(x, y, L, L))
            tiles.append(_rect(x + L, y, S, L))
            tiles.append(_rect(x, y + L, L, S))
            tiles.append(_rect(x + L, y + L, S, S))
    return tiles


def _gen_hex(radius, bbox):
    mu, Mu, mv, Mv = bbox
    du = radius * 1.5
    dv = math.sqrt(3.0) * radius
    tiles = []
    cols = int(math.ceil((Mu - mu) / du)) + 3
    rows = int(math.ceil((Mv - mv) / dv)) + 3
    ang = [math.radians(a) for a in (0, 60, 120, 180, 240, 300)]
    for r in range(-1, rows):
        for c in range(-1, cols):
            cx = mu + c * du
            cy = mv + r * dv + (c % 2) * dv * 0.5
            tiles.append([(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in ang])
    return tiles


def _gen_diamond(tw, bbox):
    mu, Mu, mv, Mv = bbox
    s = tw
    tiles = []
    cols = int(math.ceil((Mu - mu) / s)) + 3
    rows = int(math.ceil((Mv - mv) / s)) + 3
    h = s * 0.5
    for r in range(-1, rows):
        for c in range(-1, cols):
            cx = mu + c * s + (r % 2) * h
            cy = mv + r * h
            tiles.append([(cx, cy - h), (cx + h, cy), (cx, cy + h), (cx - h, cy)])
    return tiles


def _gen_scale(tw, bbox):
    mu, Mu, mv, Mv = bbox
    r = tw * 0.5
    du, dv = r * 1.15, r * 0.72
    tiles = []
    cols = int(math.ceil((Mu - mu) / du)) + 3
    rows = int(math.ceil((Mv - mv) / dv)) + 3
    n = 10
    for row in range(-1, rows):
        for col in range(-1, cols):
            cx = mu + col * du + (row % 2) * du * 0.5
            cy = mv + row * dv
            pts = []
            for i in range(n):
                a = math.pi * (0.05 + 0.9 * i / float(n - 1))
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            pts.append((cx, cy))
            tiles.append(pts)
    return tiles


def _generate_raw(pattern, tw, th, var, bond, bbox, rng):
    if pattern == PAT_PLANK:
        return _gen_plank(tw, th, var, bond, bbox, rng)
    if pattern == PAT_RUNNING:
        return _gen_running(tw, th, bond, bbox)
    if pattern == PAT_STACK:
        return _gen_stack(tw, th, bbox)
    if pattern == PAT_THIRD:
        return _gen_running(tw, th, bond, bbox, third=True)
    if pattern == PAT_ENGLISH:
        return _gen_english(tw, th, bbox)
    if pattern == PAT_HERRING:
        return _gen_herring(tw, th, bbox)
    if pattern == PAT_CHEVRON:
        return _gen_chevron(tw, th, bbox)
    if pattern == PAT_BASKET:
        return _gen_basket(tw, th, bbox)
    if pattern == PAT_WINDMILL:
        return _gen_windmill(tw, th, bbox)
    if pattern == PAT_VERSAILLES:
        return _gen_versailles(tw, th, bbox)
    if pattern == PAT_HEX:
        return _gen_hex(max(th, tw * 0.5), bbox)
    if pattern == PAT_DIAMOND:
        return _gen_diamond(tw, bbox)
    if pattern == PAT_SCALE:
        return _gen_scale(tw, bbox)
    return _gen_running(tw, th, bond, bbox)


# ══════════════════════════════════════════════════════════════════════════════
#  3D / UV / теги
# ══════════════════════════════════════════════════════════════════════════════

def _vlen(v):
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def _cross(a, b):
    return c4d.Vector(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def _dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z


def _frame(n):
    n = n / max(_vlen(n), 1e-12)
    ref = c4d.Vector(0, 1, 0) if abs(n.y) < 0.9 else c4d.Vector(1, 0, 0)
    u = _cross(ref, n)
    lu = _vlen(u)
    if lu < 1e-8:
        u = _cross(c4d.Vector(0, 0, 1), n)
        lu = _vlen(u)
    u = u / lu
    v = _cross(n, u)
    return u, v / _vlen(v), n


def _to3(u, v, origin, uu, vv, nn, h=0.0):
    return origin + uu * u + vv * v + nn * h


def _build_tile_3d(tile, thick, bevel, seam, origin, uu, vv, nn, h_jit):
    n = len(tile)
    if n < 3:
        return [], [], []
    t = max(0.001, thick + h_jit)
    bev = max(0.0, min(bevel, t * 0.45))
    work = _inset(tile, seam * 0.5) if seam > 1e-6 else list(tile)
    if work is None:
        return [], [], []
    top = _inset(work, bev) if bev > 1e-6 else list(work)
    if top is None or len(top) != len(work):
        top = list(work)
        bev = 0.0
    n = len(work)
    verts, tops, sides = [], [], []
    ib, ie, it = [], [], []
    for i in range(n):
        ib.append(len(verts))
        verts.append(_to3(work[i][0], work[i][1], origin, uu, vv, nn, 0.0))
    for i in range(n):
        ie.append(len(verts))
        verts.append(_to3(work[i][0], work[i][1], origin, uu, vv, nn, t - bev))
    for i in range(n):
        it.append(len(verts))
        verts.append(_to3(top[i][0], top[i][1], origin, uu, vv, nn, t))
    if n == 4 and _is_convex(top):
        tops.append(tuple(it))
        sides.append(tuple(reversed(ib)))
    else:
        for i0, i1, i2 in _triangulate_idx(top):
            tops.append((it[i0], it[i1], it[i2], it[i2]))
        for i0, i1, i2 in _triangulate_idx(work):
            sides.append((ib[i0], ib[i2], ib[i1], ib[i1]))
    for i in range(n):
        j = (i + 1) % n
        sides.append((ib[i], ib[j], ie[j], ie[i]))
        sides.append((ie[i], ie[j], it[j], it[i]))
    return verts, tops, sides


def _uvs(tile, su, sv, rot, rnd, rng_r, seed):
    us = [p[0] for p in tile]
    vs = [p[1] for p in tile]
    mu, mv = min(us), min(vs)
    a = rot
    if rnd:
        a += random.Random(seed).uniform(-rng_r, rng_r)
    ca, sa = math.cos(a), math.sin(a)
    out = []
    for px, py in tile:
        u = (px - mu) / su if abs(su) > 1e-9 else 0.0
        v = (py - mv) / sv if abs(sv) > 1e-9 else 0.0
        if abs(a) > 1e-8:
            u, v = u * ca - v * sa, u * sa + v * ca
        out.append(c4d.Vector(u, v, 0.0))
    return out


def _sel(obj, name, indices):
    if not indices:
        return
    tag = obj.MakeTag(c4d.Tpolygonselection)
    if not tag:
        return
    tag.SetName(name)
    bs = tag.GetBaseSelect()
    for i in indices:
        bs.Select(i)


# ══════════════════════════════════════════════════════════════════════════════
#  Контур
# ══════════════════════════════════════════════════════════════════════════════

def _loops_from_mesh(mesh):
    edge_n = {}
    for i in range(mesh.GetPolygonCount()):
        p = mesh.GetPolygon(i)
        vs = [p.a, p.b, p.c] if p.c == p.d else [p.a, p.b, p.c, p.d]
        for j in range(len(vs)):
            a, b = vs[j], vs[(j + 1) % len(vs)]
            key = (min(a, b), max(a, b))
            edge_n[key] = edge_n.get(key, 0) + 1
    bounds = [e for e, c in edge_n.items() if c == 1]
    if not bounds:
        return []
    adj = {}
    for a, b in bounds:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    left = set(v for e in bounds for v in e)
    loops = []
    while left:
        start = next(iter(left))
        loop, seen, cur = [start], {start}, start
        while True:
            nxt = None
            for nb in adj.get(cur, []):
                if nb not in seen:
                    nxt = nb
                    break
            if nxt is None:
                if start in adj.get(cur, []) and len(loop) > 2:
                    loops.append(loop)
                break
            loop.append(nxt)
            seen.add(nxt)
            cur = nxt
        for v in loop:
            left.discard(v)
    return [lp for lp in loops if len(lp) >= 3]


def _boundary_from_mesh(mesh):
    if mesh.GetPolygonCount() == 0 or mesh.GetPointCount() < 3:
        return None
    p0 = mesh.GetPolygon(0)
    pa, pb, pc = mesh.GetPoint(p0.a), mesh.GetPoint(p0.b), mesh.GetPoint(p0.c)
    nrm = _cross(pb - pa, (mesh.GetPoint(p0.d) if p0.c != p0.d else pc) - pa)
    if _vlen(nrm) < 1e-9:
        return None
    nrm = nrm / _vlen(nrm)
    origin = pa
    uu, vv, nn = _frame(nrm)
    pts2 = []
    for i in range(mesh.GetPointCount()):
        d = mesh.GetPoint(i) - origin
        pts2.append((_dot(d, uu), _dot(d, vv)))
    loops = _loops_from_mesh(mesh) or [list(range(mesh.GetPointCount()))]
    loops2 = [[pts2[i] for i in lp] for lp in loops]
    areas = [_area(lp) for lp in loops2]
    oi = max(range(len(loops2)), key=lambda i: abs(areas[i]))
    outer = _ensure_ccw(loops2[oi])
    holes = []
    for i, lp in enumerate(loops2):
        if i == oi:
            continue
        h = list(lp)
        if _area(h) > 0:
            h = list(reversed(h))
        holes.append(h)
    return origin, uu, vv, nn, outer, holes


def _default_plane(surf, sa, sb):
    origin = c4d.Vector(-sa * 0.5, 0, -sb * 0.5)
    if surf == SURF_WALL:
        uu, vv, nn = c4d.Vector(1, 0, 0), c4d.Vector(0, 1, 0), c4d.Vector(0, 0, 1)
        origin = c4d.Vector(-sa * 0.5, 0, 0)
    elif surf == SURF_CEILING:
        uu, vv, nn = c4d.Vector(1, 0, 0), c4d.Vector(0, 0, -1), c4d.Vector(0, -1, 0)
        origin = c4d.Vector(-sa * 0.5, 0, sb * 0.5)
    else:
        uu, vv, nn = c4d.Vector(1, 0, 0), c4d.Vector(0, 0, 1), c4d.Vector(0, 1, 0)
    outer = [(0, 0), (sa, 0), (sa, sb), (0, sb)]
    return origin, uu, vv, nn, outer, []


def _child_poly(op):
    child = op.GetDown()
    if child is None:
        return None
    src = child.GetDeformCache() or child.GetCache() or child
    if not src.CheckType(c4d.Opolygon):
        try:
            import c4d.utils as utils  # type: ignore
            res = utils.SendModelingCommand(
                command=c4d.MCOMMAND_CURRENTSTATETOOBJECT,
                list=[src.Clone()],
                mode=c4d.MODELINGCOMMANDMODE_ALL,
                doc=op.GetDocument(),
            )
            if not res or not res[0].CheckType(c4d.Opolygon):
                return None
            src = res[0]
        except Exception:
            return None
    if src.GetPointCount() < 3:
        return None
    info = _boundary_from_mesh(src)
    if info is None:
        return None
    origin, uu, vv, nn, outer, holes = info
    ml = child.GetMl()
    return ml, origin, uu, vv, nn, outer, holes


# ══════════════════════════════════════════════════════════════════════════════
#  Сборка
# ══════════════════════════════════════════════════════════════════════════════

def _finalize_tiles(raw, boundary, holes, angle, ou, ov, keep, yaw_jit, seed):
    mu, Mu, mv, Mv = _bbox(boundary)
    cx, cy = (mu + Mu) * 0.5, (mv + Mv) * 0.5
    rng = random.Random(seed + 17)
    out = []
    for i, poly in enumerate(raw):
        pts = [(_rot(p, cx, cy, angle) if abs(angle) > 1e-8 else p) for p in poly]
        pts = [(p[0] + ou, p[1] + ov) for p in pts]
        if yaw_jit > 1e-8:
            a = rng.uniform(-yaw_jit, yaw_jit)
            ox = sum(p[0] for p in pts) / len(pts)
            oy = sum(p[1] for p in pts) / len(pts)
            pts = [_rot(p, ox, oy, a) for p in pts]
        a0 = abs(_area(pts))
        clipped = _clip_to(pts, boundary)
        clipped = _punch_holes(clipped, holes)
        for frag in clipped:
            if len(frag) < 3:
                continue
            ar = abs(_area(frag))
            if ar < 1e-4:
                continue
            cut = ar < a0 * 0.985
            if keep and cut:
                continue
            out.append((frag, cut))
            if len(out) >= MAX_TILES:
                return out
    return out


def _build(op):
    surf = int(op[TS_SURFACE] or 0)
    sa = max(1.0, float(op[TS_SIZE_A] or 400.0))
    sb = max(1.0, float(op[TS_SIZE_B] or 400.0))
    use_child = bool(op[TS_USE_CHILD])
    child_pack = _child_poly(op) if use_child else None

    if child_pack:
        ml, origin, uu, vv, nn, outer, holes = child_pack
    else:
        ml = None
        origin, uu, vv, nn, outer, holes = _default_plane(surf, sa, sb)

    pattern = int(op[TS_PATTERN] or 0)
    tw = max(1.0, float(op[TS_LEN] or 80.0))
    th = max(1.0, float(op[TS_WID] or 16.0))
    ang = float(op[TS_ANGLE] or 0.0)
    ou = float(op[TS_OFF_U] or 0.0)
    ov = float(op[TS_OFF_V] or 0.0)
    bond = float(op[TS_BOND] or 0.5)
    var = max(0.0, float(op[TS_LEN_VAR] or 0.0)) / 100.0
    seed = int(op[TS_SEED] or 0)
    keep = bool(op[TS_KEEP])
    border = max(0.0, float(op[TS_BORDER] or 0.0))

    thick = max(0.001, float(op[TS_THICK] or 2.0))
    bevel = max(0.0, float(op[TS_BEVEL] or 0.15))
    seam = max(0.0, float(op[TS_SEAM] or 0.2))
    under = max(0.0, float(op[TS_UNDERLAY] or 0.0))
    h_jit = max(0.0, float(op[TS_H_JIT] or 0.0))
    yaw_jit = float(op[TS_YAW_JIT] or 0.0)

    uv_u = max(0.1, float(op[TS_UV_U] or 100.0))
    uv_v = max(0.1, float(op[TS_UV_V] or 100.0))
    uv_rot = float(op[TS_UV_ROT] or 0.0)
    uv_rnd = bool(op[TS_UV_RAND])
    uv_rr = float(op[TS_UV_RANDR] or 0.0)
    mat_n = max(1, int(op[TS_MAT_N] or 1))

    domain = outer
    border_poly = None
    if border > 1e-6:
        inner = _inset(outer, border)
        if inner:
            border_poly = outer
            domain = inner

    mu, Mu, mv, Mv = _expand_bbox(_bbox(domain), max(tw, th) * 3)
    rng = random.Random(seed if seed else 1)
    raw = _generate_raw(pattern, tw, th, var, bond, (mu, Mu, mv, Mv), rng)
    placed = _finalize_tiles(raw, domain, holes, ang, ou, ov, keep, yaw_jit, seed)

    verts, polys = [], []
    top_i, side_i, cut_i, border_i = [], [], [], []
    mat_i = [[] for _ in range(mat_n)]
    uv_pack = []
    hj_rng = random.Random(seed + 99)

    def add_piece(poly2d, thick_s, bev_s, seam_s, hvar, is_cut, is_border, mi):
        v, tp, sp = _build_tile_3d(poly2d, thick_s, bev_s, seam_s, origin, uu, vv, nn, hvar)
        if not v:
            return
        base_v, base_p = len(verts), len(polys)
        verts.extend(v)
        uvs = _uvs(poly2d, uv_u, uv_v, uv_rot, uv_rnd, uv_rr, seed + base_p * 13)
        uv_pack.append((base_p, base_v, tp, uvs, len(poly2d)))
        for p in tp:
            polys.append(tuple(i + base_v for i in p))
            idx = len(polys) - 1
            top_i.append(idx)
            if is_cut:
                cut_i.append(idx)
            if is_border:
                border_i.append(idx)
            mat_i[mi].append(idx)
        for p in sp:
            polys.append(tuple(i + base_v for i in p))
            side_i.append(len(polys) - 1)

    if under > 1e-6:
        add_piece(outer, under, 0.0, 0.0, 0.0, False, False, 0)

    if border_poly is not None:
        # рамка: внешний контур как одна «плитка» с вырезом domain — упрощённо полосы bbox
        bu0, bu1, bv0, bv1 = _bbox(outer)
        strips = [
            _rect(bu0, bv0, bu1 - bu0, border),
            _rect(bu0, bv1 - border, bu1 - bu0, border),
            _rect(bu0, bv0, border, bv1 - bv0),
            _rect(bu1 - border, bv0, border, bv1 - bv0),
        ]
        for s in _punch_holes(
            [c for st in strips for c in _clip_to(st, outer)], holes
        ):
            add_piece(s, thick * 1.05, bevel * 0.5, 0.0, 0.0, False, True, 0)

    for k, (frag, cut) in enumerate(placed):
        hv = hj_rng.uniform(-h_jit, h_jit) if h_jit > 1e-8 else 0.0
        add_piece(frag, thick, bevel, seam, hv, cut, False, k % mat_n)

    if not verts:
        return None

    if ml is not None:
        for i in range(len(verts)):
            verts[i] = ml * verts[i]

    obj = c4d.PolygonObject(len(verts), len(polys))
    obj.SetName("Tessera")
    for i, v in enumerate(verts):
        obj.SetPoint(i, v)
    for i, p in enumerate(polys):
        if len(p) == 4:
            obj.SetPolygon(i, c4d.CPolygon(p[0], p[1], p[2], p[3]))
        else:
            obj.SetPolygon(i, c4d.CPolygon(p[0], p[1], p[2], p[2]))
    obj.Message(c4d.MSG_UPDATE)

    _sel(obj, "TILE", top_i)
    _sel(obj, "SIDE", side_i)
    _sel(obj, "CUT", cut_i)
    _sel(obj, "BORDER", border_i)
    if mat_n > 1:
        for mi, idxs in enumerate(mat_i):
            _sel(obj, "MAT_{}".format(mi + 1), idxs)

    uvw = c4d.UVWTag(len(polys))
    for base_p, base_v, tp, uvs, n_tile in uv_pack:
        top_off = 2 * n_tile
        for pi_off in range(len(tp)):
            pi = base_p + pi_off
            if pi >= len(polys):
                continue
            p_idx = polys[pi]
            def uv_at(li):
                return uvs[li] if 0 <= li < len(uvs) else c4d.Vector()
            li0 = p_idx[0] - base_v - top_off
            li1 = p_idx[1] - base_v - top_off
            li2 = p_idx[2] - base_v - top_off
            ua, ub, uc = uv_at(li0), uv_at(li1), uv_at(li2)
            ud = uv_at(p_idx[3] - base_v - top_off) if len(p_idx) == 4 else uc
            uvw.SetSlow(pi, ua, ub, uc, ud)
    obj.InsertTag(uvw)
    return obj


# ══════════════════════════════════════════════════════════════════════════════
#  AM
# ══════════════════════════════════════════════════════════════════════════════

def _gid(i):
    return c4d.DescID(c4d.DescLevel(i, c4d.DTYPE_GROUP, 0))


def _add_grp(desc, gid, name):
    bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_GROUP)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_COLUMNS] = 1
    bc[c4d.DESC_DEFAULT] = 1
    desc.SetParameter(_gid(gid), bc, c4d.ID_LISTHEAD)
    return _gid(gid)


def _add_cycle(desc, pid, name, items, default, parent):
    bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_DEFAULT] = default
    bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
    cyc = c4d.BaseContainer()
    for i, lab in enumerate(items):
        cyc[i] = lab
    bc[c4d.DESC_CYCLE] = cyc
    desc.SetParameter(c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_LONG, 0)), bc, parent)


def _add_real(desc, pid, name, default, parent, unit=c4d.DESC_UNIT_METER,
              mn=0.0, mx=100000.0, step=1.0, smin=None, smax=None):
    bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_DEFAULT] = default
    bc[c4d.DESC_MIN] = mn
    bc[c4d.DESC_MAX] = mx
    bc[c4d.DESC_UNIT] = unit
    bc[c4d.DESC_STEP] = step
    bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
    if smin is not None:
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = smin
        bc[c4d.DESC_MAXSLIDER] = smax
    desc.SetParameter(c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_REAL, 0)), bc, parent)


def _add_long(desc, pid, name, default, parent, mn, mx):
    bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_DEFAULT] = default
    bc[c4d.DESC_MIN] = mn
    bc[c4d.DESC_MAX] = mx
    bc[c4d.DESC_STEP] = 1
    desc.SetParameter(c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_LONG, 0)), bc, parent)


def _add_bool(desc, pid, name, default, parent):
    bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
    bc[c4d.DESC_NAME] = name
    bc[c4d.DESC_DEFAULT] = default
    desc.SetParameter(c4d.DescID(c4d.DescLevel(pid, c4d.DTYPE_BOOL, 0)), bc, parent)


class TesseraObject(c4d.plugins.ObjectData):

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(PLUGIN_NAME)
            op[TS_SURFACE] = SURF_FLOOR
            op[TS_SIZE_A] = 400.0
            op[TS_SIZE_B] = 400.0
            op[TS_USE_CHILD] = True
            op[TS_PATTERN] = PAT_PLANK
            op[TS_LEN] = 80.0
            op[TS_WID] = 16.0
            op[TS_ANGLE] = 0.0
            op[TS_OFF_U] = 0.0
            op[TS_OFF_V] = 0.0
            op[TS_BOND] = 0.5
            op[TS_LEN_VAR] = 35.0
            op[TS_SEED] = 1
            op[TS_KEEP] = False
            op[TS_BORDER] = 0.0
            op[TS_THICK] = 2.0
            op[TS_BEVEL] = 0.15
            op[TS_SEAM] = 0.25
            op[TS_UNDERLAY] = 0.8
            op[TS_H_JIT] = 0.0
            op[TS_YAW_JIT] = 0.0
            op[TS_UV_U] = 100.0
            op[TS_UV_V] = 100.0
            op[TS_UV_ROT] = 0.0
            op[TS_UV_RAND] = True
            op[TS_UV_RANDR] = math.radians(8.0)
            op[TS_MAT_N] = 3
        return True

    def GetVirtualObjects(self, op, hh):
        try:
            return _build(op)
        except Exception as e:
            print("[Tessera] {}".format(e))
            import traceback
            traceback.print_exc()
            return None

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags
        g = _add_grp(description, G_SURF, "Поверхность")
        _add_cycle(description, TS_SURFACE, "Тип", ["Пол", "Стена", "Потолок"], SURF_FLOOR, g)
        _add_real(description, TS_SIZE_A, "Размер A", 400.0, g, smin=50.0, smax=2000.0)
        _add_real(description, TS_SIZE_B, "Размер B", 400.0, g, smin=50.0, smax=2000.0)
        _add_bool(description, TS_USE_CHILD, "Контур из дочернего объекта", True, g)

        g = _add_grp(description, G_PAT, "Раскладка")
        _add_cycle(description, TS_PATTERN, "Паттерн", PAT_NAMES, PAT_PLANK, g)
        _add_real(description, TS_LEN, "Длина", 80.0, g, mn=1.0, smin=10.0, smax=250.0)
        _add_real(description, TS_WID, "Ширина", 16.0, g, mn=1.0, smin=4.0, smax=80.0)
        _add_real(description, TS_ANGLE, "Угол", 0.0, g, unit=c4d.DESC_UNIT_DEGREE,
                  mn=math.radians(-180), mx=math.radians(180), step=math.radians(1),
                  smin=math.radians(-180), smax=math.radians(180))
        _add_real(description, TS_OFF_U, "Смещение U", 0.0, g, mn=-10000, mx=10000, smin=-80, smax=80)
        _add_real(description, TS_OFF_V, "Смещение V", 0.0, g, mn=-10000, mx=10000, smin=-80, smax=80)
        _add_real(description, TS_BOND, "Сдвиг ряда (bond)", 0.5, g,
                  unit=c4d.DESC_UNIT_FLOAT, mn=0.0, mx=1.0, step=0.01, smin=0.0, smax=1.0)
        _add_real(description, TS_LEN_VAR, "Разброс длины %", 35.0, g,
                  unit=c4d.DESC_UNIT_FLOAT, mn=0.0, mx=90.0, step=1.0, smin=0.0, smax=80.0)
        _add_long(description, TS_SEED, "Seed", 1, g, 0, 999999)
        _add_bool(description, TS_KEEP, "Keep Intact (не резать плитки)", False, g)
        _add_real(description, TS_BORDER, "Рамка", 0.0, g, smin=0.0, smax=80.0)

        g = _add_grp(description, G_GEO, "Профиль")
        _add_real(description, TS_THICK, "Толщина плитки", 2.0, g, smin=0.1, smax=20.0, step=0.1)
        _add_real(description, TS_BEVEL, "Фаска", 0.15, g, smin=0.0, smax=5.0, step=0.05)
        _add_real(description, TS_SEAM, "Шов", 0.25, g, smin=0.0, smax=10.0, step=0.05)
        _add_real(description, TS_UNDERLAY, "Подложка", 0.8, g, smin=0.0, smax=20.0, step=0.1)

        g = _add_grp(description, G_VAR, "Jitter")
        _add_real(description, TS_H_JIT, "Разброс высоты", 0.0, g, smin=0.0, smax=3.0, step=0.05)
        _add_real(description, TS_YAW_JIT, "Разброс угла", 0.0, g, unit=c4d.DESC_UNIT_DEGREE,
                  mn=0.0, mx=math.radians(15), step=math.radians(0.1),
                  smin=0.0, smax=math.radians(8))

        g = _add_grp(description, G_UV, "UV")
        _add_real(description, TS_UV_U, "UV U", 100.0, g, smin=10.0, smax=400.0)
        _add_real(description, TS_UV_V, "UV V", 100.0, g, smin=10.0, smax=400.0)
        _add_real(description, TS_UV_ROT, "UV угол", 0.0, g, unit=c4d.DESC_UNIT_DEGREE,
                  mn=math.radians(-180), mx=math.radians(180), step=math.radians(1),
                  smin=math.radians(-180), smax=math.radians(180))
        _add_bool(description, TS_UV_RAND, "Случайный поворот UV", True, g)
        _add_real(description, TS_UV_RANDR, "Диапазон UV", math.radians(8), g,
                  unit=c4d.DESC_UNIT_DEGREE, mn=0.0, mx=math.radians(180),
                  step=math.radians(1), smin=0.0, smax=math.radians(45))

        g = _add_grp(description, G_MAT, "Материалы")
        _add_long(description, TS_MAT_N, "Число групп MAT_n", 3, g, 1, 16)
        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def GetDEnabling(self, node, id, t_data, flags, itemdesc):
        try:
            pid = id[0].id
        except Exception:
            return True
        pat = int(node[TS_PATTERN] or 0)
        if pid == TS_LEN_VAR:
            return pat in (PAT_PLANK,)
        if pid == TS_BOND:
            return pat in (PAT_PLANK, PAT_RUNNING, PAT_THIRD)
        if pid in (TS_SIZE_A, TS_SIZE_B, TS_SURFACE):
            return not bool(node[TS_USE_CHILD] and node.GetDown())
        return True


# ══════════════════════════════════════════════════════════════════════════════
#  Иконка / регистрация
# ══════════════════════════════════════════════════════════════════════════════

_ICON_B64 = (
    "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"
)


def _make_icon():
    png_data = base64.b64decode(_ICON_B64)
    try:
        bmp = c4d.bitmaps.BaseBitmap()
    except AttributeError:
        bmp = c4d.BaseBitmap()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        tmp.write(png_data)
        tmp.close()
        bmp.InitWith(tmp.name)
    finally:
        os.unlink(tmp.name)
    return bmp


if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id=PLUGIN_ID,
        str="{} {}".format(PLUGIN_NAME, PLUGIN_VER),
        g=TesseraObject,
        description="Obase",
        icon=_make_icon(),
        info=c4d.OBJECT_GENERATOR,
    )
    print("Tessera: плагин зарегистрирован (ID={})".format(PLUGIN_ID))
