"""本地 IndexTTS-2.5 语音合成服务。

用法（在本仓库目录下执行，index-tts 已克隆到 ./index-tts 并下载好模型）：
    uv run --project index-tts python server.py

提供一个网页（http://127.0.0.1:8000）和 HTTP 接口 POST /api/tts，返回 WAV 音频。
"""

import argparse
import hmac
import os
import re
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC_DIR = os.path.join(ROOT, "public")
VOICES_DIR = os.path.join(ROOT, "voices")
AUDIO_EXTS = (".wav", ".mp3", ".flac", ".ogg", ".m4a")
MAX_TEXT_LENGTH = 20000
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
LOW_VRAM_THRESHOLD_GB = 10.0

# 情感向量的顺序必须与 IndexTTS 保持一致
EMOTIONS = ["happy", "angry", "sad", "afraid", "disgusted", "melancholic", "surprised", "calm"]
LANGS = ["ZH", "EN", "JA", "ES", "AR"]

parser = argparse.ArgumentParser(description="IndexTTS-2.5 本地语音合成服务")
parser.add_argument("--host", default="127.0.0.1", help="监听地址；局域网访问请用 0.0.0.0")
parser.add_argument("--port", type=int, default=8000)
parser.add_argument("--index_dir", default=os.path.join(ROOT, "index-tts"), help="index-tts 仓库目录")
parser.add_argument("--model_dir", default=None, help="模型目录，默认 <index_dir>/checkpoints")
parser.add_argument("--bf16", action="store_true", help="强制使用 BF16 半精度（显存不足 10GB 时会自动开启）")
parser.add_argument("--fp32", action="store_true", help="强制使用全精度")
parser.add_argument("--qwen_emo", action="store_true", help="显存不足 10GB 时也加载“情感描述文本”模型")
parser.add_argument("--no_qwen_emo", action="store_true", help="不加载“情感描述文本”模型，节省显存")
parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
parser.add_argument("--token",default=os.environ.get("ACCESS_TOKEN", ""), help="访问密码（也可用环境变量 ACCESS_TOKEN）")
args = parser.parse_args()

INDEX_DIR = os.path.abspath(args.index_dir)
MODEL_DIR = os.path.abspath(args.model_dir or os.path.join(INDEX_DIR, "checkpoints"))
if not os.path.isfile(os.path.join(MODEL_DIR, "config.yaml")):
    sys.exit(
        f"找不到模型：{os.path.join(MODEL_DIR, 'config.yaml')}\n"
        "请先在 index-tts 目录下执行：\n"
        "  uv run modelscope download --model IndexTeam/IndexTTS-2.5 --local_dir checkpoints"
    )

# IndexTTS 内部使用相对路径（如 ./checkpoints/hf_cache），必须在它的目录下运行
os.chdir(INDEX_DIR)
sys.path.insert(0, INDEX_DIR)
os.makedirs(VOICES_DIR, exist_ok=True)

import torch  # noqa: E402
from fastapi import FastAPI, File, Header, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, Response  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from indextts.infer_v2_5 import IndexTTS2  # noqa: E402

vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3 if torch.cuda.is_available() else None
low_vram = vram_gb is not None and vram_gb < LOW_VRAM_THRESHOLD_GB
use_bf16 = (args.bf16 or low_vram) and not args.fp32 and torch.cuda.is_available() and torch.cuda.is_bf16_supported()
use_qwen_emo = not args.no_qwen_emo and (args.qwen_emo or not low_vram)

if vram_gb is None:
    print(">> 警告：没有检测到 CUDA 显卡，将使用 CPU 推理，速度会非常慢。")
else:
    print(f">> 显卡：{torch.cuda.get_device_name(0)}，显存 {vram_gb:.1f} GB")
print(f">> BF16 半精度：{'开' if use_bf16 else '关'}；情感描述文本模型：{'加载' if use_qwen_emo else '不加载'}")

tts = IndexTTS2(
    cfg_path=os.path.join(MODEL_DIR, "config.yaml"),
    model_dir=MODEL_DIR,
    use_bf16=use_bf16,
    use_qwen_emo=use_qwen_emo,
)
# GPU 一次只跑一个任务，避免并发请求导致显存溢出
infer_lock = threading.Lock()

try:
    from indextts.utils.examples_downloader import ensure_examples_available

    ensure_examples_available()
except Exception as exc:  # 示例音频只是方便试用，下载失败不影响服务
    print(f">> 示例音频下载失败（不影响使用）：{exc}")


def list_voices():
    """返回 {名称: 文件路径}。用户音色在 voices/ 下，官方示例名称前加 “示例/”。"""
    voices = {}
    for name in sorted(os.listdir(VOICES_DIR)):
        if name.lower().endswith(AUDIO_EXTS):
            voices[name] = os.path.join(VOICES_DIR, name)
    examples_dir = os.path.join(INDEX_DIR, "examples")
    if os.path.isdir(examples_dir):
        for name in sorted(os.listdir(examples_dir)):
            if name.lower().endswith(AUDIO_EXTS):
                voices["示例/" + name] = os.path.join(examples_dir, name)
    return voices


def resolve_voice(name, field):
    path = list_voices().get(name or "")
    if not path:
        raise HTTPException(400, f"{field} 不存在：{name}")
    return path


def check_token(authorization):
    if not args.token:
        return
    token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
    if not hmac.compare_digest(token.encode(), args.token.encode()):
        raise HTTPException(401, "访问密码错误")


