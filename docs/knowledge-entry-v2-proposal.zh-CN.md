# KnowledgeEntry V2 提案

本文档提出 `make-frederica` 中 `KnowledgeEntry v2` 的一个候选结构。

目标不是立即定稿，而是先形成一份可讨论的草案，用来评估它是否适合以下三个方向：

- 今天把捕获内容存到 Notion
- 未来支持更多存储后端
- 提升后续检索、智能读取和问答能力

## 状态

讨论草案。

尚未批准实施。

## 背景

当前仓库中的持久化契约是 `KnowledgeEntry` JSON 对象。Notion 是一个重要后端，但更合适的定位应该是一个投影目标，而不是主数据模型本身。

当前 v1 结构是有意保持轻量的：

- `title`
- `source_tool`
- `tool_version`
- `model`
- `thinking_mode`
- `project`
- `session_date`
- `session_id`
- `tags`
- `reusability_score`
- `summary`
- `body_markdown`

这套结构已经足够支撑基础的内容捕获和人工浏览。但如果目标是更高质量的检索和问答，它就不算完整，尤其是在我们想回答这些问题时：

- 这个主题最后做了什么决策？
- 还有哪些问题没有定下来？
- 哪些条目仍然有效，哪些已经被替代？
- 涉及了哪些文件、仓库、工具或系统？
- 在向量检索开始之前，哪些条目本来就应该被优先召回？

## 问题陈述

如果未来的检索过度依赖自由文本 embedding，会遇到一些典型问题：

- 对文件路径、命令、模型名、版本号、ID 这类精确实体的检索精度不够
- 无法很好地按日期、状态、项目、笔记类型做过滤
- 难以区分过时知识和当前仍有效的知识
- 当一篇笔记同时包含背景、备选方案和结论时，很难稳定抽出最终答案

纯向量检索不够。纯结构化存储也不够。更合理的长期方向大概率是一个混合体系：

- 用结构化元数据做过滤和排序
- 用全文索引做精确匹配
- 用 embedding 做语义召回
- 用 rerank 做最终候选排序

这意味着 schema 需要同时保留两类东西：

- 灵活的叙述性上下文
- 少量但高价值的结构化事实

## 设计目标

v2 提案希望满足这些目标：

1. 保持一个不依赖 Notion 的稳定 canonical format。
2. 尽量兼容当前 v1 捕获格式。
3. 只新增那些对检索或问答确实有价值的字段。
4. 把存储问题和索引问题拆开处理。
5. 保持填写成本在合理范围内，确保正常对话捕获流程还能用。
6. 把迁移路径写清楚到足以支撑后续实现，而不是把关键升级决策留到编码阶段。

## 非目标

这个提案当前不打算：

- 定义一个完整的知识图谱模型
- 详细定义 chunk 级索引结构
- 要求每个后端都原生暴露全部字段
- 强行把所有有价值的信息都塞进刚性的结构字段中

## 建议方向

把 `KnowledgeEntry` 视为 canonical 的持久化笔记对象。

然后从它派生出两个附加视图：

1. 后端投影
   某个具体存储系统使用的形态，例如 Notion properties 加页面正文。

2. 检索投影
   面向索引的表示形式，用于全文检索、语义 chunking 和 rerank。

这样做的好处是，核心笔记格式可以保持稳定，而不同下游系统可以独立演进。

## 落地约束

当前仓库不是从零开始，所以 v2 提案必须服从一些现实约束：

- 当前运行时模型只接受 v1 字段
- 当前 `local_markdown` backend 只会序列化 v1 frontmatter 字段
- 当前 Notion 的 `Status` property 表示页面工作流状态，不等于 canonical 生命周期字段
- 当前模型除了可选的 `session_id` 外，没有稳定的条目标识

这意味着 v2 讨论不能只停留在“字段有没有价值”，还必须定义：

- v1 payload 如何被规范化
- 后端暂时无法原生投影的 v2 字段如何避免丢失
- canonical 生命周期状态如何和 backend 工作流状态区分
- 条目在更新、被替代、建立关联、进入索引时如何被稳定识别

## 建议的 V2 结构

