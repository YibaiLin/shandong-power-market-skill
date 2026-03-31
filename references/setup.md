# 安装与设置指南

## 前置要求

1. **uv** — Python 环境管理工具

   ```bash
   # 安装 uv（任选其一）
   pip install uv
   # 或
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # Windows PowerShell
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. **Claude Code** — 已安装并运行中

## 安装 Skill

### 通过 OpenClaw

```bash
# 在 Claude Code 中运行
/install YibaiLin/shandong-power-market-skill
```

### 手动安装

```bash
cd ~/.claude/skills
git clone git@github.com:YibaiLin/shandong-power-market-skill.git sd-power-market
```

## 项目目录设置

安装 Skill 后，首次触发时会自动询问你的数据目录。

**数据目录结构**（需要提前创建或已有）：

```
你的数据目录/
├── {YEAR}年山东电力交易每日快报/   ← 存放 PDF（不存在会自动创建）
└── output/                         ← Excel 输出（不存在会自动创建）
```

**示例**：
```
D:/power-market-data/
├── 2025年山东电力交易每日快报/
├── 2026年山东电力交易每日快报/
└── output/
```

## 首次运行

对 Claude 说任意触发语句，例如：
> "更新最新山东电力日报数据"

Skill 会自动询问数据目录路径，配置完成后立即开始工作。

配置保存位置：`~/.claude/sd-power-market.json`（可随时手动修改）

## 依赖说明

Python 依赖（首次运行时 uv 会自动安装，无需手动操作）：
- `requests >= 2.32.0`
- `pdfplumber >= 0.11.0`
- `pandas >= 2.0.0`
- `openpyxl >= 3.1.0`
