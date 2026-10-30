'''
Pictures of pedigrees for the tests: drawn as Pedigree Studio saves them (studio_picture), and sketched by hand, as
with the Studio's Draw tool (sketch_picture), in whole or in part.
'''
import math

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

#: Pedigree Studio's symbols and lines, in the pixels of the picture it saves (twice its canvas)
SHAPE = 104
STROKE = 4
INK = (26, 35, 50)            # #1a2332
LABEL = (107, 122, 141)       # #6b7a8d, the grey of the numbers over the symbols


def _font(size):
    try:
        return ImageFont.truetype('DejaVuSans-Bold.ttf', size)
    except OSError:
        pytest.skip('needs the DejaVu Sans Bold font to draw the labels')


def studio_picture(path, people, couples, twins=(), size=None, labels=True, transparent=False, marks=None,
                   inside=None):
    '''
    Draws a pedigree as Pedigree Studio saves it: symbols 104 pixels across with lines 4 wide in a dark blue-grey, the
    line over a family's children 60 pixels above the highest of them, twins joined to a point on that line (with a
    bar halfway down for identical twins), and each person's number written over their symbol in grey, as the Studio
    writes it: in the middle, or to the left for someone with a line down to them, or beside a twin.

    people: id -> (x, y, sex, affected), with (x, y) the top left of the symbol and sex 'M', 'F', 'U' (a diamond) or
            'T' (a triangle, for a pregnancy lost)
    couples: (partner on the left, partner on the right, [children])
    twins: (twin, twin, 'MZ' or 'DZ'), each pair children of one couple
    labels: whether to write the numbers, or {id: text} to write other text
    marks: id -> the marks on their symbol, drawn as the Studio draws them: any of 'deceased' (a slash from corner to
           corner, through a triangle from its lower left corner and out past its side), 'proband' (a small arrow off
           the lower left corner) and 'carrier' (a dot in the middle, white in a symbol filled in)
    inside: id -> a letter written in the middle of their symbol, as the Studio writes P, D or S there
    '''
    scale = 2   # drawn twice as large, and shrunk, which smooths the lines as the Studio's are
    width = size[0] if size else max(x for x, *_ in people.values()) + SHAPE + 120
    height = size[1] if size else max(y for _, y, *_ in people.values()) + SHAPE + 80
    image = Image.new('RGBA', (width * scale, height * scale), (255, 255, 255, 0 if transparent else 255))
    draw = ImageDraw.Draw(image)
    stroke = STROKE * scale

    def s(*points):
        return [(scale * x, scale * y) for x, y in points]

    def middle(pid):
        x, y = people[pid][:2]
        return x + SHAPE / 2, y + SHAPE / 2

    twin_of = {}
    for a, b, kind in twins:
        twin_of[a], twin_of[b] = (b, kind), (a, kind)
    with_line = set()
    for left, right, children in couples:
        (lx, ly), (rx, ry) = middle(left), middle(right)
        start, end = (lx + SHAPE / 2, ly), (rx - SHAPE / 2, ry)
        draw.line(s(start, end), fill=INK, width=stroke)
        if not children:
            continue
        mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
        sibship = min(people[c][1] for c in children) - 60
        draw.line(s((mx, my), (mx, sibship)), fill=INK, width=stroke)
        xs = [mx]
        done = set()
        for child in children:
            cx, top = people[child][0] + SHAPE / 2, people[child][1]
            with_line.add(child)
            if child in twin_of and twin_of[child][0] in children:
                if child in done:
                    continue
                other, kind = twin_of[child]
                done.update((child, other))
                ox, otop = people[other][0] + SHAPE / 2, people[other][1]
                fork = ((cx + ox) / 2, sibship)
                xs.append(fork[0])
                draw.line(s(fork, (cx, top)), fill=INK, width=stroke)
                draw.line(s(fork, (ox, otop)), fill=INK, width=stroke)
                if kind == 'MZ':
                    draw.line(s(((fork[0] + cx) / 2, (fork[1] + top) / 2), ((fork[0] + ox) / 2, (fork[1] + otop) / 2)),
                              fill=INK, width=stroke)
            else:
                xs.append(cx)
                draw.line(s((cx, sibship), (cx, top)), fill=INK, width=stroke)
        draw.line(s((min(xs), sibship), (max(xs), sibship)), fill=INK, width=stroke)
    for pid, (x, y, sex, affected) in people.items():
        fill = INK if affected else (255, 255, 255)
        box = s((x, y), (x + SHAPE, y + SHAPE))
        if sex == 'M':
            draw.rectangle(box, outline=INK, width=stroke, fill=fill)
        elif sex == 'F':
            draw.ellipse(box, outline=INK, width=stroke, fill=fill)
        elif sex == 'U':
            draw.polygon(s((x + SHAPE / 2, y), (x + SHAPE, y + SHAPE / 2), (x + SHAPE / 2, y + SHAPE), (x, y + SHAPE / 2)),
                         outline=INK, width=stroke, fill=fill)
        else:
            draw.polygon(s((x + SHAPE / 2, y + 6), (x + SHAPE - 4, y + SHAPE - 14), (x + 4, y + SHAPE - 14)),
                         outline=INK, width=stroke, fill=fill)
    for pid, (x, y, sex, affected) in people.items():
        drawn = set((marks or {}).get(pid, ()))
        middle_y = y + SHAPE / 2 + (8 if sex == 'T' else 0)
        if 'deceased' in drawn:
            if sex == 'T':
                draw.line(s((x + 4, y + SHAPE - 14), (x + 84, y + SHAPE - 86)), fill=INK, width=stroke)
            else:
                draw.line(s((x, y + SHAPE), (x + SHAPE, y)), fill=INK, width=stroke)
        if 'carrier' in drawn:
            r = 10
            draw.ellipse(s((x + SHAPE / 2 - r, middle_y - r), (x + SHAPE / 2 + r, middle_y + r)),
                         fill=(255, 255, 255) if affected else INK)
        if 'proband' in drawn:
            # (as the Studio draws it: off the lower left corner, pointing at it, with a head of two short strokes)
            tip = (x - 12, y + SHAPE + 16)
            for end in ((tip[0] - 28, tip[1] + 28), (tip[0] - 14, tip[1]), (tip[0], tip[1] + 14)):
                draw.line(s(tip, end), fill=INK, width=4 * scale)
        if pid in (inside or {}):
            draw.text(s((x + SHAPE / 2, middle_y))[0], inside[pid], font=_font(32 * scale), anchor='mm',
                      fill=(255, 255, 255) if affected else INK)
    if labels:
        font = _font(18 * scale)
        for pid, (x, y, *_ ) in people.items():
            text = labels[pid] if isinstance(labels, dict) else str(pid)
            if pid in twin_of:
                other = twin_of[pid][0]
                if x > people[other][0]:
                    draw.text(s((x + SHAPE + 4, y - 8))[0], text, fill=LABEL, font=font, anchor='lb')
                else:
                    draw.text(s((x - 4, y - 8))[0], text, fill=LABEL, font=font, anchor='rb')
            elif pid in with_line:
                draw.text(s((x - 4, y - 8))[0], text, fill=LABEL, font=font, anchor='rb')
            else:
                draw.text(s((x + SHAPE / 2, y - 8))[0], text, fill=LABEL, font=font, anchor='mb')
    image = image.resize((width, height), Image.LANCZOS)
    if not transparent:
        image = image.convert('RGB')
    image.save(path)


