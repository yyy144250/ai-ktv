"""
AI-KTV 视频制作工具 - FastAPI 主应用
功能: 上传MV → 去人声 → 日语歌词(手动/AI识别) → 假名标注 → 时间轴对齐 → KTV视频输出
"""

import os
import uuid
import asyncio
import logging
from pathlib import Path


logger = logging.getLogger("ai-ktv")
logging.basicConfig(level=logging.INFO)

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import aiofiles

app = FastAPI(title="AI-KTV 视频制作工具", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 目录配置
UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# 全局状态
active_connections: dict[str, WebSocket] = {}
jobs: dict[str, dict] = {}

# 支持的视频格式
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".webm", ".mov", ".flv", ".wmv"}


# ============ Pydantic Models ============

class LyricsInput(BaseModel):
    """手动输入歌词"""
    text: str  # 纯文本歌词，每行一句
    format: str = "plain"  # plain | lrc | ass


class LyricsUpdate(BaseModel):
    """修改歌词/假名"""
    lines: list[dict]  # [{text, ruby: [{char, reading}], ...}]


class LyricsSearchQuery(BaseModel):
    """歌词搜索请求"""
    keyword: str       # 歌曲名
    artist: str = ""   # 歌手名（可选）


class LyricsFetchRequest(BaseModel):
    """获取指定歌曲的 LRC 歌词"""
    source: str   # "netease"
    song_id: str  # 歌曲 ID


class RenderOptions(BaseModel):
    """渲染选项"""
    style: str = "classic_blue"  # classic_blue | pink | gold
    font_size: int = 48
    furigana_size: int = 24
    position: str = "bottom"  # bottom | top


# ============ API Endpoints ============

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    """上传 MV 视频文件"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="没有文件名")

    ext = Path(file.filename).suffix.lower()
    if ext not in VIDEO_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式: {ext}，支持: {', '.join(VIDEO_EXTS)}"
        )

    job_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{job_id}{ext}"

    # 保存文件
    async with aiofiles.open(save_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # 初始化任务
    jobs[job_id] = {
        "job_id": job_id,
        "status": "uploaded",
        "progress": 0,
        "message": "视频已上传",
        "video_info": {
            "filename": file.filename,
            "path": str(save_path),
        },
        "separation": None,
        "lyrics": None,
        "output": None,
    }

    # 自动获取视频信息
    asyncio.create_task(_probe_video(job_id, save_path))

    return {"job_id": job_id, "filename": file.filename}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """查询任务状态"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")
    job = dict(jobs[job_id])
    # 移除内部路径
    if job.get("video_info"):
        job["video_info"] = {k: v for k, v in job["video_info"].items() if k != "path"}
    return job


@app.post("/api/jobs/{job_id}/separate")
async def start_separation(job_id: str):
    """开始人声分离"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")

    job = jobs[job_id]
    if job["status"] not in ("uploaded", "probed", "failed", "separated"):
        return {"job_id": job_id, "status": job["status"], "message": "任务已在处理中"}

    asyncio.create_task(_run_separation(job_id))
    return {"job_id": job_id, "status": "separating"}


@app.post("/api/jobs/{job_id}/recognize")
async def recognize_lyrics(job_id: str):
    """AI 自动识别歌词 (Whisper)"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")

    job = jobs[job_id]
    if not job.get("separation") or job["separation"].get("status") != "done":
        raise HTTPException(status_code=400, detail="请先完成人声分离")

    asyncio.create_task(_run_recognition(job_id))
    return {"job_id": job_id, "status": "recognizing"}


