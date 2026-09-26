# Claude Desktop transcripts (2026-09-26)

How these were produced: `claude_desktop_config.json` got two extra `mcpServers` entries for the
duration of the test (removed afterwards), both running `scripts/tee-server.mjs`:

- `mcp-apps-exp` -> `src/server.js`
- `mcp-apps-exp-mutating` -> `src/server-mutating.js` (registers `late_arrival` on the first `fleet_status` call)

with `MCP_WIRE_LOG` and `PROBE_LOG` pointing at this folder.

| File | What |
| --- | --- |
| `wire-*-<start>-<pid>.jsonl` | every frame, both directions, one file per server process |
| `probe-reports*.jsonl` | what the widget measured, sent back through the host via `tools/call record_probe_report` |
| `round1/` | the first run. Its `wire*.jsonl` only holds the Cowork session's frames: the log was opened in overwrite mode, and Cowork's copy of the server truncated the chat's log. Round 2 fixed that with one file per process. `round1/probe-reports.jsonl` is intact |

Which file is which host: the `clientInfo.name` in each file's `initialize` frame. `claude-ai` is the
regular chat; `local-agent-mode-*` is Cowork.
