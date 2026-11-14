import { LibreDwg, Dwg_File_Type } from '@mlightcad/libredwg-web';
import fs from 'fs';
const [src, dst] = process.argv.slice(2);
const lib = await LibreDwg.create();
const buf = fs.readFileSync(src);
const out = lib.dwg_write_dxf(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
if (!out) { console.error('conversion failed'); process.exit(1); }
fs.writeFileSync(dst, out);
console.log('dxf bytes', out.length);
