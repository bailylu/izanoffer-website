# izanoffer

> **看得懂官网的 AI 留学顾问** —— 中国学生能直接用的留学专用AI大模型

---

## 是什么

izanoffer 是一个垂直留学的 AI 对话产品。两个核心能力合二为一：

1. **AI 顾问** — 基于知识库给选校 / 申请 / 文书 / 签证 / 海外生活全程建议
2. **官网解读** — 学生提问，AI 自动找到对应学校 / 政府官网，翻译 + 总结 + 对照学生背景解读

**核心交互（C3）**：左侧官网原文 + 右侧 AI 对话，划词即可让 AI 解读任意段落。

---

## 仓库结构

```
izanoffer/
├── README.md                            # 本文件
├── .gitignore                           # 忽略系统/IDE/敏感信息
├── docs/                                # 产品文档
│   ├── product-plan-v0.3.md             ← 当前产品方案（团队改这个）
│   ├── product-plan-v0.3.docx           ← Word 导出版（分发用）
│   └── decisions/                       # 决策记录（每个决定一个 .md）
│       ├── README.md                    # 决策记录使用说明
│       ├── _template.md                 # 新决策模板
│       ├── 0001-c3-interaction-model.md # 决定：核心交互模型
│       └── 0002-brand-name-izanoffer.md # 决定：品牌名
├── prototypes/                          # 交互原型（HTML）
│   ├── C3-prototype.html                ← 当前主原型
│   ├── server.py                        ← 本地真实抓取 + 测试账号服务
│   ├── trending.json                    ← 首页热门问题 / 官网入口数据
│   ├── users.json                       ← 本地测试账号数据（仅原型）
│   ├── C-history.html                   # 历史版本（双栏对话探索）
│   └── C2-history.html                  # 历史版本（双语原文探索）
└── research/                            # 市场与竞品调研
    └── market-and-competitor-research.docx
```

---

## 当前状态

- ✅ 行业 + 竞品调研完成
- ✅ 产品定位明确（v0.3）
- ✅ 核心交互 C3 设计 + 原型跑通
- ✅ 32 个技能包按 Pattern 重新分类
- ✅ 边界模型（绿/黄/红 三圈）+ 拒绝话术
- ✅ 准确性架构（RAG + 五层防御）
- ✅ 模型与计费策略
- ✅ 品牌名定（izanoffer）
- ⬜ 视觉识别系统（Logo / 配色 / Voice）
- ⬜ 工程实施方案（技术栈 / 数据 pipeline）
- ⬜ 用户访谈（15-20 个目标用户验证）
- ⬜ BP（融资用）

---

## 新成员快速上手

**按这个顺序看，1 小时进入状态：**

1. `docs/product-plan-v0.3.md` —— 完整产品方案（30 分钟）
2. 浏览器打开 `prototypes/C3-prototype.html` —— 体验核心交互（试试划词解读、URL 粘贴）
3. `docs/decisions/` —— 看历史决定，了解为什么是现在这样
4. `research/market-and-competitor-research.docx` —— 行业全景与对手

**做产品决策前**：先翻 `docs/product-plan-v0.3.md` 第 10.3 节（决策记录链）+ `docs/decisions/` 里的每篇记录。避免重复讨论已决定的事。

---

## 2026-06-26 原型进展

今天把 `prototypes/C3-prototype.html` 从静态交互稿推进成可真实测试的 MVP 原型：

- **定位文案**：首屏改为 `IZANOFFER · 你的 AI 留学顾问`，强调像中介一样拆解申请要求，但每一步基于官网。
- **官网内容阅读器**：新增 `prototypes/server.py`，支持 `POST /api/extract` 真实抓取学校官网正文；左侧显示中英双语、可引用段落、可划词解读。
- **AI 顾问回答结构**：右侧回答统一为 `结论 / 官网依据 / 对你的影响 / 下一步`，引用左侧 P1/P2/P3 原文。
- **学生画像引导**：用户开始提问后进入聊天式引导，收集学校、专业、成绩、语言、目标国家、预算、动机偏好；可跳过。
- **账号与画像**：接入 Clerk 的前端骨架；未配置 Clerk 时提供本地测试账号系统。画像保存到 Clerk metadata；本地测试时保存到 `users.json`。
- **个人信息中心**：新增账号状态、学生画像、重新补充画像、账号设置入口。
- **动态热门入口**：首页 `大家常问` 和 `常用官网入口` 改为从 `GET /api/trending` 读取，数据源在 `prototypes/trending.json`。

本地真实测试：

```bash
cd prototypes
python3 server.py 5173
```

测试期低成本 AI：

```bash
cd prototypes
MINIMAX_API_KEY=你的_minimax_key python3 server.py 5173
```

当前原型支持 `MINIMAX_API_KEY`、`OPENROUTER_API_KEY`、`OPENAI_API_KEY` 三种启动方式。为了先把本地和线上流程跑通，测试期可以优先使用 MiniMax；正式计费和上线前，需要切回 OpenRouter 上的 Claude Opus 4.8，并重新核对模型价格、余额和扣费策略。

如果只是验证产品流程、不想消耗任何模型额度，可以使用模拟模式：

