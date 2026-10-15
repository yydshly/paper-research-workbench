import re
import subprocess
from pathlib import Path

from adapters.europe_pmc import EuropePMC
from research.errors import ResearchError
from research.fulltext import metadata_allows, parse_fulltext
from research.search import normalize_record, deduplicate, rank

ROOT = Path(__file__).resolve().parents[2]


class Workbench:
    def __init__(self, adapter=None):
        self.adapter = adapter or EuropePMC()
        try:
            self.revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                                     stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            self.revision = "uncommitted"

    def status(self):
        return {"name": "Paper Research Workbench", "version": "0.1.0", "revision": self.revision,
                "phase": "真实数据纵向切片", "model": {"status": "not_connected", "realCalls": 0},
                "provider": "Europe PMC", "rateLimit": "本项目自限速 1 请求/秒；有限重试；15 分钟内存缓存",
                "networkCalls": self.adapter.network_calls, "hosting": "local_only", "repositoryVisibility": "public"}

    def search(self, query, count=75):
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ResearchError("INVALID_INPUT", "请输入 1–500 字符的具体课题或查询式。", 400)
        if type(count) is not int or count not in (50, 75, 100):
            raise ResearchError("INVALID_INPUT", "候选数量应为 50、75 或 100。", 400)
        query = query.strip()
        raw, total, snapshot, version = self.adapter.search(query, count)
        papers = rank(deduplicate([normalize_record(p) for p in raw]), query)
        for p in papers:
            p["readingEligible"] = bool(p["pmcid"] and p["isOpenAccess"] and metadata_allows(p["license"]))
            p["sourceUrl"] = ("https://europepmc.org/articles/" + p["pmcid"] if p["pmcid"] else
                              "https://europepmc.org/article/" + p["source"] + "/" + p["sourceId"])
        return {"query": query, "requested": count, "totalHits": total, "retrieved": len(raw),
                "unique": len(papers), "duplicatesRemoved": len(raw)-len(papers),
                "shown": min(20, len(papers)), "papers": papers[:20],
                "source": {**snapshot.evidence(), "apiVersion": version},
                "rankingNote": "候选集内词项相关度：标题 60% + 摘要 40%；不是正确率、质量或创新性评分。"}

    def paper(self, pmcid):
        if not re.fullmatch(r"PMC\d{1,12}", pmcid):
            raise ResearchError("INVALID_INPUT", "需要有效的 PMCID，例如 PMC4302049。", 400)
        records, _, meta_snapshot, version = self.adapter.search("PMCID:" + pmcid, 1)
        exact = [p for p in records if str(p.get("pmcid", "")).upper() == pmcid]
        if not exact:
            raise ResearchError("FULLTEXT_UNAVAILABLE", "未找到该 PMCID 的来源记录，请查看原文。", 404)
        metadata = normalize_record(exact[0])
        if not metadata["isOpenAccess"] or not metadata_allows(metadata["license"]):
            raise ResearchError("LICENSE_NOT_ALLOWED", "元数据许可未知或含当前不支持的限制，未下载全文。请到来源核对。", 403)
        snapshot = self.adapter.full_text(pmcid, lambda body: parse_fulltext(body, pmcid))
        article = parse_fulltext(snapshot.body, pmcid)
        return {"paper": metadata, **article, "source": {**snapshot.evidence(), "apiVersion": version},
                "metadataSource": meta_snapshot.evidence(), "modelStatus": "not_connected"}

    def explain(self):
        raise ResearchError("MODEL_NOT_CONNECTED", "真实模型未接入。双语、术语/方法和图解暂不可用，没有生成解释。", 503)
