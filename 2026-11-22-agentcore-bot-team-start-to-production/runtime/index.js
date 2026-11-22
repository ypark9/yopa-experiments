// The smallest HTTP server that follows the AgentCore Runtime contract.
// No dependencies: Node's built-in http module only. A real runtime calls a model
// here; this one echoes the prompt back word by word so the stream is easy to see.
import http from 'node:http';
import { randomUUID } from 'node:crypto';

const SESSION_HEADER = 'x-amzn-bedrock-agentcore-runtime-session-id';
const REQUEST_HEADER = 'x-amzn-bedrock-agentcore-runtime-request-id';
// Custom headers reach this code only if the runtime allowlists them.
const USER_HEADER = 'x-amzn-bedrock-agentcore-runtime-custom-user';

function json(res, status, body) {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(body));
}

const server = http.createServer(async (req, res) => {
  if (req.method === 'GET' && req.url === '/ping') {
    return json(res, 200, { status: 'Healthy' });
  }
  if (req.method !== 'POST' || req.url !== '/invocations') {
    return json(res, 404, { error: 'not found' });
  }

  const sessionId = req.headers[SESSION_HEADER];
  if (!sessionId) {
    return json(res, 400, { error: `missing header ${SESSION_HEADER}` });
  }
  const requestId = req.headers[REQUEST_HEADER] ?? randomUUID();

  let raw = '';
  for await (const chunk of req) raw += chunk;
  let input;
  try {
    input = JSON.parse(raw);
  } catch {
    return json(res, 400, { error: 'body must be JSON' });
  }

  res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
  const send = (event) => res.write(`data: ${JSON.stringify(event)}\n\n`);
  send({ type: 'start', sessionId, requestId, user: req.headers[USER_HEADER] ?? null });
  for (const word of `You said: ${input.prompt ?? ''}`.split(' ')) {
    send({ type: 'text', text: `${word} ` });
  }
  send({ type: 'end' });
  res.end();
});

server.listen(Number(process.env.PORT ?? 8080), '0.0.0.0');
