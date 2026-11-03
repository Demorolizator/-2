"""RoofStudio: attic hatches and support posts. Coordinates in metres; dimensions in mm."""
from math import ceil, hypot
from attic_model import point_in_polygon

DEFAULT_HATCH_TYPES = [dict(id='l1', code='Л1', width_mm=1000, length_mm=1000, note='Люк чердачный; параметры по обследованию')]
DEFAULT_SUPPORT_TYPES = [dict(id='s1', code='ОС1', width_mm=380, length_mm=380, height_mm=2400,
                              material='Кирпичный', spacing_mm=3000, note='Размер и шаг назначаются проектировщиком')]


def rect_corners(o, typ):
    w=float(typ['width_mm']) / 1000
    h=float(typ['length_mm']) / 1000
    if int(o.get('rotation', 0)) % 180 == 90: w,h=h,w
    x,y=float(o['x']),float(o['y'])
    return [(x-w/2,y-h/2),(x+w/2,y-h/2),(x+w/2,y+h/2),(x-w/2,y+h/2)]


def valid_placement(o, typ, contour):
    return all(point_in_polygon(p, contour) for p in rect_corners(o,typ))


def supports_on_line(start, end, spacing_mm, typ, contour, existing=()):
    """Starting point, exact-step intermediate posts, endpoint. Last bay <= spacing."""
    spacing=float(spacing_mm)/1000
    if not 0.1 <= spacing <= 100:
        raise ValueError('Шаг опор должен быть от 100 до 100000 мм')
    length=hypot(end[0]-start[0],end[1]-start[1])
    if length < 0.1: raise ValueError('Длина линии слишком мала')
    n=int(length//spacing)
    ds=[i*spacing for i in range(n+1)]
    if abs(ds[-1]-length)>1e-6:ds.append(length)
    result=[];rejected=0
    for s in ds:
        o={'type_id':typ['id'],'x':round(start[0]+(end[0]-start[0])*s/length,4),
           'y':round(start[1]+(end[1]-start[1])*s/length,4),'rotation':0}
        if not valid_placement(o,typ,contour):rejected+=1;continue
        near = any(hypot(float(e['x'])-o['x'],float(e['y'])-o['y'])<0.02 for e in (*existing,*result))
        if not near:result.append(o)
    return result,rejected


def count_by_type(instances, types):
    lookup={t['id']:t['code'] for t in types}
    counts={}
    for i in instances:
        key=lookup.get(i.get('type_id'),'Без марки')
        counts[key]=counts.get(key,0)+1
    return counts
