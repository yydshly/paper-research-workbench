# 架构

本轮采用 Python 标准库 HTTP 服务与原生 HTML/CSS/JS，零依赖，不需要新凭据。浏览器只访问同源 `/api`，由后端调用 Europe PMC，避免假设上游支持跨域。

`apps/workbench/server.py` 装配 HTTP 路由；`service.py` 编排；`adapters/europe_pmc.py` 负责固定官方主机、1 请求/秒、超时、最多三次请求、429/5xx 退避、TTL 缓存与同 key 并发合并；`research` 负责规范化去重、排序与许可核查。缓存上限避免无界增长。没有用户提供任意 URL 的代理接口。

检索用 `resultType=core` 与 `pageSize=50|75|100`，保留 API 结果数与候选数。排序在当前候选内进行，不声称全库排名。全文路径先查 PMCID 元数据，再检查全文许可与文章身份。仅从官方 fullTextXML 端点获取全文。

HTTP 仅监听 `127.0.0.1`；拒绝跨源 POST 和不匹配 Host，限制请求大小。静态目录限于网页目录，禁止目录遍历。网页用 DOM textContent 呈现外部内容，外链固定为 https 官方来源；CSP 不允许远程脚本。没有用户认证，因此不能直接绑定公网。

## 托管

最新顺序以 GitHub Pages 的研究展示为优先。展示文件在 `docs/index.html`、`site.css`、`site.js`，Pages 源配置为 `main:/docs`。公开非敏感研究页已获授权，源码仓库保持私有；静态页没有 `/api` 调用，不声称在 Pages 上运行 Python 后端。仓库公开性或新建公开展示库不可擅自调整。

本地与私有 GitHub 源码为当前默认。未获公共发布授权，不能以公开 Pages/Vercel URL 替代私有托管。Sites 工作流通常会创建临时源码写入凭据；当前指令禁止创建新凭据，因此不调用此操作。未创建账号/凭据、未升级套餐。后续如已有完全符合限制的私有部署通道，可按对应认证与部署协议接入；此时还需要适配本 Python 服务，不能只上传静态网页导致 API 失效。