@app.post("/api/jobs/{job_id}/lyrics")
async def submit_lyrics(job_id: str, data: LyricsInput):
    """手动提交歌词"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")

    from app.services.furigana import process_lyrics
    lines = process_lyrics(data.text, data.format)

    # LRC/ASS 格式自带时间戳，直接标记为已对齐
    has_time = any(line.get("start_time") is not None for line in lines)

    jobs[job_id]["lyrics"] = {
        "source": "manual",
        "lines": lines,
        "aligned": has_time,
    }
    jobs[job_id]["status"] = "lyrics_ready"
    jobs[job_id]["message"] = "歌词已提交" + ("，时间轴已就绪" if has_time else "，假名已标注")

    await _push_progress(job_id, jobs[job_id])
    return {"job_id": job_id, "lyrics": jobs[job_id]["lyrics"]}


@app.post("/api/jobs/{job_id}/search-lyrics")
async def search_lyrics_api(job_id: str, data: LyricsSearchQuery):
    """搜索在线歌词"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")

    from app.services.lyrics_search import search_lyrics
    try:
        results = await search_lyrics(data.keyword, data.artist)
        return {"job_id": job_id, "results": results}
    except Exception as e:
        logger.error(f"[{job_id}] 歌词搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@app.post("/api/jobs/{job_id}/fetch-lyrics")
async def fetch_lyrics_api(job_id: str, data: LyricsFetchRequest):
    """获取指定歌曲的 LRC 歌词并自动提交"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")

    from app.services.lyrics_search import fetch_lyrics
    from app.services.furigana import process_lyrics

    try:
        result = await fetch_lyrics(data.source, data.song_id)
        lrc_text = result["lrc"]

        # 解析 LRC 并标注假名
        lines = process_lyrics(lrc_text, "lrc")

        has_time = any(line.get("start_time") is not None for line in lines)

        jobs[job_id]["lyrics"] = {
            "source": f"search:{data.source}",
            "lines": lines,
            "aligned": has_time,
        }
        jobs[job_id]["status"] = "lyrics_ready"
        jobs[job_id]["message"] = "在线歌词已导入" + ("，时间轴已就绪" if has_time else "")

        await _push_progress(job_id, jobs[job_id])
        return {
            "job_id": job_id,
            "lyrics": jobs[job_id]["lyrics"],
            "lrc_preview": result.get("preview", ""),
            "translation": result.get("tlrc"),
        }
    except Exception as e:
        logger.error(f"[{job_id}] 获取歌词失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取歌词失败: {e}")


@app.put("/api/jobs/{job_id}/lyrics")
async def update_lyrics(job_id: str, data: LyricsUpdate):
    """修改歌词/假名"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not jobs[job_id].get("lyrics"):
        raise HTTPException(status_code=400, detail="请先提交歌词")

    jobs[job_id]["lyrics"]["lines"] = data.lines
    jobs[job_id]["message"] = "歌词已更新"
    await _push_progress(job_id, jobs[job_id])
    return {"job_id": job_id, "lyrics": jobs[job_id]["lyrics"]}


@app.post("/api/jobs/{job_id}/align")
async def align_lyrics(job_id: str):
    """自动对齐歌词时间轴"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")

    job = jobs[job_id]
    if not job.get("lyrics"):
        raise HTTPException(status_code=400, detail="请先提交歌词")
    if not job.get("separation") or job["separation"].get("status") != "done":
        raise HTTPException(status_code=400, detail="请先完成人声分离")

    asyncio.create_task(_run_alignment(job_id))
    return {"job_id": job_id, "status": "aligning"}


@app.post("/api/jobs/{job_id}/render")
async def render_video(job_id: str, options: RenderOptions = RenderOptions()):
    """生成字幕并合成最终 KTV 视频"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")

    job = jobs[job_id]
    if not job.get("lyrics"):
        raise HTTPException(status_code=400, detail="请先提交歌词")
    if not job["lyrics"].get("aligned"):
        raise HTTPException(status_code=400, detail="请先对齐时间轴")
    if not job.get("separation") or job["separation"].get("status") != "done":
        raise HTTPException(status_code=400, detail="请先完成人声分离，需要伴奏音轨来合成视频")

    asyncio.create_task(_run_render(job_id, options))
    return {"job_id": job_id, "status": "rendering"}


@app.get("/api/jobs/{job_id}/download")
async def download_video(job_id: str):
    """下载最终视频"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")

    job = jobs[job_id]
    if not job.get("output") or not job["output"].get("video_path"):
        raise HTTPException(status_code=400, detail="视频尚未生成")

    video_path = Path(job["output"]["video_path"])
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"ktv_{job['video_info']['filename']}"
    )


@app.get("/api/jobs/{job_id}/subtitle")
async def download_subtitle(job_id: str):
    """下载 ASS 字幕文件"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在")

    job = jobs[job_id]
    if not job.get("output") or not job["output"].get("subtitle_path"):
        raise HTTPException(status_code=400, detail="字幕尚未生成")

    sub_path = Path(job["output"]["subtitle_path"])
    if not sub_path.exists():
        raise HTTPException(status_code=404, detail="字幕文件不存在")

    return FileResponse(
        sub_path,
        media_type="text/x-ssa",
        filename=f"ktv_{Path(job['video_info']['filename']).stem}.ass"
    )


# ============ WebSocket ============

