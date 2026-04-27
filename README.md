# Data Zentao 禅道数据助手

一个面向 Claude Code / Codex 的禅道数据查询和报告生成工具。

克隆此仓库后，可以在 Claude Code 或 Codex 中用自然语言直接查询禅道数据、归纳进展、生成报告：

```text
平台项目这个版本产生的延期情况
未完成的待办有哪些
这个版本还有哪些需求没有完成？
帮我总结平台部当前版本的交付风险
现在线上 Bug 情况怎么样？
某个人手上还有哪些任务？
帮我生成本周项目推进汇总
帮我看一下需求池里哪些需求长期没有推进
```

这个仓库的定位不是固定报表脚本，而是一层禅道数据工具：

```text
自然语言问题
-> Claude / Codex 理解意图
-> data-zentao 查询禅道数据库
-> AI 总结、归纳、生成报告
```

日常使用时不需要打开禅道，也不需要手写查询语句。AI Agent 会根据问题查结构、取数据、做汇总。

---

## 这个仓库包含什么

```text
data-zentao/
│
│  ── 给 AI Agent 读的文件 ────────────────────────────────────────
├── AGENTS.md               Codex 工作指引
├── CLAUDE.md               Claude Code 工作指引
├── docs/
│   └── ...                  禅道字段说明和查询参考
│
│  ── 给用户看的文件 ───────────────────────────────────────────────
├── README.md               本文件
├── pyproject.toml          Python 安装配置
├── .env.example            数据库配置模板
├── .gitignore              Git 排除配置
│
│  ── 核心代码 ────────────────────────────────────────────────────
└── src/data_zentao/
    ├── cli.py              命令入口：check / ask / chat / schema / query / 报表命令
    ├── config.py           本地环境变量配置
    ├── db.py               数据库连接
    ├── repository.py       禅道数据查询工具
    ├── reports.py          报告渲染
    ├── router.py           常见问题快捷路由
    └── formatting.py       Markdown / JSON 输出工具
```

以下文件只保存在使用者本机，不进 git：

```text
data-zentao/
├── .env                    数据库连接信息
└── reports/                后续生成的本地报告
```

---

## 前提条件

- Claude Code 或 Codex 已安装并登录，至少其一
- Python 3.10 或以上
- 网络能访问禅道数据库
- 已有数据库账号

---

## 安装步骤（Mac）

### 第一步：克隆仓库

```bash
git clone <repo-url> data-zentao
cd data-zentao
```

如果是本机已有目录，直接进入仓库：

```bash
cd data-zentao
```

### 第二步：创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 第三步：安装工具

```bash
pip install -e .
```

### 第四步：配置数据库

```bash
cp .env.example .env
```

然后编辑 `.env`，填入数据库连接信息：

```text
ZENTAO_DB_HOST=
ZENTAO_DB_PORT=3306
ZENTAO_DB_USER=
ZENTAO_DB_PASSWORD=
ZENTAO_DB_NAME=zentao
```

### 第五步：验证连接

```bash
data-zentao check
```

看到类似输出即代表可用：

```text
数据库连接正常。
数据库：zentao
基础表数量：233
用户数量：233
```

### 第六步：运行完整自检

```bash
data-zentao doctor
```

这个命令会检查数据库连接、核心表字段、当前版本定位，以及需求、任务、Bug、待办、举措、日报、周报等能力的数据通路。

只要没有 `FAIL`，就代表安装和基础数据读取通过。若出现 `WARN`，通常表示当前样本数据为空，需要结合实际问题再查。

---

## Claude / Codex 使用方式

打开这个仓库目录后，Claude Code 会读取 `CLAUDE.md`，Codex 会读取 `AGENTS.md`。

可以直接提问：

```text
平台项目这个版本产生的延期情况
帮我总结当前版本的风险
查一下某位同事相关的待办和任务
需求池里最近新增了哪些需求？
本周有哪些 Bug 值得关注？
帮我出Bug界定报告
帮我出版本复盘
```

AI Agent 的工作方式是：

```text
先理解问题
-> 用 data-zentao schema 定位表和字段
-> 用 data-zentao query 查询数据
-> 用中文输出结论、明细、风险和建议
```

