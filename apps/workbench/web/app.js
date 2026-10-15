const $ = (selector) => document.querySelector(selector);
const state = { searching: false, reading: false, result: null, basket: new Map(), articles: new Map(), docRequest: 0 };
const views = { workspace: '文献检索', reader: '开放阅读', project: '项目与目标', status: '状态与验收' };
const docs = { requirements: '产品需求', goals: '目标与指标', competitors: '竞品观察', roadmap: '开发路线', acceptance: '验收标准', 'data-licensing': '数据与许可', architecture: '架构', 'model-contract': '模型接口' };
const exampleQuery = '(DESeq2 OR "RNA-seq") AND "differential expression"';

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function link(text, url, className) {
  const a = el('a', text, className);
  try {
    const target = new URL(url);
    if (target.protocol === 'https:' && ['europepmc.org', 'www.ebi.ac.uk', 'doi.org', 'creativecommons.org'].includes(target.hostname)) {
      a.href = target.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
    }
  } catch { /* Unknown source links are shown as plain text. */ }
  return a;
}
function button(text, handler, className = 'secondary') {
  const b = el('button', text, className); b.type = 'button'; b.addEventListener('click', handler); return b;
}
async function api(path, payload) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(path, { signal: controller.signal, ...(payload ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) } : {}) });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error?.message || `请求失败（${response.status}）`);
    return body;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('请求等待超时，请检查网络后重试。没有使用预置结果替代。');
    if (error instanceof TypeError) throw new Error('无法连接本地服务。请确认服务正在运行后重试。');
    throw error;
  } finally { clearTimeout(timeout); }
}
function feedback(selector, text, kind = '') {
  const box = $(selector); box.textContent = text; box.className = `feedback ${kind}`;
}
function showView(name) {
  if (!views[name]) return;
  for (const view of Object.keys(views)) $(`#${view}-view`).hidden = view !== name;
  document.querySelectorAll('.main-nav [data-view]').forEach(b => {
    b.classList.toggle('active', b.dataset.view === name);
    if (b.dataset.view === name) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  $('#view-label').textContent = views[name];
  if (name === 'status') loadStatus();
  window.scrollTo({ top: 0, behavior: 'instant' });
}
document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => showView(b.dataset.view)));
$('#example-fill').addEventListener('click', () => { $('#query').value = exampleQuery; $('#query').focus(); });

