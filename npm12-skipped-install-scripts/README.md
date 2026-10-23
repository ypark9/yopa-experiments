# npm 12 says "added N packages" and exits 0, but the native parts were never built

Experiment behind the yopa.page post *npm 12 says the install worked. Your native module disagrees.*

npm 12 blocks dependency `preinstall` / `install` / `postinstall` scripts, and the implicit
`node-gyp rebuild` for packages with a `binding.gyp`, unless the root `package.json` approves them in
`allowScripts`. This folder measures what that looks like from the outside: exit codes, what the log
says, and whether `require()` works afterwards.

## What it runs

| Piece | What it is |
|---|---|
| `fixtures/nativedemo` | Stand-in native add-on: C source + `binding.gyp`, **no** install script. npm adds an implicit `node-gyp rebuild`. |
| `fixtures/postdemo` | Stand-in codegen package: `postinstall` writes `generated.js`, which `index.js` requires. |
| `scripts/build_tarballs.sh` | Packs nativedemo 1.0.0, nativedemo 1.0.1, postdemo 1.0.0 into `registry/`. |
| `scripts/registry_server.mjs` | Read-only npm registry on `127.0.0.1:4873` that serves only those tarballs. |
| `scripts/run_matrix.sh` | 9 fixture cases + 4 real public packages on npm 11 and npm 12; writes `results/`. |
| `scripts/run_gate_checks.sh` | 5 cases for the recommended CI gate; writes `results/gate.tsv`. |

Real packages (downloaded from the public npm registry, nothing published): `sqlite3@6.0.1`,
`better-sqlite3@13.0.3`, `esbuild@0.28.2`, `bcrypt@6.0.0`.

Environment: see `results/environment.txt` (Node 24.22.0, npm 11.21.1 / 12.0.0 / 12.2.1, Linux x86_64, g++ and make for node-gyp).

## Cost

Local CPU and disk only. No cloud account, no paid API. Network: public npm registry, nodejs.org
headers for node-gyp, and (after approval) the prebuilt `sqlite3` binary from GitHub releases.

## Reproduce

```bash
# npm versions in separate prefixes so they don't touch your global npm
npm install -g --prefix "$PWD/.npm11"   npm@11.21.1
npm install -g --prefix "$PWD/.npm1200" npm@12.0.0
npm install -g --prefix "$PWD/.npm12"   npm@12.2.1
./scripts/build_tarballs.sh
NPM11=$PWD/.npm11/bin/npm NPM1200=$PWD/.npm1200/bin/npm NPM12=$PWD/.npm12/bin/npm ./scripts/run_matrix.sh
NPM11=$PWD/.npm11/bin/npm NPM12=$PWD/.npm12/bin/npm ./scripts/run_gate_checks.sh
```

## Results (`results/matrix.tsv`)

Columns: case, npm version, command, exit code, count of `install-scripts` warning lines in the log, smoke test.

| Case | npm | Command | Exit | Smoke test after install |
|---|---|---|---|---|
| c01 | 11.21.1 | `npm install` | 0 | native ok, generated ok |
| c02 | 12.2.1 | `npm install` | 0 | both FAIL: `Cannot find module './build/Release/nativedemo.node'`, `Cannot find module './generated.js'` |
| c03 | 12.2.1 | `npm ci --silent` with the lockfile npm 11 wrote | 0 | both FAIL, and the log is **empty** |
| c04 | 12.2.1 | `npm install-scripts ls` with 2 pending | 0 | (read-only listing; exit 0 even with pending packages) |
| c05 | 12.2.1 | `npm install --strict-allow-scripts` | 1 | `ESTRICTALLOWSCRIPTS`, no `node_modules` |
| c06 | 12.0.0 | `npm install` with `strict-allow-scripts=true` in `.npmrc` | 1 | same error on 12.0.0 |
| c07 | 12.2.1 | `npm install-scripts approve nativedemo postdemo` then `npm rebuild` | 0 | native ok, generated ok |
| c08 | 12.2.1 | fresh `npm ci` with `allowScripts` committed | 0 | native ok, generated ok |
| c09 | 12.2.1 | `npm install nativedemo@1.0.1` after approving `nativedemo@1.0.0` | 0 | native FAIL again (approval was pinned to 1.0.0) |
| real | 11.21.1 / 12.2.1 | `sqlite3@6.0.1` | 0 / 0 | ok / **FAIL: Could not locate the bindings file** |
| real | 11.21.1 / 12.2.1 | `better-sqlite3@13.0.3` | 0 / 0 | ok / ok (no install script; ships `prebuilds/`, `gypfile: false`) |
| real | 11.21.1 / 12.2.1 | `esbuild@0.28.2` | 0 / 0 | ok / ok (postinstall blocked, binary comes from an optional platform package) |
| real | 11.21.1 / 12.2.1 | `bcrypt@6.0.0` | 0 / 0 | ok / ok (install script blocked, ships `prebuilds/`) |
| real | 12.2.1 | `npm install-scripts approve sqlite3` + `npm rebuild` | 0 | ok |

### CI gate checks (`scripts/run_gate_checks.sh`, `results/gate.tsv`)

The gate the post recommends is `npm ci --strict-allow-scripts` followed by `require()` of the native dependencies.

| Case | What | Exit |
|---|---|---|
| g1 | npm 12.2.1, lockfile with no approvals, gate | 1 (`ESTRICTALLOWSCRIPTS`) |
| g2 | npm 12.2.1, `allowScripts` committed, gate | 0, both modules load |
| g3 | npm 12.2.1, `strict-allow-scripts=true` in project `.npmrc`, plain `npm ci` | 1 |
| g4 | npm 11.21.1, `npm ci --strict-allow-scripts` | 1 (the flag already exists on 11.21.1) |
| g5 | npm 12.2.1, `npm install-scripts ls` on a fresh checkout before any install | 0, prints `No packages with unreviewed install scripts.` |

g5 matters: the listing reads what is installed in `node_modules`, so on a clean CI checkout it reports nothing.

Raw logs: `results/*.log` (local paths replaced by `npm` and `$TMP`).

## What this does not prove

- Only Linux x86_64 and Node 24.22.0. Packages whose prebuilt binary does not cover your platform will behave differently.
- Four real packages, picked because they cover four shapes (install script that downloads/builds, no script with bundled prebuilds, postinstall with optional platform packages, install script with bundled prebuilds). Not a survey of the registry.
- Workspaces, `install-strategy=linked`, pnpm/yarn, and Docker layer caching were not tested.
- npm 11.21.1 printed a warning for the same packages but still ran the scripts; earlier npm 11 releases were not tested.
