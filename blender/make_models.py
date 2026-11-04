# Gera os modelos do jogo "Último de Pé" dentro do Blender (modo sem tela).
# Uso: blender -b --factory-startup -P blender/make_models.py -- <pasta_saida>
# Tudo é modelado por código: corpo liso (Skin + Subdivision), esqueleto,
# pesos calculados, animações e armas. Visual original do jogo.
import bpy, bmesh, math, sys, os, traceback
from mathutils import Vector, Matrix

OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '.'
os.makedirs(OUT, exist_ok=True)
FPS = 30

def log(*a):
    print('[modelos]', *a, flush=True)

def reset():
    MATS.clear()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = FPS

MATS = {}
def material(name, rgb, rough=0.7, metal=0.0):
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    MATS[name] = m
    return m

def srgb(h):
    r, g, b = ((h >> 16) & 255) / 255, ((h >> 8) & 255) / 255, (h & 255) / 255
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (f(r), f(g), f(b))

def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj

def bake(obj):
    """Aplica todos os modificadores (sem operadores)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    obj.modifiers.clear()
    old = obj.data
    obj.data = me
    bpy.data.meshes.remove(old)
    return obj

def mesh_obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))

def smooth(obj):
    for p in obj.data.polygons:
        p.use_smooth = True

def uv_sphere(name, loc, scale, seg=20, rings=12):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=1.0)
    bmesh.ops.scale(bm, vec=Vector(scale), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(loc), verts=bm.verts)
    o = mesh_obj(name, bm)
    smooth(o)
    return o

def rbox(name, loc, size, bevel=0.01, segs=2, rot=None):
    from mathutils import Euler
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if rot:
        bmesh.ops.rotate(bm, cent=Vector((0, 0, 0)), matrix=Euler(rot).to_matrix(), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(loc), verts=bm.verts)
    o = mesh_obj(name, bm)
    if bevel > 0:
        m = o.modifiers.new('b', 'BEVEL')
        m.width = bevel
        m.segments = segs
        m.limit_method = 'ANGLE'
        bake(o)
    smooth(o)
    return o

def cylinder(name, a, b, r1, r2=None, seg=16):
    r2 = r1 if r2 is None else r2
    a, b = Vector(a), Vector(b)
    d = b - a
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=d.length)
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation((a + b) / 2) @ rot, verts=bm.verts)
    o = mesh_obj(name, bm)
    smooth(o)
    return o

def set_mat(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)

def join(objs, name):
    """Junta vários objetos num só, mantendo materiais."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = name
    o.data.name = name
    return o

# --------------------------------------------------------------------------
# PERSONAGEM
# --------------------------------------------------------------------------
# Personagem olha para -Y no Blender (vira +Z no jogo). Lado L = +X.
BONES = [
    # nome, cabeça, cauda, pai
    ('hips', (0, 0, 0.96), (0, 0, 1.10), None),
    ('spine', (0, 0, 1.10), (0, 0, 1.30), 'hips'),
    ('chest', (0, 0, 1.30), (0, 0, 1.52), 'spine'),
    ('neck', (0, 0, 1.52), (0, 0, 1.62), 'chest'),
    ('head', (0, 0, 1.62), (0, 0, 1.90), 'neck'),
]
for s, n in ((1, 'L'), (-1, 'R')):
    BONES += [
        ('shoulder.' + n, (0.05 * s, 0, 1.48), (0.19 * s, 0, 1.49), 'chest'),
        ('upperarm.' + n, (0.19 * s, 0, 1.49), (0.30 * s, 0.01, 1.22), 'shoulder.' + n),
        ('forearm.' + n, (0.30 * s, 0.01, 1.22), (0.37 * s, -0.01, 0.99), 'upperarm.' + n),
        ('hand.' + n, (0.37 * s, -0.01, 0.99), (0.39 * s, -0.02, 0.87), 'forearm.' + n),
        ('thigh.' + n, (0.10 * s, 0, 0.95), (0.11 * s, -0.01, 0.53), 'hips'),
        ('shin.' + n, (0.11 * s, -0.01, 0.53), (0.12 * s, 0.01, 0.10), 'thigh.' + n),
        ('foot.' + n, (0.12 * s, 0.01, 0.10), (0.12 * s, -0.13, 0.03), 'shin.' + n),
    ]