`data-zentao` 是取数和报表工具，不替代 AI 判断。最终给用户看的回复应由 Claude/Codex 基于查询结果再做总结、判断和归纳，不建议直接把命令输出原样当最终结论。

如果问题属于已封装的高频场景，Agent 会优先使用快捷命令：

```bash
data-zentao ask "未完成的待办有哪些"
data-zentao ask "平台项目这个版本产生的延期情况"
```

如果问题是新的、不固定的，Agent 会自由组合查询：

```bash
data-zentao schema --columns 延期
data-zentao schema --table zt_task
data-zentao query --sql "SELECT id, name, status FROM zt_task WHERE deleted='0' LIMIT 20"
```

---

## 当前支持的能力

| 能力 | 状态 | 说明 |
|---|---|---|
| 禅道自由问答 | 可用 | 在 Claude/Codex 中通过 `schema + query` 查询数据 |
| 数据汇总归纳 | 可用 | 根据查询结果做中文总结、风险判断、结构化报告 |
| 查需求状态 | 已封装 | 按需求 ID 或标题关键词查询需求池状态、标准需求阶段、版本、任务、负责人 |
| 查版本推进 | 已封装 | 当前版本定位、任务分布、延期、Bug、需求概况 |
| 查个人任务 | 已封装 | 按姓名/账号查询任务、Bug、待办 |
| 查部门风险 | 已封装 | 按部门关键词聚合任务逾期和 Bug 风险 |
| 查 Bug 复盘 | 已封装 | 当前版本 Bug 汇总、归属分布、原因和部门复盘信息 |
| Bug界定 | 已封装 | 复盘前预分类材料：疑似非Bug、外部Bug、内部Bug、低质量任务 |
| 版本复盘 | 已封装 | 正式复盘材料：Bug复盘、版本趋势、需求和延期分析 |
| 查待办举措 | 已封装 | 待办 `zt_to_do_list` 和举措 `zt_measures_management` |
| 待办查询 | 已封装 | 未完成、进行中、未开始、全部待办 |
| 今日报告 | 已封装 | 对齐旧版日报：当前版本发布核查、今日推进、延期关注、Bug、下一版本准备 |
| 周汇总 / 周报 | 已封装 | 对齐旧版周报：默认汇总平台项目和游戏项目，生成效能周汇总/效能周报 |
| 单项目周报 | 已封装 | 按指定项目输出本周任务流转、Bug 流转、延期风险、待办 |
| 平台当前版本定位 | 已封装 | 默认按当天日期定位平台部当前 sprint |
| 平台版本延期报告 | 已封装 | 当前逾期未完成、已完成延期、延期原因填写情况 |
| 表结构查看 | 已封装 | `schema --table / --columns / --search` |
| 数据查询 | 已封装 | `query --sql` |
| 创建需求 / 生成任务 / 改状态 | 规划中 | 后续可接入确认、日志和写入工具 |

---

## 典型问题

### 项目和版本

```text
平台项目当前版本是哪一个？
这个版本还有几天发布？
这个版本任务完成情况如何？
这个版本有哪些延期？
这个版本交付风险是什么？
```

### 需求

```text
需求池里最近新增了哪些需求？
哪些需求还没有进入版本？
某个版本包含哪些需求？
哪些需求已经生成任务？
哪些需求计划版本和实际版本不一致？
```

### 任务和人员

```text
某个人手上还有哪些任务？
谁的剩余工时最多？
哪些任务已经逾期？
哪些任务已完成但晚于截止时间？
某个部门当前任务压力如何？
```

### Bug 和质量

```text
现在线上 Bug 情况怎么样？
这个版本有哪些高优 Bug？
哪些 Bug 还没有解决？
Bug 主要集中在哪些部门？
帮我生成 Bug 复盘要点
```

### 待办和举措

```text
未完成的待办有哪些？
进行中的待办有哪些？
AI 专项还有哪些未完成？
某个责任人的待办有哪些？
哪些待办已经过期？
```

### 项目报告

```text
帮我生成今天的平台项目日报
帮我生成本周项目推进汇总
帮我总结当前版本的延期原因
帮我输出当前版本风险摘要
帮我把当前版本问题按部门归纳
```

