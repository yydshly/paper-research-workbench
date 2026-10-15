"""Real Europe PMC network checks, public DESeq2 teaching topic only."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apps.workbench.service import Workbench
from research.errors import ResearchError


def main():
    service = Workbench()
    query = '(DESeq2 OR "RNA-seq") AND "differential expression"'
    results = service.search(query, 75)
    assert 50 <= results['retrieved'] <= 100, results['retrieved']
    assert len(results['papers']) == 20
    before = service.adapter.network_calls
    repeated = service.search(query, 75)
    assert repeated['source']['cacheHit'] and service.adapter.network_calls == before
    article = service.paper('PMC4302049')
    assert article['license']['name'] == 'CC BY 4.0'
    paragraphs = sum(len(s['paragraphs']) for s in article['sections'])
    assert paragraphs > 20 and len(article['figures']) > 0
    empty = service.search('EXT_ID:99999999999999999999', 50)
    assert empty['totalHits'] == 0 and not empty['papers']
    missing = None
    try: service.paper('PMC999999999999')
    except ResearchError as error: missing = error.code
    assert missing == 'FULLTEXT_UNAVAILABLE'
    evidence = {
        'validatedAt': datetime.now(timezone.utc).isoformat(), 'kind':'real-network',
        'query':query, 'search':{k:results[k] for k in ('requested','totalHits','retrieved','unique','duplicatesRemoved','shown','source')},
        'repeatRequest':{'cacheHit':True,'additionalNetworkCalls':0},
        'article':{'pmcid':'PMC4302049','doi':article['paper']['doi'],'license':article['license'],
                   'source':article['source'],'sections':len(article['sections']), 'paragraphs':paragraphs,
                   'figures':len(article['figures']), 'anchors':sum(bool(p['originalAnchor']) for s in article['sections'] for p in s['paragraphs'])},
        'empty':{'totalHits':empty['totalHits'],'source':empty['source']},
        'missingFulltext':missing,'model':{'status':'not_connected','realCalls':0},
        'networkCalls':service.adapter.network_calls,
        'limitations':['上游错误与许可未知分支另由模拟测试覆盖','本验收不构成模型科学质量评估','动态数据后续可变化']
    }
    output = ROOT / 'evidence' / 'live-validation.json'
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'retrieved':results['retrieved'],'shown':20,'paragraphs':paragraphs,
                      'figures':len(article['figures']), 'license':article['license']['name'],
                      'empty':True,'missing':missing,'networkCalls':service.adapter.network_calls,
                      'evidence':str(output)}, ensure_ascii=False))


if __name__ == '__main__': main()
