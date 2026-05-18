# 🎤 AI-KTV — 日本語カラオケ動画メーカー

上传 Anisong / JPop 的 MV 视频，AI 自动去除人声，添加带振り仮名（假名注音）的 KTV 字幕，输出可投屏的卡拉OK视频。

---

## ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 🎵 **AI 去人声** | Demucs v4 深度学习人声分离 |
| 🤖 **AI 歌词识别** | Whisper 自动识别日语歌词 + 逐字时间戳 |
| 🔍 **在线歌词搜索** | 从网易云等平台搜索带时间轴的 LRC 歌词 |
| あ **振り仮名标注** | MeCab/fugashi 自动为汉字标注假名读音 |
| ⏱️ **时间轴对齐** | stable-ts forced alignment 逐字对齐 |
| 🎬 **KTV 视频合成** | ASS 字幕（逐字变色 + 假名）烧入视频 |
| ✍️ **手动歌词输入** | 支持纯文本、LRC、ASS 格式 |
| 🎨 **多种字幕样式** | 蓝白经典 / 粉红 / 金色配色 |

---

## 🖼️ 工作流程

```
MV 视频 ──→ 上传 ──┬──→ 后台: Demucs 人声分离
                    │
                    └──→ 前台: 搜索在线歌词 / 手动输入 / AI 识别
                              │
                              ▼
                    fugashi 假名标注 ──→ stable-ts 时间对齐
                              │
                              ▼
                    ASS 字幕生成 (逐字变色 + 假名注音)
                              │
                              ▼
                    FFmpeg 合成 (视频 + 伴奏 + 硬字幕) ──→ KTV 视频 🎬
```

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本 | 用途 | 说明 |
|------|------|------|------|
| Python | 3.11+ | 后端运行时 | 必须 |
| Node.js | 20+ | 前端构建 | 必须 |
| FFmpeg | 最新 | 视频处理 | 必须，需支持 libass |
| NVIDIA GPU + CUDA | - | AI 模型加速 | 可选，CPU 也能跑但很慢 |

### 方式一：一键启动（推荐）

```bash
git clone https://github.com/yyy144250/ai-ktv.git
cd ai-ktv
chmod +x start-dev.sh
./start-dev.sh
```

脚本会自动创建虚拟环境、安装依赖、启动前后端。

### 方式二：手动启动

#### 1. 后端

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 安装基础依赖（轻量，几分钟搞定）
pip install -r requirements.txt

# 安装 AI 模型依赖（可选，见下方说明）
pip install demucs==4.0.1 torch==2.4.0 torchaudio==2.4.0     # 人声分离 ~2GB
pip install openai-whisper==20240930 stable-ts==2.16.0         # 语音识别 ~3GB

# 启动后端
python run.py
```

#### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

#### 3. 访问

- 前端界面: http://localhost:5173
- API 文档: http://localhost:8000/docs

### 方式三：Docker 部署到服务器（推荐生产环境）

#### 无 GPU 服务器（只需 2核4G，够用在线歌词功能）

```bash
# 在服务器上
git clone https://github.com/yyy144250/ai-ktv.git
cd ai-ktv
docker-compose up -d --build
```

访问 `http://你的服务器IP` 即可使用。

#### 有 GPU 服务器（支持 AI 功能）

```bash
# 前提：已安装 NVIDIA 驱动 + nvidia-container-toolkit
docker-compose -f docker-compose.gpu.yml up -d --build
```

#### 裸机部署（不用 Docker）

```bash
# 1. 安装系统依赖
sudo apt install -y ffmpeg python3.11 python3.11-venv nodejs npm

# 2. 后端
cd backend
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# 可选 AI 依赖: pip install torch demucs openai-whisper stable-ts
ENV=prod nohup python run.py > backend.log 2>&1 &

# 3. 前端
cd ../frontend
npm install && npm run build

# 4. 用 Nginx 托管前端 + 反代后端
sudo cp nginx.conf /etc/nginx/sites-available/ai-ktv
sudo ln -s /etc/nginx/sites-available/ai-ktv /etc/nginx/sites-enabled/
# 注意：裸机部署时需把 nginx.conf 中的 proxy_pass 改为 http://127.0.0.1:8000
sudo nginx -t && sudo systemctl reload nginx
```

---

## ⚠️ 关于大依赖（重要！）

这个项目有两类依赖：

### 基础依赖（必须安装，~50MB）

`pip install -r requirements.txt` 会安装：
- FastAPI + Uvicorn（Web 框架）
- fugashi + unidic-lite（日语假名标注）
- aiohttp（HTTP 客户端，用于歌词搜索）
- 其他轻量库

安装后即可使用：**在线歌词搜索、手动歌词输入、假名标注、字幕生成、视频合成**

### AI 模型依赖（按需安装，~5GB）

这些在 `requirements.txt` 中被注释掉了，需要手动安装：