@app.websocket("/api/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket 推送进度 — 持续推送所有状态变更"""
    await websocket.accept()
    active_connections[job_id] = websocket
    last_sent = None
    try:
        while True:
            await asyncio.sleep(0.5)
            if job_id in jobs:
                current = _safe_job_data(jobs[job_id])
                # 只在状态有变化时推送（对比 status + progress + message）
                sig = (current.get("status"), current.get("progress"), current.get("message"))
                if sig != last_sent:
                    await websocket.send_json(current)
                    last_sent = sig
                # done/failed 时发最后一次然后断开
                if current.get("status") in ("done", "failed"):
                    break
            else:
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        active_connections.pop(job_id, None)


# ============ 内部工具函数 ============

def _safe_job_data(job: dict) -> dict:
    """移除内部路径信息后的安全数据"""
    data = dict(job)
    if data.get("video_info"):
        data["video_info"] = {k: v for k, v in data["video_info"].items() if k != "path"}
    if data.get("separation"):
        data["separation"] = {k: v for k, v in data["separation"].items()
                              if k not in ("vocals_path", "accompaniment_path")}
    if data.get("output"):
        data["output"] = {k: v for k, v in data["output"].items()
                          if k not in ("video_path", "subtitle_path")}
    return data


async def _push_progress(job_id: str, data: dict):
    """推送进度到 WebSocket"""
    ws = active_connections.get(job_id)
    if ws:
        try:
            await ws.send_json(_safe_job_data(data))
        except Exception:
            pass


# ============ 后台任务 ============

async def _probe_video(job_id: str, video_path: Path):
    """获取视频元信息"""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(video_path)
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()

        import json
        info = json.loads(stdout.decode())

        # 提取关键信息
        duration = float(info.get("format", {}).get("duration", 0))
        video_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "video"), None
        )

        width = int(video_stream.get("width", 0)) if video_stream else 0
        height = int(video_stream.get("height", 0)) if video_stream else 0
        fps_str = video_stream.get("r_frame_rate", "30/1") if video_stream else "30/1"
        try:
            num, den = fps_str.split("/")
            fps = round(int(num) / int(den), 2)
        except Exception:
            fps = 30.0

        jobs[job_id]["video_info"].update({
            "duration": duration,
            "resolution": f"{width}x{height}",
            "width": width,
            "height": height,
            "fps": fps,
        })
        jobs[job_id]["status"] = "probed"
        jobs[job_id]["message"] = f"视频信息: {width}x{height}, {duration:.1f}s"
        await _push_progress(job_id, jobs[job_id])

    except Exception as e:
        jobs[job_id]["message"] = f"获取视频信息失败: {e}"
        await _push_progress(job_id, jobs[job_id])


async def _run_separation(job_id: str):
    """人声分离: FFmpeg提取音频 → 自动选择引擎(Demucs/vocal-remover)分离"""
    job = jobs[job_id]
    video_path = job["video_info"]["path"]
    out_dir = OUTPUT_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs[job_id]["status"] = "separating"
    await _push_progress(job_id, {"status": "separating", "progress": 5, "message": "正在提取音频..."})

    try:
        # Step 1: FFmpeg 提取音频
        audio_path = out_dir / "extracted_audio.wav"
        cmd_extract = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            str(audio_path)
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd_extract, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError("音频提取失败")

        jobs[job_id]["progress"] = 10
        jobs[job_id]["message"] = "音频已提取，正在启动人声分离..."
        await _push_progress(job_id, jobs[job_id])

        # Step 2: 人声分离（自动选择 Demucs 或 vocal-remover）
        from app.services.separation import separate, detect_engine

        engine = detect_engine()
        logger.info(f"[{job_id}] 使用分离引擎: {engine}")

        async def _progress_cb(progress: int, message: str):
            jobs[job_id]["progress"] = progress
            jobs[job_id]["message"] = message
            await _push_progress(job_id, jobs[job_id])

        vocals_path, accomp_path = await separate(
            audio_path=audio_path,
            output_dir=out_dir,
            progress_callback=_progress_cb,
        )

        jobs[job_id]["separation"] = {
            "status": "done",
            "engine": engine,
            "vocals_path": str(vocals_path),
            "accompaniment_path": str(accomp_path),
        }
        jobs[job_id]["status"] = "separated"
        jobs[job_id]["progress"] = 95
        jobs[job_id]["message"] = f"人声分离完成（{engine}）！可以开始处理歌词"
        await _push_progress(job_id, jobs[job_id])

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["message"] = str(e)
        jobs[job_id]["progress"] = 0
        await _push_progress(job_id, jobs[job_id])


async def _run_recognition(job_id: str):
    """Whisper 自动识别歌词"""
    job = jobs[job_id]
    vocals_path = job["separation"]["vocals_path"]

    jobs[job_id]["status"] = "recognizing"
    jobs[job_id]["message"] = "正在加载 Whisper 模型..."
    jobs[job_id]["progress"] = 0
    await _push_progress(job_id, jobs[job_id])

    try:
        from app.services.recognition import recognize_japanese_lyrics
        lines = await recognize_japanese_lyrics(vocals_path, job_id, _push_progress, jobs)

        jobs[job_id]["lyrics"] = {
            "source": "ai",
            "lines": lines,
            "aligned": True,  # Whisper 识别自带时间戳
        }
        jobs[job_id]["status"] = "lyrics_ready"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "歌词识别完成！可预览和修改"
        await _push_progress(job_id, jobs[job_id])

    except Exception as e:
        jobs[job_id]["status"] = "separated"  # 回退到分离完成状态
        jobs[job_id]["message"] = f"歌词识别失败: {e}"
        await _push_progress(job_id, jobs[job_id])


