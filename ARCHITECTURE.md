# 🏗️ AI-KTV 系统架构文档

> **版本**: 2.0  
> **更新日期**: 2026-05-12  
> **定位**: Anisong / JPop 日語カラオケ動画メーカー

---

## 1. 系统总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户浏览器                                      │
│                     http://localhost:5173                                │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  React + Vite + TailwindCSS                                      │   │
│  │  分步向导 UI (上传→分离→歌词→标注→对齐→合成→完成)                    │   │
│  └────────────────────────────┬─────────────────────────────────────┘   │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │ HTTP REST + WebSocket
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FastAPI 后端 (Python 3.11+)                         │
│                     http://localhost:8000                                │
│                                                                         │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐  │
│  │  Upload   │ │ Separate  │ │  Lyrics   │ │  Align   │ │  Render  │  │
│  │  Service  │ │  Service  │ │  Service  │ │  Service │ │  Service │  │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └────┬─────┘ └────┬─────┘  │
│        │              │              │             │             │       │
│        ▼              ▼              ▼             ▼             ▼       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  FFmpeg  │  │  Demucs  │  │ Whisper  │  │stable-ts │  │  FFmpeg  │ │
│  │ (probe)  │  │ (vocals) │  │  (ASR)   │  │ (align)  │  │ (encode) │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│        │              │              │             │             │       │
│        ▼              ▼              ▼             ▼             ▼       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                        文件系统                                    │  │
│  │   uploads/          outputs/{job_id}/                             │  │
│  │   ├── {job}.mp4     ├── extracted_audio.wav                      │  │
│  │                     ├── demucs/htdemucs/.../vocals.wav            │  │
│  │                     ├── demucs/htdemucs/.../no_vocals.wav         │  │
│  │                     ├── subtitle.ass                              │  │
│  │                     └── final.mp4                                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 技术栈

### 2.1 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.3 | UI 框架 |
| Vite | 5.4 | 构建工具 + 开发服务器 |
| TailwindCSS | 3.4 | 原子化 CSS |
| Lucide React | 0.447 | 图标库 |

### 2.2 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 运行时 |
| FastAPI | 0.115 | Web 框架 |
| Uvicorn | 0.30 | ASGI 服务器 |
| WebSocket | - | 实时进度推送 |

### 2.3 AI / ML 模型

| 技术 | 用途 | 大小 |
|------|------|------|
| Demucs v4 (htdemucs) | 人声/伴奏分离 | ~2GB (含 PyTorch) |
| Whisper large-v3 | 日语歌词语音识别 | ~3GB |
| stable-ts | 逐字时间戳对齐 (forced alignment) | 基于 Whisper |

### 2.4 日语处理

| 技术 | 用途 |
|------|------|
| fugashi (MeCab) | 日语形态素分析/分词 |
| unidic-lite | MeCab 词典 (含读音信息) |
| jaconv | 片假名 ↔ 平假名转换 |

### 2.5 多媒体处理

| 技术 | 用途 |
|------|------|
| FFmpeg | 音频提取、视频编码、字幕烧入 |
| ASS (Advanced SubStation Alpha) | 字幕格式 (支持特效) |

### 2.6 部署

| 技术 | 用途 |
|------|------|
| Docker Compose | 容器编排 |
| Nginx | 前端静态文件 + 反向代理 |
| NVIDIA Container Toolkit | GPU 加速 (可选) |

---

## 3. 目录结构

```
ai-ktv/
├── backend/                          # Python 后端
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI 主应用 (路由 + 任务调度)
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── furigana.py           # 公开接口
│   │       ├── _furigana_impl.py     # 振り仮名标注实现 (MeCab)
│   │       ├── recognition.py        # Whisper 歌词识别
│   │       ├── alignment.py          # stable-ts 时间轴对齐
│   │       ├── subtitle.py           # ASS 字幕生成
│   │       └── composer.py           # FFmpeg 视频合成
│   ├── uploads/                      # 用户上传的视频
│   ├── outputs/                      # 处理结果输出
│   │   └── {job_id}/
│   │       ├── extracted_audio.wav
│   │       ├── demucs/...
│   │       ├── subtitle.ass
│   │       └── final.mp4
│   ├── requirements.txt
│   ├── run.py                        # 开发入口
│   └── Dockerfile
├── frontend/                         # React 前端
│   ├── src/
│   │   ├── App.jsx                   # 主应用 (分步向导)
│   │   ├── main.jsx                  # 入口
│   │   ├── index.css                 # TailwindCSS 全局样式
│   │   ├── hooks/
│   │   │   └── useKTV.js            # 核心状态管理 Hook
│   │   └── components/
│   │       ├── Header.jsx            # 页面头部
│   │       ├── StepIndicator.jsx     # 步骤指示器
│   │       ├── UploadStep.jsx        # Step 1: 视频上传
│   │       ├── ProcessingStep.jsx    # 通用处理中 UI
│   │       ├── LyricsStep.jsx        # Step 2: 歌词来源选择
│   │       ├── LyricsEditStep.jsx    # Step 3: 歌词编辑+假名修正
│   │       ├── RenderStep.jsx        # Step 4: 视频渲染进度
│   │       └── DoneStep.jsx          # Step 5: 完成+下载
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── nginx.conf                    # 生产环境 Nginx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml                # 容器编排
├── start-dev.sh                      # 本地开发一键启动
├── PRD.md                            # 产品需求文档
├── ARCHITECTURE.md                   # 📍 本文件
└── README.md                         # 项目说明
```

