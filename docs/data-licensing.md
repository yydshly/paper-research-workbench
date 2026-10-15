# 数据与许可

## 数据来源与访问

- 官方 API 文档：<https://europepmc.org/RestfulWebService>
- 同一站点可读取的开发文档：<https://dev.europepmc.org/RestfulWebService>
- 官方版权说明：<https://dev.europepmc.org/Copyright>
- 实际访问 API：<https://www.ebi.ac.uk/europepmc/webservices/rest/>
- 示例全文：<https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4302049/fullTextXML>

2026-10-15 核查：版权页面明确区分可访问与可再利用，自动全文获取应使用其 REST/OAI/批量等指定服务，并逐篇遵循许可。主站 API 文档网页在本环境遇到 Cloudflare 验证，未绕过；随后通过版权页面的官方开发站链接读取了 REST 文档，确认 JSON/XML、core 元数据、检索和排序约定；实际 REST JSON/XML 接口已能访问。没有从文档页面确认统一速率上限，因此 1 请求/秒是本项目自限速，不冒称官方配额。后续实际官方限额或响应要求更严时优先遵从。

API 的使用允许与论文的版权不是同一件事。检索元数据不代表论文能翻译、重绘或再分发。按需取一篇全文，不对主网站页面做系统爬取。

官方 API 页面还要求阅读 [Europe PMC 隐私说明](https://dev.europepmc.org/doc/Privacy%20Notice%20Europe%20PMC%20Website.pdf)。检索词与调用方 IP 会经过上游服务，不能把“本地不落盘”误解为从未向数据源发送。页面提示只使用可公开的课题/关键词；不将私人或未发表研究用于示例或验收。

## 许可门禁

首期仅接受明确 CC BY（非 SA/NC/ND）或 CC0 元数据作为全文获取前置条件，随后检查 JATS `article-meta/permissions/license` 中明确的 Creative Commons 许可 URL。缺失、冲突、NC/ND/SA 或未知许可一律阻断。CC BY-SA 不是不可商业使用，但首期尚未实现其传染性义务，故保守不支持。

DESeq2：Love MI, Huber W, Anders S. *Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2*. Genome Biology (2014), DOI [10.1186/s13059-014-0550-8](https://doi.org/10.1186/s13059-014-0550-8)。实际全文许可证为 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。原文还说明数据的 CC0 条件；不能将数据条款误认作全篇文章许可。网页保留作者、题名、期刊、DOI、许可原文和链接。第三方材料单独权利如有例外仍需检查。

结构化正文经过 XML 文本提取与重排，明确标记未翻译、未模型解释。表格、数学式和图片保真有限，保留原文和图注链接，不自动重绘图像。未来翻译/图解必须标注变更和原文依据。

## 证据与隐私

来源对象保留请求 URL、UTC 采集时间、SHA-256（原始响应字节）、API 版本、来源 ID 与许可。全文额外保留原文真实锚点；无原文 ID 时只提供本地定位，不能伪造外部锚点。

用户检索与全文仅在进程内短时缓存，默认不落盘，不写请求正文日志，不提交到 Git。真实验收只使用公开 DESeq2 教学课题，仓库保存计数、ID、哈希与结果状态，不保存私人检索。浏览器阅读篮也只保存在当前页面内存。

PubMed 不是全文库。OpenAlex 可选且存在按量费用，不默认集成；Semantic Scholar 商业使用需额外许可，不默认集成。
