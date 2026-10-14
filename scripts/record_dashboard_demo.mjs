// Actual browser video, real localhost API; no mocked endpoints or fabricated results.
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root = resolve(import.meta.dirname, '..');
process.env.PLAYWRIGHT_BROWSERS_PATH ||= resolve(root, 'model-artifacts/playwright');
const { chromium } = await import('../frontend/node_modules/playwright/index.mjs');
const work = resolve(root, 'tmp/dashboard-demo');
const config = JSON.parse(readFileSync(resolve(work,'settings.json'),'utf8'));
const verification = JSON.parse(readFileSync(resolve(root,'docs/benchmarks/website-verification.json'),'utf8'));
const reports = Object.fromEntries(verification.jobs.map(j=>[j.variant,j.id]));
const clarity = JSON.parse(readFileSync(resolve(root,'docs/benchmarks/clarity-website-result.json'),'utf8')).analysis_id;
mkdirSync(resolve(work,'footage'),{recursive:true});
const browser = await chromium.launch({headless:true,channel:'chromium'});
const context = await browser.newContext({viewport:{width:1440,height:810},recordVideo:{dir:resolve(work,'footage'),size:{width:1440,height:810}}});
const chapters = [];
const sleep = ms => new Promise(r=>setTimeout(r,ms));
async function chapter(index, action) {
  const page=await context.newPage(); const start=Date.now(); const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await action(page);
  const minimum=config.durations[index-1]*1000;
  if (Date.now()-start < minimum) await sleep(minimum-(Date.now()-start));
  await page.screenshot({path:resolve(work,`chapter-${index}.png`)});
  await page.close(); const path=await page.video().path();
  if(errors.length) throw new Error(`Chapter ${index}: ${errors.join('; ')}`);
  chapters.push({index,path,duration_seconds:(Date.now()-start)/1000,narration_seconds:config.durations[index-1]});
  console.log(`Recorded real dashboard chapter ${index}`,chapters.at(-1).duration_seconds.toFixed(1),'seconds');
}
try {
  await chapter(1, async page=>{
    await page.goto('http://127.0.0.1:5173/dashboard'); await page.locator('h1').waitFor();
    await sleep(7000); await page.locator('.table-wrap').first().scrollIntoViewIfNeeded(); await sleep(7000);
    await page.goto('http://127.0.0.1:5173/settings'); await page.locator('.rubric-row').first().waitFor();
    await sleep(6000); await page.locator('.rubric-row').first().scrollIntoViewIfNeeded();
  });
  await chapter(2, async page=>{
    await page.goto('http://127.0.0.1:5173/references'); await page.locator('.library-grid .card').first().waitFor();
    await sleep(10000); await page.goto('http://127.0.0.1:5173/datasets'); await page.locator('table').first().waitFor();
    await sleep(12000); await page.locator('tr').filter({hasText:'-pause.wav'}).first().getByRole('button',{name:'Annotate',exact:true}).click();
    await page.getByRole('button',{name:/awkward_pause ·/}).first().click();
    await page.getByRole('heading',{name:'Ground-truth annotation studio'}).scrollIntoViewIfNeeded();
    await sleep(8000); await page.getByLabel('Flaw type').scrollIntoViewIfNeeded();
    // Inspect the real saved edit bounds; no benchmark label is modified.
  });
  await chapter(3, async page=>{
    await page.goto('http://127.0.0.1:5173/analyze'); await page.getByLabel('Upload audio').setInputFiles(resolve(root,'dataset/asr_checks/1272-128104-0000.wav'));
    await page.locator('.uploaded-file audio').waitFor(); await sleep(5000);
    await page.getByRole('button',{name:'Continue',exact:true}).click();
    await page.getByRole('button',{name:'Generate transcript',exact:true}).click();
    await page.waitForFunction(()=>Boolean(document.querySelector('textarea[name="transcript"]')?.value),null,{timeout:180000});
    await sleep(5000); await page.getByLabel('Confirmed transcript').fill(config.expected); await sleep(4000);
    await page.getByRole('button',{name:'Continue',exact:true}).click(); await page.getByLabel('Reference speech').selectOption(config.reference_id); await sleep(4000);
    await page.getByRole('button',{name:'Continue',exact:true}).click(); await page.getByLabel('Evaluation rubric').selectOption(config.rubric_id); await sleep(5000);
    await page.getByRole('button',{name:'Continue',exact:true}).click(); await sleep(4000);
    await page.getByRole('button',{name:'Analyze Speech',exact:true}).click();
    await page.getByRole('heading',{name:'Clarity evidence'}).waitFor({timeout:180000});
    config.demo_analysis_url=page.url(); await sleep(5000); await page.getByRole('heading',{name:'Clarity evidence'}).scrollIntoViewIfNeeded();
  });
  await chapter(4, async page=>{
    for(const variant of ['monotone','rushed-severe','pause']) {
      await page.goto('http://127.0.0.1:5173/analyses/'+reports[variant]); await page.locator('.flaw-row').first().waitFor();
      await page.locator('.flaw-row').first().click();
      const tab=page.locator('.plot-tabs button').filter({hasText:variant==='monotone'?'Pitch':'Pacing'}).first(); await tab.click();
      await page.getByRole('heading',{name:'Acoustic comparison'}).scrollIntoViewIfNeeded(); await sleep(8500);
      await page.getByText('EVIDENCE & INTERPRETATION').scrollIntoViewIfNeeded(); await sleep(7500);
    }
    await page.goto('http://127.0.0.1:5173/analyses/f884319e-ba59-4fb6-aadf-823f8c9c198b'); await page.locator('.flaw-row').first().waitFor();
    await page.getByRole('heading',{name:'Acoustic comparison'}).scrollIntoViewIfNeeded();
  });
  await chapter(5, async page=>{
    await page.goto('http://127.0.0.1:5173/analyses/'+clarity); await page.getByRole('heading',{name:'Clarity evidence'}).waitFor();
    await page.getByText('Review independently recognized words').click(); await page.getByRole('heading',{name:'Clarity evidence'}).scrollIntoViewIfNeeded(); await sleep(12000);
    await page.locator('.flaw-row').first().click(); await page.getByText('EVIDENCE & INTERPRETATION').scrollIntoViewIfNeeded(); await sleep(10000);
    await page.locator('button.word').nth(12).click(); await page.getByRole('heading',{name:'Listen in context'}).scrollIntoViewIfNeeded(); await sleep(5000);
    await page.getByRole('button',{name:'Play audio',exact:true}).first().click(); await sleep(3000); await page.getByRole('button',{name:'Pause audio',exact:true}).first().click();
    await page.locator('h1').scrollIntoViewIfNeeded();
    const download=page.waitForEvent('download'); await page.getByRole('link',{name:'PDF',exact:true}).click(); await (await download).saveAs(resolve(work,'actual-report.pdf'));
  });
  await chapter(6, async page=>{
    await page.goto('http://127.0.0.1:5173/history'); await page.locator('table').waitFor(); await sleep(10000);
    await page.getByLabel('Search analyses').fill('combined-severe'); await sleep(10000);
    await page.goto('http://127.0.0.1:5173/settings'); await page.locator('.rubric-row').first().waitFor(); await sleep(10000);
    await page.goto('http://127.0.0.1:5173/dashboard'); await page.locator('h1').waitFor();
  });
  writeFileSync(resolve(work,'recording-manifest.json'),JSON.stringify({protocol:'Actual dashboard footage with real localhost API/inference; automated browser actions; no API fixtures',chapters,demo_analysis_url:config.demo_analysis_url},null,2));
} finally { await context.close(); await browser.close(); }
