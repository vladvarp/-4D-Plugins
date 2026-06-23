# -*- coding: utf-8 -*-
"""
MolecularHexLattice — Cinema 4D ObjectData Plugin
======================================================
Генератор молекулярных связей (Description-based parameters):
  • Узлы — гексагональные шары (dual icosphere)
  • Трубки — цилиндры, стыкующиеся к отверстиям в шарах
  • Фаска на стыке шар↔трубка
  • Регулировка каркаса по X/Y/Z, плотности узлов, плотности связей, seed
  • «Strip» — плавное смещение узлов по синусоиде
  • Материальные теги: M — шары, T — трубки, F — фаски
  • Фонг-сглаживание на всех объектах
  • Уникальная иконка (генерируется программно)

Description Parameter IDs:
  2000: g_lat   (группа «Каркас»)
  2001: g_strip (группа «Strip»)
  2002: g_sph   (группа «Шары»)
  2003: g_tub   (группа «Трубки»)
  2004: g_bev   (группа «Фаска»)
  2100: ML_SIZE_X        2101: ML_SIZE_Y
  2102: ML_SIZE_Z        2103: ML_DENSITY
  2104: ML_BOND_DENS     2105: ML_SEED
  2106: ML_JITTER        2107: ML_HIDE_ISOLATED
  2110: ML_STRIP_AMP     2111: ML_STRIP_FREQ
  2112: ML_STRIP_PHASE   2113: ML_STRIP_AXIS
  2120: ML_SPHERE_RADIUS 2121: ML_SPHERE_SUBDIV
  2122: ML_SPHERE_PHONG
  2130: ML_TUBE_RADIUS   2131: ML_TUBE_SEGS_R
  2132: ML_TUBE_SEGS_H
  2140: ML_BEVEL_SIZE    2141: ML_BEVEL_SUBDIV
"""

import c4d  # type: ignore
import math
import random
import os
import base64
import tempfile


# ════════════════════════════════════════════════════════════════════════
#  Plugin ID & Name
# ════════════════════════════════════════════════════════════════════════

ID_MOLHEXLATTICE  = 1068899
NAME_MOLHEXLATTICE = "Molecular Hex Lattice v2.1"

# ════════════════════════════════════════════════════════════════════════
#  Description IDs — группы (табы)
# ════════════════════════════════════════════════════════════════════════

MHL_GRP_LAT   = 2000
MHL_GRP_STRIP = 2001
MHL_GRP_SPH   = 2002
MHL_GRP_TUB   = 2003
MHL_GRP_BEV   = 2004

# ════════════════════════════════════════════════════════════════════════
#  Description IDs — параметры
# ════════════════════════════════════════════════════════════════════════

ML_SIZE_X        = 2100
ML_SIZE_Y        = 2101
ML_SIZE_Z        = 2102
ML_DENSITY       = 2103
ML_BOND_DENS     = 2104
ML_SEED          = 2105
ML_JITTER        = 2106
ML_HIDE_ISOLATED = 2107

ML_STRIP_AMP     = 2110
ML_STRIP_FREQ    = 2111
ML_STRIP_PHASE   = 2112
ML_STRIP_AXIS    = 2113

ML_SPHERE_RADIUS = 2120
ML_SPHERE_SUBDIV = 2121
ML_SPHERE_PHONG  = 2122

ML_TUBE_RADIUS   = 2130
ML_TUBE_SEGS_R   = 2131
ML_TUBE_SEGS_H   = 2132

ML_BEVEL_SIZE    = 2140
ML_BEVEL_SUBDIV  = 2141

# ════════════════════════════════════════════════════════════════════════
#  Дефолтные значения параметров
# ════════════════════════════════════════════════════════════════════════

DEFAULT_SIZE_X        = 401.0
DEFAULT_SIZE_Y        = 401.0
DEFAULT_SIZE_Z        = 401.0
DEFAULT_DENSITY       = 200.0
DEFAULT_BOND_DENS     = 250.0
DEFAULT_SEED          = 0
DEFAULT_JITTER        = 0

DEFAULT_STRIP_AMP     = 0.0
DEFAULT_STRIP_FREQ    = 0.01
DEFAULT_STRIP_PHASE   = 0.0
DEFAULT_STRIP_AXIS    = 1

DEFAULT_SPHERE_RADIUS = 35.0
DEFAULT_SPHERE_SUBDIV = 1
DEFAULT_SPHERE_PHONG  = math.radians(0.0)

DEFAULT_TUBE_RADIUS   = 6.0
DEFAULT_TUBE_SEGS_R   = 9
DEFAULT_TUBE_SEGS_H   = 2

DEFAULT_BEVEL_SIZE    = 3.0
DEFAULT_BEVEL_SUBDIV  = 0

DEFAULT_HIDE_ISOLATED = True

# ════════════════════════════════════════════════════════════════════════
#  Математика
# ════════════════════════════════════════════════════════════════════════

def _normalize_tuple(v):
    d = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if d < 1e-12:
        return (v[0], v[1], v[2])
    return (v[0]/d, v[1]/d, v[2]/d)