function renderBasket() {
  $('#basket-count').textContent = `${state.basket.size} / 3`;
  $('#nav-count').textContent = String(state.basket.size);
  const root = $('#basket'); root.replaceChildren();
  if (!state.basket.size) root.append(el('div', '还没有选入论文。\n从左侧结果开始，或打开 DESeq2 示例。', 'basket-empty'));
  for (const [id, paper] of state.basket) {
    const card = el('article', undefined, 'basket-item');
    card.append(el('h3', paper.title));
    const actions = el('div', undefined, 'basket-item-actions');
    const read = button('打开阅读 →', () => openPaper(id), 'text-button'); read.disabled = state.reading;
    const remove = button('移除', () => { state.basket.delete(id); renderBasket(); renderResults(); }, 'text-button');
    remove.setAttribute('aria-label', `移除 ${paper.title}`);
    actions.append(read, remove); card.append(actions); root.append(card);
  }
}
function addToBasket(paper) {
  if (!paper.readingEligible || !paper.pmcid) return;
  if (state.basket.has(paper.pmcid)) return;
  if (state.basket.size >= 3) { feedback('#search-status', '阅读篮最多容纳 3 篇。请先移除一篇。', 'error'); return; }
  state.basket.set(paper.pmcid, paper); renderBasket(); renderResults();
}
function renderResults() {
  if (!state.result) return;
  const r = state.result; const root = $('#results'); root.replaceChildren();
  $('#results-count').textContent = r.shown ? `前 ${r.shown} 篇` : '';
  if (!r.papers.length) {
    const empty = el('div', undefined, 'empty-state');
    empty.append(el('h3', '没有找到匹配文献'), el('p', '请减少限定条件、检查英文关键词或换一种查询式。\n本次结果为 0，没有回退到示例数据。'));
    root.append(empty); return;
  }
  r.papers.forEach((p, i) => {
    const card = el('article', undefined, 'paper-card');
    const top = el('div', undefined, 'paper-top');
    top.append(el('span', `${String(i + 1).padStart(2, '0')} / ${p.year || '年份未知'} · ${p.journal || p.source}`), el('span', `词项相关度 ${p.relevance.score}`, 'score'));
    card.append(top, el('h3', p.title), el('p', p.authors || '作者信息缺失', 'paper-authors'));
    const tags = el('div', undefined, 'tags');
    tags.append(el('span', p.readingEligible ? '可申请开放阅读' : '当前不支持全文加工', `tag ${p.readingEligible ? 'eligible' : ''}`), el('span', p.license, 'tag'));
    if (p.pmcid) tags.append(el('span', p.pmcid, 'tag'));
    if (p.mergedCount > 1) tags.append(el('span', `合并 ${p.mergedCount} 条来源`, 'tag'));
    card.append(tags);
    const actions = el('div', undefined, 'card-actions');
    const add = button(state.basket.has(p.pmcid) ? '已在阅读篮' : '＋ 加入阅读篮', () => addToBasket(p));
    add.disabled = !p.readingEligible || state.basket.has(p.pmcid);
    const read = button('开放阅读 →', () => openPaper(p.pmcid), 'text-button'); read.disabled = !p.readingEligible || state.reading;
    actions.append(add, read, link('查看来源 ↗', p.sourceUrl));
    if (p.doi) actions.append(link('DOI ↗', `https://doi.org/${p.doi}`));
    card.append(actions);
    if (!p.readingEligible) card.append(el('p', p.pmcid ? 'OA 标记不等于再利用许可；许可未知或受限时只提供来源链接。' : '该来源没有可用的 PMCID 全文标识符。', 'eligibility-note'));
    const detail = el('details'); detail.append(el('summary', '为什么相关 · 摘要与来源记录'));
    const score = p.relevance;
    detail.append(el('p', `标题 ${score.titlePoints}/60：${score.titleMatches.join('、') || '无命中'}\n摘要 ${score.abstractPoints}/40：${score.abstractMatches.join('、') || '无命中'}\n查询词：${score.terms.join('、') || '无可评分词项'}。候选集内启发式排序，不是正确率或质量分。`));
    detail.append(el('p', p.abstract || '该来源未提供摘要。'));
    detail.append(el('div', `${p.source}:${p.sourceId} · DOI ${p.doi || '未提供'}\n采集 ${r.source.fetchedAt} · ${r.source.cacheHit ? '缓存命中' : '真实网络响应'}\n原始检索响应 SHA-256 ${r.source.sha256}`, 'provenance'));
    card.append(detail); root.append(card);
  });
}
$('#search-form').addEventListener('submit', async (event) => {
  event.preventDefault(); if (state.searching) return;
  state.searching = true; const b = $('#search-button'); b.disabled = true; b.textContent = '正在检索…';
  $('#results').setAttribute('aria-busy', 'true');
  feedback('#search-status', '正在请求 Europe PMC 真实候选。首次检索可能需要数秒…', 'loading');
  try {
    const result = await api('/api/search', { query: $('#query').value, count: Number($('#count').value) });
    state.result = result; renderResults(); $('#export-evidence').disabled = false;
    feedback('#search-status', `来源命中 ${result.totalHits.toLocaleString()} 条 · 本次获取 ${result.retrieved} 条 · 去重后 ${result.unique} 篇 · 移除重复 ${result.duplicatesRemoved} 条\n${result.rankingNote} ${result.source.cacheHit ? '本次使用 15 分钟内的来源缓存。' : '本次使用真实网络响应。'}`, 'success');
  } catch (error) { feedback('#search-status', `${error.message}${state.result ? '\n下方保留上一次成功结果，未将它当作本次检索结果。' : ''}`, 'error'); }
  finally { state.searching = false; b.disabled = false; b.textContent = '检索文献 ↗'; $('#results').removeAttribute('aria-busy'); }
});

