import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
const servers = {
  memory: "node src/memory/dist/index.js",
  sequentialthinking: "node src/sequentialthinking/dist/index.js",
  everything: "node src/everything/dist/index.js stdio",
  filesystem: "node src/filesystem/dist/index.js /tmp/mcp-fs-allow",
};
for (const [name, cmd] of Object.entries(servers)) {
  const [c, ...a] = cmd.split(" ");
  const t = new StdioClientTransport({ command: c, args: a, cwd: process.argv[2] });
  const cl = new Client({ name: "smoke", version: "0" });
  const started = Date.now();
  try {
    await cl.connect(t);
    const tools = await cl.listTools();
    const sv = cl.getServerVersion?.() ?? {};
    console.log(`OK  ${name}  ${Date.now()-started}ms  server=${sv.name}@${sv.version} tools=${tools.tools.length}`);
    await cl.close();
  } catch (e) {
    console.log(`FAIL ${name}  ${Date.now()-started}ms  ${String(e).slice(0,160)}`);
  }
}