# ---------------------------------------------------------------------------------------------------------------------
# sketched by hand
# ---------------------------------------------------------------------------------------------------------------------
def _densify(points, rng, step=(2.0, 6.0)):
    out = [points[0]]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        t = 0.0
        while True:
            t += float(rng.uniform(*step)) / max(length, 1e-9)
            if t >= 1:
                break
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        out.append((x1, y1))
    return out


def _wobble(points, rng, amp, waves=2):
    '''a slow sideways wander of up to amp pixels along a path, and a little tremor'''
    pts = np.array(points, float)
    if len(pts) < 3:
        return pts
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
    d = np.gradient(pts, axis=0)
    norm = np.hypot(d[:, 0], d[:, 1]) + 1e-9
    normal = np.stack([-d[:, 1] / norm, d[:, 0] / norm], axis=1)
    offset = sum(float(rng.normal(0, amp / math.sqrt(waves))) *
                 np.sin(2 * math.pi * s / (s[-1] or 1) * float(rng.uniform(0.5, 2)) + float(rng.uniform(0, 6.3)))
                 for _ in range(waves))
    return pts + normal * offset[:, None] + rng.normal(0, 0.4, pts.shape)


def rough_line(p0, p1, rng):
    length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    return _wobble(_densify([p0, p1], rng), rng, min(4.0, 0.03 * length + 0.5))


