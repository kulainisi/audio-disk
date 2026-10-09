// MiniMax 语音合成 (T2A v2) 代理服务
// 优先调用国际站 (api.minimax.io)，未配置或调用失败时回退到国内站 (api.minimaxi.com)。
// 依赖：Node.js >= 18（使用内置 fetch），无第三方包。

const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

// 如果项目目录下有 .env 文件，就读取其中的配置（已存在的环境变量优先）。
function loadEnvFile(file) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (!m || process.env[m[1]] !== undefined) continue;
    process.env[m[1]] = m[2].replace(/^(["'])(.*)\1$/, "$2");
  }
}
loadEnvFile(path.join(__dirname, ".env"));

const PORT = Number(process.env.PORT) || 3000;
const ACCESS_TOKEN = process.env.ACCESS_TOKEN || "";
const MAX_TEXT_LENGTH = 10000;
// 固定使用的语音模型，前端无法修改。
const MODEL = process.env.MINIMAX_MODEL || "speech-2.8-hd";
const UPSTREAM_TIMEOUT_MS = Number(process.env.UPSTREAM_TIMEOUT_MS) || 120000;

// 按优先级排列：国际站在前，国内站在后。只启用配置了 API Key 的站点。
const PROVIDERS = [
  {
    name: "intl",
    label: "国际站",
    baseUrl: process.env.MINIMAX_INTL_BASE_URL || "https://api.minimax.io",
    apiKey: process.env.MINIMAX_INTL_API_KEY || "",
    groupId: process.env.MINIMAX_INTL_GROUP_ID || "",
  },
  {
    name: "cn",
    label: "国内站",
    baseUrl: process.env.MINIMAX_CN_BASE_URL || "https://api.minimaxi.com",
    apiKey: process.env.MINIMAX_CN_API_KEY || "",
    groupId: process.env.MINIMAX_CN_GROUP_ID || "",
  },
].filter((p) => p.apiKey);

const AUDIO_TYPES = {
  mp3: "audio/mpeg",
  wav: "audio/wav",
  flac: "audio/flac",
  pcm: "application/octet-stream",
};

const PUBLIC_DIR = path.join(__dirname, "public");
const STATIC_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};

function sendJson(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(body));
}

function isAuthorized(req) {
  if (!ACCESS_TOKEN) return true;
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  const a = Buffer.from(token);
  const b = Buffer.from(ACCESS_TOKEN);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function readJsonBody(req, limit = 1024 * 1024) {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks = [];
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > limit) {
        reject(Object.assign(new Error("请求体过大"), { status: 413 }));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}"));
      } catch {
        reject(Object.assign(new Error("请求体不是合法的 JSON"), { status: 400 }));
      }
    });
    req.on("error", reject);
  });
}

function num(value, fallback) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

// 把前端传来的参数整理成 MiniMax t2a_v2 的请求体。
function buildPayload(input) {
  const text = typeof input.text === "string" ? input.text.trim() : "";
  if (!text) throw Object.assign(new Error("text 不能为空"), { status: 400 });
  if (text.length > MAX_TEXT_LENGTH) {
    throw Object.assign(new Error(`text 不能超过 ${MAX_TEXT_LENGTH} 字符`), { status: 400 });
  }
  const format = AUDIO_TYPES[input.format] ? input.format : "mp3";

  const voiceSetting = {
    voice_id: input.voice_id || "male-qn-qingse",
    speed: num(input.speed, 1),
    vol: num(input.vol, 1),
    pitch: num(input.pitch, 0),
  };
  if (input.emotion) voiceSetting.emotion = input.emotion;

  const payload = {
    model: MODEL,
    text,
    stream: false,
    voice_setting: voiceSetting,
    audio_setting: {
      sample_rate: num(input.sample_rate, 32000),
      bitrate: num(input.bitrate, 128000),
      format,
      channel: num(input.channel, 1),
    },
    output_format: "hex",
  };
  if (input.language_boost) payload.language_boost = input.language_boost;
  return payload;
}

