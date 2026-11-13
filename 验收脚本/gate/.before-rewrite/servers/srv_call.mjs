import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
async function run(label, cmd, args, env, calls) {
  const t = new StdioClientTransport({ command: cmd, args, env: { ...process.env, ...env }, cwd: process.argv[2] });
  const cl = new Client({ name: "call-smoke", version: "0" });
  await cl.connect(t);
  for (const [tool, a] of calls) {
    const r = await cl.callTool({ name: tool, arguments: a });
    console.log(`${label} ${tool} -> isError=${!!r.isError} ${String(r.content?.[0]?.text).replace(/\s+/g, " ").slice(0, 110)}`);
  }
  await cl.close();
}
await run("memory", "node", ["src/memory/dist/index.js"], { MEMORY_FILE_PATH: "/tmp/mcp-memory-smoke.jsonl" },
  [["create_entities", { entities: [{ name: "烟雾测试节点", entityType: "test", observations: ["由 #34 验证脚本写入"] }] }], ["read_graph", {}]]);
await run("sequentialthinking", "node", ["src/sequentialthinking/dist/index.js"], {},
  [["think", { thought: "第二步：确认工具可执行", thoughtNumber: 2, totalThoughts: 3, nextThoughtNeeded: true }]]);
