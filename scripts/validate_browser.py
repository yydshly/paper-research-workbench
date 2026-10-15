"""Optional QA using already-installed Playwright + Edge. Never installs a browser.

Run the local service first. This script keeps real-network and simulated UI checks
separate in evidence/browser-validation.json. It uses public teaching material only.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8765'
OUT = ROOT / 'evidence'


def main():
    checks, errors, requests = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width':1440,'height':1050}, device_scale_factor=1)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: requests.append(request.url) if request.url.endswith('/api/search') else None)
        page.goto(BASE, wait_until='networkidle')
        expect(page.locator('h1')).to_have_count(4)  # Hidden views remain in the document.
        page.screenshot(path=str(OUT / 'workspace-desktop.png'), full_page=True)
        page.locator('#example-fill').click()
        page.locator('#search-button').click()
        # Repeated submits while the first request is pending must not call API again.
        page.locator('#search-form').evaluate('(form) => { form.requestSubmit(); form.requestSubmit(); }')
        expect(page.locator('.paper-card')).to_have_count(20, timeout=90000)
        expect(page.locator('#search-button')).to_be_enabled()
        assert len(requests) == 1, requests
        checks.append({'kind':'real-network','name':'75-candidate search and duplicate submit suppression','passed':True})
        page.locator('.paper-card details summary').first.click()
        expect(page.locator('.paper-card details').first).to_contain_text('SHA-256')
        expect(page.locator('.paper-card details').first).to_contain_text('不是正确率')
        page.screenshot(path=str(OUT / 'results-desktop.png'), full_page=False)
        enabled = page.locator('.paper-card .card-actions button.secondary:enabled')
        eligible_count = enabled.count()
        for _ in range(min(3, eligible_count)):
            page.locator('.paper-card .card-actions button.secondary:enabled').first.click()
        selected = min(3, eligible_count)
        expect(page.locator('.basket-item')).to_have_count(selected)
        if eligible_count > 3:
            page.locator('.paper-card .card-actions button.secondary:enabled').first.click()
            expect(page.locator('#search-status')).to_contain_text('最多容纳 3 篇')
            expect(page.locator('.basket-item')).to_have_count(3)
        checks.append({'kind':'real-network-ui','name':'selection basket and maximum 3','eligibleTop20':eligible_count,'selected':selected,'passed':True})
        page.locator('#open-example').click()
        expect(page.locator('#reader-status')).to_contain_text('许可核查通过',timeout=90000)
        expect(page.locator('.reader-header')).to_contain_text('CC BY 4.0')
        assert page.locator('.paragraph').count() > 100
        assert page.locator('.figure-card').count() == 9
        expect(page.locator('.model-notice')).to_contain_text('真实模型未接入')
        assert all(not b.is_enabled() for b in page.locator('.model-buttons button').all())
        page.screenshot(path=str(OUT / 'reader-desktop.png'), full_page=False)
        checks.append({'kind':'real-network','name':'open article, paragraphs, figures and absent model','paragraphs':page.locator('.paragraph').count(),'passed':True})
        page.get_by_role('button', name='项目与目标', exact=False).click()
        expect(page.locator('#doc-content')).to_contain_text('核心任务')
        page.get_by_role('button', name='数据与许可', exact=True).click()
        expect(page.locator('#doc-content')).to_contain_text('API 的使用允许与论文的版权不是同一件事')
        page.get_by_role('button', name='状态与验收', exact=False).click()
        expect(page.locator('#runtime-status')).to_contain_text('真实模型调用 0 次')
        page.get_by_role('button', name='文献检索', exact=False).click()
        page.locator('#query').fill('EXT_ID:99999999999999999999')
        page.locator('#search-button').click()
        expect(page.locator('#results')).to_contain_text('没有找到匹配文献',timeout=90000)
        expect(page.locator('.paper-card')).to_have_count(0)
        checks.append({'kind':'real-network','name':'empty result without canned fallback','passed':True})

        # Explicitly simulated HTTP failures, never called live network evidence.
        page.route('**/api/search', lambda route: route.fulfill(status=503,content_type='application/json',body=json.dumps({'error':{'code':'UPSTREAM_UNAVAILABLE','message':'模拟测试：来源暂时不可用'}})))
        page.locator('#query').fill('DESeq2')
        page.locator('#search-button').click()
        expect(page.locator('#search-status')).to_contain_text('模拟测试：来源暂时不可用')
        expect(page.locator('#search-button')).to_be_enabled()
        page.unroute('**/api/search')
        page.reload(wait_until='networkidle')
        page.route('**/api/papers/PMC4302049', lambda route: route.fulfill(status=403,content_type='application/json',body=json.dumps({'error':{'code':'LICENSE_NOT_ALLOWED','message':'模拟测试：许可未知，未下载全文'}})))
        page.locator('#open-example').click()
        expect(page.locator('#reader-status')).to_contain_text('模拟测试：许可未知')
        page.unroute('**/api/papers/PMC4302049')
        # The article is cached in page memory; a fresh page exercises missing fulltext.
        page.reload(wait_until='networkidle')
        page.route('**/api/papers/PMC4302049', lambda route: route.fulfill(status=404,content_type='application/json',body=json.dumps({'error':{'code':'FULLTEXT_UNAVAILABLE','message':'模拟测试：全文不可用'}})))
        page.locator('#open-example').click()
        expect(page.locator('#reader-status')).to_contain_text('模拟测试：全文不可用')
        page.unroute('**/api/papers/PMC4302049')
        checks.append({'kind':'simulated-browser-responses','name':'upstream error, unknown license, missing fulltext','passed':True})
        page.set_viewport_size({'width':390,'height':844})
        page.get_by_role('button', name='文献检索', exact=False).click()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(OUT / 'workspace-mobile.png'), full_page=True)
        page.locator('#open-example').click()
        expect(page.locator('#reader-status')).to_contain_text('许可核查通过',timeout=90000)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(OUT / 'reader-mobile.png'), full_page=False)
        checks.append({'kind':'browser-layout','name':'390px mobile search and reader no horizontal overflow','passed':True})
        assert not errors, errors
        browser.close()
    result = {'validatedAt':datetime.now(timezone.utc).isoformat(),'browser':'installed Edge / Playwright headless',
              'checks':checks,'pageErrors':errors,'realModelCalls':0,'note':'内置 CUA 浏览器启动失败两次；未安装新浏览器，使用现有本机工具。'}
    (OUT / 'browser-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__': main()