```json
{
  "entry_id": "ke-20260308-7f3a2c1d",
  "title": "Short page title",
  "entry_type": "decision",
  "source_tool": "codex",
  "tool_version": "v0.111.0",
  "model": "gpt-5.4",
  "thinking_mode": "high",
  "project": "make-frederica",
  "session_date": "2026-03-08T16:20:00+08:00",
  "session_id": "session-123",
  "language": "zh-CN",
  "status": "active",
  "tags": ["notion", "rag", "architecture"],
  "topics": ["knowledge-capture", "retrieval", "schema-design"],
  "tech_stack": ["python", "notion-api"],
  "entities": ["Notion", "KnowledgeEntry", "RAG", "entrykit"],
  "artifacts": [
    "repo:make-frederica",
    "file:src/entrykit/models.py",
    "file:src/entrykit/notion.py"
  ],
  "reusability_score": 85,
  "summary": "Discussion about whether the current structured fields are sufficient for future retrieval and QA.",
  "decisions": [
    "Treat KnowledgeEntry as the canonical schema instead of using the Notion database shape as the primary model."
  ],
  "actions": [
    "Draft a v2 schema proposal.",
    "Define a Notion projection and a retrieval projection."
  ],
  "open_questions": [
    "Which fields should be mandatory versus optional?",
    "Should chunk-level metadata be derived from the note body or authored explicitly?"
  ],
  "related_entries": [],
  "body_markdown": "# Overview\n\nMain notes go here."
}
```

## 字段分组

建议中的字段大致分成四组。

### 1. 核心身份与来源信息

- `entry_id`
- `title`
- `entry_type`
- `source_tool`
- `tool_version`
- `model`
- `thinking_mode`
- `project`
- `session_date`
- `session_id`
- `language`
- `status`

这些字段回答的是一些基础问题：

- 这条笔记是什么
- 它来自哪里
- 发生在什么时间
- 现在是否仍然有效

### 2. 面向检索的元数据

- `tags`
- `topics`
- `tech_stack`
- `entities`
- `artifacts`
- `reusability_score`

这些字段的作用是在语义检索开始之前缩小候选范围，并在语义召回之后帮助排序。

### 3. 对问答最关键的结构化事实

- `summary`
- `decisions`
- `actions`
- `open_questions`
- `related_entries`

这些字段的设计目的是把用户最常想问、最常想引用的内容明确抽出来。

### 4. 完整叙述性上下文

- `body_markdown`

它仍然是主要的自由文本载体，用来保留背景、细节、例子、权衡和解释。

## 建议的字段定义

### 从 v1 保留的字段

- `entry_id`
  笔记的稳定 canonical 标识。

  价值：
  如果没有稳定 ID，`related_entries`、superseded 链接、chunk 继承、去重、原位更新这些行为都会变得含糊不清。

- `title`
  简短、可读的标题。

- `source_tool`
  捕获来源工具，例如 `codex`、`cursor` 或 `claude-code`。

- `tool_version`
  仅在工具明确展示版本时记录。

- `model`
  仅在工具明确展示模型名时记录。

- `thinking_mode`
  现有的语义标签，例如 `unknown`、`low`、`medium`、`high` 或 `extra-high`。

- `project`
  相关仓库、项目或工作流名称。

- `session_date`
  ISO 8601 日期或时间戳。

- `session_id`
  仅在运行时明确可见时记录会话 ID。

- `tags`
  自由标签。保留，但应把它视为弱结构，而不是主分类体系。

- `reusability_score`
  一个偏运营和排序用途的辅助信号，表示该笔记可能有多大复用价值。

- `summary`
  一到两句摘要，用于列表浏览和粗粒度召回。

- `body_markdown`
  主体内容。

### 新建议增加的字段

- `entry_type`
  规范化的笔记类型。

  候选值：
  - `decision`
  - `discussion`
  - `howto`
  - `debugging`
  - `meeting`
  - `proposal`
  - `reference`
  - `status_update`

  价值：
  如果系统能区分“最终决策”和“过程性讨论”，检索和问答质量通常都会明显提升。

