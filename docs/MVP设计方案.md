# LLM评测系统 - MVP设计方案

## 1. MVP设计原则

基于PRD和详细设计文档，MVP版本遵循以下原则：
- **核心功能优先**：聚焦评测集管理和基础评测执行，这是系统的核心价值
- **最小可行架构**：采用单体架构而非微服务，降低初期复杂度
- **快速验证**：支持CLI和Web两种使用方式，便于不同场景快速验证
- **可扩展性**：预留接口和扩展点，为后续迭代打好基础

## 2. MVP功能范围

### 2.1 核心功能（必须实现）

| 功能模块 | MVP实现内容 | 优先级 |
|---------|------------|-------|
| **评测集管理** | 测试用例CRUD、版本管理、导入导出(JSON/CSV) | P0 |
| **评分规则** | 集成DeepEval核心指标(Answer Relevancy, Faithfulness, GEval) | P0 |
| **评测执行** | 单条/批量评测执行、同步/异步执行模式 | P0 |
| **基础报告** | 评测结果展示、通过率统计、简单趋势图 | P0 |
| **质量门禁** | 基础阈值配置、通过/失败判定 | P1 |

### 2.2 暂不实现的功能（后续迭代）

- 自动化测试执行引擎（Playwright/PyTest集成）
- 场景模拟器（多轮对话、工具链路模拟）
- 可观测性平台（OpenTelemetry集成）
- 安全合规测试模块
- AI辅助能力（脚本生成、对抗样本）
- 漂移监控与告警
- 多模型投票评分
- 复杂的环境管理（K8s集成）

## 3. MVP架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面层                             │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │   Web UI     │  │   CLI工具    │                        │
│  │  (React)     │  │  (Python)    │                        │
│  └──────┬───────┘  └──────┬───────┘                        │
└─────────┼────────────────┼──────────────────────────────────┘
          │                │
          └────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                      API服务层 (FastAPI)                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │  评测集管理   │ │  评测任务    │ │  报告生成    │        │
│  │   模块       │ │   调度      │ │   模块      │        │
│  └──────────────┘ └──────┬───────┘ └──────────────┘        │
│  ┌──────────────┐        │                                │
│  │  评分规则    │        │  提交任务到Celery             │
│  │   模块       │        │                                │
│  └──────────────┘        ▼                                │
│  ┌──────────────┐ ┌──────────────────────────────┐        │
│  │  质量门禁    │ │     Celery Worker (评测执行)  │        │
│  │   模块       │ │  - 调用DeepEval              │        │
│  └──────────────┘ │  - 批量评测处理              │        │
│                   │  - 结果写入数据库            │        │
│                   └──────────────────────────────┘        │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│                      数据层                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │  PostgreSQL  │ │    Redis     │ │    MinIO     │        │
│  │  (主数据库)   │ │ (Celery队列) │ │ (报告存储)   │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 技术栈选择

| 层级 | 技术选型 | 说明 |
|-----|---------|------|
| 后端框架 | FastAPI | 高性能、自动生成API文档、异步支持 |
| 数据库 | PostgreSQL | 关系型数据存储，支持JSON字段 |
| 缓存/队列 | Redis | 评测任务队列、结果缓存 |
| 对象存储 | MinIO | 评测报告、导入文件存储 |
| 前端 | React + Ant Design | 成熟的企业级UI框架 |
| 评测核心 | DeepEval | LLM评测指标库 |
| 任务队列 | Celery | 异步评测任务执行 |
| 部署 | Docker Compose | 简化部署流程 |

### 3.3 模块职责

#### 评测集管理模块
- 评测集的增删改查
- 测试用例的版本管理（基础版本对比）
- 支持JSON/CSV格式的导入导出
- 测试用例标签管理

#### 评分规则模块
- 内置DeepEval指标配置
- 自定义GEval规则管理
- 评分参数配置（阈值、模型选择）

