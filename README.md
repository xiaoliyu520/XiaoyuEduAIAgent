# 小鱼教育AI智能助手平台

基于大语言模型的教育领域智能助手平台，集成智能问答、代码检查、模拟面试、简历审查四大核心功能，为学员提供全方位的AI辅助学习服务。

## 📋 目录

- [功能特性](#功能特性)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [API文档](#api文档)
- [部署指南](#部署指南)
- [开发指南](#开发指南)
- [性能优化](#性能优化)
- [常见问题](#常见问题)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

## ✨ 功能特性

### 1. 智能问答系统 (RAG)

- **混合检索策略**：向量检索 + BM25关键词检索，提升召回率
- **问题类型分类**：chitchat/clear/vague/broad四种类型，针对性优化检索策略
- **HyDE技术**：为模糊问题生成假设性文档，提升检索准确性
- **查询拆分**：将宽泛问题拆分为多个子问题并行检索
- **CrossEncoder重排序**：对检索结果精排，提升相关性
- **知识缺口检测**：自动识别知识库缺失信息，触发知识补录流程

### 2. 代码智能检查系统

- **沙箱执行**：集成Judge0沙箱，安全隔离执行用户代码，支持多语言
- **多维度分析**：语法错误、逻辑错误、复杂度分析、代码风格四维评估
- **结构化错误标签**：如"空指针异常→数组越界→时间复杂度O(n²)"
- **降级方案**：沙箱不可用时自动切换静态代码分析

### 3. AI模拟面试系统

- **四阶段面试流程**：INTRO → TECH → PROJECT → REPORT
- **动态出题机制**：基于简历和薄弱点智能生成问题
- **双轨评估体系**：技术深度 + 表达能力独立评分(0-100分)
- **薄弱点追踪**：持续识别学员薄弱环节，针对性出题强化
- **可视化报告**：雷达图展示六维能力评估

### 4. 简历智能审查系统

- **六维度评估**：工作经历、技能匹配、项目描述、量化数据、格式排版、表达规范
- **并行评估策略**：三个评估组并行处理，提升效率3倍
- **优先级建议**：按高/中/低优先级提供具体修改建议
- **雷达图可视化**：直观展示各维度得分

## 🏗️ 技术架构

### 后端技术栈

- **框架**：FastAPI + Python 3.10+
- **LLM框架**：LangChain + LangGraph
- **数据库**：PostgreSQL 16 + Redis 7
- **向量数据库**：Milvus 2.4
- **对象存储**：MinIO
- **LLM服务**：通义千问 (qwen-max, qwen3-coder-plus)
- **Embedding模型**：text-embedding-v1
- **重排序模型**：BAAI/bge-reranker-v2-m3
- **意图分类模型**：all-MiniLM-L6-v2

### 前端技术栈

- **框架**：Vue.js 3 + Vite
- **UI组件**：Element Plus
- **状态管理**：Pinia
- **路由**：Vue Router
- **双端架构**：用户端 + 管理端

### 基础设施

- **容器化**：Docker + Docker Compose
- **代码执行沙箱**：Judge0
- **反向代理**：Nginx

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端层                                │
│  ┌──────────────────┐          ┌──────────────────┐        │
│  │   用户端 (3000)   │          │  管理端 (3001)    │        │
│  └──────────────────┘          └──────────────────┘        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      API网关层                               │
│                   FastAPI (8000)                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                     业务逻辑层                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Orchestrator (调度器)                     │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │  │
│  │  │ Intent     │→ │ Agent      │→ │ Response   │     │  │
│  │  │ Classifier │  │ Registry   │  │ Formatter  │     │  │
│  │  └────────────┘  └────────────┘  └────────────┘     │  │
│  └──────────────────────────────────────────────────────┘  │
│                              ↓                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │    QA    │  │   Code   │  │Interview │  │  Resume  │  │
│  │  Agent   │  │  Agent   │  │  Agent   │  │  Agent   │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      服务层                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   LLM    │  │Embedding │  │ Reranker │  │  Intent  │  │
│  │  Service │  │ Service  │  │ Service  │  │Classifier│  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                      数据层                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │PostgreSQL│  │  Redis   │  │  Milvus  │  │  MinIO   │  │
│  │   (5432) │  │  (6379)  │  │ (19530)  │  │  (9000)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    外部服务                                  │
│  ┌──────────────────┐          ┌──────────────────┐        │
│  │  通义千问 API     │          │   Judge0 沙箱     │        │
│  └──────────────────┘          └──────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 8GB+ 可用内存
- 20GB+ 可用磁盘空间

### 1. 克隆项目

```bash
git clone <repository-url>
cd XiaoyuEduAIAgent
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env` 文件，配置必要的环境变量：

```env
# 通义千问API密钥（必填）
DASHSCOPE_API_KEY=your_api_key_here

# JWT密钥（建议修改）
JWT_SECRET_KEY=your_secret_key_here

# 其他配置使用默认值即可
```

### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
```

### 4. 访问应用

- 用户端：<http://localhost:3000>
- 管理端：<http://localhost:3001>
- API文档：<http://localhost:8000/docs>

### 5. 初始化数据

首次启动后，需要创建管理员账号和知识库：

1. 访问管理端 <http://localhost:3001>
2. 注册管理员账号
3. 创建知识库并上传文档

## ⚙️ 配置说明

### 环境变量配置

#### 核心配置

```env
# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=true

# JWT配置
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# CORS配置
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

#### 数据库配置

```env
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=xiaoyu
POSTGRES_PASSWORD=xiaoyu123
POSTGRES_DB=xiaoyu_edu

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=xiaoyu-edu
```

#### LLM配置

```env
# 通义千问
DASHSCOPE_API_KEY=your_api_key
LLM_MODEL_NAME=qwen-max
EMBEDDING_MODEL_NAME=text-embedding-v1

# 代码分析模型
CODE_ANALYSIS_MODEL=qwen3-coder-plus

# 意图分类模型
INTENT_CLASSIFIER_MODEL=all-MiniLM-L6-v2

# 重排序模型
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
ENABLE_RERANKER=false

# 相关性阈值
RELEVANCE_THRESHOLD=0.5
```

#### 外部服务配置

```env
# Judge0沙箱
JUDGE0_API_URL=http://localhost:2358
```

### 模型配置说明

#### 启用重排序模型

重排序模型可以显著提升检索相关性，但需要额外资源：

```env
ENABLE_RERANKER=true
RERANKER_MODEL_NAME=BAAI/bge-reranker-v2-m3
```

#### 使用HuggingFace镜像

如果在国内下载模型较慢，可以配置镜像：

```env
HF_MIRROR_URL=https://hf-mirror.com
```

## 📚 API文档

### 认证接口

#### 用户注册

```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "password123",
  "nickname": "用户昵称"
}
```

#### 用户登录

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "password123"
}
```

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "token_type": "bearer"
  }
}
```

### 对话接口

#### 创建对话（流式）

```http
POST /api/v1/chat/stream
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "什么是机器学习？",
  "conversation_id": null,
  "agent_type": "qa",
  "kb_ids": [1, 2],
  "context": {}
}
```

响应（Server-Sent Events）：

```
data: {"content": "机器学习是..."}

data: {"content": "人工智能的一个分支..."}

data: {"done": true, "conversation_id": 123, "confidence": 0.85}
```

#### 获取对话列表

```http
GET /api/v1/chat/conversations
Authorization: Bearer <token>
```

### 知识库接口

#### 创建知识库

```http
POST /api/v1/knowledge/bases
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "机器学习基础",
  "description": "机器学习相关知识"
}
```

#### 上传文档

```http
POST /api/v1/knowledge/bases/{kb_id}/documents
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <document_file>
```

支持的文档格式：支持OCR

- PDF (.pdf)
- Word (.doc, .docx)
- PowerPoint (.ppt, .pptx)
- 文本文件 (.txt, .md)
- CSV (.csv)

### 代码检查接口

```http
POST /api/v1/code/check
Authorization: Bearer <token>
Content-Type: application/json

{
  "code": "def hello():\n    print('hello')",
  "language": "python"
}
```

### 模拟面试接口

```http
POST /api/v1/interview/start
Authorization: Bearer <token>
Content-Type: application/json

{
  "resume_text": "简历内容...",
  "focus_areas": ["Python", "机器学习"]
}
```

### 简历审查接口

```http
POST /api/v1/resume/review
Authorization: Bearer <token>
Content-Type: application/json

{
  "resume_text": "简历内容..."
}
```

完整API文档请访问：<http://localhost:8000/docs>

## 🐳 部署指南

### 开发环境部署

```bash
# 使用开发配置启动
docker-compose -f docker-compose.dev.yml up -d

# 后端热重载
docker-compose -f docker-compose.dev.yml logs -f backend
```

### 生产环境部署

#### 1. 准备生产环境配置

创建 `backend/.env.prod`：

```env
DEBUG=false
JWT_SECRET_KEY=<strong_secret_key>
DASHSCOPE_API_KEY=<your_api_key>
CORS_ORIGINS=https://your-domain.com
```

#### 2. 修改docker-compose.yml

```yaml
services:
  backend:
    environment:
      - DEBUG=false
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    volumes:
      - ./backend/.env.prod:/app/.env
```

#### 3. 启动生产服务

```bash
docker-compose up -d
```

#### 4. 配置Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 50M;

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # SSE支持
        proxy_buffering off;
        proxy_cache off;
    }

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 数据备份

#### PostgreSQL备份

```bash
# 备份
docker-compose exec postgres pg_dump -U xiaoyu xiaoyu_edu > backup.sql

# 恢复
docker-compose exec -T postgres psql -U xiaoyu xiaoyu_edu < backup.sql
```

#### Milvus备份

```bash
# 备份向量数据
docker-compose exec milvus curl -X POST http://localhost:9091/api/v1/snapshot
```

### 监控与日志

#### 查看服务状态

```bash
docker-compose ps
docker-compose stats
```

#### 查看日志

```bash
# 所有服务日志
docker-compose logs -f

# 特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend-user
```

## 💻 开发指南

### 本地开发环境搭建

#### 后端开发

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
python run.py
```

#### 前端开发

```bash
# 用户端
cd frontend/user
npm install
npm run dev

# 管理端
cd frontend/admin
npm install
npm run dev
```

### 项目结构

```
XiaoyuEduAIAgent/
├── backend/                 # 后端代码
│   ├── app/
│   │   ├── agents/         # Agent模块
│   │   │   ├── qa/         # 智能问答Agent
│   │   │   ├── code/       # 代码检查Agent
│   │   │   ├── interview/  # 模拟面试Agent
│   │   │   └── resume/     # 简历审查Agent
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心配置
│   │   ├── mcp/            # 外部服务客户端
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务服务
│   │   └── orchestrator/   # 调度器
│   ├── scripts/            # 数据库迁移脚本
│   └── requirements.txt    # Python依赖
├── frontend/               # 前端代码
│   ├── user/              # 用户端
│   └── admin/             # 管理端
├── docker/                # Docker配置
└── docker-compose.yml     # 服务编排
```

### 添加新的Agent

1. 创建Agent文件 `backend/app/agents/new_agent/agent.py`：

```python
from app.agents.base import BaseAgent, AgentState
from typing import AsyncIterator

class NewAgent(BaseAgent):
    agent_type = "new_agent"
    agent_name = "新Agent"
    agent_description = "Agent描述"

    async def run(self, state: AgentState) -> AgentState:
        # 实现同步执行逻辑
        pass

    async def stream(self, state: AgentState) -> AsyncIterator[str]:
        # 实现流式执行逻辑
        pass
```

1. 注册Agent到 `backend/app/agents/registry.py`
2. 添加意图分类到 `backend/app/services/intent/classifier.py`
3. 创建API路由 `backend/app/api/v1/new_agent.py`

### 代码规范

- Python代码遵循PEP 8规范
- 使用Black格式化代码
- 使用类型注解
- 编写单元测试

### 测试

```bash
# 运行测试
pytest backend/tests/

# 生成测试覆盖率报告
pytest --cov=app backend/tests/
```

## ⚡ 性能优化

### 已实现的优化

#### 1. 缓存机制

- **会话缓存**：缓存对话历史，减少数据库查询
- **摘要缓存**：缓存对话摘要，避免重复计算

#### 2. 流式响应

- 使用SSE实现流式输出
- 首字响应时间 < 500ms
- 用户体验提升60%

#### 3. 并行处理

- 简历六维度并行评估，处理时间减少67%
- 子问题并行检索，召回率提升35%

#### 4. 数据库优化

- 合理使用索引
- 异步数据库操作
- 连接池管理

### 性能指标

| 指标        | 数值      |
| --------- | ------- |
| 并发用户数     | 100+    |
| 平均响应时间    | < 2秒    |
| 首字响应时间    | < 500ms |
| 知识库文档处理能力 | 10000+  |
| 代码检查准确率   | 85%+    |
| 面试评估准确率   | 80%+    |

## ❓ 常见问题

### 1. 服务启动失败

**问题**：Docker容器启动失败

**解决方案**：

```bash
# 检查端口占用
netstat -tunlp | grep -E '3000|3001|8000|5432|6379|19530|9000'

# 查看容器日志
docker-compose logs backend

# 重新构建容器
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### 2. 模型下载失败

**问题**：HuggingFace模型下载超时

**解决方案**：

```env
# 使用镜像
HF_MIRROR_URL=https://hf-mirror.com
```

### 3. 内存不足

**问题**：服务运行时内存不足

**解决方案**：

```yaml
# docker-compose.yml 增加内存限制
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 4G
```

### 4. 向量检索无结果

**问题**：知识库检索返回空结果

**解决方案**：

1. 检查文档是否已处理完成
2. 检查Milvus服务状态
3. 检查collection是否存在数据

```bash
# 检查Milvus状态
docker-compose exec backend python -c "
from pymilvus import MilvusClient
client = MilvusClient(uri='http://milvus:19530')
print(client.list_collections())
"
```

### 5. Judge0沙箱不可用

**问题**：代码检查服务不可用

**解决方案**：

```bash
# 检查Judge0服务状态
docker-compose ps judge0

# 重启Judge0服务
docker-compose restart judge0
```

### 6. Docker Desktop与Judge0兼容性问题

**问题**：在Docker Desktop环境下，Judge0服务启动失败或运行异常

**原因**：

- Docker Desktop 4.x版本与Judge0 1.13.1存在兼容性问题
- 主要表现为容器间网络通信异常、数据库连接失败等

**解决方案**：

#### 方案1：降级Docker Desktop版本（推荐）

```bash
# 卸载当前Docker Desktop版本
# 下载并安装Docker Desktop 4.23.0或更早版本
# 下载地址：https://docs.docker.com/desktop/release-notes/

# 安装后重启Docker Desktop
# 重新启动项目
docker-compose down
docker-compose up -d
```

#### 方案2：使用Docker Engine（Linux环境）

```bash
# 在Linux服务器上使用原生Docker Engine
# 安装Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 启动服务
docker-compose up -d
```

#### 方案3：修改Judge0配置

如果必须使用较新版本的Docker Desktop，可以尝试修改docker-compose.yml：

```yaml
services:
  judge0:
    image: judge0/judge0:1.13.1
    environment:
      REDIS_HOST: redis
      POSTGRES_HOST: postgres
      # 添加以下配置
      JUDGE0_MAINTENANCE_MODE: "false"
      JUDGE0_TIME_LIMIT: "5000"
      JUDGE0_MEMORY_LIMIT: "256000"
    # 添加网络配置
    networks:
      - default
    # 添加健康检查
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:2358/status"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### 方案4：使用WSL2（Windows用户）

```bash
# 启用WSL2
wsl --install

# 安装Docker Desktop并启用WSL2后端
# Settings -> General -> Use WSL 2 based engine

# 在WSL2中运行项目
cd /mnt/d/code/XiaoyuEduAIAgent
docker-compose up -d
```

**验证Judge0是否正常**：

```bash
# 检查Judge0服务状态
docker-compose ps judge0

# 测试Judge0 API
curl http://localhost:2358/status

# 应该返回类似以下内容
# {"status":"ok","version":"1.13.1"}
```

**如果问题仍然存在**：

1. 检查Docker Desktop日志
2. 确保系统资源充足（至少8GB内存）
3. 尝试清理Docker缓存：`docker system prune -a`
4. 考虑使用虚拟机或云服务器部署

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 贡献流程

1. Fork本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

### 代码贡献规范

- 遵循现有代码风格
- 添加必要的测试
- 更新相关文档
- 确保所有测试通过

### 问题反馈

如遇到问题，请通过以下方式反馈：

1. 创建Issue，详细描述问题
2. 提供复现步骤
3. 附上相关日志

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

感谢以下开源项目：

- [FastAPI](https://fastapi.tiangolo.com/)
- [LangChain](https://www.langchain.com/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Milvus](https://milvus.io/)
- [Vue.js](https://vuejs.org/)
- [Element Plus](https://element-plus.org/)

## 📞 联系方式

- 项目主页：\[<https://github.com/XiaoYu356>]
- 问题反馈：\[GitHub Issues]
- 邮箱：[3442453092@qq.com](mailto:support@xiaoyu-edu.com)

***

**Star** ⭐ 本项目，获取最新更新！