async def _run_alignment(job_id: str):
    """stable-ts 歌词时间轴对齐"""
    job = jobs[job_id]
    vocals_path = job["separation"]["vocals_path"]
    lyrics_lines = job["lyrics"]["lines"]

    jobs[job_id]["status"] = "aligning"
    jobs[job_id]["message"] = "正在对齐歌词时间轴..."
    jobs[job_id]["progress"] = 0
    await _push_progress(job_id, jobs[job_id])

    try:
        from app.services.alignment import align_lyrics
        import traceback as _tb
        logger.info(f"[{job_id}] 开始对齐, vocals: {vocals_path}, lines: {len(lyrics_lines)}")
        aligned_lines = await align_lyrics(vocals_path, lyrics_lines, job_id, _push_progress, jobs)

        jobs[job_id]["lyrics"]["lines"] = aligned_lines
        jobs[job_id]["lyrics"]["aligned"] = True
        jobs[job_id]["status"] = "lyrics_ready"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "时间轴对齐完成！可以渲染视频"
        logger.info(f"[{job_id}] 对齐成功, aligned {len(aligned_lines)} lines")
        await _push_progress(job_id, jobs[job_id])

    except Exception as e:
        import traceback as _tb
        logger.error(f"[{job_id}] 对齐失败: {e}\n{_tb.format_exc()}")
        jobs[job_id]["status"] = "lyrics_ready"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["message"] = f"时间轴对齐失败: {e}"
        await _push_progress(job_id, jobs[job_id])


async def _run_render(job_id: str, options: RenderOptions):
    """生成ASS字幕 + FFmpeg合成视频"""
    job = jobs[job_id]
    out_dir = OUTPUT_DIR / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs[job_id]["status"] = "rendering"
    jobs[job_id]["message"] = "正在生成字幕..."
    jobs[job_id]["progress"] = 0
    await _push_progress(job_id, jobs[job_id])

    try:
        from app.services.subtitle import generate_ass_subtitle
        from app.services.composer import compose_video

        # Step 1: 补充缺失的逐字时间（LRC 只有行时间）
        lines = job["lyrics"]["lines"]
        for line in lines:
            if not line.get("words") and line.get("start_time") is not None and line.get("end_time") is not None:
                text = line["text"]
                start = line["start_time"]
                end = line["end_time"]
                if text and end > start:
                    char_dur = (end - start) / len(text)
                    line["words"] = [
                        {"text": c, "start": round(start + i * char_dur, 3), "end": round(start + (i+1) * char_dur, 3)}
                        for i, c in enumerate(text)
                    ]

        # Step 2: 生成 ASS 字幕
        subtitle_path = out_dir / "subtitle.ass"
        video_info = job["video_info"]
        generate_ass_subtitle(
            lines=lines,
            output_path=subtitle_path,
            video_width=video_info.get("width", 1920),
            video_height=video_info.get("height", 1080),
            style=options.style,
            font_size=options.font_size,
            furigana_size=options.furigana_size,
        )

        jobs[job_id]["progress"] = 20
        jobs[job_id]["message"] = "字幕已生成，正在合成视频..."
        await _push_progress(job_id, jobs[job_id])

        # Step 2: FFmpeg 合成
        video_path = job["video_info"]["path"]
        accomp_path = job["separation"]["accompaniment_path"]
        output_path = out_dir / "final.mp4"

        actual_output = await compose_video(
            video_path=video_path,
            audio_path=accomp_path,
            subtitle_path=str(subtitle_path),
            output_path=str(output_path),
            job_id=job_id,
            push_progress=_push_progress,
            jobs=jobs,
        )

        # compose_video 可能把路径改为 .mkv（软字幕模式）
        actual_output = jobs[job_id].pop("_output_path_override", None) or actual_output or str(output_path)
        final_name = os.path.basename(actual_output)

        # 完成
        jobs[job_id]["output"] = {
            "video_path": str(actual_output),
            "video_url": f"/outputs/{job_id}/{final_name}",
            "subtitle_path": str(subtitle_path),
            "subtitle_url": f"/outputs/{job_id}/subtitle.ass",
        }
        jobs[job_id]["status"] = "done"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["message"] = "KTV 视频制作完成！"
        await _push_progress(job_id, jobs[job_id])

    except Exception as e:
        logger.error(f"[{job_id}] 渲染失败: {e}")
        jobs[job_id]["status"] = "lyrics_ready"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["message"] = f"视频合成失败: {e}"
        await _push_progress(job_id, jobs[job_id])



