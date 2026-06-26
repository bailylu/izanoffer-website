# izanoffer

> **看得懂官网的 AI 留学顾问** —— 中国学生能直接用的留学专用 Claude

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
