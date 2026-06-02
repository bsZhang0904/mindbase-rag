# MindBase

**个人知识库 + RAG 智能问答** — 上传私有文档，基于你的资料进行 AI 问答，并展示可核对的引用来源。

面向 LLM 应用 / AI 工程实习岗位的全栈练手项目：自研 RAG 流水线（非套壳、非一键 Dify 部署），覆盖鉴权、文档入库、向量检索、流式生成与引用溯源。

---

## 一句话介绍

用户注册后创建知识库，上传 PDF / Markdown / TXT，系统自动解析、切块、向量化并建立索引；在对话界面提问时，系统从你的文档中检索相关片段，调用大模型生成回答，并在回答中标注 `[1][2]`，侧边栏展示原文摘录与页码。

---

## 已完成功能

| 模块 | 能力 |
|------|------|
| **用户系统** | 注册、登录、JWT 鉴权、`/auth/me` |
| **知识库** | 创建 / 列表 / 详情 / 更新 / 删除 |
| **文档管理** | 上传 PDF、MD、TXT（≤20MB）；异步解析索引；状态 `pending → processing → ready / failed` |
| **Ingestion** | PDF 文本提取（pypdf）、段落优先切块、Embedding 批量写入 |
| **向量检索** | PostgreSQL + **pgvector**，余弦相似度 Top-K |
| **RAG 问答** | 检索 + Prompt 拼装 + LLM 生成；多轮对话与历史消息 |
| **引用溯源** | 回答标注引用序号；返回文档标题、摘录、页码、相似度分数 |
| **流式输出** | SSE 流式接口 + 前端逐字渲染 |
| **演示模式** | `MOCK_MODE=true` 时无需 API Key，使用伪向量与模板回答，本地可完整跑通 |
| **前端界面** | React 登录/注册、知识库列表与详情、文档上传与状态轮询、ChatGPT 风格对话 + 引用侧栏 |
| **基础设施** | Docker Compose 启动 PostgreSQL（pgvector）与 Redis；OpenAPI 文档 `/docs` |
| **测试与样例** | `sample_docs/rag_intro.md` 测试文档；切块单元测试 |

### RAG 核心流程（已实现）

```
上传文档 → 解析文本 → 切块 → Embedding → 写入 pgvector
                                              ↓
用户提问 → 问题向量化 → Top-K 检索 → 拼装 Prompt → LLM → 保存消息与引用
```

### 技术亮点（面试可讲）

- 自研 `Chunker` / `Embedder` / `Retriever` / `Generator`，非黑盒框架堆砌
- 向量存储与业务数据同库（PostgreSQL），降低 MVP 部署复杂度
- 引用溯源降低幻觉风险，回答可追溯到具体文档片段
- 支持 OpenAI 兼容 API（DeepSeek、通义等），便于国内环境切换

---

## 推荐 GitHub 仓库名

便于搜索与识别，任选其一即可：

| 仓库名 | 说明 |
|--------|------|
| **`mindbase-rag`** | 推荐。产品名 + 技术关键词，与项目文档规划一致 |
| **`mindbase`** | 简短，适合作为主品牌仓库 |
| **`personal-knowledge-base-rag`** | 描述性强，利于被「知识库」「RAG」关键词搜到 |
| **`rag-knowledge-base`** | 技术向命名，突出 RAG 场景 |

克隆示例：

```bash
git clone https://github.com/<你的用户名>/mindbase-rag.git
cd mindbase-rag
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI、SQLAlchemy 2.0（async）、pgvector、PyPDF、OpenAI SDK |
| 前端 | React 18、Vite、TypeScript、Ant Design、Axios |
| 数据库 | PostgreSQL 16 + pgvector |
| 缓存 | Redis 7（已纳入 Compose，限流等能力预留） |
| 部署 | Docker Compose（数据库）；后端/前端开发期本地运行 |

---

## 快速开始

### 环境要求

- Docker Desktop（或 Docker + Compose）
- Python 3.11+
- Node.js 18+

### 1. 启动数据库

```bash
docker compose up -d
```

### 2. 后端

```bash
cd backend
copy ..\.env.example .env    # Windows
# copy ../.env.example .env  # macOS / Linux