```bash
cd prototypes
AI_MOCK_MODE=1 python3 server.py 5173
```

`AI_MOCK_MODE=1` 会显示为 `MiniMax Mock`，返回本地模拟回答，不调用外部模型、不扣费。正式上线前必须关闭该模式。

打开：

```text
http://127.0.0.1:5173/C3-prototype.html
```

本地测试管理员账号：

```text
邮箱：451248901@qq.com
密码：123456
角色：admin
```

如果要测试 Clerk：

```bash
cd prototypes
CLERK_PUBLISHABLE_KEY=pk_test_xxx python3 server.py 5173
```

注意：`file://.../C3-prototype.html` 只能看静态页面，真实抓取、动态热门数据、登录接口都需要通过 `http://127.0.0.1:5173/C3-prototype.html` 访问。

---

## 2026-06-29 本次同步说明

这次主要把 C3 原型从“静态演示”推进到更接近产品闭环的版本，方便团队继续讨论和测试。

### 主要改动

- **学生端模型选择移除**：前台不再让用户选择模型，避免用户看到 OpenRouter 模型列表和成本信息。后端统一决定使用哪个模型。
- **AI Provider 策略**：`server.py` 支持 `MINIMAX_API_KEY`、`OPENROUTER_API_KEY`、`OPENAI_API_KEY`，并新增 `AI_MOCK_MODE=1`。
- **测试期 Mock AI**：当前可用 `AI_MOCK_MODE=1` 跑通流程，显示为 `MiniMax Mock / MiniMax-M2.5`。它会根据问题、学生画像和左侧官网段落生成动态模拟回答，但不调用真实模型、不扣费。
- **正式模型提醒**：正式上线前必须关闭 Mock，切回 OpenRouter 上的 Claude Opus 4.8，并重新验证余额、价格、token 扣费和回答质量。
- **OpenRouter 计费逻辑**：后端按模型 token 成本、Google Finance USD/CNY 汇率、平台倍率计算用户侧扣费。汇率会缓存，Google 抓不到时回退到默认值。
- **后台设置弹窗**：新增 `prototypes/admin.html`，用于账号信息、留学信息、支付、账单、用量、模型摘要等原型展示。现在是弹窗内嵌，不单独跳页面。
- **账户与支付原型**：账号信息支持编辑显示名称；支付页保留微信/支付宝入口占位；账单只显示充值记录，不把模型扣费混在充值账单里。
- **目标国家动态画像**：右侧聊天框不只是问答入口，也会识别用户新的目标国家。例如用户说“我要申请意大利”，画像中的 `目标国家` 会即时更新。
- **官网国家强约束**：如果用户目标国家和左侧官网国家不一致，AI 会先提醒“当前官网依据不匹配”，不会继续拿旧官网给新目标国家做判断。
- **QS 学校入口**：左侧空状态会根据用户目标国家显示该国家 QS 高排名代表院校官网入口。没显示的学校，用户可以直接在右侧输入学校名、专业名或官网 URL。
- **安全边界文案**：AI system prompt 已加入限制，违法犯罪和中国政治相关内容不回答、不展示。

### 当前测试方式

推荐先用 Mock 模式跑产品流程：

```bash
cd prototypes
AI_MOCK_MODE=1 python3 server.py 5173
```

打开：

```text
http://127.0.0.1:5173/C3-prototype.html
```

可以测试：

1. 登录本地测试账号
2. 填写或跳过学生画像
3. 在右侧输入“我要申请英国/意大利/澳洲”
4. 左侧是否切换为对应国家 QS 学校入口
5. 点击学校官网，是否抓取官网正文
6. 右侧提问“申请要求 / 截止日期 / 材料清单 / 费用预算”
7. 如果左侧官网国家和目标国家不一致，是否出现纠错提醒

### 上线前必须处理

- 关闭 `AI_MOCK_MODE=1`
- 使用真实 `OPENROUTER_API_KEY`
- 默认模型切回 Claude Opus 4.8 或正式选定模型
- 确认 OpenRouter credits 充足
- 确认用户侧价格展示不是成本价
- 接入真实 Clerk 登录与真实支付
- 不要把任何 API Key 写入仓库

---

## 协作约定

- **决策要写下来**：任何方向性决定（用什么模型、定价、配色、技术栈）都在 `docs/decisions/` 里开一个文档记下来。复制 `_template.md` 写。
- **代码与文档同 repo**：产品方案、设计稿、知识库 schema、爬虫脚本、前后端代码都在同一个 repo。
- **分支策略**：`main` 永远是可发布状态；新功能开 `feature/xxx` 分支；改完 PR 给对方 review。
- **敏感信息永远不 commit**：API Key / 密码 / 数据库连接串放 `.env`，`.gitignore` 已经处理。

---

## 关于品牌名

**izanoffer** —— 全小写，类似 `vercel` / `supabase` / `linear` 的现代科技品牌风格。

- 中文场合：izanoffer
- 英文句首：Izanoffer
- 完整描述：izanoffer · AI 留学顾问

详见 `docs/decisions/0002-brand-name-izanoffer.md`。

---

*v0.3 · 2026 年 6 月*