#### 评测任务调度模块（API层）
- 接收评测任务请求
- 任务参数校验和预处理
- 根据用例数量决定同步/异步执行
- 提交任务到Celery队列
- 提供任务状态查询接口

#### Celery Worker（评测执行层）
- 从Redis队列获取评测任务
- 调用DeepEval执行批量评测
- 支持并发控制和限流
- 实时更新任务进度
- 异常处理和重试机制

#### 报告生成模块
- 评测结果聚合和存储
- 基础报告生成（HTML/JSON）
- 通过率统计和简单趋势分析

#### 质量门禁模块
- 门禁规则配置
- 评测结果判定（通过/失败）
- CI/CD集成接口（Webhook）

## 4. 数据库设计（MVP简化版）

### 4.1 核心表结构

```sql
-- 评测集表
CREATE TABLE eval_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version INTEGER DEFAULT 1,
    tags JSONB DEFAULT '[]',
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 测试用例表
CREATE TABLE test_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID REFERENCES eval_datasets(id) ON DELETE CASCADE,
    input TEXT NOT NULL,              -- 用户输入
    expected_output TEXT,             -- 期望输出
    context TEXT,                     -- 上下文（RAG用）
    metadata JSONB DEFAULT '{}',      -- 标签、难度等
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 评分规则表
CREATE TABLE scoring_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(50) NOT NULL,   -- predefined, geval
    metric_name VARCHAR(100),         -- DeepEval指标名
    config JSONB DEFAULT '{}',        -- 配置参数
    threshold DECIMAL(5,2),           -- 通过阈值
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 评测任务表
CREATE TABLE eval_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    dataset_id UUID REFERENCES eval_datasets(id),
    status VARCHAR(50) DEFAULT 'pending', -- pending, running, completed, failed
    config JSONB DEFAULT '{}',        -- 任务配置
    result_summary JSONB DEFAULT '{}', -- 结果摘要
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- 评测结果表
CREATE TABLE eval_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES eval_tasks(id) ON DELETE CASCADE,
    case_id UUID REFERENCES test_cases(id),
    actual_output TEXT,               -- 实际输出
    metrics JSONB DEFAULT '{}',       -- 各指标得分
    overall_score DECIMAL(5,2),       -- 综合得分
    passed BOOLEAN,                   -- 是否通过
    latency_ms INTEGER,               -- 响应耗时
    error_message TEXT,               -- 错误信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 质量门禁配置表
CREATE TABLE quality_gates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    dataset_id UUID REFERENCES eval_datasets(id),
    rules JSONB DEFAULT '{}',         -- 门禁规则配置
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 5. API设计（核心接口）

### 5.1 评测集管理接口

```
GET    /api/v1/datasets              # 获取评测集列表
POST   /api/v1/datasets              # 创建评测集
GET    /api/v1/datasets/{id}         # 获取评测集详情
PUT    /api/v1/datasets/{id}         # 更新评测集
DELETE /api/v1/datasets/{id}         # 删除评测集
POST   /api/v1/datasets/{id}/import  # 导入测试用例
GET    /api/v1/datasets/{id}/export  # 导出测试用例
GET    /api/v1/datasets/{id}/cases   # 获取测试用例列表
POST   /api/v1/datasets/{id}/cases   # 添加测试用例
```

### 5.2 评测执行接口

```
POST   /api/v1/evaluate              # 创建评测任务
GET    /api/v1/evaluate/{task_id}    # 获取任务状态
GET    /api/v1/evaluate/{task_id}/results  # 获取评测结果
POST   /api/v1/evaluate/quick        # 快速评测（同步）
```

### 5.3 评分规则接口

```
GET    /api/v1/rules                 # 获取评分规则列表
POST   /api/v1/rules                 # 创建评分规则
GET    /api/v1/rules/{id}            # 获取规则详情
PUT    /api/v1/rules/{id}            # 更新规则
DELETE /api/v1/rules/{id}            # 删除规则
```

### 5.4 报告接口

```
GET    /api/v1/reports               # 获取报告列表
GET    /api/v1/reports/{id}          # 获取报告详情
GET    /api/v1/reports/{id}/download # 下载报告
```

### 5.5 质量门禁接口

```
GET    /api/v1/gates                 # 获取门禁配置
POST   /api/v1/gates                 # 创建门禁
PUT    /api/v1/gates/{id}            # 更新门禁
POST   /api/v1/gates/{id}/check      # 执行门禁检查
```

## 6. 前端交互设计

### 6.1 页面结构

```
┌─────────────────────────────────────────────────────────────┐
│  Logo    仪表盘   评测集   任务   报告   设置      [用户头像]  │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                  │
│  导航菜单  │              主内容区域                          │
│          │                                                  │
│ - 仪表盘  │                                                  │
│ - 评测集  │                                                  │
│   - 列表  │                                                  │
│   - 新建  │                                                  │
│ - 任务   │                                                  │
│   - 列表  │                                                  │
│   - 新建  │                                                  │
│ - 报告   │                                                  │
│ - 设置   │                                                  │
│          │                                                  │
└──────────┴──────────────────────────────────────────────────┘
```

### 6.2 核心页面设计

#### 仪表盘页面
- **关键指标卡片**：今日评测任务数、平均通过率、待处理任务
- **趋势图表**：近7天评测通过率趋势（折线图）
- **最近任务列表**：显示最近5个任务状态

#### 评测集列表页
- 表格展示：名称、用例数、版本、更新时间、操作
- 搜索和筛选功能
- 新建/导入/导出按钮

#### 评测集详情页
- **基本信息区**：名称、描述、标签
- **测试用例区**：
  - 表格展示所有用例（input/output预览）
  - 添加/编辑/删除用例
  - 批量导入（拖拽上传）
- **评分规则区**：配置该评测集的评分规则
- **操作区**：执行评测、导出数据

#### 任务创建页（向导式）
1. **选择评测集**：下拉选择 + 版本选择
2. **配置评分规则**：选择要使用的规则
3. **设置目标Agent**：API端点、认证信息
4. **配置执行参数**：并发数、超时时间
5. **确认提交**：预览配置并提交

#### 任务详情页
- **任务概览**：状态、进度、开始/结束时间
- **执行进度**：步骤进度条
- **结果列表**：每个用例的得分和通过状态
- **报告预览**：综合得分、通过率、失败用例分析
- **操作按钮**：重新运行、下载报告

#### 报告列表页
- 表格展示：报告名称、关联任务、生成时间、操作
- 支持按时间范围筛选
- 下载功能（HTML/JSON）

### 6.3 关键交互流程

**流程1：创建评测集并执行评测**
```
1. 用户点击"新建评测集"
2. 填写基本信息（名称、描述）
3. 添加测试用例（手动添加或批量导入）
4. 配置评分规则
5. 保存评测集
6. 点击"执行评测"
7. 配置目标Agent信息
8. 提交任务
9. 查看任务执行进度
10. 查看评测报告
```

**流程2：质量门禁检查**
```
1. 用户配置门禁规则（通过率阈值）
2. CI/CD系统调用门禁检查API
3. 系统执行评测
4. 返回检查结果（通过/失败）
5. CI/CD根据结果决定是否放行
```

## 7. CLI工具设计

### 7.1 命令结构

```bash
llm-eval [command] [options]

