# audio-disk — MiniMax 语音合成服务

一个零依赖的 Node.js 小服务，固定使用 **speech-2.8-hd** 模型，用来调用 [MiniMax 同步语音合成接口 (T2A v2)](https://platform.minimaxi.com/docs/api-reference/speech-t2a-http)。服务自带网页：输入文字、选择音色，就能直接播放或下载音频。

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
| `MINIMAX_MODEL` | 语音模型，默认 `speech-2.8-hd` |
| `PORT` | 监听端口，默认 `3000` |

两个 API Key 至少要配置一个。可以直接写在项目目录下的 `.env` 文件里（服务启动时自动读取），完整示例见 `.env.example`。

> speech-2.8-hd 是 MiniMax 的闭源模型，只能通过 API 调用，音频在 MiniMax 的服务器上生成。本服务在本地只负责转发请求，不需要显卡，普通电脑就能运行。

## 本地运行

需要 Node.js 18 或更高版本。

### Windows（双击运行）

1. 从 https://nodejs.org 安装 Node.js（LTS 版本）。
2. 下载本仓库代码，双击 `start.bat`。第一次运行会生成 `.env` 并用记事本打开，填好 API Key 后保存。
3. 再次双击 `start.bat`，浏览器会自动打开 http://localhost:3000 。

### 命令行

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
  -d '{"text":"你好，世界","voice_id":"female-shaonv","format":"mp3"}' \
  -o out.mp3
```

请求字段（只有 `text` 必填）：`text`、`voice_id`、`speed`、`vol`、`pitch`、`emotion`、`language_boost`、`format`（`mp3` / `wav` / `flac` / `pcm`）、`sample_rate`、`bitrate`、`channel`。

调用成功时直接返回音频二进制，响应头 `X-TTS-Provider` 表示实际使用的站点（`intl` 或 `cn`）。调用失败时返回 JSON，`details` 里列出每个站点的错误信息。

其他接口：`GET /api/config`（返回已启用的站点等配置信息）、`GET /healthz`（健康检查）。
