from construction_objects import supports_on_line, DEFAULT_SUPPORT_TYPES, DEFAULT_HATCH_TYPES, rect_corners, valid_placement
from attic_cad_export import write_attic_plan_dxf
import tempfile
from pathlib import Path
contour=[(0,0),(20,0),(20,10),(0,10)]
post=DEFAULT_SUPPORT_TYPES[0]
items,rejected=supports_on_line((2,3),(12,3),3000,post,contour)
assert len(items)==5 and rejected==0, (items,rejected)
assert [round(i['x'],2) for i in items]==[2,5,8,11,12]
hatch={'type_id':'l1','x':4,'y':5,'rotation':0}
assert valid_placement(hatch,DEFAULT_HATCH_TYPES[0],contour)
with tempfile.TemporaryDirectory() as t:
 path=Path(t)/'attic.dxf'
 write_attic_plan_dxf(path,contour,[(.5,.5),(19.5,.5),(19.5,9.5),(.5,9.5)],[],[],500,400,3400,28,
                      hatch_types=DEFAULT_HATCH_TYPES,hatches=[hatch],support_types=DEFAULT_SUPPORT_TYPES,supports=items)
 txt=path.read_text('ascii')
 assert 'ATTIC_HATCH' in txt and 'ATTIC_SUPPORT' in txt
print('PASS - construction objects and DXF')
