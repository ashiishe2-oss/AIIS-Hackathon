// AIIS frontend dev server (handoff tooling, zero dependencies, Node 18+).
// Serves ./public and forwards /api/* to the backend named in AIIS_API_BASE,
// so the browser sees one origin (the frontend calls relative /api/... paths).
//
//   AIIS_API_BASE=http://localhost:5000 node dev-server.js     # Backend V2 (Flask) on :5000
//   node dev-server.js                                          # frontend only; /api answers 503
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), 'public');
const PORT = Number(process.env.PORT || 8080);
const API = (process.env.AIIS_API_BASE || 'http://127.0.0.1:5000').replace(/\/+$/, '');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.txt': 'text/plain; charset=utf-8', '.ico': 'image/x-icon' };

async function proxy(req, res) {
  if (!API) {
    res.writeHead(503, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ error: 'Backend not configured. Set AIIS_API_BASE to the Backend V2 URL and restart.' }));
  }
  const chunks = []; for await (const c of req) chunks.push(c);
  const headers = {};
  for (const h of ['content-type', 'authorization', 'x-aiis-staff-code', 'x-tracking-token', 'accept']) if (req.headers[h]) headers[h] = req.headers[h];
  try {
    const r = await fetch(API + req.url, { method: req.method, headers, body: ['GET', 'HEAD'].includes(req.method) ? undefined : Buffer.concat(chunks) });
    const body = Buffer.from(await r.arrayBuffer());
    res.writeHead(r.status, { 'Content-Type': r.headers.get('content-type') || 'application/json' });
    res.end(body);
  } catch (e) {
    res.writeHead(502, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: `Cannot reach the backend at ${API}. Is it running?` }));
  }
}

function serveStatic(req, res) {
  let p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (p === '/') p = '/index.html';
  const file = path.normalize(path.join(ROOT, p));
  if (!file.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, data) => {
    if (err) { // hash-routed SPA: unknown paths get the app shell
      return fs.readFile(path.join(ROOT, 'index.html'), (e2, html) => { res.writeHead(e2 ? 404 : 200, { 'Content-Type': TYPES['.html'] }); res.end(html || 'Not found'); });
    }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
    res.end(data);
  });
}

http.createServer((req, res) => (req.url.startsWith('/api/') ? proxy(req, res) : serveStatic(req, res)))
  .listen(PORT, () => console.log(`AIIS frontend on http://localhost:${PORT}  ·  /api -> ${API || '(not set: 503)'}`));
