/**
 * Same server, but its tool inventory changes 15 seconds after start.
 *
 * Exists because the inspector does not forward the launching shell's
 * environment to the server subprocess, so MCP_MUTATE_AFTER_MS cannot be set
 * from outside. This entry point sets it before importing the server.
 *
 * Used to answer: once a host has listed tools, does it ever look again?
 */

// Round 2: mutate on the first fleet_status call instead of after a timer, so
// the change happens at a moment the tester chooses, inside one chat.
process.env.MCP_MUTATE_ON_CALL = process.env.MCP_MUTATE_ON_CALL || "fleet_status";
process.env.MCP_MUTATE_AFTER_MS = "0";

await import("./server.js");