def make_body():
    # esqueleto de vértices para o modificador Skin (raio x, raio y)
    V, E, RAD = [], [], []
    def v(p, r):
        V.append(Vector(p)); RAD.append(r); return len(V) - 1
    def e(a, b):
        E.append((a, b))
    p0 = v((0, 0, 0.90), (0.145, 0.10))
    p1 = v((0, 0, 1.00), (0.16, 0.11))
    p2 = v((0, 0, 1.12), (0.14, 0.095))
    p3 = v((0, 0, 1.27), (0.16, 0.10))
    p4 = v((0, 0, 1.41), (0.185, 0.112))
    p5 = v((0, 0, 1.50), (0.15, 0.10))
    p6 = v((0, 0, 1.56), (0.055, 0.055))
    p7 = v((0, 0, 1.64), (0.05, 0.05))
    for a, b in ((p0, p1), (p1, p2), (p2, p3), (p3, p4), (p4, p5), (p5, p6), (p6, p7)):
        e(a, b)
    for s in (1, -1):
        sh = v((0.19 * s, 0, 1.485), (0.066, 0.066)); e(p5, sh)
        ua = v((0.25 * s, 0.005, 1.36), (0.056, 0.056)); e(sh, ua)
        el = v((0.30 * s, 0.01, 1.22), (0.046, 0.046)); e(ua, el)
        fa = v((0.335 * s, 0, 1.10), (0.045, 0.04)); e(el, fa)
        wr = v((0.37 * s, -0.01, 0.99), (0.034, 0.03)); e(fa, wr)
        ha = v((0.383 * s, -0.015, 0.925), (0.044, 0.022)); e(wr, ha)
        fi = v((0.39 * s, -0.02, 0.87), (0.034, 0.018)); e(ha, fi)
        hp = v((0.10 * s, 0, 0.92), (0.088, 0.088)); e(p0, hp)
        mt = v((0.105 * s, 0, 0.74), (0.077, 0.077)); e(hp, mt)
        kn = v((0.11 * s, -0.01, 0.53), (0.06, 0.06)); e(mt, kn)
        ms = v((0.115 * s, 0, 0.31), (0.055, 0.055)); e(kn, ms)
        an = v((0.12 * s, 0.01, 0.11), (0.042, 0.046)); e(ms, an)
        to = v((0.12 * s, -0.12, 0.045), (0.05, 0.035)); e(an, to)
    me = bpy.data.meshes.new('body')
    me.from_pydata([tuple(x) for x in V], E, [])
    o = link(bpy.data.objects.new('body', me))
    sk = o.modifiers.new('skin', 'SKIN')
    sk.branch_smoothing = 0.6
    sk.use_smooth_shade = True
    for i, r in enumerate(RAD):
        sv = me.skin_vertices[0].data[i]
        sv.radius = r
        sv.use_root = (i == 0)
    ss = o.modifiers.new('sub', 'SUBSURF')
    ss.levels = 2
    ss.render_levels = 2
    bake(o)
    smooth(o)
    # zonas de roupa por posição do polígono
    names = ['skin', 'shirt', 'sleeve', 'pants', 'shoes', 'belt']
    mats = {
        'skin': material('skin', srgb(0xe0ac69), 0.55),
        'shirt': material('shirt', srgb(0xff8a1e), 0.75),
        'sleeve': material('sleeve', srgb(0xff8a1e), 0.75),
        'pants': material('pants', srgb(0x2b2d42), 0.8),
        'shoes': material('shoes', srgb(0x2b2b2b), 0.5),
        'belt': material('belt', srgb(0x2a1e14), 0.6),
    }
    for n in names:
        o.data.materials.append(mats[n])
    for p in o.data.polygons:
        c = p.center
        ax = abs(c.x)
        if c.z < 0.115:
            z = 'shoes'
        elif c.z > 1.535 and ax < 0.09:
            z = 'skin'
        elif ax > 0.33 and c.z < 1.02:
            z = 'skin'          # mãos
        elif ax > 0.27 and c.z < 1.2:
            z = 'sleeve'        # antebraço (manga curta ou comprida)
        elif 0.99 < c.z < 1.055 and ax < 0.2:
            z = 'belt'
        elif c.z < 1.0 and ax < 0.22:
            z = 'pants'
        else:
            z = 'shirt'
        p.material_index = names.index(z)
    return o

def make_head():
    parts = []
    h = uv_sphere('h', (0, -0.005, 1.765), (0.122, 0.13, 0.14), 24, 16)
    set_mat(h, material('skin', srgb(0xe0ac69), 0.55)); parts.append(h)
    # queixo/maxilar
    j = uv_sphere('j', (0, -0.035, 1.70), (0.095, 0.09, 0.07), 16, 10)
    set_mat(j, material('skin', srgb(0xe0ac69), 0.55)); parts.append(j)
    n = uv_sphere('n', (0, -0.13, 1.745), (0.02, 0.03, 0.03), 12, 8)
    set_mat(n, material('skin', srgb(0xe0ac69), 0.55)); parts.append(n)
    for s in (1, -1):
        ear = uv_sphere('e', (0.12 * s, 0, 1.76), (0.02, 0.03, 0.04), 12, 8)
        set_mat(ear, material('skin', srgb(0xe0ac69), 0.55)); parts.append(ear)
        ew = uv_sphere('ew', (0.045 * s, -0.112, 1.785), (0.026, 0.012, 0.018), 14, 8)
        set_mat(ew, material('eye_white', srgb(0xf4f4f0), 0.3)); parts.append(ew)
        pu = uv_sphere('pu', (0.044 * s, -0.122, 1.785), (0.012, 0.006, 0.013), 12, 8)
        set_mat(pu, material('eye_dark', srgb(0x1b120c), 0.2)); parts.append(pu)
        br = rbox('br', (0.047 * s, -0.115, 1.815), (0.045, 0.012, 0.009), 0.003, rot=(0, -0.12 * s, 0))
        set_mat(br, material('hair', srgb(0x1b1b1b), 0.8)); parts.append(br)
    m = rbox('m', (0, -0.118, 1.705), (0.045, 0.01, 0.008), 0.003)
    set_mat(m, material('mouth', srgb(0x7a3b2e), 0.6)); parts.append(m)
    for p in parts:
        bpy.context.view_layer.objects.active = p
    # aplica rotações antes de juntar
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    return join(parts, 'head')

