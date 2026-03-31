# shandong-power-market-skill

山东电力实时市场数据一键 Claude Code Skill

自动采集山东电力交易中心日报 PDF，提取实时市场用电侧小时级电价，生成按年 Excel 文件。

## 功能

- **一键更新**：说"更新最新山东电力数据"，自动下载 PDF + 提取 Excel
- **历史查询**：说"给我2024年电价数据"，直接返回已有 Excel 路径
- **强制重跑**：说"重新跑2026年"，带 `--no-skip` 全量重新运行

## 安装

### 前置要求

- [Claude Code](https://claude.ai/code) 已安装
- [uv](https://docs.astral.sh/uv/) 已安装

  ```bash
  # 安装 uv
  pip install uv
  # 或 Windows PowerShell
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

### 通过 OpenClaw 安装

```
/install YibaiLin/shandong-power-market-skill
```

### 手动安装

```bash
cd ~/.claude/skills
git clone git@github.com:YibaiLin/shandong-power-market-skill.git sd-power-market
```

## 首次使用

安装后，对 Claude 说：

> 更新最新山东电力日报数据

Skill 会询问你的数据目录路径（存放 PDF 年份文件夹的根目录），配置后立即运行。

配置保存在 `~/.claude/sd-power-market.json`，可随时修改。

## 数据目录结构

```
你的数据根目录/
├── 2025年山东电力交易每日快报/   ← PDF（自动下载）
├── 2026年山东电力交易每日快报/   ← PDF（自动下载）
└── output/
    ├── 山东电力_实时用电侧电价_2025.xlsx
    └── 山东电力_实时用电侧电价_2026.xlsx
```

## 数据来源

- 官网：https://pmos.sd.sgcc.com.cn
- 数据类型：山东电力市场运行工作日报（PDF）
- 覆盖范围：2022年至今

## 许可证

MIT
