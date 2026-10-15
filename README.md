# 论文研究工作台 · Paper Research Workbench

独立科研论文产品：先把文献找得有理由、读得能回到原文，再积累相近研究与方法采用的证据。研究决策由人完成。

## 立即运行

需要 Python 3.10+，无第三方依赖、无 API key、无模型费用。

```powershell
python -m apps.workbench.server --port 8765
```

打开 <http://127.0.0.1:8765>。服务只监听本机。检索与全文读取需要访问 `www.ebi.ac.uk`，如果企业网络拦截，需要由用户在运行环境允许该官方域名。

## 当前交付

阶段 1 正在开发：Europe PMC 真实检索 50–100 篇、标识符去重、前 20 篇可解释词项排序、来源卡、1–3 篇阅读篮、许可门禁后的结构化开放全文阅读。没有接入真实模型，双语翻译、术语方法讲解和图解均标记未接入；不会提供伪装模型调用的预制回答。

公开教学案例是 DESeq2，DOI `10.1186/s13059-014-0550-8` / PMCID `PMC4302049`。这不是任何用户的私人或未发表课题。

## 文档入口

| 文档 | 内容 |
| --- | --- |
| [产品需求](docs/requirements.md) | 使用者、任务、范围和限制 |
| [目标与指标](docs/goals.md) | 检索与阅读特色，评分含义 |
| [竞品观察](docs/competitors.md) | 官方资料、待实测项目和差异假设 |
| [开发路线](docs/roadmap.md) | 单一 main、分阶段交付 |
| [验收标准](docs/acceptance.md) | 正常、错误、空结果、重复、许可路径 |
| [数据与许可](docs/data-licensing.md) | API 与版权分开、允许范围和归因 |
| [架构](docs/architecture.md) | 模块边界、证据协议和运行方式 |
| [模型接口](docs/model-contract.md) | 未接入状态与后续提供方契约 |
| [验证记录](evidence/README.md) | 区分模拟、真实网络与真实模型 |

## 项目结构

```text
apps/workbench/        HTTP 服务、产品编排与网页
adapters/              Europe PMC 数据源、缓存、限速与退避
research/              规范化、去重、可解释排序、许可与全文解析
evidence/              核查记录与证据元数据（不提交用户检索内容）
tests/                 单元、HTTP 集成与浏览器测试页
scripts/               真实网络验收与启动辅助
docs/                  需求、目标、竞品、路线与验收
```

## 验证

```powershell
python -m unittest discover -s tests -v
python scripts/validate_live.py
```

单元测试使用模拟传输；`validate_live.py` 会访问真实 Europe PMC 并记录时间、计数和 SHA-256。真实模型测试数量始终为 0，直到明确接入并验收。

## 研究与发布边界

相关度是可解释词项匹配分，不是正确率、质量分或创新性判断。引用关系不等于实际采用；不能据此保证原创。PubMed 元数据不代表开放全文。NC、ND 和未知许可全文不进入加工流程。不会默认接入按量付费的 OpenAlex 或需额外商业授权的 Semantic Scholar。

仓库保持私有；不为 Pages 改公开、升级套餐或开通服务。不读取、提交朋友私人信息、未发表课题、密钥或其他项目内容。代码的对外开源许可尚未决定；论文权利单独遵循原文许可。
