#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_NAME="bansheng"

echo "=== 伴学系统 安装脚本 ==="
echo ""

# 1. Create conda environment
if ! conda env list | grep -q "^${ENV_NAME} "; then
    echo "[1/4] 创建 conda 环境: ${ENV_NAME}..."
    conda env create -f "${ROOT}/backend/environment.yml"
else
    echo "[1/4] conda 环境已存在: ${ENV_NAME}"
fi

# 2. Init .env
if [ ! -f "${ROOT}/backend/.env" ]; then
    echo "[2/4] 创建默认配置文件..."
    cat > "${ROOT}/backend/.env" << 'EOF'
# Database
DATABASE_URL=postgresql+asyncpg://bansheng:bansheng@localhost:5432/bansheng

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM Providers (fill in API keys as needed)
DEEPSEEK__API_KEY=
ZHIPU__API_KEY=
QWEN__API_KEY=
EOF
else
    echo "[2/4] 配置文件已存在: backend/.env"
fi

echo ""
echo "=== 安装完成！==="
echo ""
echo "启动方法:"
echo "  终端1: bash scripts/start-backend.sh"
echo "  终端2: bash scripts/start-frontend.sh"
echo ""
echo "前置条件（请确保以下服务已启动）:"
echo "  - LM Studio (http://localhost:1234)"
echo "  - PostgreSQL 16 + pgvector"
echo "  - Redis 7"