- `language`
  笔记主语言，例如 `zh-CN` 或 `en`。

  价值：
  有利于多语言检索、排序、翻译策略和索引切分。

- `status`
  笔记生命周期状态。

  候选值：
  - `active`
  - `draft`
  - `superseded`
  - `archived`

  价值：
  这是避免旧知识误召回的一个重要保护字段。

  额外约束：
  这个字段应该表达笔记本身的知识生命周期，而不是直接复用某个后端里已经存在、但语义不同的工作流字段。

- `topics`
  一组较稳定、较规范的主题标签。

  价值：
  相比自由 `tags`，它更适合做 taxonomy、过滤和主题聚合。

- `tech_stack`
  一组该笔记主要涉及的技术栈、框架或平台。

  候选示例：
  - `python`
  - `typescript`
  - `react`
  - `fastapi`
  - `notion-api`
  - `postgres`

  价值：
  当前很多笔记都与软件开发相关。单独设一个技术栈字段，可以在不挤占 `tags`、`topics`、`entities` 的前提下，更稳定地按技术维度检索内容。

- `entities`
  这条笔记涉及的显式命名实体，例如产品、系统、服务、API、类名或重要概念。

  价值：
  提高精确匹配能力，减少查询时再做重实体抽取的压力。

- `artifacts`
  笔记中提到的具体工件引用。

  候选示例：
  - `repo:make-frederica`
  - `file:src/entrykit/models.py`
  - `cmd:entrykit capture`
  - `url:https://...`
  - `issue:123`

  价值：
  对工程知识和工作流知识来说，这是收益很高的一组字段。

- `decisions`
  会话中形成的明确决策或结论列表。

  价值：
  问答系统经常需要回答“最后结论是什么”，而不是复述完整过程。

- `actions`
  后续动作、下一步事项或实施动作列表。

  价值：
  有利于追踪“接下来要做什么”这类问题。

- `open_questions`
  尚未解决的问题列表。

  价值：
  可以让知识库回答“哪些事情还没定”，而不是误以为每篇笔记都有明确结论。

- `related_entries`
  指向其他知识条目的引用，可以是 ID，也可以是稳定 key。

  价值：
  这是向知识图关系过渡的一种轻量方式，不需要现在就上完整图模型。

## 为什么是这些字段

这个提案刻意优先选择那些对未来检索和问答最有价值的字段。

当前没有继续细化到这些字段：

- `assumptions`
- `constraints`
- `tradeoffs`
- `alternatives_considered`
- `risks`

这些字段未来也许有价值，但它们会很快把 schema 做重。当前更务实的做法是先把这些内容留在 `body_markdown` 中，等实际使用证明它们高频且必要时再抽出来。

这也是为什么当前建议的 v2 集合里不包含 `last_verified_at`。它未来也许有价值，但它默认存在一个持续复核旧笔记的流程。就这个项目当前的使用方式而言，它带来的维护负担很可能大于检索收益。

## 版本与升级策略

真正的实现问题不只是“v2 里有哪些字段”，还包括“系统如何从 v1 升到 v2，且不破坏已有捕获，也不丢数据”。

建议做法：

1. 继续沿用 `KnowledgeEntry` 这个 canonical 对象名。
2. 把 v2 设计成 v1 的向后兼容超集，而不是另起一个顶层类型名。
3. 所有被接受的 v1 payload，在进入 backend projection 前都先规范化成内部 v2 形态。
4. 在迁移窗口内，缺失的新 v2 字段应视为 absent 或 defaulted，而不是立即变成校验错误。

这意味着需要一个明确的读写契约：

- v1 输入继续可接受
- 内部处理逐步切换到规范化后的 v2 形态
- backend 可以只投影部分字段
- canonical 存储仍需要在条件允许时保留完整 v2 对象

### 为什么 `entry_id` 是基础字段

`entry_id` 不应该被看作“以后再说也行”的附加元数据，而应该视为基础设施字段。

如果没有它，系统很难正确定义这些行为：

- `related_entries` 指向另一条 note
- `status = superseded` 时指向替代条目
- chunk 记录继承稳定的父 note 引用
- 对重复捕获做去重
- 对已经存在的 durable note 做更新，而不是每次都新建

