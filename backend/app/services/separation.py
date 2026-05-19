"""
人声分离服务 — 支持多种分离引擎

引擎选择策略:
1. SEPARATOR_ENGINE 环境变量指定: "demucs" | "vocal-remover"
2. 自动检测: 有 demucs 则用 demucs，否则尝试 vocal-remover
3. vocal-remover: 轻量 (~55MB 模型)，CPU 2-3 分钟/首歌，适合无 GPU 服务器
4. demucs: 高质量 (~1GB 模型)，GPU 30秒/首歌，需要 torch + demucs

输出:
  - vocals.wav: 人声音轨
  - no_vocals.wav: 伴奏音轨（用于最终 KTV 视频合成）
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("ai-ktv.separation")

# vocal-remover 模型配置
MODELS_DIR = Path(__file__).parent.parent.parent / "models" / "vocal-remover"
MODEL_URLS = [
    "https://huggingface.co/ModelsLab/vocal-remover-model/resolve/main/baseline.pth",
    "https://github.com/tsurumeso/vocal-remover/releases/download/v5.1.0/baseline.pth",
]
DEFAULT_MODEL_PATH = MODELS_DIR / "baseline.pth"


def detect_engine() -> str:
    """检测可用的分离引擎"""
    env = os.environ.get("SEPARATOR_ENGINE", "").lower().replace("-", "_")
    if env == "demucs":
        return "demucs"
    if env in ("vocal_remover", "vocalremover"):
        return "vocal-remover"

    # 自动检测：优先 demucs
    try:
        import demucs  # noqa: F401
        logger.info("检测到 demucs 包，使用 Demucs 引擎")
        return "demucs"
    except ImportError:
        pass

    logger.info("未检测到 demucs，使用 vocal-remover 轻量引擎")
    return "vocal-remover"


async def download_model_if_needed() -> Path:
    """确保 vocal-remover 模型存在，不存在则自动下载"""
    if DEFAULT_MODEL_PATH.exists():
        file_size = DEFAULT_MODEL_PATH.stat().st_size
        if file_size > 1_000_000:  # 至少 1MB，防止下载了空文件
            return DEFAULT_MODEL_PATH

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("首次使用 vocal-remover，正在下载模型 (~55MB)...")

    import aiohttp
    timeout = aiohttp.ClientTimeout(total=600)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for url in MODEL_URLS:
            try:
                logger.info(f"尝试从 {url} 下载...")
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        logger.warning(f"下载失败 (HTTP {resp.status}): {url}")
                        continue
                    content = await resp.read()
                    if len(content) < 1_000_000:
                        logger.warning(f"文件太小 ({len(content)} bytes)，跳过: {url}")
                        continue
                    DEFAULT_MODEL_PATH.write_bytes(content)
                    size_mb = len(content) / 1024 / 1024
                    logger.info(f"vocal-remover 模型下载完成: {size_mb:.1f} MB")
                    return DEFAULT_MODEL_PATH
            except Exception as e:
                logger.warning(f"从 {url} 下载失败: {e}")
                continue

    raise RuntimeError(
        "无法下载 vocal-remover 模型。请手动下载:\n"
        f"  curl -L -o {DEFAULT_MODEL_PATH} {MODEL_URLS[0]}\n"
        "或设置 SEPARATOR_ENGINE=demucs 使用 Demucs 引擎"
    )


async def separate_with_vocal_remover(
    audio_path: Path,
    output_dir: Path,
    progress_callback=None,
) -> Tuple[Path, Path]:
    """
    使用 vocal-remover 进行人声分离

    Args:
        audio_path: 输入音频文件路径（WAV 格式）
        output_dir: 输出目录
        progress_callback: async 回调函数，接收 (progress: int, message: str)

    Returns:
        (vocals_path, accompaniment_path) 元组
    """
    # 确保模型已下载
    model_path = await download_model_if_needed()

    if progress_callback:
        await progress_callback(15, "vocal-remover 模型已就绪，开始分离...")

    # 使用 Python 直接调用（避免额外的 inference.py 文件依赖）
    # vocal-remover 的核心逻辑很简单：加载音频 → STFT → 模型推理 → ISTFT → 保存
    vocals_path = output_dir / "vocals.wav"
    accomp_path = output_dir / "no_vocals.wav"

    # 在线程池中运行 CPU 密集型任务，避免阻塞事件循环
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        _run_vocal_remover_sync,
        str(audio_path),
        str(model_path),
        str(vocals_path),
        str(accomp_path),
    )

    if not vocals_path.exists() or not accomp_path.exists():
        raise RuntimeError("vocal-remover 分离失败：输出文件未生成")

    return vocals_path, accomp_path


def _run_vocal_remover_sync(
    audio_path: str,
    model_path: str,
    vocals_out: str,
    accomp_out: str,
):
    """
    同步执行 vocal-remover 推理（在线程池中运行）

    直接内联 vocal-remover 的推理逻辑，避免依赖外部 inference.py
    核心流程: 加载音频 → STFT → CascadedNet 推理 → 掩码分离 → ISTFT → 保存
    """
    import torch
    import numpy as np
    import librosa
    import soundfile as sf

    logger.info(f"[vocal-remover] 加载模型: {model_path}")

    # 确定设备
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    logger.info(f"[vocal-remover] 使用设备: {device}")

    # 加载模型
    model = _build_cascaded_net(n_fft=2048, hop_length=1024)
    state_dict = torch.load(model_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()

    # 加载音频（立体声，44100Hz）
    logger.info(f"[vocal-remover] 加载音频: {audio_path}")
    X, sr = librosa.load(audio_path, sr=44100, mono=False, dtype=np.float32, res_type="kaiser_fast")
    if X.ndim == 1:
        X = np.asarray([X, X])  # mono → stereo

    # STFT
    logger.info("[vocal-remover] 执行 STFT...")
    X_spec = np.asarray([
        librosa.stft(X[0], n_fft=2048, hop_length=1024),
        librosa.stft(X[1], n_fft=2048, hop_length=1024),
    ])

    # 分离
    logger.info("[vocal-remover] 模型推理中...")
    with torch.no_grad():
        mask = _predict_mask(model, X_spec, device, batchsize=4, cropsize=256, offset=model.offset)

    # 应用掩码
    X_mag = np.abs(X_spec)
    X_phase = np.angle(X_spec)
    # y = instruments (伴奏), v = vocals (人声)
    y_spec = mask * X_mag * np.exp(1.0j * X_phase)
    v_spec = (1 - mask) * X_mag * np.exp(1.0j * X_phase)

    # ISTFT
    logger.info("[vocal-remover] ISTFT 重建波形...")
    wave_instruments = np.asarray([
        librosa.istft(y_spec[0], hop_length=1024),
        librosa.istft(y_spec[1], hop_length=1024),
    ])
    wave_vocals = np.asarray([
        librosa.istft(v_spec[0], hop_length=1024),
        librosa.istft(v_spec[1], hop_length=1024),
    ])

    # 保存
    logger.info(f"[vocal-remover] 保存结果...")
    sf.write(accomp_out, wave_instruments.T, sr)
    sf.write(vocals_out, wave_vocals.T, sr)
    logger.info("[vocal-remover] 分离完成！")


def _predict_mask(model, X_spec, device, batchsize=4, cropsize=256, offset=64):
    """分块预测掩码（避免内存溢出）"""
    import torch
    import numpy as np

    n_frame = X_spec.shape[2]
    # 计算 padding
    roi_size = cropsize - offset * 2
    if roi_size == 0:
        roi_size = cropsize
    pad_l = offset
    pad_r = roi_size - (n_frame % roi_size) + pad_l

    X_spec_pad = np.pad(X_spec, ((0, 0), (0, 0), (pad_l, pad_r)), mode="constant")
    X_spec_pad_norm = X_spec_pad / (np.abs(X_spec).max() + 1e-8)

    # 分块推理
    patches = (X_spec_pad_norm.shape[2] - 2 * offset) // roi_size
    mask_list = []

    for i in range(0, patches, batchsize):
        batch_specs = []
        for j in range(i, min(i + batchsize, patches)):
            start = j * roi_size
            crop = X_spec_pad_norm[:, :, start:start + cropsize]
            batch_specs.append(crop)

        X_batch = np.asarray(batch_specs)
        X_batch_tensor = torch.from_numpy(np.abs(X_batch)).to(device)

        mask_batch = model.predict_mask(X_batch_tensor)
        mask_batch = mask_batch.detach().cpu().numpy()
        mask_batch = np.concatenate(mask_batch, axis=2)
        mask_list.append(mask_batch)

    mask = np.concatenate(mask_list, axis=2)
    mask = mask[:, :, :n_frame]
    return mask


# ============ CascadedNet 模型定义（从 vocal-remover 内联） ============

def _build_cascaded_net(n_fft=2048, hop_length=1024, nout=32, nout_lstm=128):
    """
    构建 CascadedNet 模型（精确复刻 vocal-remover 原版 lib/nets.py + lib/layers.py）
    """
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    def _crop_center(h, target):
        """中心裁剪 h 使其与 target 的空间尺寸对齐"""
        _, _, h_h, h_w = h.size()
        _, _, t_h, t_w = target.size()
        if h_h == t_h and h_w == t_w:
            return h
        s_h = (h_h - t_h) // 2
        s_w = (h_w - t_w) // 2
        return h[:, :, s_h:s_h + t_h, s_w:s_w + t_w]

    class Conv2DBNActiv(nn.Module):
        def __init__(self, nin, nout, ksize=3, stride=1, pad=1, dilation=1, activ=nn.ReLU):
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv2d(nin, nout, kernel_size=ksize, stride=stride, padding=pad, dilation=dilation, bias=False),
                nn.BatchNorm2d(nout),
                activ(),
            )

        def forward(self, x):
            return self.conv(x)

    class Encoder(nn.Module):
        def __init__(self, nin, nout, ksize=3, stride=1, pad=1, activ=nn.LeakyReLU):
            super().__init__()
            self.conv1 = Conv2DBNActiv(nin, nout, ksize, stride, pad, activ=activ)
            self.conv2 = Conv2DBNActiv(nout, nout, ksize, 1, pad, activ=activ)

        def forward(self, x):
            h = self.conv1(x)
            h = self.conv2(h)
            return h

    class Decoder(nn.Module):
        def __init__(self, nin, nout, ksize=3, stride=1, pad=1, activ=nn.ReLU, dropout=False):
            super().__init__()
            self.conv1 = Conv2DBNActiv(nin, nout, ksize, 1, pad, activ=activ)
            self.dropout = nn.Dropout2d(0.1) if dropout else None

        def forward(self, x, skip=None):
            x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=True)
            if skip is not None:
                skip = _crop_center(skip, x)
                x = torch.cat([x, skip], dim=1)
            h = self.conv1(x)
            if self.dropout is not None:
                h = self.dropout(h)
            return h

    class ASPPModule(nn.Module):
        def __init__(self, nin, nout, dilations=(4, 8, 12), activ=nn.ReLU, dropout=False):
            super().__init__()
            self.conv1 = nn.Sequential(
                nn.AdaptiveAvgPool2d((1, None)),
                Conv2DBNActiv(nin, nout, 1, 1, 0, activ=activ),
            )
            self.conv2 = Conv2DBNActiv(nin, nout, 1, 1, 0, activ=activ)
            self.conv3 = Conv2DBNActiv(nin, nout, 3, 1, dilations[0], dilations[0], activ=activ)
            self.conv4 = Conv2DBNActiv(nin, nout, 3, 1, dilations[1], dilations[1], activ=activ)
            self.conv5 = Conv2DBNActiv(nin, nout, 3, 1, dilations[2], dilations[2], activ=activ)
            self.bottleneck = Conv2DBNActiv(nout * 5, nout, 1, 1, 0, activ=activ)
            self.dropout = nn.Dropout2d(0.1) if dropout else None

        def forward(self, x):
            _, _, h, w = x.size()
            feat1 = F.interpolate(self.conv1(x), size=(h, w), mode="bilinear", align_corners=True)
            feat2 = self.conv2(x)
            feat3 = self.conv3(x)
            feat4 = self.conv4(x)
            feat5 = self.conv5(x)
            out = torch.cat((feat1, feat2, feat3, feat4, feat5), dim=1)
            out = self.bottleneck(out)
            if self.dropout is not None:
                out = self.dropout(out)
            return out

    class LSTMModule(nn.Module):
        def __init__(self, nin_conv, nin_lstm, nout_lstm):
            super().__init__()
            self.conv = Conv2DBNActiv(nin_conv, 1, 1, 1, 0)
            self.lstm = nn.LSTM(input_size=nin_lstm, hidden_size=nout_lstm // 2, bidirectional=True)
            self.dense = nn.Sequential(nn.Linear(nout_lstm, nin_lstm), nn.BatchNorm1d(nin_lstm), nn.ReLU())

        def forward(self, x):
            N, _, nbins, nframes = x.size()
            h = self.conv(x)[:, 0]  # (N, nbins, nframes)
            h = h.permute(2, 0, 1)  # (nframes, N, nbins)
            h, _ = self.lstm(h)
            h = self.dense(h.reshape(-1, h.size()[-1]))  # (nframes*N, nin_lstm)
            h = h.reshape(nframes, N, 1, nbins)
            h = h.permute(1, 2, 3, 0)  # (N, 1, nbins, nframes)
            return h

    class BaseNet(nn.Module):
        def __init__(self, nin, nout, nin_lstm, nout_lstm, dilations=((4, 2), (8, 4), (12, 6))):
            super().__init__()
            # enc1 不下采样（Conv2DBNActiv, stride=1），enc2~enc5 下采样（Encoder, stride=2）
            self.enc1 = Conv2DBNActiv(nin, nout, 3, 1, 1)
            self.enc2 = Encoder(nout, nout * 2, 3, 2, 1)
            self.enc3 = Encoder(nout * 2, nout * 4, 3, 2, 1)
            self.enc4 = Encoder(nout * 4, nout * 6, 3, 2, 1)
            self.enc5 = Encoder(nout * 6, nout * 8, 3, 2, 1)

            self.aspp = ASPPModule(nout * 8, nout * 8, dilations=dilations, dropout=True)

            self.dec4 = Decoder(nout * (6 + 8), nout * 6, 3, 1, 1)
            self.dec3 = Decoder(nout * (4 + 6), nout * 4, 3, 1, 1)
            self.dec2 = Decoder(nout * (2 + 4), nout * 2, 3, 1, 1)
            self.lstm_dec2 = LSTMModule(nout * 2, nin_lstm, nout_lstm)
            self.dec1 = Decoder(nout * (1 + 2) + 1, nout * 1, 3, 1, 1)

        def forward(self, x):
            e1 = self.enc1(x)
            e2 = self.enc2(e1)
            e3 = self.enc3(e2)
            e4 = self.enc4(e3)
            e5 = self.enc5(e4)

            h = self.aspp(e5)

            h = self.dec4(h, e4)
            h = self.dec3(h, e3)
            h = self.dec2(h, e2)
            h = torch.cat([h, self.lstm_dec2(h)], dim=1)
            h = self.dec1(h, e1)
            return h

    class CascadedNet(nn.Module):
        def __init__(self, n_fft, hop_length, nout=32, nout_lstm=128, is_complex=False):
            super().__init__()
            self.n_fft = n_fft
            self.hop_length = hop_length
            self.max_bin = n_fft // 2
            self.output_bin = n_fft // 2 + 1
            self.nin_lstm = self.max_bin // 2
            self.offset = 64
            nin = 4 if is_complex else 2

            self.stg1_low_band_net = nn.Sequential(
                BaseNet(nin, nout // 2, self.nin_lstm // 2, nout_lstm),
                Conv2DBNActiv(nout // 2, nout // 4, 1, 1, 0),
            )
            self.stg1_high_band_net = BaseNet(nin, nout // 4, self.nin_lstm // 2, nout_lstm // 2)

            self.stg2_low_band_net = nn.Sequential(
                BaseNet(nout // 4 + nin, nout, self.nin_lstm // 2, nout_lstm),
                Conv2DBNActiv(nout, nout // 2, 1, 1, 0),
            )
            self.stg2_high_band_net = BaseNet(nout // 4 + nin, nout // 2, self.nin_lstm // 2, nout_lstm // 2)

            self.stg3_full_band_net = BaseNet(3 * nout // 4 + nin, nout, self.nin_lstm, nout_lstm)

            self.out = nn.Conv2d(nout, nin, 1, bias=False)
            self.aux_out = nn.Conv2d(3 * nout // 4, nin, 1, bias=False)

        def forward(self, x):
            x = x[:, :, :self.max_bin]
            bandw = x.size()[2] // 2

            l1_in = x[:, :, :bandw]
            h1_in = x[:, :, bandw:]

            l1 = self.stg1_low_band_net(l1_in)
            h1 = self.stg1_high_band_net(h1_in)
            aux1 = torch.cat([l1, h1], dim=2)

            l2_in = torch.cat([l1_in, l1], dim=1)
            h2_in = torch.cat([h1_in, h1], dim=1)
            l2 = self.stg2_low_band_net(l2_in)
            h2 = self.stg2_high_band_net(h2_in)
            aux2 = torch.cat([l2, h2], dim=2)

            f3_in = torch.cat([x, aux1, aux2], dim=1)
            f3 = self.stg3_full_band_net(f3_in)

            mask = torch.sigmoid(self.out(f3))
            mask = F.pad(
                input=mask,
                pad=(0, 0, 0, self.output_bin - mask.size()[2]),
                mode="replicate",
            )
            return mask

        def predict_mask(self, x):
            mask = self.forward(x)
            if self.offset > 0:
                mask = mask[:, :, :, self.offset:-self.offset]
                assert mask.size()[3] > 0
            return mask

    return CascadedNet(n_fft, hop_length, nout, nout_lstm)


# ============ Demucs 引擎（使用子进程，与现有代码兼容） ============

async def separate_with_demucs(
    audio_path: Path,
    output_dir: Path,
    progress_callback=None,
) -> Tuple[Path, Path]:
    """
    使用 Demucs 进行人声分离（通过子进程调用）

    Args:
        audio_path: 输入音频文件路径
        output_dir: 输出目录
        progress_callback: async 回调，接收 (progress: int, message: str)

    Returns:
        (vocals_path, accompaniment_path) 元组
    """
    demucs_out = output_dir / "demucs"
    cmd = [
        "python", "-m", "demucs",
        "--two-stems", "vocals",
        "-o", str(demucs_out),
        str(audio_path),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    assert proc.stdout
    output_lines: list = []
    async for line in proc.stdout:
        text = line.decode("utf-8", errors="replace").strip()
        if text:
            output_lines.append(text)
        if "%" in text and progress_callback:
            try:
                pct = int(text.split("%")[0].split()[-1])
                mapped = 10 + int(pct * 0.80)  # 10~90
                await progress_callback(mapped, f"Demucs 分离中 {pct}%")
            except Exception:
                pass

    await proc.wait()

    if proc.returncode != 0:
        error_detail = "\n".join(output_lines[-5:]) if output_lines else "（无输出）"
        raise RuntimeError(f"Demucs 执行失败: {error_detail}")

    # 查找输出文件
    vocals_path = _find_stem_file(demucs_out, "vocals")
    accomp_path = _find_stem_file(demucs_out, "no_vocals")

    if not vocals_path or not accomp_path:
        raise RuntimeError("Demucs 找不到分离结果文件")

    return vocals_path, accomp_path


def _find_stem_file(base_dir: Path, stem_name: str) -> Optional[Path]:
    """在 demucs 输出目录中递归查找指定 stem 文件"""
    for p in base_dir.rglob(f"{stem_name}.*"):
        if p.suffix in (".wav", ".mp3", ".flac") and p.is_file():
            return p
    return None


# ============ 统一入口 ============

async def separate(
    audio_path: Path,
    output_dir: Path,
    progress_callback=None,
    engine: Optional[str] = None,
) -> Tuple[Path, Path]:
    """
    统一人声分离入口

    Args:
        audio_path: 输入音频路径（WAV 格式）
        output_dir: 输出目录
        progress_callback: async 回调，接收 (progress: int, message: str)
        engine: 指定引擎 "demucs" | "vocal-remover"，None 则自动检测

    Returns:
        (vocals_path, accompaniment_path) 元组
    """
    if engine is None:
        engine = detect_engine()

    logger.info(f"使用人声分离引擎: {engine}")

    if engine == "demucs":
        return await separate_with_demucs(audio_path, output_dir, progress_callback)
    else:
        return await separate_with_vocal_remover(audio_path, output_dir, progress_callback)
