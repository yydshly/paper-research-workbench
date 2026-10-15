# GitHub Pages 研究展示

只发布 `main` 的 `/docs` 目录，包含非敏感研究、需求与来源方案；不发布应用源码或用户数据，不将静态托管误称为在线研究 API。

## 已准备

- `docs/index.html` / `site.css` / `site.js`：无需构建、无需外部依赖的研究展示。
- `docs/.nojekyll`：静态直出。
- `deploy/pages-source.json`：`build_type=legacy`，`main:/docs`。
- `scripts/preview_research.ps1`：本机 8766 预览。
- `scripts/validate_research_page.py`：六来源、过滤器、详情、桌面/390px、无后台 API/模型调用的浏览器检查。

## 资格检查

2026-10-15：仓库为 private，`has_pages=false`；读取 Pages 返回 404（尚未启用）。`GET /user` 未返回 plan 字段，因此不能把 null 当成 Free 套餐。

[GitHub 官方说明](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)列明：Free 支持公开库 Pages；私有库 Pages 需 Pro/Team/Enterprise 等支持。现有用户授权公开非敏感研究页，因此在内容检查、推送后可做一次 Pages 创建检查；不升级套餐、不改库可见性、不创建新 key。结果待记录。

```powershell
gh api --method POST repos/yydshly/paper-research-workbench/pages --input deploy/pages-source.json
```

此命令仅在当前授权与资格仍适用时执行；若返回套餐限制，不反复重试。

## 若当前私有库不支持

免费最小替代：另建一个仅含研究展示文件的公开仓库（建议 `paper-research-workbench-research`），主应用库继续私有。公开展示库将包含 `index.html`、`site.css`、`site.js`、`.nojekyll` 和说明，不复制应用、证据原始响应或任何密钥。**尚未获新建公开库授权，先报告具体错误，由父线程询问用户。**

没有成功部署就不提供推测 URL 当成可打开入口。若获准另建展示库，还需核实部署 commit SHA、Pages build 状态和真实 HTTP/浏览器入口。
