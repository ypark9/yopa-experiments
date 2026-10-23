// Minimal npm registry on 127.0.0.1: GET /<name> -> packument, GET /<name>/-/<file>.tgz -> tarball.
// Serves only what is in ./registry. Read-only. No auth, no publish.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import zlib from 'node:zlib';

const dir = path.resolve(process.argv[2]);
const port = Number(process.argv[3] || 4873);
const base = `http://127.0.0.1:${port}`;

function readPkgJson(tgz) {
  // tiny tar reader: find package/package.json in the gunzipped tar
  const tar = zlib.gunzipSync(fs.readFileSync(tgz));
  for (let off = 0; off + 512 <= tar.length;) {
    const name = tar.subarray(off, off + 100).toString().replace(/\0.*$/s, '');
    const size = parseInt(tar.subarray(off + 124, off + 136).toString().replace(/\0.*$/s, '').trim() || '0', 8);
    if (!name) break;
    if (name === 'package/package.json') return JSON.parse(tar.subarray(off + 512, off + 512 + size).toString());
    off += 512 + Math.ceil(size / 512) * 512;
  }
  throw new Error(`no package.json in ${tgz}`);
}

function packuments() {
  const out = {};
  for (const f of fs.readdirSync(dir).filter((f) => f.endsWith('.tgz'))) {
    const file = path.join(dir, f);
    const pj = readPkgJson(file);
    const buf = fs.readFileSync(file);
    const p = (out[pj.name] ??= { name: pj.name, 'dist-tags': {}, versions: {} });
    p.versions[pj.version] = {
      ...pj,
      // npm's real registry sets this flag for packages with install scripts or binding.gyp
      ...(pj.scripts?.install || pj.scripts?.preinstall || pj.scripts?.postinstall || pj.gypfile ? { hasInstallScript: true } : {}),
      dist: {
        tarball: `${base}/${pj.name}/-/${f}`,
        integrity: 'sha512-' + crypto.createHash('sha512').update(buf).digest('base64'),
        shasum: crypto.createHash('sha1').update(buf).digest('hex'),
      },
    };
    const vs = Object.keys(p.versions).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    p['dist-tags'].latest = vs.at(-1);
  }
  return out;
}

http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split('?')[0]);
  const m = url.match(/^\/([^/]+)\/-\/([^/]+\.tgz)$/);
  if (m) {
    const file = path.join(dir, m[2]);
    if (!fs.existsSync(file)) { res.writeHead(404).end(); return; }
    res.writeHead(200, { 'content-type': 'application/octet-stream' });
    fs.createReadStream(file).pipe(res);
    return;
  }
  const p = packuments()[url.slice(1)];
  if (!p) { res.writeHead(404, { 'content-type': 'application/json' }).end('{"error":"not found"}'); return; }
  res.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(p));
}).listen(port, '127.0.0.1', () => console.log(`registry on ${base}`));
