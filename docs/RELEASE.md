# Handouter 发布流程

当前目标版本：`0.2.0`。本文件只定义最小 release/tag 流程，不引入额外发布平台或自动部署。

## 1. RC 基线

真实课程验收开始前，先确保：

```bash
git status --short
git pull --ff-only
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
node --check zhiyun_exporter.user.js
```

并确认 GitHub Actions CI 为 green。随后将当前验收候选提交并标记：

先用 `git status --short` 人工确认没有课程私有材料或凭证，再只暂存已经审阅的源码/文档/CI 文件，不建议对验收仓库无检查地执行 `git add .`。例如本次 CI 变更可用：

```bash
git add .github/workflows/ci.yml CHANGELOG.md PROJECT_STATUS.md README.md \
  docs/ACCEPTANCE.md docs/ROADMAP.md docs/RELEASE.md
git commit -m "ci: add acceptance quality gate"
git push origin main
git tag -a v0.2.0-rc1 -m "Handouter 0.2.0 release candidate 1"
git push origin v0.2.0-rc1
```

若真实验收期间需要修复代码，使用 `v0.2.0-rc2`、`rc3` 递增，不移动已经推送的 RC tag。

## 2. 正式验收

严格按 [ACCEPTANCE.md](ACCEPTANCE.md) 执行。至少记录：

- 一次真实智云导出与 `build-asset`；
- 一门完整长课 ASR；
- 两门不同课程的 deep/summary 与可选 full Agent 输出、以及人工语义结论；
- 一次 TUI 实际运行与取消测试；
- `validate` / `validate-note` 结果。

CI green 只能证明工程回归，不等于真实验收通过。

## 3. 正式版

全部阻塞性验收项通过后：

1. 将 `PROJECT_STATUS.md` 从“0.2.0 验收候选”更新为“0.2.0 已验收”。
2. 在 `CHANGELOG.md` 中补真实验收范围和已知限制。
3. 再跑完整测试、JS 语法和 clean install。
4. 提交并推送。
5. 创建不可变正式 tag：

```bash
git tag -a v0.2.0 -m "Handouter 0.2.0"
git push origin v0.2.0
```

不要在正式 tag 后静默改历史；后续修复使用 `0.2.1`。

## 4. 不进入 0.2.0 的事项

阶段级缓存 DAG、OCR 缓存、SRT/VTT、复杂 RAG、多模型自动路由、云端账户/分享、legacy 物理迁移均不作为 `0.2.0` 发布阻塞项，除非真实验收证明其中某项是必要修复。