Commands:
  dataset    评测集管理
  evaluate   执行评测
  report     报告管理
  gate       质量门禁
  config     配置管理

Options:
  --version   显示版本
  --help      显示帮助
  --server    指定服务端地址
  --api-key   API认证密钥
```

### 7.2 常用命令示例

```bash
# 初始化配置
llm-eval config set-server http://localhost:8000
llm-eval config set-api-key xxx

# 评测集管理
llm-eval dataset list
llm-eval dataset create --name "客服场景测试" --description "测试客服Agent"
llm-eval dataset import --id <dataset-id> --file cases.json
llm-eval dataset export --id <dataset-id> --output cases.json

# 执行评测
llm-eval evaluate run --dataset <id> --target http://agent-api --output result.json
llm-eval evaluate status --task <task-id>
llm-eval evaluate results --task <task-id>

# 质量门禁
llm-eval gate check --dataset <id> --target http://agent-api --threshold 0.9
```

## 8. 部署方案

### 8.1 开发环境（Docker Compose）

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/llm_eval
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
    depends_on:
      - postgres
      - redis
      - minio

  worker:
    build: ./backend
    command: celery -A app.tasks worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/llm_eval
      - REDIS_URL=redis://redis:6379/0
      - MINIO_ENDPOINT=minio:9000
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - postgres
      - redis
      - minio
    # 资源限制，防止LLM调用过多导致内存溢出
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M

  # 可选：Flower监控面板（开发环境使用）
  flower:
    build: ./backend
    command: celery -A app.tasks flower --port=5555
    ports:
      - "5555:5555"
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - api

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=llm_eval
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### 8.2 目录结构

```
llm-evaluation-system/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI入口
│   │   ├── api/               # API路由
│   │   │   ├── datasets.py
│   │   │   ├── evaluate.py    # 评测任务调度接口
│   │   │   ├── rules.py
│   │   │   ├── reports.py
│   │   │   └── gates.py
│   │   ├── models/            # 数据模型
│   │   │   ├── database.py
│   │   │   └── schemas.py
│   │   ├── services/          # 业务逻辑
│   │   │   ├── dataset_service.py
│   │   │   ├── eval_service.py
│   │   │   └── report_service.py
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py
│   │   │   ├── celery_app.py  # Celery配置
│   │   │   └── deepeval_integration.py
│   │   └── tasks/             # Celery任务
│   │       ├── __init__.py
│   │       └── evaluation.py  # 评测执行任务
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # 前端应用
│   ├── src/
│   │   ├── components/        # 组件
│   │   ├── pages/             # 页面
│   │   ├── services/          # API服务
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── cli/                        # CLI工具
│   ├── llm_eval/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── commands/
│   ├── setup.py
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

