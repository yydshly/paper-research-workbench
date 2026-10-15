import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError

from adapters.europe_pmc import EuropePMC
from apps.workbench.service import Workbench
from research.errors import ResearchError
from research.fulltext import metadata_allows, inspect_xml_license, parse_fulltext
from research.search import normalize_record, deduplicate, rank


def xml(license_url="https://creativecommons.org/licenses/by/4.0/", pmcid="PMC4302049", body=True):
    content = '<body><sec id="S1"><title>Methods</title><p>First <italic>important</italic> paragraph.</p><sec id="S2"><title>Nested</title><p id="P2">Second paragraph.</p></sec><fig id="F1"><label>Figure 1</label><caption><p>Original caption.</p></caption></fig></sec></body>' if body else ''
    return (f'<article xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><article-id pub-id-type="pmc">{pmcid}</article-id><title-group><article-title>Example</article-title></title-group><permissions><license><license-p>Article license <ext-link xlink:href="{license_url}">link</ext-link></license-p></license></permissions></article-meta></front>{content}</article>').encode()


def raw(license_name="cc by", pmcid="PMC4302049"):
    return {"id": "25516281", "source": "MED", "title": "DESeq2 RNA-seq", "abstractText": "differential expression",
            "doi": "10.1186/s13059-014-0550-8", "pmcid": pmcid, "isOpenAccess": "Y", "license": license_name}


def response(records=None):
    records = [raw()] if records is None else records
    return json.dumps({"version": "fixture", "hitCount": len(records), "resultList": {"result": records}}).encode()


class SearchTests(unittest.TestCase):
    def test_transitive_dedup_and_normalized_doi(self):
        rows = [normalize_record({"id": "1", "source": "MED", "doi": "https://doi.org/10.1/ABC"}),
                normalize_record({"id": "2", "source": "PMC", "pmcid": "PMC1"}),
                normalize_record({"id": "3", "source": "MED", "doi": "10.1/abc", "pmcid": "PMC1"})]
        result = deduplicate(rows)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["mergedCount"], 3)
        self.assertEqual(result[0]["doi"], "10.1/abc")

    def test_missing_identifiers_do_not_merge_by_title(self):
        self.assertEqual(len(deduplicate([normalize_record({"title": "same"}), normalize_record({"title": "same"})])), 2)

    def test_score_has_checkable_components_no_citation_bonus(self):
        a = normalize_record({"title": "DESeq2", "abstractText": "RNA-seq", "citedByCount": 1})
        b = normalize_record({"title": "unrelated", "citedByCount": 999999})
        ranked = rank([b, a], "TITLE:DESeq2 AND RNA-seq")
        self.assertEqual(ranked[0]["relevance"]["score"], 50)
        self.assertEqual(ranked[0]["relevance"]["titlePoints"], 30)
        self.assertEqual(ranked[0]["relevance"]["abstractPoints"], 20)
        self.assertEqual(ranked[1]["relevance"]["score"], 0)


class LicenseTests(unittest.TestCase):
    def test_metadata_allowlist(self):
        for value in ["cc by", "CC-BY", "cc by 4.0", "cc0"]:
            self.assertTrue(metadata_allows(value), value)
        for value in ["unknown", "cc by-nc", "cc by-nd", "cc by-sa", "", "not cc by"]:
            self.assertFalse(metadata_allows(value), value)

    def test_sections_no_double_count_captions_and_original_anchors(self):
        article = parse_fulltext(xml(), "PMC4302049")
        self.assertEqual(article["license"]["name"], "CC BY 4.0")
        self.assertEqual(len(article["sections"]), 2)
        self.assertEqual(sum(len(s["paragraphs"]) for s in article["sections"]), 2)
        self.assertEqual(article["sections"][0]["paragraphs"][0]["originalAnchor"], "S1")
        self.assertEqual(article["figures"][0]["caption"], "Original caption.")

    def test_restricted_and_unknown_xml(self):
        for url in ["https://creativecommons.org/licenses/by-nc/4.0/", "https://creativecommons.org/licenses/by-nd/4.0/", "https://example.org/unknown"]:
            with self.assertRaises(ResearchError) as ctx:
                inspect_xml_license(xml(url))
            self.assertEqual(ctx.exception.status, 403)

    def test_identity_and_missing_body(self):
        with self.assertRaises(ResearchError) as ctx:
            parse_fulltext(xml(pmcid="PMC1"), "PMC4302049")
        self.assertEqual(ctx.exception.code, "ARTICLE_ID_MISMATCH")
        with self.assertRaises(ResearchError) as ctx:
            parse_fulltext(xml(body=False), "PMC4302049")
        self.assertEqual(ctx.exception.code, "FULLTEXT_UNAVAILABLE")

    def test_data_cc0_not_promoted_to_article_permission(self):
        data_only = xml("https://creativecommons.org/publicdomain/zero/1.0/").replace(b'Article license', b'This waiver applies to the data made available')
        with self.assertRaises(ResearchError):
            inspect_xml_license(data_only)

    def test_invalid_and_entity_xml_rejected(self):
        for value in [b'<article>', b'<!DOCTYPE a [<!ENTITY x "test">]><article/>']:
            with self.assertRaises(ResearchError):
                inspect_xml_license(value)

    def test_conflicting_license_links_rejected(self):
        value = xml().replace(b'</license-p>', b'<ext-link xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="https://creativecommons.org/licenses/by-nc/4.0/">other terms</ext-link></license-p>')
        with self.assertRaises(ResearchError) as ctx:
            inspect_xml_license(value)
        self.assertEqual(ctx.exception.code, 'LICENSE_RESTRICTED')


