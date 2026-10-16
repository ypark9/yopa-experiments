#!/usr/bin/env python3
"""Run the probe battery under Deno and Node permission settings and record the matrix.

Local only: temp directories, a fake secret, and an HTTP server on 127.0.0.1.
No cloud account, no paid API.

usage: python3 run.py --deno PATH --node22 PATH --node24 PATH --node26 PATH [--out results]
"""
import argparse, http.server, json, os, resource, shutil, sqlite3, subprocess, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
FAKE_SECRET = 'fake-secret-not-real-0000'

# yt-dlp's own Deno options (yt_dlp/extractor/youtube/jsc/_builtin/deno.py @ 8973412),
# plus the two it adds for its builtin (non-npm) script variant.
DENO_YTDLP = ['--ext=js', '--no-code-cache', '--no-prompt', '--no-remote',
              '--no-lock', '--node-modules-dir=none', '--no-config', '--no-npm', '--cached-only']


def node_permission_flag(version):
    # Same rule as yt-dlp's node.py: experimental flag below 23.5.0.
    return (['--experimental-permission', '--no-warnings=ExperimentalWarning']
            if version < (23, 5, 0) else ['--permission'])


def build_cmds(rt, work):
    cmds = {}
    for name, path in rt.items():
        if name == 'deno':
            base = [path, 'run', *DENO_YTDLP]
            cmds[(name, 'control')] = [path, 'run', '-A', '--ext=js', '--no-config', '--no-lock', '-']
            cmds[(name, 'P0')] = [*base, '-']
            cmds[(name, 'P1')] = [*base, f'--allow-read={work}', f'--allow-write={work}', '-']
        else:
            ver = tuple(int(x) for x in subprocess.check_output([path, '--version'], text=True).strip().lstrip('v').split('.'))
            perm = node_permission_flag(ver)
            cmds[(name, 'control')] = [path, '-']
            cmds[(name, 'P0')] = [path, *perm, '-']
            cmds[(name, 'P1')] = [path, *perm, f'--allow-fs-read={work}', f'--allow-fs-write={work}', '-']
    return cmds


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'local-server-reply\n'
        self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers()
        self.wfile.write(body)
    def log_message(self, *a):
        pass


def start_sibling(node):
    # An ordinary Node process with no permission flags, like any other tool on the machine.
    # --inspect-port=0: if something turns its inspector on, it picks a free port.
    return subprocess.Popen([node, '--inspect-port=0', '-e', 'setInterval(() => {}, 1000)'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)


def sibling_inspector_opened(p):
    time.sleep(0.8)
    p.terminate()
    try:
        _, err = p.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill(); _, err = p.communicate()
    return 'Debugger listening' in (err or '')


def fresh_fixture(base):
    shutil.rmtree(base, ignore_errors=True)
    work, outside = os.path.join(base, 'work'), os.path.join(base, 'outside')
    os.makedirs(work); os.makedirs(outside)
    secret = os.path.join(outside, 'secret.txt')
    with open(secret, 'w') as f:
        f.write('outside-file-content\n')
    os.symlink(secret, os.path.join(work, 'link-to-outside.txt'))
    db = os.path.join(outside, 'app.db')
    con = sqlite3.connect(db); con.execute('CREATE TABLE secrets(v TEXT)')
    con.execute("INSERT INTO secrets VALUES ('outside-db-row')"); con.commit(); con.close()
    return work, outside, secret, db


def run_cell(cmd, cfg_extra, base, port, node_for_sibling):
    work, outside, secret, db = fresh_fixture(base)
    sib_a, sib_b = start_sibling(node_for_sibling), start_sibling(node_for_sibling)
    fd = os.open(secret, os.O_RDONLY)
    cfg = dict(outsideFile=secret, outsideWrite=os.path.join(outside, 'written.txt'),
               workWrite=os.path.join(work, 'written.txt'), symlinkInWork=os.path.join(work, 'link-to-outside.txt'),
               url=f'http://127.0.0.1:{port}/', port=port, outsideDb=db, inheritedFd=3,
               siblingPidA=sib_a.pid, siblingPidB=sib_b.pid, **cfg_extra)
    script = 'const CFG = ' + json.dumps(cfg) + ';\n' + open(os.path.join(HERE, 'probe.js')).read()
    env = {'PATH': '/usr/bin:/bin', 'HOME': base, 'DENO_DIR': os.path.join(base, 'deno-dir'),
           'PROBE_FAKE_SECRET': FAKE_SECRET}
    # Give the child the secret file as fd 3, the way a parent process can leak an open handle.
    os.dup2(fd, 3) if fd != 3 else None
    try:
        p = subprocess.run(cmd, input=script, capture_output=True, text=True, env=env, timeout=60, pass_fds=(3,), cwd=work)
    finally:
        os.close(fd)
    res = {}
    try:
        res = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        res = {'_error': {'result': 'error', 'detail': (p.stderr or p.stdout)[-300:]}}
    res['debug_process_sibling']['sibling_inspector_opened'] = sibling_inspector_opened(sib_a) if 'debug_process_sibling' in res else None
    res['signal_sibling_sigusr1']['sibling_inspector_opened'] = sibling_inspector_opened(sib_b) if 'signal_sibling_sigusr1' in res else None
    # What actually happened on disk (independent of what the probe reported).
    res['_disk'] = {'outside_written': os.path.exists(os.path.join(outside, 'written.txt')),
                    'work_written': os.path.exists(os.path.join(work, 'written.txt'))}
    con = sqlite3.connect(db); res['_disk']['db_rows'] = con.execute('SELECT count(*) FROM secrets').fetchone()[0]; con.close()
    return res


def run_memory(cmd, mode, base):
    cfg = {'mode': mode, 'chunks': 8, 'chunkMb': 64}  # 512 MB ceiling
    script = 'const CFG = ' + json.dumps(cfg) + ';\n' + open(os.path.join(HERE, 'memory.js')).read()
    env = {'PATH': '/usr/bin:/bin', 'HOME': base, 'DENO_DIR': os.path.join(base, 'deno-dir')}
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=base)
    p.stdin.write(script); p.stdin.close()
    out, err = p.stdout.read(), p.stderr.read()
    _, status, ru = os.wait4(p.pid, 0)
    p.returncode = os.waitstatus_to_exitcode(status)
    return {'exit_code': p.returncode,
            'stdout': out.strip()[-200:],
            'heap_oom_message': any(s in out + err for s in ('heap out of memory', 'Reached heap limit')),
            'peak_rss_mb': round(ru.ru_maxrss / 1024)}