---

## 4. 数据流 & 处理管道

### 4.1 完整处理流程

```
用户上传 MV (mp4/mkv)
        │
        ▼
┌─ Step 1: 视频预处理 ─────────────────────────────────────────────┐
│  FFmpeg: 提取音频 (WAV 44.1kHz 16bit stereo)                     │
│  FFprobe: 获取视频元信息 (分辨率、时长、帧率)                       │
└──────────────────────────────────┬────────────────────────────────┘
                                   ▼
┌─ Step 2: 人声分离 ───────────────────────────────────────────────┐
│  Demucs (htdemucs, --two-stems vocals)                           │
│  输入: extracted_audio.wav                                        │
│  输出: vocals.wav (人声) + no_vocals.wav (伴奏)                    │
│  耗时: 约 1-3 分钟 (GPU) / 5-15 分钟 (CPU)                        │
└──────────────────────────────────┬────────────────────────────────┘
                                   ▼
┌─ Step 3: 歌词获取 (二选一) ──────────────────────────────────────┐
│                                                                   │
│  [A] AI 自动识别                    [B] 手动输入/粘贴              │
│  ├── Whisper (large-v3, lang=ja)    ├── 纯文本 (每行一句)         │
│  ├── stable-ts (word timestamps)    ├── LRC 格式 (带时间轴)       │
│  └── 输出: 逐字时间戳 + 文本         └── ASS 格式                  │
│                                                                   │
└──────────────────────────────────┬────────────────────────────────┘
                                   ▼
┌─ Step 4: 振り仮名标注 ──────────────────────────────────────────┐
│  fugashi (MeCab) + unidic-lite 词典                              │
│  输入: 歌词文本                                                   │
│  处理: 形态素分析 → 提取读音 → 片假名转平假名                       │
│  输出: [{char: "夜", reading: "よる"}, {char: "に", reading: ""}]  │
│  用户可手动修正特殊读法 (当て字)                                    │
└──────────────────────────────────┬────────────────────────────────┘
                                   ▼
┌─ Step 5: 时间轴对齐 ────────────────────────────────────────────┐
│  stable-ts model.align()                                         │
│  输入: 歌词文本 + 人声音频 (vocals.wav)                            │
│  方法: Forced Alignment (强制对齐)                                │
│  输出: 每个字/词的精确 start/end 时间戳                             │
│  (如果 AI 识别已包含时间戳则跳过此步)                                │
└──────────────────────────────────┬────────────────────────────────┘
                                   ▼
┌─ Step 6: 字幕生成 ──────────────────────────────────────────────┐
│  自研 ASS 生成器                                                  │
│  ├── Main 样式: 主歌词 + \kf 逐字变色                             │
│  ├── Furigana 样式: 小号假名行 (对齐在主字幕上方)                   │
│  ├── 配色方案: 蓝白 / 粉红 / 金色                                 │
│  └── 输出: subtitle.ass                                          │
└──────────────────────────────────┬────────────────────────────────┘
                                   ▼
┌─ Step 7: 视频合成 ──────────────────────────────────────────────┐
│  FFmpeg 命令:                                                    │
│  ffmpeg -i 原视频 -i no_vocals.wav                               │
│         -map 0:v -map 1:a                                        │
│         -vf "ass=subtitle.ass"                                   │
│         -c:v libx264 -crf 23 -c:a aac -b:a 192k                 │
│         final.mp4                                                │
│                                                                   │
│  效果: 原画面 + 伴奏音轨 + 硬字幕(含假名+逐字变色)                  │
│  耗时: 约等于视频时长的 1-3 倍                                     │
└──────────────────────────────────┬────────────────────────────────┘
                                   ▼
                          最终 KTV 视频 (final.mp4)
                          + ASS 字幕文件 (subtitle.ass)
```

### 4.2 数据状态机

