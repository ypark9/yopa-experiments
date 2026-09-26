# Does an MCP App behave the same on every host?

Code and raw data for [Should Your Service Render Inside the AI Host?](https://www.yopa.page/blog/2026-09-26-should-your-service-render-inside-the-ai-host.html).

An MCP server with MCP Apps (SEP-1865) `ui://` resources, run against two hosts:

1. **MCP Inspector 2.8.0** as a local host stand-in (2026-09-23).
2. **Claude Desktop 2.9939.2**, a real host, with the same server over stdio (2026-09-26).

**What it calls:** nothing on AWS, no deployment, no public endpoint. The server is a stdio child
process with no sockets. The widget makes a few public requests on purpose, to test the sandbox's
content security policy (CSP): an image from `cdn.jsdelivr.net`, a stylesheet from
`fonts.googleapis.com`, `fetch()` to `api.github.com/zen` and `example.com`, and an iframe to
`example.com`. The data is three fake unicorns. Cost: $0.

**Read [FINDINGS.md](FINDINGS.md)** for what it settled and what it did not. Section 5 is the
Claude Desktop run.

## Layout

| Path | What it is |
|---|---|
| `src/server.js` | The server. Two widget tools, one text-only control tool, two `ui://` resources that differ only in their declared CSP. |
| `src/widget.html` | The widget. Renders `structuredContent` and probes six asset-loading paths, reporting the CSP the host actually enforced. |
| `src/server-mutating.js` | Same server, but registers `late_arrival` on the first `fleet_status` call. Used to test whether a host re-reads the tool list on its own. |
| `scripts/tee-server.mjs` | Transparent stdio proxy that logs every JSON-RPC frame, one file per process (`<MCP_WIRE_LOG>-<start>-<pid>.jsonl`). |
| `transcripts/` | Raw evidence: protocol payloads, wire logs, widget probe reports, render screenshot. |

## Quick start

```bash
npm install
npm run inspector      # opens the inspector UI; connect, Apps tab, Open App
```

See the Reproducing section of [FINDINGS.md](FINDINGS.md) for the individual capture commands.

## Three things to know before you trust a run of this

1. **Do not infer CSP behaviour from `onload`/`onerror`.** A stylesheet blocked by CSP still
   yields a non-null `link.sheet`, and a blocked iframe still fires `load`. Two of the six
   probes here reported the wrong answer that way, every run. Listen for
   `securitypolicyviolation` and read `originalPolicy`.
2. **The inspector does not pass the shell's environment to the server it spawns.**
   `FOO=1 npx @modelcontextprotocol/inspector ...` will not reach your server. Pass
   configuration as an argument, as `scripts/tee-server.mjs` does.
3. **`ui/initialize` takes `appInfo`, not `clientInfo`.** The spec's "you don't need an SDK"
   snippet shows `clientInfo`, but that snippet is for the base `initialize` method. Copying
   it into a `ui/initialize` call gets you `-32602`. The widget here sends the wrong shape
   first and the right one second, on purpose, so both are in the transcript.

## Scripts

```bash
npm run inspector            # inspector UI against src/server.js
npm run inspector:wire       # same, logging every frame to transcripts/wire.jsonl
npm run inspector:mutating   # server grows a tool 15s in, for the listing-staleness test
npm run capture:no-ui        # drive the server as a host with no MCP Apps capability
```