function renderArticle(article) {
  const root = $('#reader-content'); root.replaceChildren();
  const h = el('article', undefined, 'reader-header');
  h.append(el('span', `${article.paper.pmcid} · ${article.license.name}`, 'soft-tag'), el('h2', article.title),
    el('p', `${article.paper.authors} · ${article.paper.journal} · ${article.paper.year}`), link('在 Europe PMC 查看原文 ↗', article.sourceUrl));
  if (article.paper.doi) { h.append(document.createTextNode('　'), link('DOI ↗', `https://doi.org/${article.paper.doi}`)); }
  h.append(el('p', article.transformation));
  h.append(el('div', `全文采集 ${article.source.fetchedAt} · ${article.source.cacheHit ? '来源缓存' : '真实网络响应'}\n原始全文 SHA-256 ${article.source.sha256}`, 'provenance'));
  const lic = el('details', undefined, 'license-details'); lic.append(el('summary', '许可证据与归因'), el('p', article.license.statement), link(article.license.name, article.license.url), el('p', '归因：上方作者、文章题名、期刊、DOI 与原文链接。呈现仅做结构化提取与重排；第三方材料如有例外须另核对。')); h.append(lic); root.append(h);
  const notice = el('aside', undefined, 'model-notice');
  notice.append(el('strong', '真实模型未接入 · 当前只显示原文'), el('p', '按需双语、术语/方法和一张图解释暂不可用。没有生成回答，也没有用人工示例伪装模型调用。'));
  const modelButtons = el('div', undefined, 'model-buttons'); ['按需双语', '术语 / 方法', '一张图解释'].forEach(t => { const b = button(t, () => {}); b.disabled = true; b.title = '真实模型未接入'; modelButtons.append(b); }); notice.append(modelButtons); root.append(notice);
  const layout = el('div', undefined, 'reader-layout'); const toc = el('nav', undefined, 'toc'); toc.setAttribute('aria-label', '文章目录'); toc.append(el('span', '文章目录', 'eyebrow'));
  const text = el('article', undefined, 'reader-text');
  for (const section of article.sections) {
    const s = el('section', undefined, 'article-section'); s.id = section.id; s.append(el('h3', section.title));
    const local = el('a', section.title); local.href = `#${section.id}`; toc.append(local);
    section.paragraphs.forEach((p, i) => {
      const item = el('div', undefined, 'paragraph'); item.id = p.id;
      item.append(el('p', p.text), link(p.hasOriginalAnchor ? `§ ${i + 1} · 定位原文 ${p.originalAnchor}` : `§ ${i + 1} · 原文无段落 ID，打开文章`, p.sourceUrl)); s.append(item);
    }); text.append(s);
  }
  if (article.figures.length) {
    const section = el('section', undefined, 'article-section'); section.id = 'original-figures'; section.append(el('h3', 'Figures · 原文图注'));
    const a = el('a', '原文图注'); a.href = '#original-figures'; toc.append(a);
    article.figures.forEach(fig => {
      const f = el('article', undefined, 'figure-card'); f.append(el('h3', fig.label || fig.id), el('p', fig.caption), link('定位原图与图注 ↗', fig.sourceUrl), el('p', '以上为原文图注，不是模型解释；未下载图片或重新绘制。')); section.append(f);
    }); text.append(section);
  }
  layout.append(toc, text); root.append(layout);
}
async function openPaper(pmcid) {
  if (state.reading) return;
  state.reading = true; renderBasket(); renderResults(); showView('reader');
  $('#reader-content').setAttribute('aria-busy', 'true');
  feedback('#reader-status', `正在核查 ${pmcid} 的元数据许可与全文许可证据…`, 'loading');
  try {
    const article = state.articles.get(pmcid) || await api(`/api/papers/${encodeURIComponent(pmcid)}`);
    state.articles.set(pmcid, article); if (state.articles.size > 3) state.articles.delete(state.articles.keys().next().value);
    renderArticle(article);
    if (!state.basket.has(pmcid) && state.basket.size < 3) state.basket.set(pmcid, { ...article.paper, readingEligible: true });
    feedback('#reader-status', `许可核查通过：${article.license.name} · ${article.sections.length} 个正文分节 · ${article.figures.length} 条原文图注`, 'success');
  } catch (error) { feedback('#reader-status', `${error.message}\n已有检索结果和阅读篮仍可使用；下方如有内容，为上一次打开的原文。`, 'error'); }
  finally { state.reading = false; $('#reader-content').removeAttribute('aria-busy'); renderBasket(); renderResults(); }
}
$('#open-example').addEventListener('click', () => openPaper('PMC4302049'));
$('#reader-example').addEventListener('click', () => openPaper('PMC4302049'));

async function loadDoc(name) {
  const request = ++state.docRequest;
  $('#doc-title').textContent = docs[name]; $('#doc-content').textContent = '正在读取文档…';
  document.querySelectorAll('#doc-nav button').forEach(b => b.classList.toggle('active', b.dataset.doc === name));
  try { const doc = await api(`/api/docs/${name}`); if (request === state.docRequest) $('#doc-content').textContent = doc.content; }
  catch (error) { if (request === state.docRequest) $('#doc-content').textContent = error.message; }
}
for (const [id, title] of Object.entries(docs)) { const b = button(title, () => loadDoc(id), ''); b.dataset.doc = id; $('#doc-nav').append(b); }
$('#show-acceptance').addEventListener('click', () => { showView('project'); loadDoc('acceptance'); });
async function loadStatus() {
  try { const status = await api('/api/status'); const root = $('#runtime-status'); root.replaceChildren(); root.append(el('strong', `${status.name} · v${status.version}`), el('div', `当前阶段：${status.phase}`), el('div', '模型状态：未接入 · 真实模型调用 0 次'), el('div', `数据源：${status.provider} · 本进程上游请求 ${status.networkCalls} 次`), el('div', status.rateLimit), el('div', `源码版本：${status.revision}`), el('div', '服务范围：127.0.0.1 本机 · GitHub 仓库公开'));
  } catch (error) { $('#runtime-status').textContent = error.message; }
}
$('#export-evidence').addEventListener('click', () => {
  if (!state.result) return;
  const data = { ...state.result, exportedAt: new Date().toISOString(), modelStatus: 'not_connected', selectedPmcids: [...state.basket.keys()] };
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const a = el('a'); a.href = url; a.download = 'paper-sources.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
renderBasket(); loadDoc('requirements');
