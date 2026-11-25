// node render.cjs START END STEP outdir  -> JPEG frames of the three.js scene at 30 fps
const { chromium } = require('playwright'); const http = require('http'); const fs = require('fs'); const path = require('path');
const [s0, s1, st, out] = [parseFloat(process.argv[2]), parseFloat(process.argv[3]), parseFloat(process.argv[4] || 1/30), process.argv[5] || 'frames'];
const types = {'.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript'};
const srv = http.createServer((q, r) => { const f = path.join(__dirname, decodeURIComponent(q.url.split('?')[0])); fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, {'Content-Type': types[path.extname(f)] || 'application/octet-stream'}); r.end(d); }); });
srv.listen(0, async () => {
  const port = srv.address().port; fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  p.on('console', m => console.log('page:', m.text())); p.on('pageerror', e => console.log('ERR', e.message));
  await p.goto(`http://127.0.0.1:${port}/index.html`); await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  let i = Math.round(s0 / st);
  for (let t = s0; t < s1 - 1e-6; t += st, i++) {
    const d = await p.evaluate(tt => { window.renderAt(tt); return document.querySelector('canvas').toDataURL('image/jpeg', .93); }, t);
    fs.writeFileSync(path.join(out, `f${String(i).padStart(4, '0')}.jpg`), Buffer.from(d.split(',')[1], 'base64'));
  }
  await b.close(); srv.close(); console.log('done', out);
});