建议约束：

- 字符串类型
- 对外可以是不透明值，但一旦生成应保持稳定
- 缺失时由应用生成
- 不应该只由用户可编辑的标题直接派生

具体格式没有稳定性保证重要。

### v1 到 v2 的规范化

当系统读取一个 v1 payload 时：

- 保留全部既有 v1 字段
- 如果缺少 `entry_id`，则生成它
- 其他新 v2 字段如果不能被安全推导，就保持 absent
- 不要在没有明确策略时猜测 `entry_type`、`status` 或 `last_verified_at`

这样迁移会更保守，也能避免系统悄悄发明一些以后看起来像“权威事实”的结构化字段。

## 对索引层的含义

这个 schema 更适合支撑一个多信号混合检索链路，而不是依赖单一方法。

建议的检索层次：

1. 结构化过滤
   使用 `project`、`entry_type`、`status`、`session_date`、`topics`、`tech_stack`、`language` 等字段。

2. 全文检索
   使用 `title`、`summary`、`decisions`、`open_questions`、`artifacts`、`body_markdown` 等字段。

3. 语义检索
   对 note 的 chunk 做 embedding，而不是只对整篇 note 做 embedding。

4. Rerank
   根据 query 相关性和元数据相关性重新排序。

### note 级与 chunk 级索引

canonical schema 应保持 note 视角。

chunking 更适合被视为索引层问题，而不是主存储结构的一部分。未来的 retrieval index 可以从一条 note 派生出多个 chunk 记录，并让这些 chunk 继承父级元数据，例如：

- 父条目 ID
- `project`
- `entry_type`
- `status`
- `session_date`
- `topics`
- `tech_stack`
- `entities`

这样可以避免把索引实现细节反向污染 canonical note format。

chunk 层应继承 `entry_id` 作为稳定的父引用。一个讨论 parent-child 关系的 retrieval 设计，如果没有 canonical note ID，本质上还是未定义完整。

## Notion 投影建议

不应该要求 Notion 完整镜像 canonical schema。

这里还有一个重要落地细节：当前 Notion 数据库已经有一个 `Status` property，但它代表的是操作层工作流状态，而不是 canonical 生命周期字段。除非迁移方案明确规定，否则不应静默重定义它。

建议在 Notion property 中保留的字段：

- `Name`
- `Entry Type`
- `Source Tool`
- `Thinking Mode`
- `Project`
- `Session Date`
- `Language`
- `Lifecycle Status`
- `Tags`
- `Topics`
- `Tech Stack`
- `Entities`
- `Reusability Score`
- `Summary`

建议放在 Notion 页面正文中的部分：

- `Decisions`
- `Actions`
- `Open Questions`
- `Artifacts`
- 主体叙述内容

这样既能让 Notion 在列表浏览和过滤上好用，又不会因为 property 过多、过长、过复杂而变得笨重。

### canonical 生命周期状态 与 backend 工作流状态

这里应该显式区分两个概念：

- canonical 生命周期状态
  例如：`active`、`draft`、`superseded`、`archived`

- backend 工作流状态
  例如 Notion 当前已有的：`Captured`

建议规则：

- `KnowledgeEntry v2` 中的 `status` 表示 canonical 生命周期状态
- 迁移期间，已有的 backend 工作流字段可以继续单独存在
- 如果以后要在 Notion 里直接暴露 canonical 生命周期状态，应该通过显式 schema migration 完成，而不是隐式复用旧字段名

### 字段边界建议

为了避免 schema 变成几个相互重叠的标签篮子，面向检索的字段应尽量保持分工清晰：

- `topics`
  表示这条笔记在“讨论什么”。
  例如：`schema-design`、`retrieval`、`debugging-workflow`

- `tech_stack`
  表示这条笔记主要涉及哪些技术栈或平台。
  例如：`python`、`react`、`notion-api`

- `entities`
  表示这条笔记里出现了哪些明确命名的系统、产品、类、服务或概念。
  例如：`KnowledgeEntry`、`Notion`、`entrykit`、`FastAPI`