def cut_below(obj, fn):
    bm = bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if fn(v.co)], context='VERTS')
    bm.to_mesh(obj.data); bm.free()
    return obj

def make_hairs():
    hm = material('hair', srgb(0x1b1b1b), 0.8)
    cm = material('cap', srgb(0x1d3557), 0.7)
    out = []
    # 1) curto
    a = uv_sphere('hair_short', (0, 0.0, 1.775), (0.132, 0.142, 0.15), 24, 16)
    cut_below(a, lambda c: c.z < 1.845 and c.y < -0.03 or c.z < 1.70)
    sol = a.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.012; bake(a); smooth(a)
    set_mat(a, hm); out.append(a)
    # 2) boné
    b1 = uv_sphere('cap_top', (0, 0.0, 1.835), (0.137, 0.145, 0.115), 24, 14)
    cut_below(b1, lambda c: c.z < 1.83)
    sol = b1.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.015; bake(b1); smooth(b1)
    set_mat(b1, cm)
    br = cylinder('brim', (0, -0.15, 1.832), (0, -0.15, 1.845), 0.11, 0.11, 24)
    br.scale = (1, 0.9, 1)
    set_mat(br, cm)
    back = uv_sphere('hb', (0, 0.02, 1.75), (0.128, 0.13, 0.1), 20, 12)
    cut_below(back, lambda c: c.y < -0.02 or c.z < 1.69)
    set_mat(back, hm)
    for o in (b1, br, back):
        o.select_set(True)
    bpy.context.view_layer.objects.active = br
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    out.append(join([b1, br, back], 'hair_cap'))
    # 3) moicano
    base = uv_sphere('mb', (0, 0.0, 1.77), (0.126, 0.137, 0.142), 20, 12)
    cut_below(base, lambda c: c.z < 1.845 and c.y < -0.03 or c.z < 1.69)
    set_mat(base, hm)
    spikes = [base]
    for k in range(6):
        y = -0.09 + k * 0.04
        c = cylinder('sp', (0, y, 1.86 - abs(k - 2) * 0.008), (0, y + 0.03, 1.97 - abs(k - 2.5) * 0.02), 0.03, 0.002, 10)
        set_mat(c, hm); spikes.append(c)
    out.append(join(spikes, 'hair_mohawk'))
    # 4) comprido com rabo de cavalo
    l1 = uv_sphere('l1', (0, 0.0, 1.775), (0.134, 0.144, 0.152), 24, 16)
    cut_below(l1, lambda c: c.z < 1.845 and c.y < -0.03 or c.z < 1.66)
    set_mat(l1, hm)
    tail = cylinder('tail', (0, 0.13, 1.77), (0, 0.17, 1.52), 0.045, 0.02, 14); set_mat(tail, hm)
    tie = cylinder('tie', (0, 0.135, 1.765), (0, 0.142, 1.74), 0.048, 0.048, 14); set_mat(tie, cm)
    out.append(join([l1, tail, tie], 'hair_long'))
    # 5) bandana
    bd = uv_sphere('bd', (0, 0.0, 1.79), (0.133, 0.143, 0.145), 24, 16)
    cut_below(bd, lambda c: c.z < 1.835)
    set_mat(bd, cm)
    kn = uv_sphere('kn', (0, 0.14, 1.79), (0.03, 0.025, 0.03), 12, 8); set_mat(kn, cm)
    t1 = rbox('t1', (0.02, 0.15, 1.73), (0.025, 0.008, 0.09), 0.003); set_mat(t1, cm)
    hb = uv_sphere('hb2', (0, 0.02, 1.75), (0.128, 0.13, 0.1), 20, 12)
    cut_below(hb, lambda c: c.y < -0.02 or c.z < 1.69); set_mat(hb, hm)
    out.append(join([bd, kn, t1, hb], 'hair_bandana'))
    return out

def make_gear():
    pk = material('pack', srgb(0x55613f), 0.8)
    st = material('strap', srgb(0x2a2a2a), 0.7)
    vs = material('vest', srgb(0x3c5a7a), 0.6)
    vd = material('vest_dark', srgb(0x2c4258), 0.6)
    # mochila
    p1 = rbox('p1', (0, 0.16, 1.30), (0.30, 0.13, 0.36), 0.04, 3); set_mat(p1, pk)
    p2 = rbox('p2', (0, 0.235, 1.22), (0.22, 0.05, 0.14), 0.015); set_mat(p2, pk)
    parts = [p1, p2]
    for s in (1, -1):
        a = rbox('st', (0.085 * s, -0.1, 1.36), (0.035, 0.012, 0.3), 0.004, rot=(0.15, 0, 0)); set_mat(a, st); parts.append(a)
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    bag = join(parts, 'backpack')
    # colete (some até pegar um)
    v1 = cylinder('v1', (0, -0.005, 1.15), (0, -0.005, 1.52), 0.185, 0.2, 20); v1.scale = (1, 0.68, 1)
    v1.select_set(True); bpy.context.view_layer.objects.active = v1
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bm = bmesh.new(); bm.from_mesh(v1.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if abs(f.normal.z) > 0.9], context='FACES')
    bm.to_mesh(v1.data); bm.free()
    sol = v1.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.03; bake(v1); smooth(v1)
    set_mat(v1, vs)
    pl = rbox('pl', (0, -0.14, 1.36), (0.2, 0.03, 0.2), 0.01); set_mat(pl, vd)
    po = [v1, pl]
    for s in (1, -1):
        b = rbox('po', (0.11 * s, -0.135, 1.2), (0.08, 0.035, 0.1), 0.008); set_mat(b, vd); po.append(b)
    vest = join(po, 'vest')
    return bag, vest

