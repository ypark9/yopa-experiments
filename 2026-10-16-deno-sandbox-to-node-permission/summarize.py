#!/usr/bin/env python3
"""Turn results/raw*.json into results/matrix.md and check that all runs agree."""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
runs = sorted(glob.glob(os.path.join(HERE, 'results', 'raw*.json')))
data = [json.load(open(r)) for r in runs]
PROBES = ['fs_read_outside', 'fs_write_outside', 'fs_write_workdir', 'fs_read_via_symlink_in_workdir', 'env_secret',
          'net_fetch_localhost', 'net_tcp_localhost', 'child_process', 'sqlite_read_outside', 'sqlite_write_outside',
          'inherited_fd_read', 'debug_process_sibling', 'signal_sibling_sigusr1']
COLS = ['deno/P0', 'node22/P0', 'node24/P0', 'node26/P0', 'deno/P1', 'node22/P1', 'node24/P1', 'node26/P1']

def cell(m, col, probe):
    p = m[col]['probes'][probe]
    ctrl = m[col.split('/')[0] + '/control']['probes'][probe]['result']
    if ctrl != 'allowed':
        return 'n/a'            # the probe cannot succeed even with full access in this runtime
    r = p['result']
    if probe in ('debug_process_sibling', 'signal_sibling_sigusr1'):
        r = 'allowed' if p.get('sibling_inspector_opened') else 'blocked'
    return r

def table(m):
    lines = ['| probe | ' + ' | '.join(COLS) + ' |', '|' + '---|' * (len(COLS) + 1)]
    for pr in PROBES:
        lines.append(f'| {pr} | ' + ' | '.join(cell(m, c, pr) for c in COLS) + ' |')
    return lines

tables = [table(d['matrix']) for d in data]
agree = all(t == tables[0] for t in tables)
out = [f'# Probe matrix ({len(runs)} runs, identical: {agree})', '', 'Versions: ' + ', '.join(data[0]['versions'].values()), '',
       'P0 = no grants (yt-dlp style). P1 = read+write grant on the work dir only. "allowed" means the probe got through;',
       'for the two sibling probes it means the sibling process actually opened its inspector. "n/a" = fails even with full access.', '']
out += tables[0]
out += ['', '## Counts: probes that Deno blocks but Node allows', '']
for prof in ('P0', 'P1'):
    for n in ('node22', 'node24', 'node26'):
        c = [pr for pr in PROBES if cell(data[0]['matrix'], f'deno/{prof}', pr) == 'blocked' and cell(data[0]['matrix'], f'{n}/{prof}', pr) == 'allowed']
        out.append(f'- {prof} {n}: {len(c)} ({", ".join(c)})')
out += ['', '## Memory: heap cap 128 MB, then try to hold 512 MB', '', '| runtime/mode | exit code | heap OOM message | allocated | peak RSS MB |', '|---|---|---|---|---|']
for k, v in data[0]['memory_cap_128mb_try_512mb'].items():
    out.append(f"| {k} | {v['exit_code']} | {v['heap_oom_message']} | {v['stdout'] or '-'} | {v['peak_rss_mb']} |")
open(os.path.join(HERE, 'results', 'matrix.md'), 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
sys.exit(0 if agree else 1)
