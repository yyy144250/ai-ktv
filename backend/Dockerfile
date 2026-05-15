FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libass-dev \
    git \
    mecab \
    libmecab-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 下载 unidic 词典
RUN python -c "import unidic_lite; print(unidic_lite.DICDIR)"

COPY . .

# 创建必要目录
RUN mkdir -p uploads outputs

EXPOSE 8000

CMD ["python", "run.py"]
