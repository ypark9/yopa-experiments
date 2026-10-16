// Probe battery. The harness prepends `const CFG = {...};` and pipes this file to the
// runtime on stdin, the same way yt-dlp feeds its JavaScript to Deno or Node.
// Every probe either returns a value ("allowed") or throws ("blocked").
(async () => {
  const fs = await import('node:fs');
  const proc = (await import('node:process')).default;
  const out = {};
  async function probe(name, fn) {
    try {
      const v = await fn();
      out[name] = { result: 'allowed', detail: String(v).slice(0, 80) };
    } catch (e) {
      let msg = String((e && e.message) || e).split('\n')[0].slice(0, 160);
      if (e && e.cause) msg += ` (cause: ${e.cause.code || ''} ${String(e.cause.message || e.cause).split('\n')[0].slice(0, 120)})`;
      out[name] = { result: 'blocked', detail: `${(e && (e.code || e.name)) || 'Error'}: ${msg}` };
    }
  }
  const timeout = (ms) => new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), ms));

  await probe('fs_read_outside', () => fs.readFileSync(CFG.outsideFile, 'utf8').trim());
  await probe('fs_write_outside', () => { fs.writeFileSync(CFG.outsideWrite, 'x'); return 'wrote'; });
  await probe('fs_write_workdir', () => { fs.writeFileSync(CFG.workWrite, 'x'); return 'wrote'; });
  await probe('fs_read_via_symlink_in_workdir', () => fs.readFileSync(CFG.symlinkInWork, 'utf8').trim());
  await probe('env_secret', () => {
    const v = proc.env.PROBE_FAKE_SECRET;
    if (v === undefined) throw new Error('PROBE_FAKE_SECRET is undefined');
    return v;
  });
  await probe('net_fetch_localhost', async () => {
    const r = await Promise.race([fetch(CFG.url), timeout(3000)]);
    return (await r.text()).trim();
  });
  await probe('net_tcp_localhost', async () => {
    const net = await import('node:net');
    return await Promise.race([timeout(3000), new Promise((res, rej) => {
      const s = net.createConnection({ host: '127.0.0.1', port: CFG.port }, () => {
        s.write('GET / HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n');
      });
      let buf = '';
      s.on('data', (d) => { buf += d; });
      s.on('end', () => res(buf.split('\r\n\r\n')[1] || buf));
      s.on('error', rej);
    })]);
  });
  await probe('child_process', async () => {
    const cp = await import('node:child_process');
    return cp.execFileSync('/bin/echo', ['child-ran']).toString().trim();
  });
  await probe('sqlite_read_outside', async () => {
    const { DatabaseSync } = await import('node:sqlite');
    const db = new DatabaseSync(CFG.outsideDb);
    return db.prepare('SELECT v FROM secrets').get().v;
  });
  await probe('sqlite_write_outside', async () => {
    const { DatabaseSync } = await import('node:sqlite');
    const db = new DatabaseSync(CFG.outsideDb);
    db.exec("INSERT INTO secrets VALUES ('written-by-probe')");
    return 'inserted';
  });
  await probe('inherited_fd_read', () => {
    const b = Buffer.alloc(64);
    const n = fs.readSync(CFG.inheritedFd, b, 0, 64, 0);
    return b.subarray(0, n).toString().trim();
  });
  await probe('debug_process_sibling', () => {
    if (typeof proc._debugProcess !== 'function') throw new Error('process._debugProcess is not a function');
    proc._debugProcess(CFG.siblingPidA);
    return 'called';
  });
  await probe('signal_sibling_sigusr1', () => { proc.kill(CFG.siblingPidB, 'SIGUSR1'); return 'sent'; });

  proc.stdout.write(JSON.stringify(out) + '\n');
})();
