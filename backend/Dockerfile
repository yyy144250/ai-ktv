FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libass-dev \
    git \
    mecab \
    libmecab-dev \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先安装 PyTorch CPU 版（避免下载 CUDA 版本，节省空间）
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu

# 安装其他 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 下载 unidic 词典
RUN python -c "import unidic_lite; print(unidic_lite.DICDIR)"

COPY . .

# 创建必要目录
RUN mkdir -p uploads outputs models/vocal-remover

EXPOSE 8000

CMD ["python", "run.py"]
