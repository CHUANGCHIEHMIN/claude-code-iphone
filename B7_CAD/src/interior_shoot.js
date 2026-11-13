const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const root = __dirname;
const srv = http.createServer((q, s) => {
  const f = path.join(root, decodeURIComponent(q.url.split('?')[0]));
  const types = {'.html':'text/html','.js':'text/javascript','.glb':'model/gltf-binary'};
  fs.readFile(f, (e, d) => { if (e) { s.writeHead(404); s.end(); } else { s.writeHead(200, {'Content-Type': types[path.extname(f)]||'application/octet-stream'}); s.end(d); } });
}).listen(8766);
const shots = JSON.parse(process.argv[2]);
(async () => {
  const b = await chromium.launch({args:['--use-gl=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  for (const [name, qs, w, h] of shots) {
    const p = await b.newPage({viewport:{width:w, height:h}});
    p.on('console', m => { if (m.type() === 'error') console.log('ERR', m.text()); });
    p.on('pageerror', e => console.log('PAGEERR', e.message));
    const t0 = Date.now();
    await p.goto(`http://localhost:8766/interior.html?w=${w}&h=${h}&${qs}`);
    await p.waitForFunction(() => document.title === 'done', null, {timeout: 600000});
    await p.screenshot({path: path.join(root, name + '.png')});
    console.log('shot', name, (Date.now() - t0) / 1000 + 's');
    await p.close();
  }
  await b.close(); srv.close();
})();
