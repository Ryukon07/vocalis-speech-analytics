import { chromium } from '../frontend/node_modules/playwright/index.mjs';
const browser = await chromium.launch({ headless: true, channel: 'chromium' });
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  for (const route of ['/history', '/settings']) {
    await page.goto('http://127.0.0.1:5173' + route); await page.locator('table, .rubric-row').first().waitFor();
    console.log(route, await page.evaluate(() => ({ documentWidth:document.documentElement.scrollWidth, elements: Array.from(document.querySelectorAll('*')).map(e => { const r=e.getBoundingClientRect(); return { tag:e.tagName, className:e.className, left:r.left, right:r.right, width:r.width, css: getComputedStyle(e).overflowX, scroll:e.scrollWidth }; }).filter(e => e.right > innerWidth+2).slice(0,15) })));
  }
} finally { await browser.close(); }
