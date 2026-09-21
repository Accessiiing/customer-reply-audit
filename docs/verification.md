# 验证记录

> 本文只记录实际执行过的验证；未执行的真实 Jev 运行不写成通过。

## 2026-09-21 16:15 +08:00 · 远端干净克隆

| 项目 | 结果 |
|---|---|
| 仓库 | `https://github.com/Accessiiing/customer-reply-audit.git` |
| 分支 | `feat/jev-system-one` |
| 验证提交 | `53960e1` |
| 克隆 | ✅ `--single-branch` 成功 |
| Python | 3.12.2（由 uv 选择） |
| `uv sync --extra dev` | ✅ 20 个依赖安装成功 |
| `python -m pytest -q` | ✅ 23 passed |
| 跟踪文件密钥模式扫描 | ✅ 未发现 `apikey_`、`sk-`、`gh*_` 形式的凭证 |

## 本地运行证据

| 项目 | 结果 |
|---|---|
| 原始回复附件 | ❌ 合法 JSON 后存在 27 个尾部字符；源 SHA-256 已记录于决策档案 |
| 显式派生 | ✅ 20 条；源文件未修改；源/派生/尾部哈希已写入 ignored manifest |
| V1 规则基线 | ✅ run `20260921T080717Z-a0f055b2`；TP=18、FP=1、TN=1、FN=0 |
| 无 Jev key 的 benchmark | ✅ 退出码 2；在写部分三版结果前失败 |
| V2/V3 官方 Jev 全量运行 | ⏳ 未执行；不能形成最终 winner |