def make_armature():
    arm = bpy.data.armatures.new('rig')
    ao = link(bpy.data.objects.new('rig', arm))
    bpy.context.view_layer.objects.active = ao
    ao.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = {}
    for n, h, t, par in BONES:
        b = arm.edit_bones.new(n)
        b.head = Vector(h); b.tail = Vector(t)
        b.align_roll(Vector((0, 0, 1)) if n.startswith('foot') else Vector((0, -1, 0)))  # eixo Z local = frente
        if par:
            b.parent = eb[par]
            b.use_connect = False
        eb[n] = b
    bpy.ops.object.mode_set(mode='OBJECT')
    return ao

def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (p - (a + ab * t)).length

def weight(obj, rig, fixed=None):
    for n, *_ in BONES:
        obj.vertex_groups.new(name=n)
    segs = [(n, Vector(h), Vector(t)) for n, h, t, _ in BONES]
    for v in obj.data.vertices:
        p = obj.matrix_world @ v.co
        if fixed:
            obj.vertex_groups[fixed].add([v.index], 1.0, 'REPLACE')
            continue
        side = 'L' if p.x > 0.012 else ('R' if p.x < -0.012 else None)
        cand = []
        for n, a, b in segs:
            if n.endswith('.L') and side == 'R':
                continue
            if n.endswith('.R') and side == 'L':
                continue
            if n.startswith('shoulder') or n in ('neck',):
                pass
            d = seg_dist(p, a, b)
            cand.append((d, n))
        cand.sort()
        top = cand[:2]
        ws = [1.0 / (d + 0.008) ** 4 for d, _ in top]
        tot = sum(ws)
        for (d, n), w in zip(top, ws):
            obj.vertex_groups[n].add([v.index], w / tot, 'REPLACE')
    obj.parent = rig
    m = obj.modifiers.new('rig', 'ARMATURE')
    m.object = rig

# ---------------- animações ----------------
D = math.radians
def pose(rig, frame, spec, loc=None):
    for n, rot in spec.items():
        pb = rig.pose.bones[n]
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = tuple(D(x) for x in rot)
        pb.keyframe_insert('rotation_euler', frame=frame)
    if loc is not None:
        pb = rig.pose.bones['hips']
        pb.location = loc
        pb.keyframe_insert('location', frame=frame)

ALL = [b[0] for b in BONES]
def neutral():
    return {n: (0, 0, 0) for n in ALL}

# braços relaxados (abertos um pouco)
def relaxed(sp):
    sp['upperarm.L'] = (0, 0, 6); sp['upperarm.R'] = (0, 0, -6)
    sp['forearm.L'] = (8, 0, 0); sp['forearm.R'] = (8, 0, 0)
    return sp

# segurando o rifle: braço direito e esquerdo à frente
def aiming(sp, lean=0):
    sp['upperarm.R'] = (72, 0, 18); sp['forearm.R'] = (38, 0, 0); sp['hand.R'] = (-10, 0, 0)
    sp['upperarm.L'] = (78, 0, -32); sp['forearm.L'] = (55, 0, 10); sp['hand.L'] = (-5, 0, 0)
    sp['chest'] = (lean, 0, 0)
    return sp

def leg_cycle(sp, ph, amp, knee):
    # ph 0..1, perna L na frente em 0
    s = math.sin(ph * 2 * math.pi)
    c = math.cos(ph * 2 * math.pi)
    sp['thigh.L'] = (amp * s, 0, 0); sp['thigh.R'] = (-amp * s, 0, 0)
    sp['shin.L'] = (-knee * max(0, -c) - 6, 0, 0); sp['shin.R'] = (-knee * max(0, c) - 6, 0, 0)
    sp['foot.L'] = (max(0, -s) * 15, 0, 0); sp['foot.R'] = (max(0, s) * 15, 0, 0)
    return s

def make_action(rig, name, frames, builder, loop=True):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = act
    n = len(frames)
    for i, f in enumerate(frames):
        t = i / (n - 1) if n > 1 else 0
        sp, loc = builder(t)
        pose(rig, f, sp, loc)
    for fc in act.fcurves:
        for k in fc.keyframe_points:
            k.interpolation = 'BEZIER'
    tr = rig.animation_data.nla_tracks.new()
    tr.name = name
    tr.strips.new(name, int(frames[0]), act)
    rig.animation_data.action = None
    return act

