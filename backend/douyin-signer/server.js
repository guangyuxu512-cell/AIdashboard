"use strict";

const crypto = require("crypto");
const http = require("http");
const { spawn } = require("child_process");
const path = require("path");

const port = Number(process.env.PORT || 8787);
const apiKey = (process.env.BACKEND_DOUYIN_SIGNER_API_KEY || "").trim();

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  console.error("Douyin signer requires a valid PORT.");
  process.exit(1);
}
if (!apiKey) {
  console.error("Douyin signer requires BACKEND_DOUYIN_SIGNER_API_KEY.");
  process.exit(1);
}

function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(body),
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let total = 0;
    req.on("data", (chunk) => {
      total += chunk.length;
      if (total > 1024 * 1024) {
        reject(new Error("request body too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

function isAuthorized(req) {
  const provided = req.headers["x-api-key"];
  if (typeof provided !== "string") return false;
  const expectedBytes = Buffer.from(apiKey);
  const providedBytes = Buffer.from(provided);
  return (
    expectedBytes.length === providedBytes.length
    && crypto.timingSafeEqual(expectedBytes, providedBytes)
  );
}

async function handleSign(req, res) {
  if (!isAuthorized(req)) {
    sendJson(res, 401, { ok: false, error: "unauthorized" });
    return;
  }
  const started = Date.now();
  try {
    const raw = await readBody(req);
    const input = JSON.parse(raw || "{}");
    const result = await signInChild(input);
    sendJson(res, result.a_bogus ? 200 : 500, {
      ok: Boolean(result.a_bogus),
      a_bogus: result.a_bogus || null,
      msToken: result.msToken || "",
      duration_ms: Date.now() - started,
      version: "abogus-node-env-1",
      error: result.error || undefined,
    });
  } catch (error) {
    sendJson(res, 500, {
      ok: false,
      a_bogus: null,
      duration_ms: Date.now() - started,
      error: error && error.message ? error.message : String(error),
    });
  }
}

function signInChild(input) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(__dirname, "sign_once.js")], {
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    const timeout = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error("sign child timed out"));
    }, Number(input.child_timeout_ms || 10000));
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", (error) => {
      clearTimeout(timeout);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timeout);
      try {
        const result = JSON.parse(stdout || "{}");
        if (code !== 0 && !result.error) {
          result.error = stderr || `sign child exited with ${code}`;
        }
        resolve(result);
      } catch (_error) {
        reject(new Error("sign child returned non-json output"));
      }
    });
    child.stdin.end(JSON.stringify(input));
  });
}

const server = http.createServer(async (req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    sendJson(res, 200, { ok: true, service: "abogus-signer" });
    return;
  }
  if (req.method === "GET" && req.url === "/version") {
    sendJson(res, 200, { ok: true, version: "abogus-node-env-1" });
    return;
  }
  if (req.method === "POST" && req.url === "/sign") {
    await handleSign(req, res);
    return;
  }
  sendJson(res, 404, { ok: false, error: "not found" });
});

server.listen(port, "127.0.0.1", () => {
  console.log(`Douyin signer listening on 127.0.0.1:${port}`);
});