def rough_symbol(cx, cy, size, sex, rng):
    '''the outline of a symbol drawn by hand, which may not quite close, or may run on past where it began; and its
    polygon, to fill it in'''
    w, h = size * float(rng.uniform(0.92, 1.08)), size * float(rng.uniform(0.92, 1.08))
    if sex == 'F':
        start = float(rng.uniform(0, 2 * math.pi))
        poly = [(cx + w / 2 * math.cos(start + 2 * math.pi * k / 64), cy + h / 2 * math.sin(start + 2 * math.pi * k / 64))
                for k in range(65)]
    elif sex == 'T':
        poly = [(cx, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]
        poly.append(poly[0])
    else:
        corners = ([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]
                   if sex == 'M' else [(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)])
        poly = [(x + float(rng.normal(0, 0.03 * size)), y + float(rng.normal(0, 0.03 * size))) for x, y in corners]
        poly.append(poly[0])
    pts = _wobble(_densify(poly, rng, (2.0, 5.0)), rng, 0.012 * size + 0.3, waves=3)
    # a gap where the pen came back to where it began, or a little run on past it
    if rng.random() < 0.5:
        pts = pts[:-max(1, int(len(pts) * float(rng.uniform(0.01, 0.04))))]
    else:
        pts = np.concatenate([pts, pts[1:1 + int(len(pts) * float(rng.uniform(0.01, 0.05)))]])
    return pts, poly[:-1]


def scribble(poly, rng, pen):
    '''filled in by hand: zig-zags across the symbol, a little more than the pen's width apart'''
    pts = np.array(poly, float)
    cx, cy = pts.mean(axis=0)
    angle = float(rng.uniform(0, math.pi))
    c, s = math.cos(-angle), math.sin(-angle)
    rot = (pts - [cx, cy]) @ np.array([[c, -s], [s, c]]).T
    path, flip, y = [], False, rot[:, 1].min() + pen
    while y < rot[:, 1].max():
        xs = [x0 + (x1 - x0) * (y - y0) / (y1 - y0) for (x0, y0), (x1, y1) in zip(rot, np.roll(rot, -1, axis=0))
              if (y0 - y) * (y1 - y) <= 0 and y0 != y1]
        if len(xs) >= 2:
            seg = [(min(xs) + 1, y), (max(xs) - 1, y)]
            path += seg[::-1] if flip else seg
            flip = not flip
        y += float(rng.uniform(1.8, 2.6)) * pen
    c, s = math.cos(angle), math.sin(angle)
    return _wobble(_densify([(cx + x * c - y * s, cy + x * s + y * c) for x, y in path], rng, (2.0, 5.0)), rng, 0.6)


def slash(cx, cy, size, rng):
    '''a slash drawn by hand through a symbol, rising to the right and out past it at both ends'''
    r = size * float(rng.uniform(0.68, 0.78))
    return rough_line((cx - r, cy + r), (cx + r, cy - r), rng)


def arrow(cx, cy, size, rng):
    '''a proband's arrow drawn by hand: a line up from the lower left to just off the symbol, and a head of two strokes'''
    d = (-math.cos(math.radians(45)), math.sin(math.radians(45)))
    edge = size / 2 * float(rng.uniform(1.15, 1.3))
    tip = (cx + d[0] * edge, cy + d[1] * edge)
    tail = (tip[0] + d[0] * 0.6 * size, tip[1] + d[1] * 0.6 * size)
    ends = [(tip[0] + 0.2 * size * math.cos(math.atan2(d[1], d[0]) + turn),
             tip[1] + 0.2 * size * math.sin(math.atan2(d[1], d[0]) + turn)) for turn in (0.6, -0.6)]
    return [rough_line(tail, tip, rng), np.concatenate([rough_line(ends[0], tip, rng), rough_line(tip, ends[1], rng)])]


def dot(cx, cy, size, width):
    '''a carrier's dot drawn by hand: a small spiral in to the middle, close enough for the pen to fill it in'''
    r = 0.09 * size
    turns = max(2, int(math.ceil(r / (0.7 * width))) + 1)
    t = np.linspace(0, 1, 24 * turns + 1)
    return np.stack([cx + (r * (1 - t) + 0.3) * np.cos(2 * math.pi * turns * t),
                     cy + (r * (1 - t) + 0.3) * np.sin(2 * math.pi * turns * t)], axis=1)


def sketch_picture(path, people, couples, twins=(), seed=0, pen=(192, 57, 43), width=4, studio=(), transparent=False,
                   size=None, room=(22, 32), marks=None):
    '''
    Sketches a pedigree by hand, as with Pedigree Studio's Draw tool: symbols of unequal sizes whose outlines don't
    quite close, or run on, affected ones scribbled in, and lines that wobble and stop short of what they join or run
    a little past it. The people in studio are drawn as Studio symbols instead, with the lines among them, as when
    someone begins a pedigree with the Studio's symbols and finishes it by hand.

    people: id -> (x, y, size, sex, affected), with (x, y) the middle of the symbol, and sex 'M', 'F', 'U' or 'T'
    couples: (partner on the left, partner on the right, [children])
    twins: (twin, twin, 'MZ' or 'DZ')
    pen: the pen's colour, as (red, green, blue)
    room: how far above the children the line over them is drawn, from the top of the highest of them, at the least
        and at the most
    marks: id -> the marks drawn by hand on their symbol: any of 'deceased' (a slash), 'proband' (an arrow at the
        lower left) and 'carrier' (a dot in the middle)
    '''
    rng = np.random.default_rng(seed)
    w = size[0] if size else int(max(x + s for x, _, s, *_ in people.values()) + 80)
    h = size[1] if size else int(max(y + s for _, y, s, *_ in people.values()) + 80)
    img = np.full((h, w, 4), (255, 255, 255, 0 if transparent else 255), np.uint8)
    colour = (pen[2], pen[1], pen[0], 255)
    strokes = []

    def gap():
        return float(rng.uniform(-3, 8))

    P = {pid: dict(zip(('x', 'y', 'size', 'sex', 'affected'), p)) for pid, p in people.items()}
    for pid, p in P.items():
        if pid in studio:
            continue
        outline, poly = rough_symbol(p['x'], p['y'], p['size'], p['sex'], rng)
        strokes.append(outline)
        if p['affected']:
            strokes.append(scribble(poly, rng, width))
    twin_of = {}
    for a, b, kind in twins:
        twin_of[a], twin_of[b] = (b, kind), (a, kind)
    for left, right, children in couples:
        a, b = P[left], P[right]
        by_hand = not (left in studio and right in studio)
        y0 = (a['y'] + b['y']) / 2
        x0, x1 = a['x'] + a['size'] / 2 + gap(), b['x'] - b['size'] / 2 - gap()
        if by_hand:
            strokes.append(rough_line((x0, y0), (x1, y0), rng))
        if not children:
            continue
        if not by_hand and all(c in studio for c in children):
            continue   # (the Studio draws these lines, below)
        mx = (x0 + x1) / 2
        tops = [P[c]['y'] - P[c]['size'] / 2 for c in children]
        ysib = min(tops) - float(rng.uniform(*room))
        xs, done = [mx], set()
        strokes.append(rough_line((mx, y0 + gap()), (mx, ysib + float(rng.uniform(-3, 3))), rng))
        for c in children:
            k = P[c]
            if c in twin_of and twin_of[c][0] in children:
                if c in done:
                    continue
                other, kind = twin_of[c]
                done.update((c, other))
                o = P[other]
                apex = ((k['x'] + o['x']) / 2, ysib + float(rng.uniform(-2, 3)))
                xs.append(apex[0])
                ends = [(t['x'] + float(rng.normal(0, 2)), t['y'] - t['size'] / 2 - float(rng.uniform(0, 6))) for t in (k, o)]
                for end in ends:
                    strokes.append(rough_line(apex, end, rng))
                if kind == 'MZ':
                    f = float(rng.uniform(0.45, 0.55))
                    p = (apex[0] + (ends[0][0] - apex[0]) * f, apex[1] + (ends[0][1] - apex[1]) * f)
                    q = (apex[0] + (ends[1][0] - apex[0]) * f, apex[1] + (ends[1][1] - apex[1]) * f)
                    strokes.append(rough_line(p, q, rng))
            else:
                xs.append(k['x'])
                strokes.append(rough_line((k['x'], ysib + float(rng.uniform(-3, 4))), (k['x'], k['y'] - k['size'] / 2 - gap()), rng))
        strokes.append(rough_line((min(xs) - float(rng.uniform(-3, 3)), ysib), (max(xs) + float(rng.uniform(-3, 3)), ysib), rng))
    # (the marks last, so that the rest is drawn the same with them or without)
    for pid, drawn in sorted((marks or {}).items()):
        p = P[pid]
        if 'deceased' in drawn:
            strokes.append(slash(p['x'], p['y'], p['size'], rng))
        if 'proband' in drawn:
            strokes += arrow(p['x'], p['y'], p['size'], rng)
        if 'carrier' in drawn:
            strokes.append(dot(p['x'], p['y'], p['size'], width))
    for pts in strokes:
        cv2.polylines(img, [np.round(np.asarray(pts) * 16).astype(np.int32)], False, colour, width, cv2.LINE_AA, shift=4)
    # the Studio's symbols, and the lines among them, drawn as it draws them
    if studio:
        overlay = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA))
        draw = ImageDraw.Draw(overlay)
        font = _font(18)
        for left, right, children in couples:
            if not (left in studio and right in studio):
                continue
            a, b = P[left], P[right]
            draw.line([(a['x'] + SHAPE / 2, a['y']), (b['x'] - SHAPE / 2, b['y'])], fill=INK, width=STROKE)
            if not children or not all(c in studio for c in children):
                continue
            mx, my = (a['x'] + b['x']) / 2, (a['y'] + b['y']) / 2
            sibship = min(P[c]['y'] for c in children) - SHAPE / 2 - 60
            draw.line([(mx, my), (mx, sibship)], fill=INK, width=STROKE)
            xs, done = [mx], set()
            for c in children:
                k = P[c]
                if c in twin_of and twin_of[c][0] in children:
                    if c in done:
                        continue
                    other, kind = twin_of[c]
                    done.update((c, other))
                    o = P[other]
                    fork = ((k['x'] + o['x']) / 2, sibship)
                    xs.append(fork[0])
                    ends = [(t['x'], t['y'] - SHAPE / 2) for t in (k, o)]
                    for end in ends:
                        draw.line([fork, end], fill=INK, width=STROKE)
                    if kind == 'MZ':
                        draw.line([((fork[0] + ends[0][0]) / 2, (fork[1] + ends[0][1]) / 2),
                                   ((fork[0] + ends[1][0]) / 2, (fork[1] + ends[1][1]) / 2)], fill=INK, width=STROKE)
                else:
                    xs.append(k['x'])
                    draw.line([(k['x'], sibship), (k['x'], k['y'] - SHAPE / 2)], fill=INK, width=STROKE)
            draw.line([(min(xs), sibship), (max(xs), sibship)], fill=INK, width=STROKE)
        children = {c for _, _, kids in couples for c in kids}
        for pid in studio:
            p = P[pid]
            box = [p['x'] - SHAPE / 2, p['y'] - SHAPE / 2, p['x'] + SHAPE / 2, p['y'] + SHAPE / 2]
            fill = INK if p['affected'] else (255, 255, 255)
            (draw.rectangle if p['sex'] == 'M' else draw.ellipse)(box, outline=INK, width=STROKE, fill=fill)
            # (where the Studio writes the number: beside a twin, to the left of someone with a line down to them, and
            # otherwise in the middle)
            top = p['y'] - SHAPE / 2 - 8
            if pid in twin_of and P[twin_of[pid][0]]['x'] < p['x']:
                draw.text((p['x'] + SHAPE / 2 + 4, top), str(pid), fill=LABEL, font=font, anchor='lb')
            elif pid in twin_of or pid in children:
                draw.text((p['x'] - SHAPE / 2 - 4, top), str(pid), fill=LABEL, font=font, anchor='rb')
            else:
                draw.text((p['x'], top), str(pid), fill=LABEL, font=font, anchor='mb')
        img = cv2.cvtColor(np.array(overlay), cv2.COLOR_RGBA2BGRA)
    if transparent:
        cv2.imwrite(str(path), img)
    else:
        cv2.imwrite(str(path), img[:, :, :3])
