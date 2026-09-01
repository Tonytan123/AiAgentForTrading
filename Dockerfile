# ==============================================================================
# Dockerfile: 量化交易智能体决策、执行与回测系统容器镜像
# ==============================================================================

# 基础镜像：Python 3.12 官方轻量版
FROM python:3.12-slim

# 环境变量设置
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 工作目录
WORKDIR /app

# 安装操作系统级基础依赖（编译基础与系统工具）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 从官方 uv 镜像复制 uv 高性能包管理二进制文件
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 优先复制依赖清单，充分利用 Docker 镜像分层缓存
COPY pyproject.toml requirements.txt ./

# 使用 uv 秒级完成 Python 依赖安装
RUN uv pip install --system -r requirements.txt

# 复制整个项目源代码
COPY . .

# 确保日志与配置目录就绪
RUN mkdir -p logs config

# 默认容器入口命令：运行主交互交易终端
CMD ["python", "main.py"]