| 包 | 大小 | 功能 | 何时需要 |
|----|------|------|----------|
| `torch` + `torchaudio` | ~2GB | PyTorch 运行时 | 使用 AI 功能时 |
| `demucs` | ~300MB (+模型 ~1GB) | 人声分离 | 需要去除MV中的人声时 |
| `openai-whisper` | ~100MB (+模型 ~3GB) | 语音识别 | 使用 AI 识别歌词时 |
| `stable-ts` | ~10MB | 时间轴对齐 | 纯文本歌词需要对齐时 |

**安装命令**：

```bash
# 有 NVIDIA GPU (推荐，快10倍以上)
pip install torch==2.4.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cu121
pip install demucs==4.0.1
pip install openai-whisper==20240930 stable-ts==2.16.0

# 仅 CPU (无GPU也能用，就是慢)
pip install torch==2.4.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cpu
pip install demucs==4.0.1
pip install openai-whisper==20240930 stable-ts==2.16.0

# macOS Apple Silicon (M1/M2/M3)
pip install torch==2.4.0 torchaudio==2.4.0
pip install demucs==4.0.1
pip install openai-whisper==20240930 stable-ts==2.16.0
```

### 💡 不安装 AI 依赖也能用！

如果你只想用「搜索在线歌词」功能（推荐方式），**不需要安装任何 AI 依赖**：

1. 上传 MV → 搜索歌词（网易云 LRC，自带时间轴）→ 生成视频

只有以下场景需要 AI 依赖：
- **人声分离**（`demucs` + `torch`）：从 MV 中提取伴奏音轨
- **AI 识别歌词**（`whisper`）：自动从音频识别歌词
- **时间轴对齐**（`stable-ts`）：将纯文本歌词与音频对齐

> ⚡ 首次运行 AI 功能时，模型会自动下载到 `~/.cache/`，Demucs 模型约 1GB，Whisper large-v3 模型约 3GB。

### FFmpeg 安装

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (使用 scoop 或手动下载)
scoop install ffmpeg
```

确保 FFmpeg 编译时包含 `libass`（用于字幕烧入），大多数发行版的 FFmpeg 默认包含。

---

## 📂 项目结构

```
ai-ktv/
├── backend/
│   ├── app/
│   │   ├── main.py              ← FastAPI 主应用 (所有 API)
│   │   └── services/
│   │       ├── furigana.py      ← 振り仮名标注 (fugashi + MeCab)
│   │       ├── lyrics_search.py ← 在线歌词搜索 (网易云 API)
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
│   │       ├── LyricsStep.jsx   ← 歌词来源 (搜索/手动/AI)
│   │       ├── LyricsEditStep.jsx ← 歌词编辑 + 假名修正
│   │       ├── ProcessingStep.jsx
│   │       ├── RenderStep.jsx   ← 渲染进度
│   │       └── DoneStep.jsx     ← 完成 + 下载
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── package.json
├── docker-compose.yml
├── start-dev.sh                 ← 一键启动脚本
├── ARCHITECTURE.md
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
| POST | `/api/jobs/{id}/search-lyrics` | 搜索在线歌词 |
| POST | `/api/jobs/{id}/fetch-lyrics` | 获取在线 LRC 并导入 |
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
| 歌词搜索 | 网易云音乐 API |
| 假名标注 | fugashi (MeCab) + unidic-lite |
| 字幕 | ASS (Advanced SubStation Alpha) |
| 视频处理 | FFmpeg |
| 部署 | Docker Compose (GPU 支持) |

---

## 🐛 常见问题

### Q: 安装 fugashi 报错？

```bash
# macOS 需要先安装 mecab
brew install mecab

# 或者直接用 unidic-lite（requirements.txt 已包含）
pip install fugashi[unidic-lite]
```

### Q: FFmpeg 不支持 libass？

```bash
# 检查是否支持
ffmpeg -filters 2>&1 | grep subtitles

# macOS 重新安装带 libass 的版本
brew install ffmpeg
```

### Q: GPU 内存不够？

Demucs 和 Whisper 各需要约 4-6GB 显存。如果显存不够：
- 可以用 CPU 模式（慢但不需要 GPU）
- 或者不安装 AI 依赖，只使用在线歌词搜索功能

### Q: Whisper 模型下载太慢？

模型会下载到 `~/.cache/whisper/`，可以手动下载后放到该目录：
- large-v3: https://openaipublic.azureedge.net/main/whisper/models/large-v3.pt

### Q: 不想安装这么多东西，能直接用吗？

可以！只安装基础依赖 + FFmpeg，然后使用「搜索在线歌词」功能：
1. `pip install -r requirements.txt`
2. 上传 MV → 搜索歌词 → 编辑假名 → 生成视频
3. 这种方式完全不需要 GPU 和 AI 模型

---

## 📝 License

MIT
