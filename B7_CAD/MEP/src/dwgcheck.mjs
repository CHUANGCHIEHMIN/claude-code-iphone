import { LibreDwg, Dwg_File_Type } from '@mlightcad/libredwg-web';
import fs from 'fs';
const lib = await LibreDwg.create();
const f = process.argv[2], kind = process.argv[3];
const buf = fs.readFileSync(f);
const data = kind === 'dwg' ? buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) : buf.toString('utf8');
const dwg = lib.dwg_read_data(data, kind === 'dwg' ? Dwg_File_Type.DWG : Dwg_File_Type.DXF);
const db = lib.convert(dwg);
console.log(kind, Object.keys(db), 'entities', (db.entities || []).length);