def main():
    ap = argparse.ArgumentParser()
    for n in ('deno', 'node22', 'node24', 'node26'):
        ap.add_argument('--' + n, required=True)
    ap.add_argument('--out', default=os.path.join(HERE, 'results'))
    ap.add_argument('--name', default='raw.json')
    a = ap.parse_args()
    rt = {'deno': a.deno, 'node22': a.node22, 'node24': a.node24, 'node26': a.node26}
    os.makedirs(a.out, exist_ok=True)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = tempfile.mkdtemp(prefix='probe-')
    versions = {}
    for n, pth in rt.items():
        versions[n] = subprocess.check_output([pth, '--version'], text=True).strip().splitlines()[0]
    cmds = build_cmds(rt, os.path.join(base, 'work'))
    matrix = {}
    for (name, prof), cmd in cmds.items():
        r = run_cell(cmd, {}, base, port, a.node24)
        matrix[f'{name}/{prof}'] = {'cmd': [os.path.basename(cmd[0])] + [c.replace(base, '<base>') for c in cmd[1:]], 'probes': r}
        print(name, prof, {k: v.get('result') for k, v in r.items() if not k.startswith('_')}, file=sys.stderr)
    # Memory: heap cap 128 MB, then try to hold 512 MB.
    mem = {}
    for name, pth in rt.items():
        if name == 'deno':
            cmd = [pth, 'run', '--v8-flags=--max-old-space-size=128', *DENO_YTDLP, '-']
        else:
            cmd = [pth, '--max-old-space-size=128', '-']
        for mode in ('heap', 'arraybuffer'):
            mem[f'{name}/{mode}'] = r = run_memory(cmd, mode, base)
            r['cmd'] = [os.path.basename(cmd[0])] + cmd[1:]
            print(name, mode, r, file=sys.stderr)
    srv.shutdown()
    shutil.rmtree(base, ignore_errors=True)
    def clean(o):
        return json.loads(json.dumps(o).replace(base, '<base>'))
    json.dump(clean({'versions': versions, 'matrix': matrix, 'memory_cap_128mb_try_512mb': mem}),
              open(os.path.join(a.out, a.name), 'w'), indent=1)
    print('wrote', a.name, file=sys.stderr)


if __name__ == '__main__':
    main()
