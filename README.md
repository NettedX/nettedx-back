# NettedX Backend

The frontend of NettedX.

## 技术栈

- FastAPI
- Uvicorn
- Pydantic Settings
- Pytest + HTTPX
- Ruff

## 环境要求

- Python >= 3.12

## 快速开始

> 对于第一次使用，请先安装 [uv](https://github.com/astral-sh/uv)

1. 安装依赖

  ```sh
	uv sync
  ```

2. 本地开发运行

  ```sh
	uv run dev
  ```

	或者

  ```sh
	uv run uvicorn app.main:app --reload
  ```

3. 打开内置文档

  与你的代码实时同步，正式的文档定义请以 Apifox 为准。
  
	http://127.0.0.1:8000/docs

## 测试与检查

- 运行测试

  ```sh
	uv run pytest
  ```

- 代码检查

  ```sh
	uv run ruff check
  ```

- 代码格式化

  ```sh
  uv run ruff format
  ```

## 环境变量

可复制 .env.example 为 .env 并按需修改。
