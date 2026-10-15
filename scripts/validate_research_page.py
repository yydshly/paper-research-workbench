"""QA for the static research presentation. No research APIs or models are called."""
import json
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors, calls = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:calls.append(r.url))
        page.goto('http://127.0.0.1:8766',wait_until='networkidle')
        expect(page.locator('#source-table tr')).to_have_count(6)
        expect(page.locator('#overview')).to_contain_text('暂停超前功能扩展')
        expect(page.locator('#sources')).to_contain_text('等待用户确认')
        page.screenshot(path=str(ROOT/'evidence'/'research-desktop.png'),full_page=False)
        page.locator('[data-filter="optional"]').click()
        expect(page.locator('#source-table tr:visible')).to_have_count(2)
        page.locator('[data-filter="deferred"]').click()
        expect(page.locator('#source-table tr:visible')).to_have_count(1)
        page.locator('[data-filter="candidate"]').click()
        expect(page.locator('#source-table tr:visible')).to_have_count(3)
        page.locator('[data-filter="all"]').click()
        page.locator('#source-table a').first.click()
        expect(page.locator('#europe-pmc')).to_have_attribute('open','')
        expect(page.locator('#europe-pmc')).to_contain_text('失败回退')
        expect(page.locator('#europe-pmc')).to_contain_text('无需 key')
        page.screenshot(path=str(ROOT/'evidence'/'research-sources.png'),full_page=False)
        expect(page.locator('#status')).to_contain_text('没有模型调用')
        page.set_viewport_size({'width':390,'height':844})
        page.goto('http://127.0.0.1:8766',wait_until='networkidle')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(ROOT/'evidence'/'research-mobile.png'),full_page=True)
        assert not errors,errors
        assert not any('/api/' in url for url in calls), calls
        browser.close()
    result={'validatedAt':datetime.now(timezone.utc).isoformat(),'kind':'static-presentation-browser-qa',
            'sourceRows':6,'filters':[3,2,1],'desktop':True,'mobileWidth':390,'pageErrors':errors,
            'researchApiCalls':0,'modelCalls':0,'note':'页面用于研究方案审阅，不执行论文搜索，不代表模型或源选择已确认。'}
    (ROOT/'evidence'/'research-page-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
