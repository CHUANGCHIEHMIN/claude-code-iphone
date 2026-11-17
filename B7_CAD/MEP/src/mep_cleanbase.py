"""Rebuild the base plan into a brand-new, clean DXF document (no LibreDWG-converted dynamic-block objects).
All INSERT / MLINE / DIMENSION are exploded to plain geometry, then copied with their layers, linetypes and
text styles into a fresh ezdxf document.
usage: python3 mep_cleanbase.py base.dxf base_clean.dxf"""
import sys, io, contextlib
import ezdxf
from ezdxf import recover, xref

src, dst = sys.argv[1:3]
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    sdoc, _ = recover.readfile(src)
msp = sdoc.modelspace()

# explode until only primitive entities remain
for _ in range(8):
    todo = [e for e in msp if e.dxftype() in ('INSERT', 'MLINE', 'DIMENSION', 'ARC_DIMENSION', 'LEADER', 'MULTILEADER')]
    if not todo:
        break
    for e in todo:
        try:
            ents = list(e.virtual_entities())
        except Exception as ex:
            print('explode failed', e.dxftype(), getattr(e.dxf, 'name', ''), ex)
            ents = []
        for ve in ents:
            if ve.dxftype() in ('ATTDEF',):
                continue
            try:
                msp.add_entity(ve)
            except Exception as ex:
                print('add failed', ve.dxftype(), ex)
        try:
            msp.delete_entity(e)
        except Exception:
            pass
# drop attribute definitions / unsupported leftovers
for e in list(msp):
    if e.dxftype() in ('ATTDEF', 'ATTRIB', 'POINT', 'WIPEOUT', 'IMAGE', 'OLE2FRAME', 'ACAD_PROXY_ENTITY'):
        msp.delete_entity(e)
    elif e.dxftype() == 'TEXT' and not e.dxf.text.strip():
        msp.delete_entity(e)
    elif e.dxftype() == 'MTEXT' and not e.plain_text().strip():
        msp.delete_entity(e)

tdoc = ezdxf.new('R2013', setup=['linetypes'])
for var in ('$INSUNITS', '$MEASUREMENT', '$LTSCALE', '$DIMSCALE', '$LUNITS', '$LUPREC', '$TEXTSIZE'):
    try:
        tdoc.header[var] = sdoc.header[var]
    except Exception:
        pass
xref.load_modelspace(sdoc, tdoc)
# text styles without a font file (e.g. WJJ) -> Traditional-Chinese TrueType so AutoCAD never meets an empty font
for st in tdoc.styles:
    if not st.dxf.get('font'):
        st.dxf.font = 'msjh.ttc'
        st.set_extended_font_data(family='Microsoft JhengHei')
from collections import Counter
print('clean base entities', Counter(e.dxftype() for e in tdoc.modelspace()))
print('blocks', [b.name for b in tdoc.blocks if not b.name.startswith('*')])
tdoc.saveas(dst)
print('saved', dst)
