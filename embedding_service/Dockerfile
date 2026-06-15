# GPU 推理服务镜像（部署到 192.168.110.3，需宿主装 nvidia 驱动 + nvidia-container-toolkit）
# torch 的 cu13x wheel 自带 CUDA 运行时库，故用 python slim 基础镜像即可。
FROM python:3.12-slim

# uv：从官方镜像拷二进制
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 先拷依赖清单，利用层缓存
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 拷源码
COPY app.py models.py ./

# 模型缓存目录（compose 里挂卷持久化，避免每次重启重新下载）
ENV HF_HOME=/models
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