def build_animations(rig):
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')
    K = lambda dur, n: [1 + round(dur * i / (n - 1)) for i in range(n)]

    def idle(t, armed=False):
        sp = neutral(); b = math.sin(t * 2 * math.pi)
        sp['chest'] = (1.5 * b, 0, 0); sp['head'] = (-1 * b, 0, 0)
        if armed: aiming(sp, 1.5 * b)
        else: relaxed(sp); sp['upperarm.L'] = (0, 0, 6 + b); sp['upperarm.R'] = (0, 0, -6 - b)
        return sp, (0, 0.004 * b, 0)
    make_action(rig, 'idle', K(60, 9), lambda t: idle(t))
    make_action(rig, 'aim_idle', K(60, 9), lambda t: idle(t, True))

    def walk(t, armed=False, run=False):
        sp = neutral()
        s = leg_cycle(sp, t, 44 if run else 26, 85 if run else 40)
        bob = abs(math.cos(t * 2 * math.pi))
        sp['spine'] = (8 if run else 2, -s * (6 if run else 4), 0)
        if armed:
            aiming(sp, 4 if run else 0)
        else:
            relaxed(sp)
            sw = 42 if run else 20
            sp['upperarm.L'] = (-s * sw, 0, 8); sp['upperarm.R'] = (s * sw, 0, -8)
            sp['forearm.L'] = ((70 if run else 15) + max(0, -s) * 15, 0, 0); sp['forearm.R'] = ((70 if run else 15) + max(0, s) * 15, 0, 0)
        return sp, (0, (0.045 if run else 0.025) * bob - (0.03 if run else 0.01), 0)
    make_action(rig, 'walk', K(32, 9), lambda t: walk(t))
    make_action(rig, 'run', K(20, 9), lambda t: walk(t, run=True))
    make_action(rig, 'aim_walk', K(32, 9), lambda t: walk(t, True))
    make_action(rig, 'aim_run', K(20, 9), lambda t: walk(t, True, True))

    def crouch(t, moving):
        sp = neutral(); aiming(sp, 8)
        if moving:
            s = math.sin(t * 2 * math.pi)
            sp['thigh.L'] = (75 + 18 * s, 0, 0); sp['thigh.R'] = (75 - 18 * s, 0, 0)
        else:
            sp['thigh.L'] = (85, 0, 4); sp['thigh.R'] = (40, 0, -4)
        sp['shin.L'] = (-110 if not moving else -105, 0, 0); sp['shin.R'] = (-115 if not moving else -105, 0, 0)
        sp['foot.L'] = (25, 0, 0); sp['foot.R'] = (45 if not moving else 25, 0, 0)
        sp['spine'] = (12, 0, 0)
        return sp, (0, -0.36, 0)
    make_action(rig, 'crouch_idle', K(40, 5), lambda t: crouch(t, False))
    make_action(rig, 'crouch_walk', K(36, 9), lambda t: crouch(t, True))

    def fall(t):
        sp = neutral(); w = math.sin(t * 2 * math.pi)
        sp['upperarm.L'] = (10, 0, 75 - 5 * w); sp['upperarm.R'] = (10, 0, -75 + 5 * w)
        sp['forearm.L'] = (20, 0, 0); sp['forearm.R'] = (20, 0, 0)
        sp['thigh.L'] = (-10, 0, 12); sp['thigh.R'] = (-10, 0, -12)
        sp['shin.L'] = (-45 - 5 * w, 0, 0); sp['shin.R'] = (-40 + 5 * w, 0, 0)
        sp['head'] = (-25, 0, 0)
        return sp, None
    make_action(rig, 'fall', K(30, 5), fall)

    def chute(t):
        sp = neutral(); w = math.sin(t * 2 * math.pi)
        sp['upperarm.L'] = (165, 0, 12); sp['upperarm.R'] = (165, 0, -12)
        sp['forearm.L'] = (15, 0, 0); sp['forearm.R'] = (15, 0, 0)
        sp['thigh.L'] = (12 + 5 * w, 0, 0); sp['thigh.R'] = (5 - 5 * w, 0, 0)
        sp['shin.L'] = (-20, 0, 0); sp['shin.R'] = (-12, 0, 0)
        return sp, None
    make_action(rig, 'chute', K(60, 5), chute)

    def jump(t, armed=True):
        sp = neutral()
        if armed: aiming(sp)
        else: relaxed(sp)
        sp['thigh.L'] = (55, 0, 0); sp['thigh.R'] = (20, 0, 0); sp['shin.L'] = (-75, 0, 0); sp['shin.R'] = (-45, 0, 0)
        return sp, None
    make_action(rig, 'jump', K(10, 2), lambda t: jump(t, False))
    make_action(rig, 'aim_jump', K(10, 2), lambda t: jump(t, True))

    def reload(t):
        sp, loc = idle(0, True)
        k = math.sin(t * math.pi)
        sp['upperarm.L'] = (40 - 10 * k, 0, -20); sp['forearm.L'] = (95 * k + 30, 0, 0)
        return sp, loc
    make_action(rig, 'reload', K(36, 7), reload)

    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in rig.pose.bones:
        pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0)

def build_character():
    reset()
    log('corpo')
    body = make_body()
    log('cabeça')
    head = make_head()
    log('cabelos')
    hairs = make_hairs()
    log('acessórios')
    bag, vest = make_gear()
    rig = make_armature()
    log('pesos')
    weight(body, rig)
    weight(head, rig, 'head')
    for h in hairs:
        weight(h, rig, 'head')
    weight(bag, rig, 'chest')
    weight(vest, rig, 'chest')
    log('animações')
    build_animations(rig)
    path = os.path.join(OUT, 'personagem.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=False,
                              export_animations=True, export_animation_mode='ACTIONS',
                              export_skins=True, export_yup=True, export_apply=False,
                              export_force_sampling=True, export_frame_range=False)
    log('salvo', path, os.path.getsize(path))