---

## 命令行工具说明

### 检查连接

```bash
data-zentao check
```

### 自然语言快捷问答

```bash
data-zentao ask "未完成的待办有哪些"
data-zentao ask "平台项目这个版本产生的延期情况"
data-zentao ask "查需求状态 VIP 权益功能优化"
data-zentao ask "查一下某位同事相关的待办和任务"
data-zentao ask "查部门风险 产品部"
data-zentao ask "帮我出Bug界定报告"
data-zentao ask "帮我出版本复盘"
```

说明：`ask` 目前是常见问题快捷路由。更开放的问题由 Claude/Codex 完成理解，工具层负责查数据。

### 进入简单对话模式

```bash
data-zentao chat
```

### 查看表结构

```bash
data-zentao schema --search task
data-zentao schema --table zt_task
data-zentao schema --columns 延期
```

### 查询数据

```bash
data-zentao query --sql "SELECT id, name, status FROM zt_task WHERE deleted='0' LIMIT 20"
```

返回 JSON：

```bash
data-zentao query --format json --sql "SELECT id, name FROM zt_project LIMIT 10"
```

### 高频报表

```bash
data-zentao todos --status unfinished
data-zentao doctor
data-zentao todos --status ongoing
data-zentao demand-status "VIP 权益功能优化"
data-zentao person-tasks "person_account"
data-zentao dept-risk "PHP1"
data-zentao measures
data-zentao bug-review
data-zentao bug-boundary
data-zentao version-review
data-zentao daily-report
data-zentao weekly-summary
data-zentao weekly-report
data-zentao platform-delay
data-zentao version-delay --version-id 405
```

说明：`weekly-summary` 是旧版周报能力，默认生成 `效能周汇总` 和 `效能周报` 两份文件；`weekly-report` 是单项目周报，适合只看一个项目时使用。

---

## 常见问题

**Q：这个工具是不是只能查 README 里列出来的几个问题？**

不是。README 里列的是典型问题。新的问题可以由 Claude/Codex 先查表结构，再查询数据，最后总结结果。

**Q：为什么还保留 `todos`、`platform-delay` 这些固定命令？**

因为这些是高频问题，封装后更稳定、更快，也能避免每次都重新推理查询方式。自由查询和固定工具会并存。

**Q：能不能直接创建需求、生成任务？**

可以作为后续能力接入。第一版先以查询、总结和报告为主。

**Q：安装后还需要登录禅道吗？**

不需要登录禅道网页。这个工具直接读取数据库；使用者需要配置可访问数据库的 `.env`，并且本机网络要能连到数据库。

**Q：最终输出是 AI 判断过的吗？**

通过 Claude/Codex 使用时，最终回复必须由 AI 基于工具返回的数据再判断、归纳和解释。直接在终端运行 `data-zentao` 得到的是数据材料或报告草稿，不等同于完整 AI 结论。

**Q：报告数据不对怎么办？**

先让 AI 说明它用了哪些表、哪些字段、什么筛选条件。必要时用 `schema --table` 和 `query --format json` 复核原始数据。

**Q：工具更新怎么同步？**

```bash
cd data-zentao
git pull
pip install -e .
```

---

## 版本历史

| 版本 | 日期 | 说明 |
|---|---|---|
| v0.6 | 2026-04-27 | 对齐旧版日报、双项目周汇总、Bug界定和版本复盘的输出结构与文件命名 |
| v0.5 | 2026-04-27 | 同步旧版日报下一版本预览、Bug界定、版本复盘能力，并修正需求/任务截止口径 |
| v0.4 | 2026-04-27 | 新增 `doctor` 安装自检，明确最终输出需经 AI 判断 |
| v0.3 | 2026-04-27 | 补齐需求状态、个人任务、部门风险、Bug 复盘、待办举措、日报、周报等核心能力 |
| v0.2 | 2026-04-27 | README 按自由对话入口重写，新增 `schema` 和 `query`，支持 Agent 查询禅道数据 |
| v0.1 | 2026-04-27 | 初始化项目，支持待办查询、平台当前版本定位、平台版本延期报告 |
