// Memory probe. The harness prepends `const CFG = {...};`.
// mode "arraybuffer": allocate CFG.chunks buffers of CFG.chunkMb MB outside the JS heap.
// mode "heap": grow an ordinary JS array, which lives on the V8 heap.
(async () => {
  const proc = (await import('node:process')).default;
  let held = [];
  let mb = 0;
  if (CFG.mode === 'arraybuffer') {
    for (let i = 0; i < CFG.chunks; i++) {
      const u = new Uint8Array(CFG.chunkMb * 1024 * 1024);
      u.fill(1);                       // touch every page so it is really resident
      held.push(u);
      mb += CFG.chunkMb;
    }
  } else {
    while (mb < CFG.chunks * CFG.chunkMb) {
      const a = new Array(1024 * 1024 / 8).fill(0).map((_, i) => i + 0.5);  // ~1 MB of doubles
      held.push(a);
      mb += 1;
    }
  }
  proc.stdout.write(JSON.stringify({ allocated_mb: mb }) + '\n');
})();