class TtsRequest(BaseModel):
    text: str
    voice: str = Field(description="音色参考音频名称（见 /api/config 的 voices）")
    lang: str = "ZH"
    # 情感控制：none=跟随音色参考音频，audio=情感参考音频，vector=情感向量，text=情感描述文本
    emo_mode: str = "none"
    emo_voice: str | None = None
    emo_alpha: float = Field(1.0, ge=0, le=1)
    emo_vector: list[float] | None = None
    emo_text: str | None = None
    use_random: bool = False
    duration_factor: float = Field(1.0, ge=0.5, le=2.0)
    interval_silence: int = Field(200, ge=0, le=2000)
    temperature: float | None = Field(None, gt=0, le=2)
    top_p: float | None = Field(None, gt=0, le=1)
    top_k: int | None = Field(None, ge=0, le=200)
    repetition_penalty: float | None = Field(None, ge=1, le=20)


app = FastAPI(title="IndexTTS-2.5 本地服务")


@app.exception_handler(HTTPException)
async def http_error(_, exc):
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


@app.get("/")
def index():
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/config")
def config():
    return {
        "model": "IndexTTS-2.5",
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "bf16": use_bf16,
        "qwenEmo": use_qwen_emo,
        "requireToken": bool(args.token),
        "maxTextLength": MAX_TEXT_LENGTH,
        "langs": LANGS,
        "emotions": EMOTIONS,
        "voices": list(list_voices().keys()),
    }


@app.get("/api/voices/{name:path}")
def get_voice(name: str, token: str = "", authorization: str | None = Header(None)):
    # <audio> 标签无法带请求头，所以也接受 ?token= 参数
    check_token(authorization or (f"Bearer {token}" if token else None))
    return FileResponse(resolve_voice(name, "voice"))


@app.post("/api/voices")
async def upload_voice(file: UploadFile = File(...), authorization: str | None = Header(None)):
    check_token(authorization)
    base, ext = os.path.splitext(os.path.basename(file.filename or ""))
    ext = ext.lower()
    if ext not in AUDIO_EXTS:
        raise HTTPException(400, f"只支持 {' / '.join(AUDIO_EXTS)} 格式")
    base = re.sub(r"[^\w一-鿿-]+", "_", base).strip("_") or f"voice_{int(time.time())}"
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "文件不能超过 20MB")
    name = base + ext
    with open(os.path.join(VOICES_DIR, name), "wb") as f:
        f.write(data)
    return {"name": name}


@app.post("/api/tts")
def synthesize(req: TtsRequest, authorization: str | None = Header(None)):
    check_token(authorization)
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "text 不能为空")
    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(400, f"text 不能超过 {MAX_TEXT_LENGTH} 字")
    if req.lang.upper() not in LANGS:
        raise HTTPException(400, f"lang 只支持 {', '.join(LANGS)}")

    kwargs = dict(
        spk_audio_prompt=resolve_voice(req.voice, "voice"),
        text=text,
        lang=req.lang.upper(),
        use_random=req.use_random,
        duration_factor=req.duration_factor,
        interval_silence=req.interval_silence,
    )
    if req.emo_mode == "audio":
        kwargs["emo_audio_prompt"] = resolve_voice(req.emo_voice, "emo_voice")
        kwargs["emo_alpha"] = req.emo_alpha
    elif req.emo_mode == "vector":
        if not req.emo_vector or len(req.emo_vector) != len(EMOTIONS):
            raise HTTPException(400, f"emo_vector 需要 {len(EMOTIONS)} 个数值：{', '.join(EMOTIONS)}")
        kwargs["emo_vector"] = tts.normalize_emo_vec([max(0.0, min(1.0, v)) for v in req.emo_vector])
    elif req.emo_mode == "text":
        if not use_qwen_emo:
            raise HTTPException(400, "服务启动时没有加载情感描述文本模型（可加 --qwen_emo 启动）")
        kwargs["use_emo_text"] = True
        kwargs["emo_text"] = (req.emo_text or "").strip() or None
        kwargs["emo_alpha"] = req.emo_alpha
    elif req.emo_mode != "none":
        raise HTTPException(400, "emo_mode 只能是 none / audio / vector / text")

    for key in ("temperature", "top_p", "top_k", "repetition_penalty"):
        value = getattr(req, key)
        if value is not None:
            kwargs[key] = value
    if req.top_k == 0:
        kwargs["top_k"] = None

    fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        start = time.perf_counter()
        with infer_lock:
            result = tts.infer(output_path=out_path, **kwargs)
        elapsed = time.perf_counter() - start
        if not result or not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
            raise HTTPException(500, "生成失败，没有输出音频")
        with open(out_path, "rb") as f:
            audio = f.read()
    except HTTPException:
        raise
    except Exception as exc:
        print(f">> 生成失败：{exc!r}")
        raise HTTPException(500, f"生成失败：{exc}")
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)

    return Response(
        audio,
        media_type="audio/wav",
        headers={
            "Content-Disposition": 'inline; filename="tts.wav"',
            "X-TTS-Elapsed-Seconds": f"{elapsed:.2f}",
        },
    )


if __name__ == "__main__":
    import uvicorn

    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.port}"
    print(f">> 模型加载完成，打开 {url} 开始使用")
    if args.open:
        import webbrowser

        threading.Timer(1.5, webbrowser.open, [url]).start()
    uvicorn.run(app, host=args.host, port=args.port)