- `artifacts`
  表示这条笔记关联了哪些具体文件、命令、URL、仓库、issue 或其他可定位工件。
  例如：`file:src/entrykit/models.py`、`cmd:entrykit capture`

## 兼容策略

落地时应尽量兼容当前 v1 输入。

建议的兼容原则：

- 现有 v1 payload 继续有效
- 新增 v2 字段先全部作为可选字段
- 写入 Notion 时，暂时未投影到 property 的字段可以仍然保存在正文中
- 本地 JSON 应尽量保留完整 canonical object，即使某个后端无法原生存下所有字段
- 任何暂时不能原生投影 v2 字段的 backend，都必须通过无损 canonical 表示保留这些字段，或者明确声明该字段当前不支持 durable storage

这意味着需要接受三件事：

1. Canonical JSON 应该是信息最完整的表示。
2. Backend projection 可以是部分映射。
3. Retrieval index 可以包含从原始 note 派生出来的结构，而不必完全等同于原始 note。

### backend 兼容性要求

如果一个 backend 会静默丢掉新增 canonical 字段，这次迁移就是不安全的。

落到实现上，至少要满足：

- Notion 可以只把一部分 v2 字段投影成 database properties，但剩余字段需要通过页面正文或其他 durable 方式保留下来
- 如果 `local_markdown` 仍承担 durable local storage 角色，它就不能长期停留在只序列化 v1 的状态
- rollout 期间，每个可写 backend 都应被明确归类为：
  - 对 v2 无损
  - 有文档说明的部分降级
  - 尚未兼容 v2 canonical storage

## 建议的 rollout

### 第一阶段

先增加一组最小但高收益的新字段，并补齐迁移基础设施：

- `entry_id`
- `entry_type`
- `language`
- `status`
- `topics`
- `tech_stack`
- `entities`
- `decisions`
- `open_questions`
- `artifacts`

第一阶段至少要达成这些实现结果：

- v1 输入继续可解析
- 内部规范化后能够表达 v2
- 没有任何可写 backend 会静默丢失 canonical v2 字段
- `status` 的语义已经与现有 backend 工作流状态拆开

这组字段已经足以明显提升检索质量，同时不会让填写负担一下子变得太重。

### 第二阶段

再增加：

- `actions`
- `related_entries`

这组字段更偏向工作流连续性。

### 第三阶段

再根据实际使用情况判断，是否值得引入更细的结构：

- `assumptions`
- `constraints`
- `tradeoffs`
- `alternatives_considered`
- `risks`

## 待讨论问题

在真正实施前，仍然值得讨论的问题包括：

- 除了当前 v1 的必填字段外，哪些新字段真的应该设为必填？
- `entry_id` 应该在每次写入时都自动生成，还是只在条目第一次持久化时生成？
- `entry_type` 和 `status` 应该是严格枚举，还是软约束字符串加推荐值？
- `topics` 一开始要不要做集中维护，还是先允许自然生长？
- `tech_stack` 应该做集中词表，还是只给推荐值、允许开放扩展？
- `entities` 应该人工填写、LLM 抽取，还是两者结合？
- `artifacts` 应该用带前缀的字符串约定，还是更结构化的对象格式？
- 新 schema 里有多少字段值得作为 Notion property 暴露出来？
- 一条笔记在什么条件下应标记为 `superseded`，以及它是否必须指向替代条目的 `entry_id`？
- `local_markdown` 未来要不要承担无损 canonical backup 的角色，还是保留为一个有意降级的 projection？

## 建议结论

建议接受 `KnowledgeEntry v2` 的总体方向，但第一版实现要故意保持克制。

最重要的决定不是每个字段最终叫什么名字，而是先把这三层明确分开：

- canonical note schema
- backend-specific projection
- retrieval-oriented derived index

只要这个分层成立，系统就可以今天先服务 Notion，同时为未来更高质量的检索能力预留空间，而不需要到时再做一次大的 schema 重置。

在真正开始实现前，这份 proposal 至少还应明确回答四个迁移关键问题：

- `entry_id` 如何分配
- v1 payload 如何规范化成 v2
- canonical `status` 如何和 backend 工作流状态区分
- 每个可写 backend 如何避免静默丢失 v2 字段