# --------------------------------------------------------------------------
# ARMAS (cano para -Y no Blender = frente no jogo; origem no cabo)
# --------------------------------------------------------------------------
def build_guns():
    reset()
    metal = material('metal', srgb(0x2a2d33), 0.35, 0.8)
    dark = material('preto', srgb(0x151618), 0.55, 0.3)
    wood = material('madeira', srgb(0x6b4a2b), 0.6)
    tan = material('areia', srgb(0x8a7148), 0.7)
    gold = material('ouro', srgb(0xd4a017), 0.22, 1.0)
    def rifle(name, body_mat, acc_mat):
        p = []
        b = rbox('b', (0, -0.18, 0.02), (0.07, 0.42, 0.1), 0.01); set_mat(b, body_mat); p.append(b)
        up = rbox('u', (0, -0.16, 0.085), (0.06, 0.36, 0.03), 0.006); set_mat(up, dark); p.append(up)
        hg = rbox('hg', (0, -0.5, 0.025), (0.075, 0.3, 0.08), 0.012); set_mat(hg, acc_mat); p.append(hg)
        br = cylinder('br', (0, -0.62, 0.035), (0, -0.92, 0.035), 0.013, 0.013, 12); set_mat(br, metal); p.append(br)
        mz = cylinder('mz', (0, -0.9, 0.035), (0, -0.96, 0.035), 0.022, 0.022, 12); set_mat(mz, dark); p.append(mz)
        mg = rbox('mg', (0, -0.24, -0.1), (0.05, 0.08, 0.17), 0.008, rot=(D(-14), 0, 0)); set_mat(mg, dark); p.append(mg)
        gr = rbox('gr', (0, -0.02, -0.08), (0.045, 0.05, 0.12), 0.008, rot=(D(18), 0, 0)); set_mat(gr, dark); p.append(gr)
        sk = rbox('sk', (0, 0.17, -0.005), (0.06, 0.24, 0.09), 0.015); set_mat(sk, acc_mat); p.append(sk)
        sp = rbox('sp', (0, 0.3, -0.02), (0.065, 0.03, 0.13), 0.01); set_mat(sp, dark); p.append(sp)
        sc = cylinder('sc', (0, -0.05, 0.135), (0, -0.26, 0.135), 0.022, 0.022, 14); set_mat(sc, dark); p.append(sc)
        rl = rbox('rl', (0, -0.15, 0.105), (0.03, 0.12, 0.02), 0.004); set_mat(rl, metal); p.append(rl)
        tg = rbox('tg', (0, -0.07, -0.045), (0.01, 0.06, 0.035), 0.003); set_mat(tg, metal); p.append(tg)
        for o in p: o.select_set(True)
        bpy.context.view_layer.objects.active = p[0]
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        return join(p, name)
    rifle('gun_rifle', dark, tan)
    g = rifle('gun_gold', gold, gold)
    g.location.x = 0.3
    p = []
    b = rbox('pb', (0, -0.07, 0.03), (0.04, 0.2, 0.05), 0.008); set_mat(b, dark); p.append(b)
    sl = rbox('ps', (0, -0.075, 0.062), (0.038, 0.2, 0.025), 0.005); set_mat(sl, metal); p.append(sl)
    gr = rbox('pg', (0, 0.0, -0.05), (0.036, 0.055, 0.12), 0.008, rot=(D(14), 0, 0)); set_mat(gr, dark); p.append(gr)
    br = cylinder('pbr', (0, -0.17, 0.045), (0, -0.19, 0.045), 0.009, 0.009, 10); set_mat(br, dark); p.append(br)
    for o in p: o.select_set(True)
    bpy.context.view_layer.objects.active = p[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    pi = join(p, 'gun_pistol'); pi.location.x = -0.3
    path = os.path.join(OUT, 'armas.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=False, export_animations=False, export_yup=True, export_apply=True)
    log('salvo', path, os.path.getsize(path))

# --------------------------------------------------------------------------
# PEÇAS DO MAPA (frente = -Y no Blender; origem no chão)
# --------------------------------------------------------------------------
from mathutils import noise as mnoise
import random

def ico(name, loc, scale, sub=2, amp=0.0, seed=0, flat=False):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    for v in bm.verts:
        if amp:
            n = mnoise.noise(v.co * 1.7 + Vector((seed, seed * 2, seed * 3)))
            v.co *= 1 + amp * n
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2])) + Vector(loc)
    o = mesh_obj(name, bm)
    if not flat:
        smooth(o)
    return o

def jitter(obj, amp, seed=0):
    random.seed(seed)
    for v in obj.data.vertices:
        v.co += Vector((random.uniform(-amp, amp), random.uniform(-amp, amp), random.uniform(-amp, amp)))

def finish(parts, name):
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    o = join(parts, name)
    return o

