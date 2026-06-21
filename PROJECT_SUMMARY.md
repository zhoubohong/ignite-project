# 伴学系统 Bansheng — 项目总结

面向中国初中（7-9年级）和高中（10-12年级）学生的 AI 智能学习伴侣。

---

## 项目结构

```
ignite project/
├── backend/                   # FastAPI Python 后端
│   ├── app/
│   │   ├── main.py            # 应用入口，CORS，路由挂载
│   │   ├── api/               # REST API 层
│   │   │   ├── chat.py        # 对话（同步+SSE流式）+ 答题批改
│   │   │   ├── questions.py   # 题库 CRUD + LLM 生成题目
│   │   │   └── dashboard.py   # 学习统计/掌握度/错题/趋势
│   │   ├── agents/
│   │   │   └── orchestrator.py # 意图分类 + 文理分科路由
│   │   ├── llm/
│   │   │   └── gateway.py     # 多 Provider LLM Gateway（fallback + 重试）
│   │   ├── memory/
│   │   │   ├── session.py     # L1 会话记忆（Redis）
│   │   │   └── learning.py    # L2 学习状态（BKT 掌握度追踪 + 错题本）
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   │   ├── base.py        # Declarative Base
│   │   │   ├── user.py        # User, KnowledgeMastery, MistakeRecord
│   │   │   ├── question.py    # Question（pgvector 嵌入）
│   │   │   └── session.py     # StudySession, AnswerRecord
│   │   ├── question_bank/
│   │   │   └── generator.py   # LLM 题目生成器（6 种题型）
│   │   ├── db/
│   │   │   └── database.py    # 数据库引擎（PostgreSQL/SQLite 自适应）
│   │   └── core/
│   │       └── config.py      # Pydantic Settings（5 个 LLM Provider）
│   ├── tests/                 # 85 个单元/集成测试
│   ├── .env                   # 环境变量
│   └── environment.yml        # Conda 依赖
├── frontend/                  # Next.js 16 + React 19 + Tailwind 4
│   └── src/app/
│       ├── layout.tsx         # 根布局
│       ├── page.tsx           # 单页面应用（聊天+面板+刷题）
│       └── globals.css        # 全局样式
└── scripts/
    ├── setup.sh               # 一键安装脚本
    └── start-backend.sh       # 后端启动脚本
```

---

## 核心功能

### 1. AI 对话（SSE 流式打字机）

- **端点**：`POST /api/chat/send`（同步）、`POST /api/chat/stream`（SSE 流式）
- **流程**：用户输入 → Orchestrator 意图分类（learn/practice/exam/review/other） → 学科识别（8 科） → 文理分科路由 → LLM 生成回复
- **前端**：SSE 逐字流式渲染，元数据标签展示（学科·意图）

### 2. 学习面板（4 标签数据可视化）

| 标签 | 数据来源 | 内容 |
|------|---------|------|
| 概览 | `/api/dashboard/stats/{uid}` | 学习会话数、做题总数、近期错题、掌握度分布、薄弱知识点 TOP5 |
| 掌握度 | `/api/dashboard/mastery/{uid}` | 每知识点 P(L) 进度条（红→黄→蓝→绿）、状态徽章、做题次数 |
| 错题 | `/api/dashboard/mistakes/{uid}` | 按错因分组的水平条形图（概念/公式/计算/单位/审题） |
| 趋势 | `/api/dashboard/daily/{uid}` | 7 天每日答题量柱状图 + 正确率颜色编码 |

### 3. 刷题练习（选题→答题→批改→反馈）

- **端点**：`POST /api/questions/`、`GET /api/questions/`、`POST /api/chat/answer/check`
- **题型支持**：单选题（A/B/C/D 按钮）、填空题/简答题/计算题（文本输入）
- **批改反馈**：✅/❌ 指示、正确答案、错因分类标签、解析文本、当前 P(L) 掌握度
- **下一题**：通过 offset 从题库轮转

### 4. BKT 掌握度引擎

- **算法**：Bayesian Knowledge Tracing（P(L), P(G), P(S), P(T)）
- **状态机**：untouched → exposed → practicing → mastered
- **错题本**：LLM 自动错因分类（5 类），记录在 MistakeRecord 表

### 5. 多 Provider LLM Gateway

优先级 fallback 链：LM Studio（本地） → Ollama（本地） → DeepSeek → 智谱 GLM → 通义千问

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI 0.115 + Uvicorn |
| 数据库 | PostgreSQL 16 + pgvector / SQLite（开发） |
| ORM | SQLAlchemy 2.0（异步） |
| 缓存/会话 | Redis 8（aioredis） |
| LLM 接入 | OpenAI-compatible SDK（多 provider） |
| 掌握度模型 | BKT（贝叶斯知识追踪） |
| 前端框架 | Next.js 16 + React 19 |
| 样式 | Tailwind CSS 4 |
| 语言 | Python 3.11 + TypeScript 5 |

---

## 测试

85 个后端测试全部通过（`pytest tests/ -q`），覆盖：

- BKT 数学验证（4 个纯数学测试）
- BKT 状态机（4 个集成测试）
- 错题记录（2 个集成测试）
- 学习记忆（9 个集成测试）
- 会话记忆（3 个集成测试）
- LLM Gateway（8 个测试含 fallback 逻辑）
- Chat API（10 个测试含 SSE 流式 + 答题批改）
- Dashboard API（10 个测试）
- Question API（14 个测试）
- Orchestrator（意图分类 + system prompt 组装）

TypeScript 编译零错误（`npx tsc --noEmit`）。

---

## 本地运行

前置条件：
- LM Studio（模型：qwen/qwen3.6-35b-a3b，19GB VRAM）
- Redis 8（`brew install redis && brew services start redis`）
- Python 3.11 + Conda

```bash
# 安装
bash scripts/setup.sh

# 启动后端（终端1）
bash scripts/start-backend.sh     # → http://localhost:8000

# 启动前端（终端2）
cd frontend && npm install && npm run dev   # → http://localhost:3000
```

---

## Git 历史

```
24ddbce chore: configure LM Studio with qwen3.6-35b model identifier
fac3a9a feat: exercise/practice UI with answer checking and BKT feedback (#2)
3ee8118 Merge pull request #1 (dashboard + SSE streaming)
bc7c001 feat: exercise/practice UI with answer checking and BKT feedback
83981dc feat: replace sync chat with SSE streaming
65326f9 feat: integrate mastery/mistakes/daily dashboard APIs
0e61ffc fix: SSE stream terminator uses valid JSON
3b29fe4 feat: 伴学系统 Phase 1 — initial scaffold
```

---

## 后续工作

- [ ] 用户注册/登录/鉴权（当前为匿名 UUID）
- [ ] 题目嵌入向量生成 + 相似题推荐（sentence-transformers 已配置，未调用）
- [ ] 前端适配移动端
- [ ] Docker 化 + 云部署（当前为本地开发模式）
- [ ] 考试模式（组卷 + 计时 + 评分）
- [ ] 家长/教师仪表盘
