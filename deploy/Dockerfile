FROM python:3.10-slim

WORKDIR /code

# 安装 uv
RUN pip install --no-cache-dir uv

# 复制 pyproject.toml
COPY ./pyproject.toml /code/pyproject.toml

# 锁文件
COPY ./poetry.lock /code/poetry.lock
# 使用 uv 安装依赖，从 pyproject.toml
RUN uv pip install --no-cache-dir --upgrade .

# 复制代码
COPY . /code/

EXPOSE 12345

CMD ["gunicorn", "app.api:app", "--bind", "0.0.0.0:12345", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker"]
