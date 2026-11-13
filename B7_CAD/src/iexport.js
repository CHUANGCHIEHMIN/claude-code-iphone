const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const root = __dirname;
const srv = http.createServer((q, s) => {
  const f = path.join(root, decodeURIComponent(q.url.split('?')[0]));
  const types = {'.html':'text/html','.js':'text/javascript','.glb':'model/gltf-binary'};
  fs.readFile(f, (e, d) => { if (e) { s.writeHead(404); s.end(); } else { s.writeHead(200, {'Content-Type': types[path.extname(f)]||'application/octet-stream'}); s.end(d); } });
}).listen(8767);
(async () => {
  const b = await chromium.launch({args:['--use-gl=swiftshader','--enable-unsafe-swiftshader']});
  const p = await b.newPage({viewport:{width:640,height:360}});
  p.on('pageerror', e => console.log('PAGEERR', e.message));
  await p.goto('http://localhost:8767/interior.html?w=640&h=360&export=1');
  await p.waitForFunction(() => document.title === 'exported' || document.title.startsWith('ERR'), null, {timeout: 600000});
  console.log(await p.title());
  const b64 = await p.evaluate(() => window.__glb);
  fs.writeFileSync(process.argv[2], Buffer.from(b64, 'base64'));
  console.log('wrote', process.argv[2]);
  await b.close(); srv.close();
})();