def build_props():
    reset()
    bark = material('casca', srgb(0x6b4426), 0.9)
    bark2 = material('casca_clara', srgb(0x7a5432), 0.9)
    pine = material('pinho', srgb(0x2d7a3a), 0.85)
    pine2 = material('pinho_escuro', srgb(0x23663a), 0.85)
    leaf = material('folha', srgb(0x55a23e), 0.8)
    leaf2 = material('folha_clara', srgb(0x6db84c), 0.8)
    stone = material('pedra', srgb(0x8f959b), 0.95)
    moss = material('musgo', srgb(0x5e8a3a), 0.95)
    paint = material('paint', (0.85, 0.85, 0.85), 0.35, 0.3)
    glass = material('vidro', srgb(0x1f2a33), 0.08, 0.2)
    tire = material('pneu', srgb(0x161616), 0.9)
    rim = material('aro', srgb(0xb8bec4), 0.3, 0.9)
    lamp_c = material('farol', srgb(0xfff3c0), 0.2)
    tail = material('lanterna', srgb(0xc0392b), 0.3)
    trim = material('plastico', srgb(0x2a2c30), 0.6)
    wood = material('madeira', srgb(0xb98548), 0.75)
    wood_d = material('madeira_escura', srgb(0x7a5130), 0.8)
    metal = material('metal', srgb(0x3b3f46), 0.4, 0.8)
    straw = material('palha', srgb(0xe2c35a), 0.95)
    straw_d = material('palha_escura', srgb(0xc9a843), 0.95)
    # ---- pinheiros (2 variações) ----
    for k, (m1, m2) in enumerate(((pine, pine2), (pine2, pine))):
        parts = []
        t = cylinder('t', (0, 0, 0), (0, 0, 2.2), 0.24, 0.13, 10); set_mat(t, bark); parts.append(t)
        layers = [(1.1, 2.3, 2.15), (2.3, 2.1, 1.7), (3.4, 1.9, 1.25), (4.4, 1.6, 0.8)]
        for i, (z, h, r) in enumerate(layers):
            c = cylinder('c', (0, 0, z), (0, 0, z + h), r, 0.04, 12 + k * 2)
            for v in c.data.vertices:
                if v.co.z < z + 0.05:  # borda de baixo ondulada
                    a = math.atan2(v.co.y, v.co.x)
                    v.co.z -= 0.18 * (0.5 + 0.5 * math.sin(a * 6 + i + k))
            jitter(c, 0.05, i + k * 10)
            set_mat(c, m1 if i % 2 == 0 else m2); parts.append(c)
        finish(parts, 'pine_' + 'ab'[k])
    # ---- árvore frondosa ----
    parts = []
    t = cylinder('t', (0, 0, 0), (0, 0, 2.6), 0.3, 0.17, 10); set_mat(t, bark2); parts.append(t)
    b1 = cylinder('b1', (0, 0, 1.9), (0.7, 0.2, 2.8), 0.12, 0.06, 8); set_mat(b1, bark2); parts.append(b1)
    b2 = cylinder('b2', (0, 0, 2.1), (-0.6, -0.4, 3.0), 0.11, 0.05, 8); set_mat(b2, bark2); parts.append(b2)
    for i, (x, y, z, r) in enumerate(((0, 0, 3.4, 1.55), (0.9, 0.3, 3.0, 1.05), (-0.8, -0.5, 3.15, 1.0), (0.2, -0.7, 3.9, 0.95), (-0.3, 0.7, 3.7, 0.9))):
        f = ico('f', (x, y, z), (r, r, r * 0.85), 2, 0.22, i * 3.1)
        set_mat(f, leaf if i % 2 == 0 else leaf2); parts.append(f)
    finish(parts, 'tree_round')
    # ---- arbusto ----
    parts = []
    for i, (x, y, z, r) in enumerate(((0, 0, 0.45, 0.62), (0.5, 0.15, 0.35, 0.45), (-0.4, -0.2, 0.33, 0.42), (0.1, -0.4, 0.4, 0.4))):
        f = ico('b', (x, y, z), (r, r, r * 0.8), 2, 0.2, i * 7.3)
        set_mat(f, leaf if i % 2 else leaf2); parts.append(f)
    finish(parts, 'bush')
    # ---- pedras (raio ~1, achatadas, musgo em cima) ----
    for k in range(2):
        r = ico('rock_' + 'ab'[k], (0, 0, 0.3), (1.0, 0.85 + 0.15 * k, 0.7), 2, 0.28, 11 + k * 5, flat=True)
        r.data.materials.append(stone); r.data.materials.append(moss)
        for pl in r.data.polygons:
            pl.material_index = 1 if pl.normal.z > 0.82 else 0
    # ---- carro (comprimento em Y) ----
    parts = []
    L, Wd = 4.2, 1.85
    body = rbox('body', (0, 0, 0.66), (Wd, L, 0.62), 0.12, 3); set_mat(body, paint); parts.append(body)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        top = v.co.z > 0
        v.co.x *= Wd * (0.86 if top else 0.94)
        v.co.y = v.co.y * (L * (0.36 if top else 0.56)) + 0.15
        v.co.z = v.co.z * 0.58 + 1.24
    cab = mesh_obj('cab', bm)
    mb = cab.modifiers.new('b', 'BEVEL'); mb.width = 0.08; mb.segments = 3; bake(cab); smooth(cab)
    set_mat(cab, paint); parts.append(cab)
    win = rbox('win', (0, 0.15, 1.28), (Wd * 0.9, L * 0.4, 0.34), 0.06, 2); set_mat(win, glass); parts.append(win)
    for sy in (1, -1):
        bp = rbox('bp', (0, sy * (L / 2 + 0.02), 0.5), (Wd * 0.96, 0.16, 0.22), 0.06); set_mat(bp, trim); parts.append(bp)
    for sx in (1, -1):
        hl = rbox('hl', (sx * 0.62, -L / 2 - 0.01, 0.76), (0.34, 0.06, 0.14), 0.03); set_mat(hl, lamp_c); parts.append(hl)
        tl = rbox('tl', (sx * 0.66, L / 2 + 0.01, 0.78), (0.3, 0.06, 0.12), 0.03); set_mat(tl, tail); parts.append(tl)
        mi = rbox('mi', (sx * (Wd / 2 + 0.08), -0.55, 1.05), (0.14, 0.08, 0.1), 0.02); set_mat(mi, trim); parts.append(mi)
        for sy in (1, -1):
            wy = sy * L * 0.31
            tr = cylinder('tr', (sx * (Wd / 2 - 0.12), wy, 0.38), (sx * (Wd / 2 + 0.06), wy, 0.38), 0.38, 0.38, 18); set_mat(tr, tire); parts.append(tr)
            rm = cylinder('rm', (sx * (Wd / 2 + 0.02), wy, 0.38), (sx * (Wd / 2 + 0.07), wy, 0.38), 0.22, 0.22, 14); set_mat(rm, rim); parts.append(rm)
    gr = rbox('gr', (0, -L / 2 - 0.015, 0.6), (0.9, 0.05, 0.16), 0.02); set_mat(gr, trim); parts.append(gr)
    finish(parts, 'car')
    # ---- caixote (cubo de 1 m) ----
    parts = []
    c = rbox('c', (0, 0, 0.5), (0.96, 0.96, 0.96), 0.02); set_mat(c, wood); parts.append(c)
    for k in range(-1, 2):
        for sy in (1, -1):
            pl = rbox('p', (0, sy * 0.49, 0.5 + k * 0.3), (0.9, 0.03, 0.24), 0.01); set_mat(pl, wood); parts.append(pl)
            pl = rbox('p', (sy * 0.49, 0, 0.5 + k * 0.3), (0.03, 0.9, 0.24), 0.01); set_mat(pl, wood); parts.append(pl)
    for sx in (1, -1):
        for sy in (1, -1):
            e = rbox('e', (sx * 0.46, sy * 0.46, 0.5), (0.1, 0.1, 1.0), 0.015); set_mat(e, wood_d); parts.append(e)
        for z in (0.04, 0.96):
            e = rbox('e', (sx * 0.46, 0, z), (0.1, 1.0, 0.1), 0.015); set_mat(e, wood_d); parts.append(e)
            e = rbox('e', (0, sx * 0.46, z), (1.0, 0.1, 0.1), 0.015); set_mat(e, wood_d); parts.append(e)
    finish(parts, 'crate')
    # ---- barril ----
    parts = []
    b = cylinder('b', (0, 0, 0), (0, 0, 1.2), 0.4, 0.4, 20); set_mat(b, paint); parts.append(b)
    for z in (0.08, 0.42, 0.78, 1.12):
        r = cylinder('r', (0, 0, z - 0.03), (0, 0, z + 0.03), 0.425, 0.425, 20); set_mat(r, metal); parts.append(r)
    lid = cylinder('l', (0, 0, 1.2), (0, 0, 1.22), 0.36, 0.36, 20); set_mat(lid, metal); parts.append(lid)
    cap = cylinder('cp', (0.18, 0, 1.22), (0.18, 0, 1.26), 0.05, 0.05, 10); set_mat(cap, trim); parts.append(cap)
    finish(parts, 'barrel')
    # ---- poste ----
    parts = []
    p1 = cylinder('p', (0, 0, 0), (0, 0, 4.3), 0.1, 0.07, 10); set_mat(p1, metal); parts.append(p1)
    bs = cylinder('bs', (0, 0, 0), (0, 0, 0.35), 0.17, 0.14, 10); set_mat(bs, metal); parts.append(bs)
    pts = [(0, 0, 4.3), (0.25, 0, 4.5), (0.6, 0, 4.55), (0.9, 0, 4.45)]
    for a, b2 in zip(pts, pts[1:]):
        s2 = cylinder('a', a, b2, 0.05, 0.05, 8); set_mat(s2, metal); parts.append(s2)
    hd = rbox('h', (0.92, 0, 4.35), (0.42, 0.24, 0.14), 0.04); set_mat(hd, metal); parts.append(hd)
    lt = rbox('lt', (0.92, 0, 4.27), (0.34, 0.18, 0.04), 0.01); set_mat(lt, lamp_c); parts.append(lt)
    finish(parts, 'lamp')
    # ---- fardo de feno (deitado no eixo X) ----
    parts = []
    hb = cylinder('h', (-0.6, 0, 0.65), (0.6, 0, 0.65), 0.65, 0.65, 24)
    mbv = hb.modifiers.new('b', 'BEVEL'); mbv.width = 0.08; mbv.segments = 3; bake(hb); smooth(hb)
    jitter(hb, 0.015, 3); set_mat(hb, straw); parts.append(hb)
    for x in (-0.3, 0.3):
        bd = cylinder('bd', (x - 0.03, 0, 0.65), (x + 0.03, 0, 0.65), 0.662, 0.662, 24); set_mat(bd, straw_d); parts.append(bd)
    finish(parts, 'hay')
    path = os.path.join(OUT, 'mapa.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', use_selection=False, export_animations=False, export_yup=True, export_apply=True)
    log('salvo', path, os.path.getsize(path))

ok = True
for fn in (build_character, build_guns, build_props):
    try:
        fn()
    except Exception:
        ok = False
        traceback.print_exc()
        log('ERRO em', fn.__name__)
log('FIM', 'OK' if ok else 'COM ERROS')
