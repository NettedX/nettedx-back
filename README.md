# NettedX Backend

NettedX Backend is a backend service built with FastAPI, designed to provide a robust and efficient API for NettedX. This project is structured to facilitate easy development, testing, and deployment.

## Technical Stack

- FastAPI
- Uvicorn
- Pydantic Settings
- Pytest + HTTPX
- Ruff

## Requirements

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv)

## Development Guidelines

Please refer to the [Development Guidelines](https://github.com/NettedX/.github/blob/main/docs/DEVELOPMENT_GUIDELINES.md)

## Running with Docker

> For users and production environments.

Make sure you have [Docker](https://www.docker.com/products/docker-desktop/) and Docker Compose installed on your device.

There are two ways to run the application using Docker:

1. With the source code:

  Clone the repository and run the following command in the project root directory:

  ```sh
  docker-compose up --build
  ```

2. With released Docker image:

  Pull the latest released Docker image from [ghcr](https://github.com/NettedX/nettedx-back/pkgs/container/nettedx-back) and run it:

   ```sh
   docker run -p 8000:8000 ghcr.io/nettedx/nettedx-back:latest
   ```

## Quick Start 

> For Developers Only.

1. Clone the repository

  ```sh
  git clone https://github.com/NettedX/nettedx-back.git
  ```

2. Install dependencies

  ```sh
	uv sync
  ```

2. Start the development server

  ```sh
	uv run dev
  ```

  or

  ```sh
	uv run uvicorn app.main:app --reload
  ```

3. Open the built-in documentation

  Synchronized with your code in real-time, please refer to Apifox for the official documentation.

	http://127.0.0.1:8000/docs

## Available Commands

- Run tests

  ```sh
	uv run pytest
  ```

- Run linter

  ```sh
	uv run ruff check
  ```

- Run formatter

  ```sh
  uv run ruff format
  ```

## Environment Variables

All environment variables are managed using dotenv. Please refer to the `.env.example` file for a list of required environment variables.

Copy the `.env.example` file to `.env` and change the values as needed.

```sh
cp .env.example .env
```