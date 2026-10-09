# audio-disk — IndexTTS-2.5 本地配音

在自己电脑的显卡上运行 B 站开源的 [IndexTTS-2.5](https://github.com/index-tts/index-tts)，提供一个简洁的网页和 HTTP 接口：

- **音色克隆**：给一段 5–15 秒的参考录音，生成的声音就会模仿它，包括语气和气息。
- **情感控制**：可以跟随参考录音，也可以用另一段录音指定情感、手动调节 8 种情感强度，或者用文字描述情感（例如“温柔地低声说”）。
- **语速、多音字控制**：语速 0.5–2 倍可调；多音字写成 `<行|HANG2>` 即可指定读音。
- **长文本**：自动分段合成，生成完整的一段音频。
- 纯本地运行，不需要 API Key，不按字数收费。

## 硬件要求

- NVIDIA 显卡，显存 8GB 以上（RTX 3060 12GB 可以全精度运行；8GB 版本会自动切换为 BF16 半精度，并关闭“文字描述情感”功能以节省显存）。
- 磁盘空间 15GB 以上（依赖约 5GB，模型约 6GB）。
- 如果安装时报 CUDA 相关错误，请安装 [CUDA Toolkit 12.8](https://developer.nvidia.com/cuda-toolkit) 或更新版本，并更新显卡驱动。

## 安装（Windows）

1. 安装 [Git](https://git-scm.com/downloads)。
2. 下载本仓库，双击 **`setup.bat`**。它会依次：
   - 安装 `uv`（第一次安装后需要关闭窗口、重新双击 setup.bat）；
   - 把 IndexTTS 代码下载到 `index-tts/` 目录；
   - 安装依赖（使用阿里云 PyPI 镜像）；
   - 从 ModelScope 下载 IndexTTS-2.5 模型到 `index-tts/checkpoints/`；
   - 检查显卡是否可用。
3. 双击 **`start.bat`**。模型加载大约需要 1–2 分钟，完成后会自动打开浏览器，地址是 http://127.0.0.1:8000 。

Linux 下对应的是 `./setup.sh` 和 `./start.sh`。

### 不影响本机已有的 Python

安装过程不会改动你电脑上原有的 Python 和其中的包：

- IndexTTS 需要 Python 3.10 或 3.11。`setup.bat` 会用 uv 单独下载一份 Python 3.11，放在 uv 自己的目录里，并加上 `--no-bin --no-registry` 参数，所以不会加入 PATH，也不会写入注册表，命令行里的 `python` 仍然是你原来的版本。
- 所有依赖（包括 PyTorch）都安装在 `index-tts\.venv` 这个独立环境里。
- 如果需要 pip 来安装 uv，会用 `--target` 装到项目的 `.tools` 文件夹，而不是装进系统 Python。
- 不想用了，直接删除整个项目文件夹即可；uv 下载的 Python 可以用 `uv python uninstall 3.11` 删除。

### 使用本机已有的 Python

如果电脑上已经装了 Python 3.10 或 3.11，可以在命令提示符里运行（参数可以是 Python 文件夹，也可以是 python.exe 的路径）：

```
setup.bat F:\python
```

这样就不用再下载 Python。路径会记在 `python-path.txt` 里，`start.bat` 会自动使用它。

注意：IndexTTS 需要指定版本的 PyTorch（2.8 + CUDA 12.8）和配套依赖，这些仍然会安装到 `index-tts\.venv` 这个独立环境里，不会改动你本机 Python 里已有的包。所以本机 Python 里的 torch 不会被复用。

> 第一次启动时，IndexTTS 还会自动下载几个小模型。启动脚本已默认使用 `hf-mirror.com` 镜像，如需改回官方源，先设置环境变量 `HF_ENDPOINT=https://huggingface.co`。

## 让声音更自然的建议

- **参考录音最重要**：用干净的人声（无背景音乐、无回声），5–15 秒，语气就是你想要的语气。想要带气息、轻声的效果，参考录音本身就要是那样说话的。
- 把常用的参考录音放进 `voices/` 文件夹，或者在网页上点“上传”，以后就能直接从列表里选择。
- 录长篇（有声书、长段旁白）时，固定使用同一段参考录音，并保持“情感随机采样”关闭，前后音色会更一致。
- 情感强度不要拉满。用“文字描述情感”时，官方建议强度在 0.6 左右或更低。

## 启动参数

```
start.bat [参数]

--host 0.0.0.0     允许局域网内其他设备访问（默认只允许本机）
--port 8000        端口
--token 密码       设置访问密码（也可以用环境变量 ACCESS_TOKEN）
--bf16 / --fp32    强制半精度 / 全精度（默认按显存自动选择）
--qwen_emo         显存不足 10GB 时也启用“文字描述情感”
--no_qwen_emo      不启用“文字描述情感”，节省显存
```

## 接口

`POST /api/tts`，返回 WAV 音频。设置了访问密码时，需要带请求头 `Authorization: Bearer <密码>`。

```bash
curl -X POST http://127.0.0.1:8000/api/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，世界","voice":"我的声音.wav","emo_mode":"vector","emo_vector":[0.6,0,0,0,0,0,0,0]}' \
  -o out.wav
```

| 字段 | 说明 |
| --- | --- |
| `text` | 要合成的文字（必填） |
| `voice` | 音色参考音频名称（必填），可用名称见 `GET /api/config` 返回的 `voices` |
| `lang` | `ZH` / `EN` / `JA` / `ES` / `AR`，默认 `ZH` |
| `duration_factor` | 时长倍数 0.5–2，大于 1 变慢，默认 1 |
| `emo_mode` | `none` 跟随参考音频（默认）/ `audio` 情感参考音频 / `vector` 情感向量 / `text` 文字描述情感 |
| `emo_voice` | `emo_mode=audio` 时使用的情感参考音频名称 |
| `emo_vector` | `emo_mode=vector` 时的 8 个数值（0–1），顺序：开心、生气、悲伤、害怕、厌恶、低落、惊讶、平静 |
| `emo_text` | `emo_mode=text` 时的情感描述，留空则根据正文判断 |
| `emo_alpha` | 情感强度 0–1，用于 `audio` 和 `text` 模式 |
| `use_random` | 情感随机采样，默认 `false` |
| `interval_silence` | 分段之间的停顿（毫秒），默认 200 |
| `temperature` / `top_p` / `top_k` / `repetition_penalty` | 采样参数，不填则使用 IndexTTS 的默认值 |

其他接口：`GET /api/config`（配置和音色列表）、`POST /api/voices`（上传参考音频，表单字段 `file`）、`GET /api/voices/<名称>`（下载参考音频）、`GET /healthz`。

## 许可证

IndexTTS 的代码和模型使用 bilibili 的自定义许可证（bilibili Model Use License Agreement），商用前请阅读 `index-tts/LICENSE_ZH.txt`。
