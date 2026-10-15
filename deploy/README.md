# GitHub Pages 研究展示

当前仓库为 **public**，用户选择公开现有仓库并保留现有提交历史。没有新建仓库、重写历史、强推、付费或创建新凭据。

线上入口：<https://yydshly.github.io/paper-research-workbench/>。Pages 已启用、HTTPS enforced，首次构建于 2026-10-15 17:45 UTC 达到 `built`。最新部署提交以 Pages builds API 与最终核验回执为准。

Pages 只发布 `main:/docs`：研究、需求、数据源获取方式、检索策略和费用/许可边界。应用源码可在公开仓库查看，但 Python API 不在 Pages 上运行；真实模型调用为 0。

## 发布文件

- `docs/index.html` / `site.css` / `site.js`：研究档案，版本 `research-2026-10-15-r2`。
- `docs/.nojekyll`：静态直出，无额外依赖或构建工具。
- `deploy/pages-source.json`：`build_type=legacy`，`main:/docs`。
- `scripts/preview_research.ps1`：本机预览。
- `scripts/validate_research_page.py`：来源表、过滤器、详情与响应式检查。

## 可见性与历史

2026-10-15 已实际核实 `private=false` / `visibility=public`，用户可能已自行完成修改，因此没有重复修改。原有 4 次提交保留，原型工程提交仍为 `f103371`。

此前私有库启用 Pages 返回 HTTP 422（当前套餐不支持），该结果保留在 `evidence/pages-attempt.json`，属于历史状态，不代表公开库仍受阻。

## 部署与核验

```powershell
gh api --method POST repos/yydshly/paper-research-workbench/pages --input deploy/pages-source.json
gh api repos/yydshly/paper-research-workbench/pages
gh api repos/yydshly/paper-research-workbench/pages/builds/latest
```

仅在尚未启用时创建。网络中断或 EOF 属于不确定响应，先读取当前状态，再决定是否重试；不盲目重复创建。

核验部署终态 `built`、部署 commit 与远端 main 相同，实际 HTTPS 访问首页/CSS/JS 并与源码哈希比较，再检查桌面、390px 窄屏、导航、6项来源表、过滤器及主要官方外链。最终 API 与浏览器核验回执保存于本地 `.cache`，同时 GitHub Pages builds API 保留部署记录；避免为了把提交 SHA 写进同一提交造成自引用。

本页只展示研究方案，不执行论文检索，不代表模型解读、科研质量评测或方向查新已经完成。后续仍需用户确认数据源和公开样例后再推进功能。
