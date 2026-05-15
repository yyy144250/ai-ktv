# 🎤 AI-KTV — 日本語カラオケ動画メーカー

上传 Anisong / JPop 的 MV 视频，AI 自动去除人声，添加带振り仮名（假名注音）的 KTV 字幕，输出可投屏的卡拉OK视频。

---

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 🎵 **AI 去人声** | Demucs v4 深度学习人声分离 |
| 🤖 **AI 歌词识别** | Whisper 自动识别日语歌词 + 逐字时间戳 |
| あ **振り仮名标注** | MeCab/fugashi 自动为汉字标注假名读音 |
| ⏱️ **时间轴对齐** | stable-ts forced alignment 逐字对齐 |
| 🎬 **KTV 视频合成** | ASS 字幕（逐字变色 + 假名）烧入视频 |
| ✍️ **手动歌词输入** | 支持纯文本、LRC、ASS 格式 |
| 🎨 **多种字幕样式** | 蓝白经典 / 粉红 / 金色配色 |

---

## 🖼️ 工作流程

```
MV 视频 ──→ FFmpeg 提取音频 ──→ Demucs 去人声 ──→ Whisper 识别歌词
                                                       │
                          ┌────────────────────────────┘
                          ▼
              fugashi 假名标注 ──→ stable-ts 时间对齐 ──→ ASS 字幕生成
                                                             │
                          ┌──────────────────────────────────┘
                          ▼
              FFmpeg 合成 (视频 + 伴奏 + 硬字幕) ──→ 最终 KTV 视频 🎬
```

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- FFmpeg (编译时需支持 libass)
- NVIDIA GPU + CUDA (推荐，CPU 也可运行但较慢)

### 本地开发

```bash
# 一键启动
chmod +x start-dev.sh
./start-dev.sh

# 或者分别启动
# 后端
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py

# 前端
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### Docker 部署

```bash
docker-compose up --build
```

---

## 📂 项目结构

```
ai-ktv/
├── backend/
│   ├── app/
│   │   ├── main.py              ← FastAPI 主应用 (所有 API)
│   │   └── services/
│   │       ├── furigana.py      ← 振り仮名标注 (fugashi + MeCab)
│   │       ├── recognition.py   ← Whisper 歌词识别
│   │       ├── alignment.py     ← stable-ts 时间轴对齐
│   │       ├── subtitle.py      ← ASS 字幕生成 (KTV 样式)
│   │       └── composer.py      ← FFmpeg 视频合成
│   ├── requirements.txt
│   ├── run.py
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx              ← 主界面 (分步向导)
│   │   ├── hooks/useKTV.js      ← 核心状态管理 Hook
│   │   └── components/
│   │       ├── Header.jsx
│   │       ├── StepIndicator.jsx
│   │       ├── UploadStep.jsx   ← 视频上传
│   │       ├── ProcessingStep.jsx
│   │       ├── LyricsStep.jsx   ← 歌词输入 (手动/AI)
│   │       ├── LyricsEditStep.jsx ← 歌词编辑 + 假名修正
│   │       ├── RenderStep.jsx   ← 渲染进度
│   │       └── DoneStep.jsx     ← 完成 + 下载
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── package.json
├── docker-compose.yml
├── start-dev.sh
└── PRD.md                       ← 产品需求文档
```

---

## 🔌 API

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/upload` | 上传 MV 视频 |
| GET | `/api/jobs/{id}` | 查询任务状态 |
| POST | `/api/jobs/{id}/separate` | 开始人声分离 |
| POST | `/api/jobs/{id}/recognize` | AI 识别歌词 |
| POST | `/api/jobs/{id}/lyrics` | 手动提交歌词 |
| PUT | `/api/jobs/{id}/lyrics` | 修改歌词/假名 |
| POST | `/api/jobs/{id}/align` | 自动对齐时间轴 |
| POST | `/api/jobs/{id}/render` | 生成 KTV 视频 |
| GET | `/api/jobs/{id}/download` | 下载视频 |
| GET | `/api/jobs/{id}/subtitle` | 下载 ASS 字幕 |
| WS | `/api/ws/{id}` | WebSocket 进度推送 |

API 文档: http://localhost:8000/docs

---

## 🎨 字幕效果

```
      ざん こく    てん し
      残  酷  な 天  使 の テ ー ゼ
      ████████░░░░░░░░░░░░░░░░░░░
      ↑ 已唱(高亮色)   ↑ 未唱(白色)
```

支持配色: 蓝白经典 | 粉红 | 金色

---

## 🛠️ 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + Vite + TailwindCSS |
| 后端 | Python FastAPI + Uvicorn |
| 人声分离 | Demucs v4 (PyTorch) |
| 语音识别 | Whisper large-v3 + stable-ts |
| 假名标注 | fugashi (MeCab) + unidic-lite |
| 字幕 | ASS (Advanced SubStation Alpha) |
| 视频处理 | FFmpeg |
| 部署 | Docker Compose (GPU 支持) |

---

## 📝 License

MIT
