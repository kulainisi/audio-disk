# audio-disk — MiniMax 语音合成服务

一个零依赖的 Node.js 小服务，用来调用 [MiniMax 同步语音合成接口 (T2A v2)](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http)。服务自带网页：输入文字、选择音色，就能直接播放或下载音频。

- **优先国际站，回退国内站**：配置了国际站 Key 时先调用 `api.minimax.io`，失败后自动改调国内站 `api.minimaxi.com`。只配置一个站点时只调用该站点。
- **API Key 只保存在服务端**，浏览器拿不到。
- 可以设置 **访问密码**（`ACCESS_TOKEN`），防止别人盗用你的额度。

## 配置

| 环境变量 | 说明 |
| --- | --- |
| `MINIMAX_INTL_API_KEY` | 国际站 API Key（可选） |
| `MINIMAX_CN_API_KEY` | 国内站 API Key（可选） |
| `MINIMAX_INTL_GROUP_ID` / `MINIMAX_CN_GROUP_ID` | 旧版账号需要 GroupId 时填写（可选） |
| `ACCESS_TOKEN` | 访问密码，强烈建议公网部署时设置 |
| `PORT` | 监听端口，默认 `3000` |

两个 API Key 至少要配置一个。完整示例见 `.env.example`。

## 本地运行

需要 Node.js 18 或更高版本。

```bash
MINIMAX_CN_API_KEY=你的Key ACCESS_TOKEN=自定义密码 npm start
# 浏览器打开 http://localhost:3000
```

## 部署

### Docker（任意云服务器，包括阿里云/腾讯云）

```bash
docker build -t audio-disk .
docker run -d --name audio-disk -p 3000:3000 --restart unless-stopped \
  -e MINIMAX_INTL_API_KEY=国际站Key \
  -e MINIMAX_CN_API_KEY=国内站Key \
  -e ACCESS_TOKEN=自定义密码 \
  audio-disk
```

### Render / Railway / Zeabur / Fly.io 等平台

连接本仓库后选择 Dockerfile 部署（或使用 Node 环境，启动命令为 `npm start`），然后在平台后台填写上面的环境变量。

> 提示：服务部署在海外时，访问国际站更快；部署在国内时，访问国内站更稳定。如果你的服务器在国内、但又想优先使用国际站，请先确认服务器能访问 `api.minimax.io`。

## 接口

`POST /api/tts`。设置了访问密码时，需要带请求头 `Authorization: Bearer <ACCESS_TOKEN>`。

```bash
curl -X POST http://localhost:3000/api/tts \
  -H "Authorization: Bearer 自定义密码" \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，世界","voice_id":"female-shaonv","model":"speech-2.6-hd","format":"mp3"}' \
  -o out.mp3
```

请求字段（只有 `text` 必填）：`text`、`model`、`voice_id`、`speed`、`vol`、`pitch`、`emotion`、`language_boost`、`format`（`mp3` / `wav` / `flac` / `pcm`）、`sample_rate`、`bitrate`、`channel`。

调用成功时直接返回音频二进制，响应头 `X-TTS-Provider` 表示实际使用的站点（`intl` 或 `cn`）。调用失败时返回 JSON，`details` 里列出每个站点的错误信息。

其他接口：`GET /api/config`（返回已启用的站点等配置信息）、`GET /healthz`（健康检查）。