```
                    upload
        ┌───────── uploaded ─────────┐
        │              │             │
        │         ffprobe            │
        │              ▼             │
        │           probed           │
        │              │             │
        │       POST /separate       │
        │              ▼             │
        │         separating ────→ failed
        │              │             ↑
        │              ▼             │
        │         separated          │
        │           │    │           │
        │    manual │    │ AI        │
        │           ▼    ▼           │
        │     lyrics_ready           │
        │        │      │            │
        │  align │      │ render     │
        │        ▼      │            │
        │     aligning  │            │
        │        │      │            │
        │        ▼      ▼            │
        │      rendering ────────────┘
        │           │
        │           ▼
        └──────── done
```

---

## 5. API 设计

### 5.1 REST API

| Method | Path | 功能 | 请求体 | 响应 |
|--------|------|------|--------|------|
| GET | `/api/health` | 健康检查 | - | `{status, version}` |
| POST | `/api/upload` | 上传视频 | `multipart/form-data` | `{job_id, filename}` |
| GET | `/api/jobs/{id}` | 查询状态 | - | Job 对象 |
| POST | `/api/jobs/{id}/separate` | 开始分离 | - | `{job_id, status}` |
| POST | `/api/jobs/{id}/recognize` | AI 识别歌词 | - | `{job_id, status}` |
| POST | `/api/jobs/{id}/lyrics` | 提交歌词 | `{text, format}` | `{job_id, lyrics}` |
| PUT | `/api/jobs/{id}/lyrics` | 修改歌词 | `{lines}` | `{job_id, lyrics}` |
| POST | `/api/jobs/{id}/align` | 对齐时间轴 | - | `{job_id, status}` |
| POST | `/api/jobs/{id}/render` | 渲染视频 | `{style, font_size, ...}` | `{job_id, status}` |
| GET | `/api/jobs/{id}/download` | 下载视频 | - | `video/mp4` |
| GET | `/api/jobs/{id}/subtitle` | 下载字幕 | - | `text/x-ssa` |

### 5.2 WebSocket

```
WS /api/ws/{job_id}
```

服务端推送 Job 状态变更：
```json
{
  "job_id": "uuid",
  "status": "separating",
  "progress": 45,
  "message": "人声分离中 45%",
  "video_info": {...},
  "lyrics": {...},
  "output": {...}
}
```

### 5.3 Job 数据模型

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "lyrics_ready",
  "progress": 100,
  "message": "歌词已提交，假名已标注",
  "video_info": {
    "filename": "yoasobi_idol.mp4",
    "duration": 213.5,
    "resolution": "1920x1080",
    "width": 1920,
    "height": 1080,
    "fps": 30.0
  },
  "separation": {
    "status": "done"
  },
  "lyrics": {
    "source": "manual",
    "aligned": true,
    "lines": [
      {
        "text": "夜に駆ける",
        "ruby": [
          {"char": "夜", "reading": "よる"},
          {"char": "に", "reading": ""},
          {"char": "駆", "reading": "か"},
          {"char": "け", "reading": ""},
          {"char": "る", "reading": ""}
        ],
        "start_time": 12.5,
        "end_time": 15.2,
        "words": [
          {"text": "夜", "start": 12.5, "end": 13.0},
          {"text": "に", "start": 13.0, "end": 13.2},
          {"text": "駆け", "start": 13.2, "end": 14.5},
          {"text": "る", "start": 14.5, "end": 15.2}
        ]
      }
    ]
  },
  "output": {
    "video_url": "/outputs/{job_id}/final.mp4",
    "subtitle_url": "/outputs/{job_id}/subtitle.ass"
  }
}
```

---

## 6. 前端组件架构

```
App.jsx
├── Header                          # Logo + 标题
├── StepIndicator                   # 步骤进度条 (7步)
│
├── UploadStep                      # 拖拽上传视频
│   └── 文件选择 + 格式验证
│
├── ProcessingStep (复用)            # 通用处理中 UI
│   └── 进度条 + 消息 + 加载动画
│
├── LyricsStep                      # 歌词来源选择
│   ├── AI 识别按钮 → 调用 /recognize
│   └── 手动输入表单
│       ├── 格式选择 (plain/lrc/ass)
│       └── 文本输入框
│
├── LyricsEditStep                  # 歌词预览 & 编辑
│   ├── Ruby 注音展示 (可点击修改)
│   ├── 时间轴信息
│   ├── 样式选择器
│   ├── [对齐时间轴] 按钮
│   └── [生成视频] 按钮
│
├── RenderStep                      # 渲染进度
│   └── 进度条 (字幕生成 → 视频编码)
│
└── DoneStep                        # 完成页面
    ├── 视频播放器预览
    ├── 下载视频 / 下载字幕
    └── [重新制作] 按钮
```

### 状态管理: `useKTV` Hook

```javascript
// 暴露的状态
jobId, job, step, progress, message, error

