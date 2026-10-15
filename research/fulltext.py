import hashlib
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

from research.errors import ResearchError


def metadata_allows(license_name):
    value = re.sub(r"[\s_]+", "-", str(license_name).strip().lower())
    return bool(re.fullmatch(r"(?:cc-?by(?:-\d\.\d)?|cc0(?:-1\.0)?|cc-0)", value))


def xml_text(node):
    if node is None:
        return ""
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def parse_xml(body):
    if b"<!ENTITY" in body.upper():
        raise ResearchError("INVALID_XML", "全文含不支持的 XML 实体定义。")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ResearchError("INVALID_XML", "来源全文格式异常，无法安全解析。") from exc
    if root.tag != "article":
        raise ResearchError("INVALID_XML", "来源未返回 JATS 文章。")
    return root


def inspect_xml_license(body):
    root = parse_xml(body)
    permissions = root.find("./front/article-meta/permissions")
    licenses = permissions.findall("license") if permissions is not None else []
    if not licenses:
        raise ResearchError("LICENSE_UNKNOWN", "全文缺少明确许可，未进入阅读与加工流程。", 403)
    statement = " ".join(xml_text(n) for n in licenses)
    if re.search(r"non.?commercial|no.?derivatives|by[-\s]+(?:nc|nd|sa)", statement, re.I):
        raise ResearchError("LICENSE_RESTRICTED", "该全文许可包含当前不支持的限制，未进入加工流程。", 403)
    urls = []
    for lic in licenses:
        for node in lic.iter():
            for key, value in node.attrib.items():
                if key.endswith("href"):
                    urls.append(value)
    if any(re.search(r"/licenses/by-(?:nc|nd|sa)(?:[-/]|$)", url, re.I) for url in urls):
        raise ResearchError("LICENSE_RESTRICTED", "全文存在受限或冲突许可链接，未进入加工流程。", 403)
    # Article BY permission takes precedence over a CC0 clause applying only to data.
    for url in urls:
        if re.fullmatch(r"https?://creativecommons\.org/licenses/by/(?:[1-4]\.0)/?", url, re.I):
            return {"name": "CC BY " + re.search(r"/by/([^/]+)", url).group(1),
                    "url": url.replace("http:", "https:"), "statement": statement,
                    "scope": "article", "processingAllowed": True}
    # Accept CC0 only when it is the sole license URL and clearly applies to the article.
    if len(set(urls)) == 1 and re.fullmatch(r"https?://creativecommons\.org/publicdomain/zero/1\.0/?", urls[0], re.I):
        if not re.search(r"applies to (?:the )?data|data made available", statement, re.I):
            return {"name": "CC0 1.0", "url": urls[0].replace("http:", "https:"),
                    "statement": statement, "scope": "article", "processingAllowed": True}
    raise ResearchError("LICENSE_UNKNOWN", "全文许可不在当前明确允许的范围，未进入阅读与加工流程。", 403)


def parse_fulltext(body, pmcid):
    license_info = inspect_xml_license(body)
    root = parse_xml(body)
    article_ids = {xml_text(n).upper() for n in root.findall("./front/article-meta/article-id")
                   if n.get("pub-id-type") in ("pmc", "pmcid")}
    if pmcid not in article_ids and pmcid.removeprefix("PMC") not in article_ids:
        raise ResearchError("ARTICLE_ID_MISMATCH", "全文中的文章标识符与请求不一致。")
    parent = {child: node for node in root.iter() for child in node}
    source_url = "https://europepmc.org/articles/" + pmcid

    def original(anchor):
        return source_url + ("#" + quote(anchor) if anchor else "")

    sections = []
    abstract = root.find("./front/article-meta/abstract")
    body_node = root.find("body")
    if body_node is None:
        raise ResearchError("FULLTEXT_UNAVAILABLE", "来源没有提供结构化正文，请查看原文。", 404)
    for area, default_title in ((abstract, "Abstract"), (body_node, "正文")):
        if area is None:
            continue
        groups = {}
        for paragraph in area.iter("p"):
            node, closest_sec, skip = paragraph, None, False
            while node is not area:
                node = parent.get(node)
                if node is None:
                    break
                if node.tag in ("fig", "table-wrap"):
                    skip = True
                if closest_sec is None and node.tag == "sec":
                    closest_sec = node
            if skip:
                continue
            section = closest_sec if closest_sec is not None else area
            if section not in groups:
                sid = section.get("id", "")
                group = {"id": f"section-{len(sections)+1}", "originalId": sid,
                         "title": xml_text(section.find("title")) or default_title,
                         "sourceUrl": original(sid), "paragraphs": []}
                groups[section] = group
                sections.append(group)
            text = xml_text(paragraph)
            if not text:
                continue
            group = groups[section]
            anchor = paragraph.get("id", "") or group["originalId"]
            group["paragraphs"].append({"id": f"{group['id']}-p{len(group['paragraphs'])+1}",
                "originalId": paragraph.get("id", ""), "originalAnchor": anchor,
                "sourceUrl": original(anchor), "hasOriginalAnchor": bool(anchor), "text": text,
                "sha256": hashlib.sha256(text.encode()).hexdigest()})
    figures = []
    for fig in body_node.iter("fig"):
        fid = fig.get("id", "")
        figures.append({"id": fid or f"figure-{len(figures)+1}", "label": xml_text(fig.find("label")),
                        "caption": xml_text(fig.find("caption")), "sourceUrl": original(fid),
                        "hasOriginalAnchor": bool(fid)})
    return {"title": xml_text(root.find("./front/article-meta/title-group/article-title")),
            "license": license_info, "sections": sections, "figures": figures,
            "sourceUrl": source_url, "transformation": "JATS 纯文本提取与重排；未翻译、未使用模型解释；公式/表格/图片请对照原文。"}