# 编辑 .env：配置 LLM_API_KEY / EMBEDDING_API_KEY
# 或保持 MOCK_MODE=true 进行无 Key 演示

python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS / Linux

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API 文档：<http://localhost:8000/docs>

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

访问：<http://localhost:5173>

### 4. 体验流程

1. 注册并登录
2. 创建知识库
3. 上传 `sample_docs/rag_intro.md`
4. 等待文档状态变为 **已就绪**
5. 进入对话，提问：「什么是 RAG？」
6. 查看回答中的 `[1][2]` 与右侧引用面板

---

## 配置说明

| 变量 | 说明 |
|------|------|
| `MOCK_MODE=true` | 无 API Key 时使用确定性伪向量 + 模板回答，适合本地 Demo |
| `LLM_API_KEY` | 大模型 API Key（DeepSeek / 通义等 OpenAI 兼容接口） |
| `LLM_BASE_URL` / `LLM_MODEL` | 大模型服务地址与模型名 |
| `EMBEDDING_API_KEY` | Embedding API Key |
| `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` | 向量模型配置 |
| `DATABASE_URL` | PostgreSQL 异步连接串 |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 切块大小与重叠 |
| `RETRIEVAL_TOP_K` | 检索返回片段数量 |

---

## 项目结构

```
.
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/          # REST API（鉴权、知识库、文档、对话）
│   │   ├── services/rag/    # Chunker、Embedder、Retriever、Generator
│   │   └── models/          # SQLAlchemy 数据模型
│   └── tests/               # 单元测试
├── frontend/                # React 前端
│   └── src/pages/           # 登录、知识库、对话页
├── docs/                    # 规划、架构、数据库、API、里程碑等设计文档
├── sample_docs/             # 测试用样例文档
├── docker-compose.yml       # PostgreSQL + Redis
└── .env.example             # 环境变量模板
```

---

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/login` | 登录，返回 JWT |
| GET | `/api/v1/knowledge-bases` | 知识库列表 |
| POST | `/api/v1/knowledge-bases/{kb_id}/documents` | 上传文档（异步索引） |
| GET | `/api/v1/documents/{doc_id}` | 查询文档解析状态 |
| POST | `/api/v1/knowledge-bases/{kb_id}/conversations` | 创建对话 |
| POST | `/api/v1/conversations/{conv_id}/chat` | RAG 问答（非流式） |
| POST | `/api/v1/conversations/{conv_id}/chat/stream` | RAG 问答（SSE 流式） |

完整接口见 Swagger：<http://localhost:8000/docs>

---

## 架构示意

```
┌──────────────┐     REST / SSE      ┌─────────────────────────────┐
│ React 前端   │ ◄────────────────► │ FastAPI                     │
│ 知识库·对话  │                     │ Auth │ KB │ Doc │ Chat API  │
└──────────────┘                     └───────────┬─────────────────┘
                                                 │
                    ┌────────────────────────────┼────────────────┐
                    ▼                            ▼                ▼
             PostgreSQL+pgvector              Redis           LLM / Embedding API
             （业务数据 + 向量）              （预留）          （或 MOCK_MODE）
```

---

## 设计文档

更详细的规划与面试准备材料见 `docs/` 目录：

- [项目规划](docs/01-项目规划.md)
- [架构设计](docs/02-架构设计.md)
- [数据库设计](docs/03-数据库设计.md)
- [API 设计](docs/04-API设计.md)
- [开发里程碑](docs/05-开发里程碑.md)
- [面试准备](docs/06-面试准备.md)

---

## 后续可扩展（未纳入当前 MVP）

- Redis 限流与任务队列（Celery）
- 混合检索（全文 + 向量）与 Rerank
- 后端 / 前端生产镜像一键部署
- 多模态文档、Agent 编排等

---

## License

个人学习项目，可按需自行选择开源协议（如 MIT）。
