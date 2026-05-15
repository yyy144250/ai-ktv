# 🎤 AI-KTV 视频制作工具 — 产品需求文档 (PRD)

> **目标**: 制作 Anisong / JPop 可投屏 KTV 视频，支持上传 MV → 去人声 → 添加日语歌词字幕（含振り仮名标注） → 输出 KTV 视频

---

## 1. 产品概述

### 1.1 定位
一个面向 Anisong / JPop 爱好者的 **KTV 视频制作工具**，核心场景是将已有的 MV 视频转换为可在 KTV 投屏播放的卡拉 OK 视频。

### 1.2 核心用户场景
1. 用户拿到一首喜欢的日语歌曲 MV（如 LoveLive!、YOASOBI 等）
2. 上传 MV 视频到本工具
3. 工具自动去除人声，保留伴奏和视频画面
4. 用户输入/粘贴歌词（或使用 AI 自动识别歌词）
5. 工具自动为汉字标注假名（振り仮名）
6. 工具自动对齐歌词时间轴（或用户手动调整）
7. 输出带有 KTV 风格字幕的最终视频，可直接投屏播放

### 1.3 与竞品/参考项目的差异

| 参考项目 | 做了什么 | 我们的补充 |
|---------|---------|-----------|
| [AI_karaoke_subtitles](https://github.com/WatanabeChika/AI_karaoke_subtitles) | Whisper 逐字对齐 + 自动注音 + 卡拉OK 样式 ASS | ✅ 核心参考，加上视频去人声和 Web UI |
| [FuriganaSubtitles](https://github.com/lachlanchen/FuriganaSubtitles) | Python + OpenCV 烧录振り仮名字幕到视频 | ✅ 参考字幕渲染方案 |
| [Aegisub Furigana Karaoke](https://aegisub.org/docs/latest/furigana_karaoke/) | ASS 字幕中的振り仮名 + 卡拉OK 模板 | ✅ 参考 ASS 字幕格式 |
| [Karaoke Mugen](https://docs.karaokes.moe/) | 多语言卡拉 OK 社区 + 高级模板 | ✅ 参考字幕效果 |
| Demucs / Spleeter | 音频人声分离 | ✅ 已有基础，扩展到视频 |
| Whisper / stable-ts | 语音识别 + 逐字时间戳 | ✅ 用于自动歌词识别和对齐 |

---

## 2. 功能需求

### 2.1 核心流程 (Pipeline)

```
┌─────────────────────────────────────────────────────────────────┐
│                      用户上传 MV 视频                              │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: 视频预处理                                               │
│  - FFmpeg 提取音频轨                                              │
│  - 获取视频元信息 (分辨率、帧率、时长)                                │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: 人声分离 (Demucs)                                        │
│  - 输入: 提取的音频                                                │
│  - 输出: 伴奏音轨 (no_vocals) + 人声音轨 (vocals)                   │
│  - 实时推送进度                                                    │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: 歌词获取 (二选一 / 组合)                                   │
│  ┌─────────────────┐  ┌──────────────────────────────────┐      │
│  │ A. 手动输入/粘贴  │  │ B. AI 自动识别 (Whisper)           │      │
│  │ - 纯文本歌词     │  │ - 从人声音轨识别日语歌词             │      │
│  │ - LRC 带时间轴   │  │ - 输出逐字/逐句时间戳               │      │
│  │ - ASS 字幕文件   │  │ - 用户可修正识别结果                │      │
│  └─────────────────┘  └──────────────────────────────────┘      │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: 振り仮名标注                                              │
│  - MeCab / fugashi 对歌词进行形态素分析                              │
│  - 自动为汉字（漢字）标注假名读音                                     │
│  - 用户可手动修正（特殊读法、歌词独特假名）                             │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 5: 歌词时间轴对齐                                            │
│  ┌──────────────────────────────┐  ┌──────────────────────┐     │
│  │ A. 自动对齐 (stable-ts/Whisper) │  │ B. 手动调整时间轴    │     │
│  │ - forced alignment             │  │ - 拖拽时间轴编辑器   │     │
│  │ - 逐字级别时间戳                 │  │ - 试听微调          │     │
│  └──────────────────────────────┘  └──────────────────────┘     │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 6: 字幕生成 & 视频合成                                       │
│  - 生成 ASS 字幕文件 (含振り仮名 + KTV 逐字变色效果)                  │
│  - FFmpeg 合并: 原视频画面 + 伴奏音轨 + ASS 字幕                     │
│  - 输出最终 KTV 视频 (硬字幕烧入)                                    │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 7: 预览 & 下载                                              │
│  - 在线预览最终视频                                                 │
│  - 下载 KTV 视频文件                                               │
│  - (可选) 下载 ASS 字幕文件                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

### 2.2 功能模块详细说明

#### 模块 A: 视频上传与预处理

| 项目 | 说明 |
|------|------|
| 支持格式 | mp4, mkv, avi, webm, mov |
| 文件大小限制 | 建议 500MB 以内 (可配置) |
| 预处理 | FFmpeg 提取音频 (wav/flac)，获取视频元信息 |
| 进度反馈 | WebSocket 实时推送 |

#### 模块 B: 人声分离

| 项目 | 说明 |
|------|------|
| 引擎 | Demucs v4 (htdemucs) |
| 模式 | `--two-stems vocals` (人声 vs 伴奏) |
| 输入 | 从视频提取的音频 |
| 输出 | `vocals.wav` (用于歌词识别) + `no_vocals.wav` (最终伴奏) |
| 进度 | 实时推送百分比 |

#### 模块 C: 歌词输入

**方式 1 — 手动输入/粘贴:**
- 纯文本歌词（无时间轴，后续需对齐）
- LRC 格式（带行级时间轴）
- ASS/SRT 格式（带时间轴的字幕文件）

**方式 2 — AI 自动识别:**
- 使用 Whisper (large-v3) 对分离的人声进行日语语音识别
- 使用 stable-ts 获取逐字级别时间戳
- 识别结果可编辑修正

#### 模块 D: 振り仮名（假名注音）

| 项目 | 说明 |
|------|------|
| 引擎 | fugashi (MeCab wrapper) + unidic 词典 |
| 功能 | 自动识别汉字，标注对应假名读音 |
| 特殊处理 | 歌词中非标准读法支持手动覆盖 |
| 输出格式 | 每个字/词带 ruby 注音信息 |

**示例：**
```
输入: 夜に駆ける
输出: 夜(よる)に駆(か)ける

输入: 残酷な天使のテーゼ
输出: 残酷(ざんこく)な天使(てんし)のテーゼ
```

#### 模块 E: 时间轴对齐

**自动对齐:**
- 使用 stable-ts / whisper-timestamped 进行 forced alignment
- 输入: 歌词文本 + 人声音频
- 输出: 逐字/逐音节时间戳

**手动调整 (V2):**
- 波形 + 歌词时间轴编辑器
- 拖拽调整每行/每字的起止时间
- 试听预览

#### 模块 F: 字幕生成

| 项目 | 说明 |
|------|------|
| 格式 | ASS (Advanced SubStation Alpha) |
| 效果 | KTV 式逐字变色/高亮 |
| 假名显示 | ASS `\fsp` + 多行布局，主文字上方小号假名 |
| 位置 | 视频底部居中 (可配置) |
| 样式 | 可选配色方案 (经典蓝白、粉白、自定义) |

**字幕样式示例：**
```
  よる    か
  夜 に 駆 け る        ← 主字幕 (大字)
  ~~~已唱过(高亮色)     ← KTV 逐字变色效果
```

#### 模块 G: 视频合成与输出

| 项目 | 说明 |
|------|------|
| 合成方式 | FFmpeg: 原视频画面 + 伴奏音轨 + 硬字幕烧入 |
| 命令本质 | `ffmpeg -i video -i no_vocals.wav -vf "ass=subtitle.ass" output.mp4` |
| 输出格式 | mp4 (H.264 + AAC)，兼容投屏设备 |
| 分辨率 | 保持原视频分辨率 |
| 进度 | 实时推送编码进度 |

---

### 2.3 前端页面设计

#### 页面 1: 首页 / 上传
- 拖拽或选择上传 MV 视频
- 显示支持的格式提示
- 上传进度条

#### 页面 2: 处理中心 (分步向导)
- **Step 1**: 人声分离进度
- **Step 2**: 歌词输入（手动粘贴 / AI 识别 二选一）
- **Step 3**: 歌词编辑 & 假名标注预览（可修正）
- **Step 4**: 时间轴对齐（自动 / 手动微调）
- **Step 5**: 字幕样式选择
- **Step 6**: 合成输出进度

#### 页面 3: 预览 & 下载
- 在线视频播放器预览最终效果
- 下载按钮（最终视频 / ASS 字幕文件）
- "重新制作" 按钮

---

## 3. 技术架构

### 3.1 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| **前端** | React + Vite + TailwindCSS | Web UI |
| **后端** | Python FastAPI | API 服务 |
| **人声分离** | Demucs v4 (PyTorch) | 去人声 |
| **语音识别** | Whisper large-v3 + stable-ts | 日语歌词自动识别 + 逐字对齐 |
| **假名标注** | fugashi + unidic | 汉字 → 假名 |
| **字幕生成** | 自研 ASS 生成器 | KTV 样式 + 振り仮名 |
| **视频处理** | FFmpeg | 提取音频、合并音视频、烧入字幕 |
| **实时通信** | WebSocket | 进度推送 |
| **部署** | Docker Compose | 一键部署 |

### 3.2 后端 API 设计

```
POST   /api/upload              上传 MV 视频，返回 job_id
GET    /api/jobs/{job_id}       查询任务状态
WS     /api/ws/{job_id}        WebSocket 实时进度

POST   /api/jobs/{job_id}/separate       开始人声分离
POST   /api/jobs/{job_id}/recognize      AI 识别歌词
POST   /api/jobs/{job_id}/lyrics         手动提交歌词
PUT    /api/jobs/{job_id}/lyrics         修改歌词/假名
POST   /api/jobs/{job_id}/align          自动对齐时间轴
POST   /api/jobs/{job_id}/render         生成字幕 + 合成视频

GET    /api/jobs/{job_id}/preview        获取预览视频 URL
GET    /api/jobs/{job_id}/download       下载最终视频
GET    /api/jobs/{job_id}/subtitle       下载 ASS 字幕文件
```

### 3.3 数据模型

```python
# Job 任务对象
{
    "job_id": "uuid",
    "status": "uploaded | separating | separated | aligning | rendering | done | failed",
    "video_info": {
        "filename": "song.mp4",
        "duration": 240.5,
        "resolution": "1920x1080",
        "fps": 30
    },
    "separation": {
        "status": "done",
        "vocals_path": "...",
        "accompaniment_path": "..."
    },
    "lyrics": {
        "source": "manual | ai",
        "lines": [
            {
                "text": "夜に駆ける",
                "ruby": [
                    {"char": "夜", "reading": "よる"},
                    {"char": "駆", "reading": "か"}
                ],
                "start_time": 12.5,
                "end_time": 15.2,
                "words": [
                    {"text": "夜", "start": 12.5, "end": 13.0},
                    {"text": "に", "start": 13.0, "end": 13.2},
                    {"text": "駆", "start": 13.2, "end": 13.8},
                    {"text": "け", "start": 13.8, "end": 14.2},
                    {"text": "る", "start": 14.2, "end": 15.2}
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

### 3.4 依赖清单

**Python (后端):**
```
fastapi
uvicorn[standard]
python-multipart
aiofiles
websockets

# AI / ML
demucs>=4.0
torch>=2.0
torchaudio
openai-whisper  (或 faster-whisper)
stable-ts

# 日语处理
fugashi
unidic-lite  (或 unidic)
jaconv       (假名转换工具)

# 视频处理
ffmpeg-python  (FFmpeg Python 封装)
```

**系统依赖:**
```
ffmpeg (需编译 libass 支持)
mecab (通过 fugashi 自动安装)
```

**前端:**
```
react
react-dom
vite
tailwindcss
lucide-react     (图标)
```

---

## 4. 分阶段实施计划

### Phase 1: MVP 核心管道 (1-2 周)
> 目标: 完整走通「上传视频 → 去人声 → 手动粘贴歌词 → 自动假名标注 → 自动对齐 → 生成 KTV 视频」

- [x] 项目框架搭建（基于现有项目改造）
- [ ] 视频上传 + FFmpeg 音频提取
- [ ] Demucs 人声分离（复用现有逻辑，改为视频输入）
- [ ] 歌词手动输入接口
- [ ] fugashi 假名自动标注
- [ ] stable-ts 歌词时间轴自动对齐
- [ ] ASS 字幕生成（含假名 + KTV 变色效果）
- [ ] FFmpeg 视频合成（画面 + 伴奏 + 硬字幕）
- [ ] 基础前端 UI（分步向导）

### Phase 2: AI 增强 (1 周)
> 目标: 增加 AI 自动歌词识别能力

- [ ] Whisper 日语歌词自动识别
- [ ] 识别结果编辑界面
- [ ] 假名修正界面（支持特殊读法覆盖）
- [ ] 多种字幕样式模板

### Phase 3: 体验优化 (1 周)
> 目标: 打磨用户体验

- [ ] 时间轴手动微调编辑器
- [ ] 视频实时预览（局部片段）
- [ ] 字幕样式自定义（颜色、字体、位置）
- [ ] 批量处理
- [ ] 更好的错误处理和进度提示

---

## 5. 字幕样式规格

### 5.1 KTV 逐字变色 + 振り仮名

显示效果示意（底部居中）:

```
      ざん こく    てん し
      残  酷  な 天  使 の テ ー ゼ
      ████████░░░░░░░░░░░░░░░░░░░
      ↑ 已唱部分(亮色)   ↑ 未唱部分(暗色)
```

### 5.2 ASS 字幕技术实现

使用 ASS 的 `\k` (逐字计时) + 多行模拟 ruby text：
- 主字幕行: 大号字体，KTV `\k` 逐字着色
- 假名行: 小号字体，位于对应汉字正上方
- 使用 `\an8` (顶部对齐) 或 `\pos` 精确定位

### 5.3 配色方案

| 方案 | 已唱色 | 未唱色 | 假名色 | 背景 |
|------|--------|--------|--------|------|
| 经典蓝白 | `#00BFFF` | `#FFFFFF` | `#AAAAAA` | 半透明黑 |
| 粉白 | `#FF69B4` | `#FFFFFF` | `#FFAACC` | 半透明黑 |
| 金色 | `#FFD700` | `#FFFFFF` | `#FFEC8B` | 半透明黑 |

---

## 6. 关键技术难点与方案

### 6.1 日语歌词逐字时间戳对齐

**难点**: Whisper 默认只给出句级时间戳，需要字级

**方案**: 
- 使用 `stable-ts` 的 `align()` 方法进行 forced alignment
- 输入已知歌词文本 + 人声音频，获得逐字时间戳
- 对于合并假名的情况（如「駆ける」→ か-け-る），需要按音节拆分时间

### 6.2 振り仮名的 ASS 字幕渲染

**难点**: ASS 字幕没有原生 ruby text 支持

**方案** (参考 Aegisub Furigana 和 FuriganaSubtitles):
- 方案 A: 使用两行字幕模拟（上行小字假名 + 下行主文字），通过 `\pos` 精确定位
- 方案 B: 使用 FFmpeg 的 drawtext filter 直接绘制（更灵活但更复杂）
- **推荐方案 A**: 兼容性好，效果成熟，参考 Aegisub 社区大量实践

### 6.3 歌词中的特殊读法

**难点**: Anisong 歌词经常有非标准读法（当て字），如：
- 「運命」读作「さだめ」而非「うんめい」
- 「世界」读作「せかい」但歌词注音为「ここ」

**方案**:
- 默认使用 MeCab 标准标注
- 提供编辑界面，用户可逐字修正假名
- 未来可建立 Anisong 常见特殊读法词典

---

## 7. 非功能需求

| 项目 | 要求 |
|------|------|
| 视频处理时长 | 4 分钟 MV ≤ 10 分钟总处理时间 (有 GPU) |
| 最大文件 | 500MB |
| 输出质量 | 与原视频相同分辨率 |
| 浏览器兼容 | Chrome / Edge / Safari 最新版 |
| 部署方式 | Docker Compose 一键部署 |
| GPU 要求 | NVIDIA GPU (CUDA) 推荐，CPU 模式可用但慢 |

---

## 8. 后续扩展 (Future)

- [ ] 支持导入网易云/Spotify 等平台的 LRC 歌词
- [ ] 支持罗马字 (romaji) 标注模式（适合非日语母语者）
- [ ] 支持中文歌词 + 拼音标注
- [ ] 歌词翻译对照显示（日语 + 中文翻译双行）
- [ ] 更多 KTV 字幕特效（渐变、发光、弹跳等）
- [ ] 在线歌词库接入（自动搜索匹配歌词）
- [ ] 移动端适配

---

## 9. 参考项目 & 资源

| 项目 | 链接 | 参考价值 |
|------|------|---------|
| AI_karaoke_subtitles | https://github.com/WatanabeChika/AI_karaoke_subtitles | ⭐ 最核心参考：Whisper 逐字对齐 + 自动注音 + 卡拉OK ASS |
| FuriganaSubtitles | https://github.com/lachlanchen/FuriganaSubtitles | Python 烧录振り仮名到视频 (OpenCV) |
| Aegisub Furigana Karaoke | https://aegisub.org/docs/latest/furigana_karaoke/ | ASS 振り仮名语法规范 |
| Karaoke Mugen | https://docs.karaokes.moe/ | 卡拉OK 社区字幕效果参考 |
| stable-ts | https://github.com/jianfch/stable-ts | Whisper 增强版，逐字时间戳 |
| fugashi | https://github.com/polm/fugashi | MeCab Python 封装，日语形态素分析 |
| Demucs | https://github.com/facebookresearch/demucs | 音频人声分离 |
| DigitalOcean Karaoke Tutorial | https://www.digitalocean.com/community/tutorials/how-to-make-karaoke-videos-using-whisper-and-spleeter-ai-tools | Whisper + Spleeter 制作卡拉OK 教程 |

---

## 10. 总结

这个工具的核心价值是**将多个开源 AI 工具串联成一个自动化管道**，解决 Anisong/JPop 爱好者制作 KTV 投屏视频的痛点：

```
MV 视频 ──→ 去人声 ──→ 加日语字幕(含假名) ──→ KTV 视频
         Demucs      Whisper + fugashi        FFmpeg + ASS
```

**一句话**: 上传 MV，一键生成带假名标注的日语 KTV 视频。

---

*文档版本: v1.0*  
*创建时间: 2026-05-12*  
*状态: 待确认*
