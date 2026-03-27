import "dotenv/config";
import crypto from "crypto";
import express from "express";
import { createServer } from "http";
import { WebSocketServer } from "ws";
import { chat } from "./agent.js";
import { closeMCP } from "./mcp.js";
import { closeDb } from "./db.js"; // dbTools imported by agent.js

const app = express();
const server = createServer(app);
const wss = new WebSocketServer({ noServer: true });

app.get("/health", (req, res) => res.json({ status: "healthy" }));
app.use(express.static("public"));

server.on("upgrade", (req, socket, head) => {
  wss.handleUpgrade(req, socket, head, (ws) => {
    wss.emit("connection", ws, req);
  });
});

wss.on("connection", (ws) => {
  const threadId = crypto.randomUUID();
  console.log(`[ws] New connection, threadId=${threadId}`);

  ws.on("message", async (data) => {
    try {
      const raw = data.toString();
      let content;
      try {
        const parsed = JSON.parse(raw);
        content = parsed.content ?? raw;
      } catch {
        content = raw;
      }

      console.log(`[ws] [${threadId}] Received: ${content}`);
      const start = Date.now();
      const response = await chat(content, threadId);
      console.log(`[ws] [${threadId}] Response (${Date.now() - start}ms): ${response.slice(0, 200)}`);

      if (ws.readyState === ws.OPEN) {
        ws.send(JSON.stringify({ type: "chunk", content: response, metadata: {} }));
        ws.send(JSON.stringify({ type: "done", content: response, metadata: { final: true } }));
      }
    } catch (err) {
      console.error(`[ws] [${threadId}] Error:`, err);
      if (ws.readyState === ws.OPEN) {
        ws.send(JSON.stringify({ type: "error", content: err.message }));
      }
    }
  });

  ws.on("close", () => console.log(`[ws] [${threadId}] Disconnected`));
});

const PORT = process.env.PORT || 8000;

server.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
  console.log(`NODE_OPTIONS: ${process.env.NODE_OPTIONS || "(not set)"}`);
  console.log(`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: ${process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT || "(not set)"}`);
  console.log(`DATABASE_URL: ${process.env.DATABASE_URL ? "(set)" : "(not set)"}`);
});

server.on("error", (err) => {
  if (err.code === "EADDRINUSE") {
    setTimeout(() => server.listen(PORT), 1000);
  } else {
    throw err;
  }
});

function shutdown() {
  for (const client of wss.clients) client.terminate();
  server.close();
  Promise.all([closeMCP(), closeDb()]).finally(() => process.exit(0));
  setTimeout(() => process.exit(0), 1000);
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