## 9. 迭代路线图

### MVP（4-6周）
- [ ] 评测集管理（CRUD、导入导出）
- [ ] DeepEval基础指标集成
- [ ] 评测任务执行（同步/异步）
- [ ] 基础报告生成
- [ ] Web界面核心页面
- [ ] CLI工具基础功能

### v1.1（2-3周）
- [ ] 质量门禁CI/CD集成
- [ ] 自定义GEval规则编辑器
- [ ] 评测集版本对比
- [ ] 报告导出PDF/Excel

### v1.2（3-4周）
- [ ] 基础自动化测试（PyTest集成）
- [ ] 多轮对话评测支持
- [ ] 简单漂移监控

### v2.0（后续规划）
- [ ] 场景模拟器
- [ ] 可观测性平台
- [ ] 安全测试模块
- [ ] AI辅助能力
- [ ] 微服务架构拆分

## 10. 风险评估与应对

| 风险 | 影响 | 应对措施 |
|-----|------|---------|
| DeepEval集成复杂度 | 中 | 提前进行技术验证，预留缓冲时间 |
| LLM调用成本 | 中 | 支持本地模型选项，添加调用限流 |
| 并发性能问题 | 低 | 使用Celery异步处理，支持水平扩展 |
| 前端开发进度 | 中 | 优先保证API和CLI，Web界面可后续迭代 |

## 11. 成功标准

MVP版本成功的衡量标准：
1. **功能完整性**：核心评测流程跑通，支持创建-执行-查看报告完整闭环
2. **性能指标**：单条评测<5秒，批量100条<10分钟
3. **易用性**：测试工程师能在30分钟内上手使用
4. **稳定性**：连续运行7天无严重故障

---

**下一步**：如确认此设计方案，可开始：
1. 搭建开发环境（Docker Compose）
2. 实现后端API核心接口
3. 开发前端基础页面
4. 集成DeepEval评测能力