def _midpoint_sphere(a, b):
    return _normalize_tuple(((a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2))


def _v3_normalize(v):
    d = math.sqrt(v.x**2 + v.y**2 + v.z**2)
    if d < 1e-12:
        return c4d.Vector(0, 1, 0)
    return c4d.Vector(v.x/d, v.y/d, v.z/d)


def _v3_len(v):
    return math.sqrt(v.x**2 + v.y**2 + v.z**2)


def _v3_dot(a, b):
    return a.x*b.x + a.y*b.y + a.z*b.z


def _v3_cross(a, b):
    return c4d.Vector(
        a.y*b.z - a.z*b.y,
        a.z*b.x - a.x*b.z,
        a.x*b.y - a.y*b.x
    )


def _v3_lerp(a, b, t):
    return c4d.Vector(
        a.x + (b.x - a.x)*t,
        a.y + (b.y - a.y)*t,
        a.z + (b.z - a.z)*t
    )


# ════════════════════════════════════════════════════════════════════════
#  Dual Icosphere
# ════════════════════════════════════════════════════════════════════════

def _icosphere_tris(subdivisions):
    PHI = (1.0 + math.sqrt(5.0)) / 2.0
    raw = [
        ( 0,  1,  PHI), ( 0, -1,  PHI), ( 0,  1, -PHI), ( 0, -1, -PHI),
        ( 1,  PHI, 0),  (-1,  PHI, 0),  ( 1, -PHI, 0),  (-1, -PHI, 0),
        ( PHI, 0,  1),  (-PHI, 0,  1),  ( PHI, 0, -1),  (-PHI, 0, -1),
    ]
    verts = [list(_normalize_tuple(v)) for v in raw]
    faces = [
        [0,1,8],  [0,8,4],  [0,4,5],  [0,5,9],  [0,9,1],
        [1,6,8],  [8,6,10], [8,10,4], [4,10,2],  [4,2,5],
        [5,2,11], [5,11,9], [9,11,7], [9,7,1],   [1,7,6],
        [3,6,7],  [3,7,11], [3,11,2], [3,2,10],  [3,10,6],
    ]
    for _ in range(subdivisions):
        new_faces  = []
        edge_cache = {}

        def get_mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in edge_cache:
                edge_cache[key] = len(verts)
                verts.append(list(_midpoint_sphere(verts[a], verts[b])))
            return edge_cache[key]

        for f in faces:
            a, b, c = f[0], f[1], f[2]
            ab = get_mid(a, b)
            bc = get_mid(b, c)
            ca = get_mid(c, a)
            new_faces += [[a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]]
        faces = new_faces
    return verts, faces


def _dual_mesh(ico_verts, ico_faces):
    n_verts = len(ico_verts)
    dual_verts = []
    for f in ico_faces:
        cx = (ico_verts[f[0]][0] + ico_verts[f[1]][0] + ico_verts[f[2]][0]) / 3.0
        cy = (ico_verts[f[0]][1] + ico_verts[f[1]][1] + ico_verts[f[2]][1]) / 3.0
        cz = (ico_verts[f[0]][2] + ico_verts[f[1]][2] + ico_verts[f[2]][2]) / 3.0
        dual_verts.append(list(_normalize_tuple((cx, cy, cz))))

    vert_to_faces = [[] for _ in range(n_verts)]
    for fi, f in enumerate(ico_faces):
        for vi in f:
            vert_to_faces[vi].append(fi)

    dual_polys     = []
    face_normals   = []

    for vi in range(n_verts):
        adj = vert_to_faces[vi]
        if len(adj) < 3:
            continue

        nx, ny, nz = ico_verts[vi]

        if abs(nx) < 0.9:
            tx, ty, tz = 1.0, 0.0, 0.0
        else:
            tx, ty, tz = 0.0, 1.0, 0.0
        dot = tx*nx + ty*ny + tz*nz
        tx -= dot*nx; ty -= dot*ny; tz -= dot*nz
        td = math.sqrt(tx**2 + ty**2 + tz**2)
        tx /= td; ty /= td; tz /= td
        bx = ny*tz - nz*ty
        by = nz*tx - nx*tz
        bz = nx*ty - ny*tx

        def _angle(fi, _nx=nx,_ny=ny,_nz=nz,_tx=tx,_ty=ty,_tz=tz,_bx=bx,_by=by,_bz=bz):
            dvx = dual_verts[fi][0] - _nx
            dvy = dual_verts[fi][1] - _ny
            dvz = dual_verts[fi][2] - _nz
            u = dvx*_tx + dvy*_ty + dvz*_tz
            v = dvx*_bx + dvy*_by + dvz*_bz
            return math.atan2(v, u)

        ordered = sorted(adj, key=_angle)

        p0 = c4d.Vector(*dual_verts[ordered[0]])
        p1 = c4d.Vector(*dual_verts[ordered[1]])
        p2 = c4d.Vector(*dual_verts[ordered[2]])
        normal = (p1 - p0).Cross(p2 - p0)
        centroid = c4d.Vector()
        for idx in ordered:
            centroid += c4d.Vector(*dual_verts[idx])
        centroid /= float(len(ordered))
        if normal.Dot(centroid) < 0.0:
            ordered = list(reversed(ordered))

        dual_polys.append(ordered)
        face_normals.append((nx, ny, nz))

    return dual_verts, dual_polys, face_normals


def _build_hex_sphere_data(radius, subdivisions):
    subdivisions = max(1, min(4, int(subdivisions)))
    ico_verts, ico_faces = _icosphere_tris(subdivisions)
    dual_verts, dual_polys, face_normals = _dual_mesh(ico_verts, ico_faces)
    sphere_pts = [c4d.Vector(v[0]*radius, v[1]*radius, v[2]*radius)
                  for v in dual_verts]
    return sphere_pts, dual_polys, face_normals, dual_verts


# ════════════════════════════════════════════════════════════════════════
#  Phong-тег
# ════════════════════════════════════════════════════════════════════════

def _add_phong_tag(obj, angle_deg=45.0):
    tag = obj.MakeTag(c4d.Tphong)
    if tag:
        tag[c4d.PHONGTAG_PHONG_ANGLELIMIT] = True
        tag[c4d.PHONGTAG_PHONG_ANGLE]      = math.radians(angle_deg)
        tag[c4d.PHONGTAG_PHONG_USEEDGES]   = True
    return tag


# ════════════════════════════════════════════════════════════════════════
#  Утилита создания PolygonObject
# ════════════════════════════════════════════════════════════════════════

def _make_poly_object(pts, cpolys, name):
    obj = c4d.PolygonObject(len(pts), len(cpolys))
    obj.SetName(name)
    for i, p in enumerate(pts):
        obj.SetPoint(i, p)
    for i, cp in enumerate(cpolys):
        obj.SetPolygon(i, cp)
    obj.Message(c4d.MSG_UPDATE)
    return obj


# ════════════════════════════════════════════════════════════════════════
#  Гексагональная сфера
# ════════════════════════════════════════════════════════════════════════

def _fan_triangulate(indices, pts):
    n = len(indices)
    if n == 3:
        return [c4d.CPolygon(indices[0], indices[1], indices[2], indices[2])]
    if n == 4:
        return [c4d.CPolygon(indices[0], indices[1], indices[2], indices[3])]
    cx = sum(pts[idx].x for idx in indices) / n
    cy = sum(pts[idx].y for idx in indices) / n
    cz = sum(pts[idx].z for idx in indices) / n
    center_idx = len(pts)
    pts.append(c4d.Vector(cx, cy, cz))
    result = []
    for k in range(n):
        a = indices[k]
        b = indices[(k + 1) % n]
        result.append(c4d.CPolygon(center_idx, a, b, b))
    return result


def _build_sphere_with_holes(radius, subdivisions, hole_face_indices, phong_angle=45.0):
    sphere_pts, dual_polys, face_normals, dual_verts_unit =         _build_hex_sphere_data(radius, subdivisions)

    pts    = list(sphere_pts)
    cpols  = []
    hidden = []

    hole_centers = []
    hole_normals = []

    for fi, poly_idx_list in enumerate(dual_polys):
        if fi in set(hole_face_indices):
            cx = cy = cz = 0.0
            for idx in poly_idx_list:
                cx += pts[idx].x
                cy += pts[idx].y
                cz += pts[idx].z
            n_p = len(poly_idx_list)
            cx /= n_p; cy /= n_p; cz /= n_p
            hole_centers.append(c4d.Vector(cx, cy, cz))
            hole_normals.append(c4d.Vector(*face_normals[fi]))

        start = len(cpols)
        new_cps = _fan_triangulate(poly_idx_list, pts)
        cpols.extend(new_cps)

        n = len(poly_idx_list)
        if n > 4:
            for t in range(n):
                pi = start + t
                hidden.append(4 * pi + 0)

    obj = _make_poly_object(pts, cpols, "MHL_Sphere")

    if hidden:
        eh = obj.GetEdgeH()
        for eid in hidden:
            eh.Select(eid)

    _add_phong_tag(obj, phong_angle)
    return obj, hole_centers, hole_normals


# ════════════════════════════════════════════════════════════════════════
#  Матрица поворота: ось Y → direction
# ════════════════════════════════════════════════════════════════════════

def _matrix_y_to_dir(direction):
    up = _v3_normalize(direction)

    helper = c4d.Vector(0, 0, 1)
    if abs(_v3_dot(up, helper)) > 0.99:
        helper = c4d.Vector(1, 0, 0)

    right  = _v3_normalize(_v3_cross(helper, up))
    fwd    = _v3_normalize(_v3_cross(up, right))

    mg = c4d.Matrix()
    mg.v1 = right
    mg.v2 = up
    mg.v3 = fwd
    mg.off = c4d.Vector(0, 0, 0)
    return mg


# ════════════════════════════════════════════════════════════════════════
#  Генератор трубки + фаски
# ════════════════════════════════════════════════════════════════════════

def _build_tube_between(pt_a, pt_b, tube_radius, segs_r, segs_h,
                         bevel_size, bevel_subdiv):
    diff   = pt_b - pt_a
    length = _v3_len(diff)
    if length < 1e-6:
        return None, []

    direction = _v3_normalize(diff)
    midpoint  = _v3_lerp(pt_a, pt_b, 0.5)

    segs_r       = max(3,   int(segs_r))
    segs_h       = max(1,   int(segs_h))
    bevel_subdiv = max(0,   int(bevel_subdiv))
    bevel_size   = max(0.0, float(bevel_size))

    actual_bevel = min(bevel_size, length * 0.45)
    inner_half   = length * 0.5 - actual_bevel

    tube_pts   = []
    tube_cpols = []

    for row in range(segs_h + 1):
        t = row / segs_h
        y = -inner_half + t * (inner_half * 2.0)
        for col in range(segs_r):
            a = col / segs_r * 2.0 * math.pi
            tube_pts.append(c4d.Vector(
                tube_radius * math.cos(a),
                y,
                tube_radius * math.sin(a)
            ))

    for row in range(segs_h):
        for col in range(segs_r):
            bl = row * segs_r + col
            br = row * segs_r + (col + 1) % segs_r
            tl = (row + 1) * segs_r + col
            tr = (row + 1) * segs_r + (col + 1) % segs_r
            tube_cpols.append(c4d.CPolygon(bl, tl, tr, br))

    tube_obj = _make_poly_object(tube_pts, tube_cpols, "MHL_Tube")
    _add_phong_tag(tube_obj, 45.0)

    mg = _matrix_y_to_dir(direction)
    mg.off = midpoint
    tube_obj.SetMg(mg)

    bevel_list = []

    if actual_bevel > 1e-4:
        n_bev = max(1, bevel_subdiv + 1)

        for end_sign in (-1.0, 1.0):
            bev_pts   = []
            bev_cpols = []

            n_rings = n_bev + 2

            for ring in range(n_rings):
                if ring <= n_bev:
                    t     = ring / n_bev
                    angle = t * math.pi * 0.5
                    r_ring = tube_radius + actual_bevel * math.sin(angle)
                    y_ring = end_sign * (inner_half + actual_bevel * (1.0 - math.cos(angle)))
                else:
                    r_ring = tube_radius + actual_bevel
                    y_ring = end_sign * (inner_half + actual_bevel + actual_bevel)

                for col in range(segs_r):
                    a = col / segs_r * 2.0 * math.pi
                    bev_pts.append(c4d.Vector(
                        r_ring * math.cos(a),
                        y_ring,
                        r_ring * math.sin(a)
                    ))

            for ring in range(n_rings - 1):
                for col in range(segs_r):
                    bl = ring * segs_r + col
                    br = ring * segs_r + (col + 1) % segs_r
                    tl = (ring + 1) * segs_r + col
                    tr = (ring + 1) * segs_r + (col + 1) % segs_r
                    if end_sign < 0:
                        bev_cpols.append(c4d.CPolygon(bl, br, tr, tl))
                    else:
                        bev_cpols.append(c4d.CPolygon(bl, tl, tr, br))

            bev_obj = _make_poly_object(bev_pts, bev_cpols, "MHL_Bevel")
            _add_phong_tag(bev_obj, 45.0)
            bev_obj.SetMg(mg)
            bevel_list.append(bev_obj)

    return tube_obj, bevel_list


# ════════════════════════════════════════════════════════════════════════
#  Генератор позиций и связей
# ════════════════════════════════════════════════════════════════════════

def _generate_positions(size_x, size_y, size_z, density, seed, jitter):
    rng     = random.Random(int(seed))
    density = max(1.0, float(density))
    nx = max(1, int(math.ceil(size_x / density)))
    ny = max(1, int(math.ceil(size_y / density)))
    nz = max(1, int(math.ceil(size_z / density)))

    positions = []
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                x = ix * density - size_x * 0.5
                y = iy * density - size_y * 0.5
                z = iz * density - size_z * 0.5
                if jitter > 1e-4:
                    x += rng.uniform(-jitter, jitter)
                    y += rng.uniform(-jitter, jitter)
                    z += rng.uniform(-jitter, jitter)
                positions.append(c4d.Vector(x, y, z))
    return positions


def _apply_strip(positions, amplitude, frequency, phase, axis):
    if amplitude < 1e-6:
        return positions
    result = []
    for p in positions:
        if axis == 0:
            val = math.sin(p.x * frequency + phase)
            result.append(c4d.Vector(p.x, p.y + amplitude * val, p.z))
        elif axis == 1:
            val = math.sin(p.y * frequency + phase)
            result.append(c4d.Vector(p.x + amplitude * val, p.y, p.z))
        else:
            val = math.sin(p.z * frequency + phase)
            result.append(c4d.Vector(p.x, p.y + amplitude * val, p.z))
    return result


def _find_bonds(positions, max_dist):
    bonds  = []
    max_sq = max_dist * max_dist
    n = len(positions)
    for i in range(n):
        for j in range(i + 1, n):
            d  = positions[i] - positions[j]
            sq = d.x**2 + d.y**2 + d.z**2
            if sq <= max_sq:
                bonds.append((i, j))
    return bonds


def _find_best_face(face_normals, direction):
    best_idx = 0
    best_dot = -2.0
    dx, dy, dz = direction.x, direction.y, direction.z
    for fi, (nx, ny, nz) in enumerate(face_normals):
        dot = nx*dx + ny*dy + nz*dz
        if dot > best_dot:
            best_dot = dot
            best_idx = fi
    return best_idx


# ════════════════════════════════════════════════════════════════════════
#  Теги выделения полигонов
# ════════════════════════════════════════════════════════════════════════

def _apply_selection_tag(obj, selection_name):
    n_polys = obj.GetPolygonCount()
    if n_polys == 0:
        return
    tag = obj.MakeTag(c4d.Tpolygonselection)
    if tag is None:
        return
    tag.SetName(selection_name)
    sel = tag.GetBaseSelect()
    for pi in range(n_polys):
        sel.Select(pi)


# ════════════════════════════════════════════════════════════════════════
#  Главный генератор
# ════════════════════════════════════════════════════════════════════════

def _build_lattice(op):
    size_x      = max(1.0,  float(op[ML_SIZE_X]))
    size_y      = max(1.0,  float(op[ML_SIZE_Y]))
    size_z      = max(1.0,  float(op[ML_SIZE_Z]))
    density     = max(10.0, float(op[ML_DENSITY]))
    bond_dens   = max(1.0,  float(op[ML_BOND_DENS]))
    seed        = int(op[ML_SEED])
    jitter      = max(0.0,  float(op[ML_JITTER]))

    strip_amp   = max(0.0,   float(op[ML_STRIP_AMP]))
    strip_freq  = max(0.0001, float(op[ML_STRIP_FREQ]))
    strip_phase = float(op[ML_STRIP_PHASE])
    strip_axis  = int(op[ML_STRIP_AXIS])

    sphere_r    = max(1.0,  float(op[ML_SPHERE_RADIUS]))
    sphere_sub  = max(1,    min(4, int(op[ML_SPHERE_SUBDIV])))

    tube_r      = max(0.5,  float(op[ML_TUBE_RADIUS]))
    tube_sr     = max(3,    int(op[ML_TUBE_SEGS_R]))
    tube_sh     = max(1,    int(op[ML_TUBE_SEGS_H]))

    bevel_size  = max(0.0,  float(op[ML_BEVEL_SIZE]))
    bevel_sub   = max(0,    int(op[ML_BEVEL_SUBDIV]))

    sphere_phong = math.degrees(max(0.0, min(math.radians(180.0), float(op[ML_SPHERE_PHONG]))))

    hide_isolated = bool(op[ML_HIDE_ISOLATED])

    positions_raw = _generate_positions(size_x, size_y, size_z, density, seed, jitter)

    MAX_NODES = 150
    if len(positions_raw) > MAX_NODES:
        positions_raw = positions_raw[:MAX_NODES]

    positions = _apply_strip(positions_raw, strip_amp, strip_freq, strip_phase, strip_axis)

    if not positions:
        null = c4d.BaseObject(c4d.Onull)
        null.SetName("MolecularHexLattice [пусто]")
        return null

    bonds = _find_bonds(positions, bond_dens)

    MAX_BONDS = 500
    if len(bonds) > MAX_BONDS:
        bonds = bonds[:MAX_BONDS]

    _, _, face_normals, _ = _build_hex_sphere_data(1.0, sphere_sub)
    n_faces = len(face_normals)

    node_holes = [[] for _ in range(len(positions))]

    for i, j in bonds:
        dir_ij = _v3_normalize(positions[j] - positions[i])
        dir_ji = _v3_normalize(positions[i] - positions[j])

        fi_ij = _find_best_face(face_normals, dir_ij)
        fi_ji = _find_best_face(face_normals, dir_ji)

        if fi_ij not in node_holes[i]:
            node_holes[i].append(fi_ij)
        if fi_ji not in node_holes[j]:
            node_holes[j].append(fi_ji)

    if hide_isolated:
        connected = set()
        for i, j in bonds:
            connected.add(i)
            connected.add(j)

        remap = {}
        new_positions  = []
        new_node_holes = []
        for old_idx, pos in enumerate(positions):
            if old_idx in connected:
                remap[old_idx] = len(new_positions)
                new_positions.append(pos)
                new_node_holes.append(node_holes[old_idx])

        positions  = new_positions
        node_holes = new_node_holes
        bonds = [(remap[i], remap[j]) for i, j in bonds]

    root = c4d.BaseObject(c4d.Onull)
    root.SetName("MolecularHexLattice")

    g_spheres = c4d.BaseObject(c4d.Onull)
    g_spheres.SetName("Spheres")
    g_spheres.InsertUnder(root)

    g_tubes = c4d.BaseObject(c4d.Onull)
    g_tubes.SetName("Tubes")
    g_tubes.InsertUnder(root)

    g_bevels = c4d.BaseObject(c4d.Onull)
    g_bevels.SetName("Bevels")
    g_bevels.InsertUnder(root)

    for node_idx, pos in enumerate(positions):
        hole_faces = [f for f in node_holes[node_idx] if f < n_faces]

        sphere_obj, hole_centers, hole_normals =             _build_sphere_with_holes(sphere_r, sphere_sub, hole_faces, sphere_phong)

        sphere_obj.SetAbsPos(pos)
        sphere_obj.SetName("Sphere_%03d" % node_idx)
        _apply_selection_tag(sphere_obj, "M")
        sphere_obj.InsertUnder(g_spheres)

    for bond_idx, (i, j) in enumerate(bonds):
        pi = positions[i]
        pj = positions[j]
        diff   = pj - pi
        length = _v3_len(diff)
        if length < 1e-6:
            continue

        dir_n = _v3_normalize(diff)

        pt_a = pi + dir_n * sphere_r
        pt_b = pj - dir_n * sphere_r

        tube_len = _v3_len(pt_b - pt_a)
        if tube_len < tube_r * 0.1:
            continue

        tube_obj, bevel_list = _build_tube_between(
            pt_a, pt_b,
            tube_r, tube_sr, tube_sh,
            bevel_size, bevel_sub
        )

        if tube_obj is not None:
            tube_obj.SetName("Tube_%03d" % bond_idx)
            _apply_selection_tag(tube_obj, "T")
            tube_obj.InsertUnder(g_tubes)

        for bv_idx, bev_obj in enumerate(bevel_list):
            bev_obj.SetName("Bevel_%03d_%d" % (bond_idx, bv_idx))
            _apply_selection_tag(bev_obj, "F")
            bev_obj.InsertUnder(g_bevels)

    return root


# ════════════════════════════════════════════════════════════════════════
#  Plugin class
# ════════════════════════════════════════════════════════════════════════

class MolecularHexLatticeObject(c4d.plugins.ObjectData):

    OBJECT_NAME = "Molecular Hex Lattice"

    def Init(self, op, isload=False):
        if not isload:
            op.SetName(self.OBJECT_NAME)
            op[ML_SIZE_X]        = DEFAULT_SIZE_X
            op[ML_SIZE_Y]        = DEFAULT_SIZE_Y
            op[ML_SIZE_Z]        = DEFAULT_SIZE_Z
            op[ML_DENSITY]       = DEFAULT_DENSITY
            op[ML_BOND_DENS]     = DEFAULT_BOND_DENS
            op[ML_SEED]          = DEFAULT_SEED
            op[ML_JITTER]        = DEFAULT_JITTER
            op[ML_HIDE_ISOLATED] = DEFAULT_HIDE_ISOLATED

            op[ML_STRIP_AMP]    = DEFAULT_STRIP_AMP
            op[ML_STRIP_FREQ]   = DEFAULT_STRIP_FREQ
            op[ML_STRIP_PHASE]  = DEFAULT_STRIP_PHASE
            op[ML_STRIP_AXIS]   = DEFAULT_STRIP_AXIS

            op[ML_SPHERE_RADIUS] = DEFAULT_SPHERE_RADIUS
            op[ML_SPHERE_SUBDIV] = DEFAULT_SPHERE_SUBDIV
            op[ML_SPHERE_PHONG]  = DEFAULT_SPHERE_PHONG

            op[ML_TUBE_RADIUS]  = DEFAULT_TUBE_RADIUS
            op[ML_TUBE_SEGS_R]  = DEFAULT_TUBE_SEGS_R
            op[ML_TUBE_SEGS_H]  = DEFAULT_TUBE_SEGS_H

            op[ML_BEVEL_SIZE]   = DEFAULT_BEVEL_SIZE
            op[ML_BEVEL_SUBDIV] = DEFAULT_BEVEL_SUBDIV
        return True

    def GetVirtualObjects(self, op, hh):
        return _build_lattice(op)

    def GetDDescription(self, op, description, flags):
        if not description.LoadDescription("Obase"):
            return False, flags

        # ── Каркас (Lattice) ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Каркас (Lattice)"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(MHL_GRP_LAT, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_lat = c4d.DescID(c4d.DescLevel(MHL_GRP_LAT, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Размер X"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_SIZE_X
        bc[c4d.DESC_MIN]       = 10.0
        bc[c4d.DESC_MAX]       = 100000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_SIZE_X, c4d.DTYPE_REAL, 0)),
            bc, gid_lat
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Размер Y"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_SIZE_Y
        bc[c4d.DESC_MIN]       = 10.0
        bc[c4d.DESC_MAX]       = 100000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_SIZE_Y, c4d.DTYPE_REAL, 0)),
            bc, gid_lat
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Размер Z"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_SIZE_Z
        bc[c4d.DESC_MIN]       = 10.0
        bc[c4d.DESC_MAX]       = 100000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_SIZE_Z, c4d.DTYPE_REAL, 0)),
            bc, gid_lat
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Плотность (шаг сетки)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_DENSITY
        bc[c4d.DESC_MIN]       = 10.0
        bc[c4d.DESC_MAX]       = 10000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 10.0
        bc[c4d.DESC_MAXSLIDER] = 500.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_DENSITY, c4d.DTYPE_REAL, 0)),
            bc, gid_lat
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Макс. длина связи"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_BOND_DENS
        bc[c4d.DESC_MIN]       = 10.0
        bc[c4d.DESC_MAX]       = 10000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 10.0
        bc[c4d.DESC_MAXSLIDER] = 400.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_BOND_DENS, c4d.DTYPE_REAL, 0)),
            bc, gid_lat
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Seed"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_SEED
        bc[c4d.DESC_MIN]       = 0
        bc[c4d.DESC_MAX]       = 99999
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_SEED, c4d.DTYPE_LONG, 0)),
            bc, gid_lat
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Джиттер (шум позиций)"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_JITTER
        bc[c4d.DESC_MIN]       = 0.0
        bc[c4d.DESC_MAX]       = 5000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.0
        bc[c4d.DESC_MAXSLIDER] = 500.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_JITTER, c4d.DTYPE_REAL, 0)),
            bc, gid_lat
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_BOOL)
        bc[c4d.DESC_NAME]    = "Скрывать одиночные шары"
        bc[c4d.DESC_DEFAULT] = DEFAULT_HIDE_ISOLATED
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_HIDE_ISOLATED, c4d.DTYPE_BOOL, 0)),
            bc, gid_lat
        )

        # ── Strip — волновое смещение ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Strip — волновое смещение"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(MHL_GRP_STRIP, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_strip = c4d.DescID(c4d.DescLevel(MHL_GRP_STRIP, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Амплитуда"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_STRIP_AMP
        bc[c4d.DESC_MIN]       = 0.0
        bc[c4d.DESC_MAX]       = 10000.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]      = 1.0
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.0
        bc[c4d.DESC_MAXSLIDER] = 500.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_STRIP_AMP, c4d.DTYPE_REAL, 0)),
            bc, gid_strip
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]      = "Частота"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_STRIP_FREQ
        bc[c4d.DESC_MIN]       = 0.0001
        bc[c4d.DESC_MAX]       = 10.0
        bc[c4d.DESC_UNIT]      = c4d.DESC_UNIT_FLOAT
        bc[c4d.DESC_STEP]      = 0.001
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.0001
        bc[c4d.DESC_MAXSLIDER] = 10.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_STRIP_FREQ, c4d.DTYPE_REAL, 0)),
            bc, gid_strip
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Фаза (анимировать)"
        bc[c4d.DESC_DEFAULT] = DEFAULT_STRIP_PHASE
        bc[c4d.DESC_MIN]     = -1000.0
        bc[c4d.DESC_MAX]     = 1000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_FLOAT
        bc[c4d.DESC_STEP]    = 0.01
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = -10
        bc[c4d.DESC_MAXSLIDER] = 10
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_STRIP_PHASE, c4d.DTYPE_REAL, 0)),
            bc, gid_strip
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Ось волны"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_STRIP_AXIS
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_CYCLE
        cyc = c4d.BaseContainer()
        cyc[0] = "X (смещение Y)"
        cyc[1] = "Y (смещение X)"
        cyc[2] = "Z (смещение Y)"
        bc[c4d.DESC_CYCLE] = cyc
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_STRIP_AXIS, c4d.DTYPE_LONG, 0)),
            bc, gid_strip
        )

        # ── Шары [M] ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Шары  [M]"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(MHL_GRP_SPH, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_sph = c4d.DescID(c4d.DescLevel(MHL_GRP_SPH, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Радиус шара"
        bc[c4d.DESC_DEFAULT] = DEFAULT_SPHERE_RADIUS
        bc[c4d.DESC_MIN]     = 1.0
        bc[c4d.DESC_MAX]     = 100000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 10
        bc[c4d.DESC_MAXSLIDER] = 100
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_SPHERE_RADIUS, c4d.DTYPE_REAL, 0)),
            bc, gid_sph
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Подразделение"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_SPHERE_SUBDIV
        bc[c4d.DESC_MIN]       = 1
        bc[c4d.DESC_MAX]       = 4
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 1
        bc[c4d.DESC_MAXSLIDER] = 4
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_SPHERE_SUBDIV, c4d.DTYPE_LONG, 0)),
            bc, gid_sph
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Фонг шаров"
        bc[c4d.DESC_DEFAULT] = DEFAULT_SPHERE_PHONG
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = math.radians(180.0)
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_DEGREE
        bc[c4d.DESC_STEP]    = math.radians(1.0)
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.0
        bc[c4d.DESC_MAXSLIDER] = 180.0
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_SPHERE_PHONG, c4d.DTYPE_REAL, 0)),
            bc, gid_sph
        )

        # ── Трубки [T] ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Трубки  [T]"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(MHL_GRP_TUB, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_tub = c4d.DescID(c4d.DescLevel(MHL_GRP_TUB, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Радиус трубки"
        bc[c4d.DESC_DEFAULT] = DEFAULT_TUBE_RADIUS
        bc[c4d.DESC_MIN]     = 0.5
        bc[c4d.DESC_MAX]     = 100000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 0.5
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0.5
        bc[c4d.DESC_MAXSLIDER] = 100
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_TUBE_RADIUS, c4d.DTYPE_REAL, 0)),
            bc, gid_tub
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Сегменты окружности"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_TUBE_SEGS_R
        bc[c4d.DESC_MIN]       = 3
        bc[c4d.DESC_MAX]       = 300
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 3
        bc[c4d.DESC_MAXSLIDER] = 20
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_TUBE_SEGS_R, c4d.DTYPE_LONG, 0)),
            bc, gid_tub
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Сегменты длины"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_TUBE_SEGS_H
        bc[c4d.DESC_MIN]       = 1
        bc[c4d.DESC_MAX]       = 300
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 1
        bc[c4d.DESC_MAXSLIDER] = 20
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_TUBE_SEGS_H, c4d.DTYPE_LONG, 0)),
            bc, gid_tub
        )

        # ── Фаска [F] ──
        bc = c4d.GetCustomDatatypeDefault(c4d.DTYPE_GROUP)
        bc[c4d.DESC_NAME]    = "Фаска  [F]"
        bc[c4d.DESC_COLUMNS] = 1
        bc[c4d.DESC_DEFAULT] = 1
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(MHL_GRP_BEV, c4d.DTYPE_GROUP, 0)),
            bc, c4d.ID_LISTHEAD
        )
        gid_bev = c4d.DescID(c4d.DescLevel(MHL_GRP_BEV, c4d.DTYPE_GROUP, 0))

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_REAL)
        bc[c4d.DESC_NAME]    = "Размер фаски"
        bc[c4d.DESC_DEFAULT] = DEFAULT_BEVEL_SIZE
        bc[c4d.DESC_MIN]     = 0.0
        bc[c4d.DESC_MAX]     = 100000.0
        bc[c4d.DESC_UNIT]    = c4d.DESC_UNIT_METER
        bc[c4d.DESC_STEP]    = 1.0
        bc[c4d.DESC_ANIMATE] = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 1
        bc[c4d.DESC_MAXSLIDER] = 30
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_BEVEL_SIZE, c4d.DTYPE_REAL, 0)),
            bc, gid_bev
        )

        bc = c4d.GetCustomDataTypeDefault(c4d.DTYPE_LONG)
        bc[c4d.DESC_NAME]      = "Подразделение фаски"
        bc[c4d.DESC_DEFAULT]   = DEFAULT_BEVEL_SUBDIV
        bc[c4d.DESC_MIN]       = 0
        bc[c4d.DESC_MAX]       = 8
        bc[c4d.DESC_STEP]      = 1
        bc[c4d.DESC_ANIMATE]   = c4d.DESC_ANIMATE_ON
        bc[c4d.DESC_CUSTOMGUI] = c4d.CUSTOMGUI_REALSLIDER
        bc[c4d.DESC_MINSLIDER] = 0
        bc[c4d.DESC_MAXSLIDER] = 8
        description.SetParameter(
            c4d.DescID(c4d.DescLevel(ML_BEVEL_SUBDIV, c4d.DTYPE_LONG, 0)),
            bc, gid_bev
        )

        return True, flags | c4d.DESCFLAGS_DESC_LOADED

    def CheckDirty(self, op, doc):
        op.SetDirty(c4d.DIRTYFLAGS_DATA)

    def Draw(self, op, drawpass, bd, bh):
        return c4d.DRAWRESULT_OK

