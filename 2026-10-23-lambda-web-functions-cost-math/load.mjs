// Sends N GET requests at fixed concurrency and prints a summary. Usage: node load.mjs <url> <n> <concurrency>
// Owner-run: point it ONLY at your own throwaway endpoint. Every request is billable there.
const [url, n = '200', c = '8'] = process.argv.slice(2);
if (!url) { console.error('usage: node load.mjs <url> <n> <concurrency>'); process.exit(2); }
const N = Number(n), C = Number(c);
if (N > 5000) { console.error('refusing: n > 5000 (cost guard)'); process.exit(2); }
let next = 0, ok = 0, bad = 0; const lat = [];
const t0 = performance.now();
await Promise.all(Array.from({ length: C }, async () => {
  while (next < N) {
    next++; const s = performance.now();
    try { const r = await fetch(url); await r.arrayBuffer(); r.ok ? ok++ : bad++; }
    catch { bad++; }
    lat.push(performance.now() - s);
  }
}));
lat.sort((a, b) => a - b);
const p = (q) => Math.round(lat[Math.min(lat.length - 1, Math.floor(q * lat.length))]);
console.log(JSON.stringify({ url_host: new URL(url).host, requests: N, concurrency: C, ok, bad,
  wall_s: +((performance.now() - t0) / 1000).toFixed(1), p50_ms: p(0.5), p99_ms: p(0.99),
  started_utc: new Date(Date.now() - (performance.now() - t0)).toISOString() }));
