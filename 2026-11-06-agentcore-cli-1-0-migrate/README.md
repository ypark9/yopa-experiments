# AgentCore CLI 1.0.1: what `migrate` rejects before it rewrites a project

Local, no-AWS experiment for the yopa.page draft on Amazon Bedrock AgentCore CLI 1.0
(`@aws/agentcore@1.0.1`). It installs the CLI from npm, builds small v0-style
`agentcore/agentcore.json` fixtures, and runs `agentcore migrate` (never `--yes`
against a real stack; never `deploy` / `invoke`).

## Cost

- **local:** Node/npm CPU and disk; `npm pack @aws/agentcore@1.0.1`
- **CI:** GitHub Actions `identifier-check` only on this repo
- **cloud:** none
- **billing:** unconfirmed (not checked)

AWS credentials are unset. `AWS_EC2_METADATA_DISABLED=true` and empty
`AWS_CONFIG_FILE` / `AWS_SHARED_CREDENTIALS_FILE` are set in the run script.

## Files

| Path | What it is |
| --- | --- |
| `fixtures/*/agentcore/agentcore.json` | Input shapes (allowed keys, rejected keys, incomplete fields, already-v2) |
| `fixtures/ready_local_minimal/` | Stub with git + `aws-targets.json` (account `123456789012`) + a too-old CDK `package.json` |
| `scripts/run_migrate_matrix.sh` | Install CLI 1.0.1 and run migrate on every fixture |
| `scripts/parse_results.py` | Build `results/parsed.json` from stdout |
| `results/*.txt` | Raw migrate stdout/stderr per fixture |
| `results/help/` | `--version`, `migrate`/`create`/`status`/`add` help, `add knowledge-base` error |
| `results/plans/` | Migrate plan markdown when the CLI wrote one |
| `results/summary.tsv` | fixture / exit / one-line output |
| `results/parsed.json` | Structured reject keys and exit hints |
| `results/environment.txt` | Package version and credential posture |

## Reproduce

```bash
# Node >= 20.12 (CLI engines field). From this folder:
./scripts/run_migrate_matrix.sh
python3 scripts/parse_results.py
```

Or point at an already-unpacked binary:

```bash
AGENTCORE_BIN=/path/to/@aws/agentcore/dist/index.js ./scripts/run_migrate_matrix.sh
```

## What the matrix showed (2026-11-06, CLI 1.0.1)

### Stage A — deserialize (fails before a plan)

| Situation (plain words) | Top-level JSON shape | Observed |
| --- | --- | --- |
| Guessed wrapper key `resources` | `version:1`, `name`, `resources:{}` | `Unrecognized key: "resources"` |
| Old name `agents` for runtimes | `agents:[...]` | `Unrecognized key: "agents"` |
| Top-level `gateways` / `targets` | those keys present | `Unrecognized key(s)` for them |
| Create-era flags parked on the project file | `language`, `framework` | `Unrecognized keys: "language", "framework"` |
| Arbitrary extra key | `fooBar:true` | `Unrecognized key: "fooBar"` |
| Empty object | `{}` | Missing `name`; `version` expected `2` (v1 schema path) |
| Already migrated | `version:2` | `This project is already in the v1 format` |
| Incomplete `runtimes[]` | name only | Field errors: `build` must be `CodeZip`\|`Container`; missing `entrypoint`, `codeLocation` |
| Incomplete `memories[]` | name only | Missing `eventExpiryDuration` |
| Incomplete `harnesses[]` | name only | Missing `path` |
| Incomplete knowledge base | name + empty-ish data source | Discriminator / `uri` field errors (schema still knows `knowledgeBases`) |

### Stage B — plan written, not ready (still no AWS)

A minimal `{ "version": 1, "name": "demo" }` **does** deserialize. Migrate then writes a plan and lists local blockers, for example:

- git repository required (clean working tree)
- `agentcore/cdk/package.json` must exist and CDK deps must be ≥ v0.24.2 (CLI tells you to run `npx @aws/agentcore@0 deploy` once — **we did not run that**; it would touch AWS)
- `agentcore/cdk/bin/cdk.ts` and `lib/cdk-stack.ts` required
- `agentcore/aws-targets.json` required
- CodeZip runtimes need `runtimeVersion` (value format not fully mapped here)
- Harnesses need `app/<name>/harness.json` on disk

`ready_local_minimal` cleared git + aws-targets and still failed on CDK age, missing CDK app files, and `runtimeVersion`.

### Command surface checks (help / unknown command)

- `agentcore add knowledge-base` → `unknown command 'knowledge-base' for 'add'`
- `agentcore create --help` → `--name`, `--template`, `--skip-install`, `--skip-git` only (no `--language` / `--framework`)
- `agentcore add harness --help` → `--model` / `--memory` JSON, `--timeout-seconds`
- `agentcore status --help` → `--target` only (no runtime/state/type filters)

## What this does not show

- It does **not** complete a migrate with `--yes` on a real deployed v0 project.
- It does **not** prove ARN / name preservation for deployed resources (plans for undeployed stubs say "never deployed; no names to keep").
- It does **not** run `deploy`, `invoke`, or any AWS API.
- Knowledge-base **entries can still appear in a v0 `agentcore.json` schema** that migrate reads; management via `add knowledge-base` is what the CLI removed (use AWS CLI per the breaking-changes page).

## Placeholder account

`fixtures/ready_local_minimal/agentcore/aws-targets.json` uses `123456789012` only.