_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAAsTAAALEwEAmpwYAAAE7mlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgOS4xLWMwMDIgNzkuNzhiNzYzOCwgMjAyNS8wMi8xMS0xOToxMDowOCAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1sbnM6eG1wTU09Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9tbS8iIHhtbG5zOnN0RXZ0PSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvc1R5cGUvUmVzb3VyY2VFdmVudCMiIHhtcDpDcmVhdG9yVG9vbD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjYtMDYtMTZUMTY6MzU6MTkrMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjYtMDYtMTZUMTY6MzU6MTkrMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiB4bXBNTTpJbnN0YW5jZUlEPSJ4bXAuaWlkOmY4Y2Y1MGViLTc0NzctNWQ0MC04MjU1LThiNGU0NTY4ZTA4NCIgeG1wTU06RG9jdW1lbnRJRD0ieG1wLmRpZDpmOGNmNTBlYi03NDc3LTVkNDAtODI1NS04YjRlNDU2OGUwODQiIHhtcE1NOk9yaWdpbmFsRG9jdW1lbnRJRD0ieG1wLmRpZDpmOGNmNTBlYi03NDc3LTVkNDAtODI1NS04YjRlNDU2OGUwODQiPiA8eG1wTU06SGlzdG9yeT4gPHJkZjpTZXE+IDxyZGY6bGkgc3RFdnQ6YWN0aW9uPSJjcmVhdGVkIiBzdEV2dDppbnN0YW5jZUlEPSJ4bXAuaWlkOmY4Y2Y1MGViLTc0NzctNWQ0MC04MjU1LThiNGU0NTY4ZTA4NCIgc3RFdnQ6d2hlbj0iMjAyNi0wNi0xNlQxNjozMzowOSswMzowMCIgc3RFdnQ6c29mdHdhcmVBZ2VudD0iQWRvYmUgUGhvdG9zaG9wIDI2LjUgKFdpbmRvd3MpIi8+IDwvcmRmOlNlcT4gPC94bXBNTTpIaXN0b3J5PiA8L3JkZjpEZXNjcmlwdGlvbj4gPC9yZGY6UkRGPiA8L3g6eG1wbWV0YT4gPD94cGFja2V0IGVuZD0iciI/PnsS39sAAALqSURBVFiF7VdfSFNRHP5+95h/t6kRhCQlOCkwBtKb4EMYvkRBL8GmD1K+VfagRI8+mhulZk+hLEwRIgJ7K98iyyxpdyjB7rYwihg1QueG5T2/HuZ0rrnt3iB78IPB7mG/7zs7v+985x5iZuwllD1V/x8mANMt8AXdUDUdqqbDF3Sb1SZmBhGBb5/oBnMndDFKN5bu5a1WtQ0AYvNJh8NelFcwQ4OZky3gYbsNEkNgapICIzxst+UiGnNyjzUhUuKwJoQYc3JPTvFhu01KGgJTExR5N6WR7gEGgLhSjIqW6Tkshh2ZJOMd3PrAxZ8Ugufs66oIgSSBZNvbymWF4PG6+PtYO5/7Q30x7LC2PHkTFyXbY9ESuTUB6tZWIJVrABbGa04/jIuSGui6D6r2Baqmk0/TL4xEl3WJGQbKJeH81PXqw+yoF+yoF4+vHDwmFJwhIK4wpi8O/oiQb9MfajAEXX8fKyqtHT3S9gjAAiCvUt9iLPm3dzOhPzgAVePUxzoXZm879+ZaZgDwtnOvdS7M6bXwBweytiXdhFmhajq221SQ0Tbr0g0q4bCLbD/bMuGuILjL1wXK1wVA8BQknqzzpNXl3qL5csDr4iWvi5cKFjdQl38F/gH2J5DbA76gu2w+xGXzITaU9wXWFbINDee9kTpDJrQmhCg4iNLOiXzIlwMeAHoq78Fwb+V9OFwFv9YPv9aPQMCWOifAcKfOCQB6vvzI3YIMjHdwq5Twrh/g2ptdyzJauaEAQPVKkbx1/6hS/IuiktB5aYKeFsLHzOZeSJonvs7syHpV45aJyDOjPKaDaPbk6qvMsReO1VkzXOZyYK30DoBE2kgcFmXQDJUhD+xAIGBDAiEAgPhZh8bGmFGKvzsLGhpWAIoAFDEjnoLpFeC+U4dGjzd/ZCJ0fXhZR33vvhnmYEZhyZYNltjU5c/PK5LfMQmgzQyN+RYQtvcvw/T9zvwKrFqcsKxNAgBEzGmWhvYvp3s9gd83v5eCf3My/wAAAABJRU5ErkJggg=="
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


ICON_B64 = _make_icon()

# ══════════════════════════════════════════════════════════════════════════════
#  Точка входа — регистрация плагина
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    c4d.plugins.RegisterObjectPlugin(
        id          = ID_MOLHEXLATTICE,
        str         = NAME_MOLHEXLATTICE,
        g           = MolecularHexLatticeObject,
        description = "Obase",
        icon        = ICON_B64,
        info        = c4d.OBJECT_GENERATOR,
    )