async function callProvider(provider, payload) {
  const url = new URL(provider.baseUrl.replace(/\/+$/, "") + "/v1/t2a_v2");
  if (provider.groupId) url.searchParams.set("GroupId", provider.groupId);

  const resp = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${provider.apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
  });

  const raw = await resp.text();
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    throw new Error(`HTTP ${resp.status}，返回内容不是 JSON：${raw.slice(0, 200)}`);
  }

  const base = data.base_resp || {};
  if (!resp.ok || (base.status_code !== undefined && base.status_code !== 0)) {
    throw new Error(
      `HTTP ${resp.status}，status_code=${base.status_code}，${base.status_msg || "未知错误"}` +
        (data.trace_id ? `，trace_id=${data.trace_id}` : "")
    );
  }
  const hex = data.data && data.data.audio;
  if (!hex) throw new Error("返回结果中没有音频数据");

  return { audio: Buffer.from(hex, "hex"), extra: data.extra_info || {}, traceId: data.trace_id || "" };
}

async function handleTts(req, res) {
  if (!isAuthorized(req)) return sendJson(res, 401, { error: "访问密码错误" });
  if (PROVIDERS.length === 0) {
    return sendJson(res, 500, { error: "服务端未配置 MINIMAX_INTL_API_KEY 或 MINIMAX_CN_API_KEY" });
  }

  let payload;
  try {
    payload = buildPayload(await readJsonBody(req));
  } catch (err) {
    return sendJson(res, err.status || 400, { error: err.message });
  }

  const errors = [];
  for (const provider of PROVIDERS) {
    try {
      const result = await callProvider(provider, payload);
      const format = payload.audio_setting.format;
      res.writeHead(200, {
        "Content-Type": AUDIO_TYPES[format],
        "Content-Length": result.audio.length,
        "Content-Disposition": `inline; filename="tts.${format}"`,
        "X-TTS-Provider": provider.name,
        "X-TTS-Trace-Id": result.traceId,
        "X-TTS-Audio-Length-Ms": String(result.extra.audio_length || ""),
        "X-TTS-Usage-Characters": String(result.extra.usage_characters || ""),
        "Access-Control-Expose-Headers":
          "X-TTS-Provider, X-TTS-Trace-Id, X-TTS-Audio-Length-Ms, X-TTS-Usage-Characters",
      });
      return res.end(result.audio);
    } catch (err) {
      const message = `${provider.label}：${err.message}`;
      console.error(`[tts] ${message}`);
      errors.push(message);
    }
  }
  sendJson(res, 502, { error: "所有站点调用均失败", details: errors });
}

function serveStatic(req, res) {
  const urlPath = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const filePath = path.join(PUBLIC_DIR, urlPath === "/" ? "index.html" : urlPath);
  if (!filePath.startsWith(PUBLIC_DIR + path.sep)) return sendJson(res, 404, { error: "Not Found" });
  fs.readFile(filePath, (err, content) => {
    if (err) return sendJson(res, 404, { error: "Not Found" });
    res.writeHead(200, {
      "Content-Type": STATIC_TYPES[path.extname(filePath)] || "application/octet-stream",
    });
    res.end(content);
  });
}

const server = http.createServer(async (req, res) => {
  const { pathname } = new URL(req.url, "http://x");
  try {
    if (pathname === "/api/tts" && req.method === "POST") return await handleTts(req, res);
    if (pathname === "/api/config" && req.method === "GET") {
      return sendJson(res, 200, {
        providers: PROVIDERS.map((p) => p.name),
        model: MODEL,
        requireToken: Boolean(ACCESS_TOKEN),
        maxTextLength: MAX_TEXT_LENGTH,
      });
    }
    if (pathname === "/healthz") return sendJson(res, 200, { ok: true });
    if (req.method === "GET") return serveStatic(req, res);
    sendJson(res, 405, { error: "Method Not Allowed" });
  } catch (err) {
    console.error(err);
    if (!res.headersSent) sendJson(res, 500, { error: "服务器内部错误" });
  }
});

server.listen(PORT, () => {
  const order = PROVIDERS.map((p) => `${p.label}(${p.baseUrl})`).join(" -> ") || "无（未配置 API Key）";
  console.log(`MiniMax TTS 服务已启动：http://localhost:${PORT}`);
  console.log(`调用顺序：${order}`);
  console.log(`语音模型：${MODEL}`);
  if (!ACCESS_TOKEN) console.log("提示：未设置 ACCESS_TOKEN，任何人都可以调用本服务。");
});