// 暴露的操作
uploadVideo(file)      // 上传并自动开始分离
recognizeLyrics()      // AI 识别歌词
submitLyrics(text, fmt) // 手动提交歌词
updateLyrics(lines)    // 修改歌词/假名
alignLyrics()          // 对齐时间轴
renderVideo(options)   // 生成视频
reset()                // 重置所有状态
```

---

## 7. ASS 字幕技术方案

### 7.1 两行模拟 Ruby Text

ASS 没有原生 ruby 支持，使用 **双层字幕** 实现：

```
[V4+ Styles]
Style: Main,Noto Sans JP,48,...    ← 主歌词 (大字, 底部)
Style: Furigana,Noto Sans JP,24,... ← 假名 (小字, 主歌词上方)

[Events]
Dialogue: 0,0:00:12.50,0:00:15.20,Furigana,,,,, よる　　か
Dialogue: 1,0:00:12.50,0:00:15.20,Main,,,,,{\kf50}夜{\kf20}に{\kf130}駆け{\kf70}る
```

### 7.2 KTV 逐字变色

使用 `\kf` (fill 模式) 标签：
- `\kf50` = 该字持续 50 centiseconds (0.5秒)
- 播放时该字从 SecondaryColour 渐变到 PrimaryColour

### 7.3 配色方案 (BGR 格式)

| 方案 | 已唱色 | 未唱色 | 假名色 |
|------|--------|--------|--------|
| classic_blue | `&H00FFBF00&` (亮蓝) | `&H00FFFFFF&` (白) | `&H00AAAAAA&` (灰) |
| pink | `&H00B469FF&` (粉红) | `&H00FFFFFF&` | `&H00CCAAFF&` |
| gold | `&H0000D7FF&` (金) | `&H00FFFFFF&` | `&H008BECFF&` |

---

## 8. 部署架构

### 8.1 本地开发

```
[浏览器] ←──→ [Vite Dev Server :5173] ──proxy──→ [FastAPI :8000]
                                                       │
                                                  [FFmpeg / Demucs / Whisper]
                                                       │
                                                  [文件系统: uploads/ outputs/]
```

### 8.2 Docker 生产部署

```
[浏览器] ←──→ [Nginx :5173] ──proxy──→ [FastAPI :8000]
                  │                          │
            [静态文件]                   [GPU Container]
                                             │
                                    [Volume: uploads/ outputs/ cache/]
```

### 8.3 docker-compose 服务

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| backend | python:3.11-slim + deps | 8000 | FastAPI + AI 模型 |
| frontend | nginx:alpine | 5173→80 | 静态文件 + 反代 |

---

## 9. 性能参考

### 4 分钟 MV 处理时间估计

| 步骤 | GPU (RTX 3060+) | CPU (M1 Mac) |
|------|:---:|:---:|
| 音频提取 | 2-3s | 2-3s |
| Demucs 人声分离 | 1-2 min | 5-10 min |
| Whisper 歌词识别 | 30s-1 min | 3-5 min |
| 时间轴对齐 | 20-40s | 2-3 min |
| ASS 字幕生成 | < 1s | < 1s |
| FFmpeg 视频合成 | 2-4 min | 4-8 min |
| **总计** | **~5-8 min** | **~15-30 min** |

---

## 10. 扩展性考虑

### 10.1 当前限制
- 任务状态存储在内存 (`dict`)，重启丢失
- 单进程，同时只能处理有限任务
- 无用户认证系统

### 10.2 未来扩展方向
- **持久化**: 引入 SQLite / Redis 存储任务状态
- **队列**: Celery / RQ 处理异步重任务
- **多用户**: 添加认证 + 任务隔离
- **歌词库**: 接入在线 LRC 歌词数据源
- **更多语言**: 中文(拼音)、韩文(罗马字)
- **字幕特效**: 更多 KTV 动画效果 (弹跳、发光、渐变)
- **移动端**: 响应式 UI 适配

---

## 11. 依赖关系图

```
前端 (Node.js)                      后端 (Python 3.11+)
─────────────                       ───────────────────
react                               fastapi
react-dom                           uvicorn
vite                                aiofiles
tailwindcss                         websockets
lucide-react                        pydantic
postcss                             │
autoprefixer                        ├── fugashi (MeCab)
                                    │   └── unidic-lite
                                    ├── jaconv
                                    ├── ffmpeg-python
                                    │
                                    ├── demucs ←─── torch, torchaudio
                                    ├── openai-whisper ←─── torch
                                    └── stable-ts ←─── whisper

系统依赖
────────
FFmpeg (含 libass 支持)
MeCab (通过 fugashi 自动管理)
CUDA (可选, GPU 加速)
```

---

*本文档描述 AI-KTV v2.0 的系统架构。随项目演进持续更新。*
