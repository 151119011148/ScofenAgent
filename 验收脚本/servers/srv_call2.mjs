import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
const t = new StdioClientTransport({ command: "node", args: ["src/sequentialthinking/dist/index.js"], cwd: process.argv[2] });
const cl = new Client({ name: "seq-smoke", version: "0" });
await cl.connect(t);
const r = await cl.callTool({ name: "think", arguments: { thought: "确认工具可执行", thoughtNumber: 2, totalThoughts: 3, nextThoughtNeeded: true } });
console.log("RESULT isError=" + !!r.isError + " | " + String(r.content?.[0]?.text).replace(/\s+/g, " ").slice(0, 160));
await cl.close();
