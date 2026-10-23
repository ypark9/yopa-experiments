// Local stand-in for an LLM streaming proxy: how much CPU does one 3-second streamed request burn?
// Everything is on 127.0.0.1. Box CPU is x86 (not Graviton), no TLS, no Lambda runtime: a ballpark, not a bill.
import http from 'node:http';
const TOKENS = 300, GAP_MS = 10;            // ~3 s stream, like AWS pricing example 4
// fake upstream model: emits TOKENS JSON chunks GAP_MS apart (runs in a separate process)
if (process.argv[2] === 'upstream') {
  http.createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'application/x-ndjson' });
    let i = 0;
    const t = setInterval(() => {
      res.write(JSON.stringify({ type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: ' token' + i } }) + '\n');
      if (++i === TOKENS) { clearInterval(t); res.end(); }
    }, GAP_MS);
  }).listen(0, '127.0.0.1', function () { console.log(this.address().port); });
} else {
  const upstreamPort = Number(process.argv[2]);
  const agent = new http.Agent({ keepAlive: true, maxSockets: 256 });
  // the handler under test: proxy upstream chunks to the client as SSE, re-encoding each one
  const server = http.createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    http.get({ host: '127.0.0.1', port: upstreamPort, path: '/', agent }, (up) => {
      let buf = '';
      up.on('data', (c) => {
        buf += c; let n;
        while ((n = buf.indexOf('\n')) >= 0) {
          const ev = JSON.parse(buf.slice(0, n)); buf = buf.slice(n + 1);
          res.write('event: delta\ndata: ' + JSON.stringify({ text: ev.delta.text }) + '\n\n');
        }
      });
      up.on('end', () => res.end('event: done\ndata: {}\n\n'));
    });
  });
  server.listen(0, '127.0.0.1', async () => {
    const port = server.address().port;
    const one = () => new Promise((ok) => http.get({ host: '127.0.0.1', port, path: '/', agent }, (r) => { r.resume(); r.on('end', ok); }));
    for (const conc of [1, 8, 64]) {
      await Promise.all(Array.from({ length: conc }, one));        // warm up
      const ROUNDS = conc === 1 ? 10 : 3;
      const c0 = process.cpuUsage(), w0 = performance.now();
      for (let r = 0; r < ROUNDS; r++) await Promise.all(Array.from({ length: conc }, one));
      const c = process.cpuUsage(c0), wall = performance.now() - w0, n = conc * ROUNDS;
      // note: client and server share this process, so this over-counts handler CPU
      console.log(JSON.stringify({ concurrency: conc, requests: n, wall_ms: Math.round(wall),
        cpu_ms_per_request_incl_client: +(((c.user + c.system) / 1000) / n).toFixed(2) }));
    }
    process.exit(0);
  });
}