class AdapterTests(unittest.TestCase):
    def test_cache_and_singleflight(self):
        entered, release = threading.Event(), threading.Event()
        calls = []

        def transport(url):
            calls.append(url); entered.set(); release.wait(2); return response()

        adapter = EuropePMC(transport=transport, interval=0)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(adapter.search, "DESeq2", 75)
            self.assertTrue(entered.wait(1))
            second = pool.submit(adapter.search, "DESeq2", 75)
            release.set()
            self.assertEqual(first.result()[1], second.result()[1])
        self.assertTrue(adapter.search("DESeq2", 75)[2].cache_hit)
        self.assertEqual(len(calls), 1)

    def test_ttl_expiry_and_cache_bound(self):
        now = [0.0]
        adapter = EuropePMC(transport=lambda _: response(), interval=0, ttl=10, clock=lambda: now[0])
        adapter.search("q", 50); now[0] = 11; adapter.search("q", 50)
        self.assertEqual(adapter.network_calls, 2)
        for i in range(30): adapter.search(str(i), 50)
        self.assertLessEqual(len(adapter.cache), 24)

    def test_rate_limit_and_retry_after(self):
        sleeps, starts, now = [], [], [0.0]
        def sleeper(delay): sleeps.append(delay); now[0] += delay
        def transport(url):
            starts.append(now[0])
            if len(starts) == 1: raise HTTPError(url, 429, "limited", {"Retry-After": "2"}, None)
            return response()
        adapter = EuropePMC(transport=transport, clock=lambda: now[0], sleeper=sleeper)
        adapter.search("a", 50); adapter.search("b", 50)
        self.assertTrue(all(b-a >= 1 for a,b in zip(starts, starts[1:])))
        self.assertIn(2, sleeps)

    def test_network_failure_is_bounded(self):
        def fail(_): raise URLError("simulated offline")
        adapter = EuropePMC(transport=fail, interval=0, sleeper=lambda _: None)
        with self.assertRaises(ResearchError) as ctx: adapter.search("q", 50)
        self.assertEqual(ctx.exception.code, "UPSTREAM_UNAVAILABLE")
        self.assertEqual(adapter.network_calls, 3)
        self.assertEqual(len(adapter.cache), 0)

    def test_long_retry_after_surfaces_without_hammering(self):
        def fail(url): raise HTTPError(url, 429, "limited", {"Retry-After": "120"}, None)
        adapter = EuropePMC(transport=fail, interval=0)
        with self.assertRaises(ResearchError) as ctx: adapter.search("q", 50)
        self.assertEqual(ctx.exception.code, "UPSTREAM_RATE_LIMIT")
        self.assertEqual(adapter.network_calls, 1)

    def test_unknown_fulltext_not_cached(self):
        adapter = EuropePMC(transport=lambda _: xml("https://example.org/unknown"), interval=0)
        with self.assertRaises(ResearchError): adapter.full_text("PMC1", inspect_xml_license)
        self.assertEqual(len(adapter.cache), 0)


class ServiceTests(unittest.TestCase):
    def test_empty_and_invalid_inputs(self):
        workbench = Workbench(EuropePMC(transport=lambda _: response([]), interval=0))
        self.assertEqual(workbench.search("no matches")["retrieved"], 0)
        for query, count in [(None,75), (" ",75), ("a"*501,75), ("x",0), ("x",True)]:
            with self.assertRaises(ResearchError) as ctx: workbench.search(query, count)
            self.assertEqual(ctx.exception.status, 400)

    def test_metadata_unknown_does_not_download_fulltext(self):
        urls = []
        def transport(url): urls.append(url); return response([raw("unknown")])
        service = Workbench(EuropePMC(transport=transport, interval=0))
        with self.assertRaises(ResearchError) as ctx: service.paper("PMC4302049")
        self.assertEqual(ctx.exception.code, "LICENSE_NOT_ALLOWED")
        self.assertEqual(len(urls), 1)
        self.assertNotIn("fullTextXML", urls[0])

    def test_missing_fulltext_and_malformed_result(self):
        service = Workbench(EuropePMC(transport=lambda _: response([]), interval=0))
        with self.assertRaises(ResearchError) as ctx: service.paper("PMC999")
        self.assertEqual(ctx.exception.status, 404)
        service = Workbench(EuropePMC(transport=lambda _: b'{"resultList":{}}', interval=0))
        with self.assertRaises(ResearchError) as ctx: service.search("q")
        self.assertEqual(ctx.exception.code, "INVALID_UPSTREAM_DATA")

    def test_valid_reader_provenance_and_model_absence(self):
        def transport(url): return xml() if url.endswith('fullTextXML') else response()
        service = Workbench(EuropePMC(transport=transport, interval=0))
        article = service.paper("PMC4302049")
        self.assertEqual(len(article["source"]["sha256"]), 64)
        self.assertEqual(article["modelStatus"], "not_connected")
        with self.assertRaises(ResearchError) as ctx: service.explain()
        self.assertEqual(ctx.exception.code, "MODEL_NOT_CONNECTED")


if __name__ == '__main__': unittest.main()
