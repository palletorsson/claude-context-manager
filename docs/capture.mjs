import puppeteer from 'puppeteer';

const BASE = 'http://localhost:3001';
const OUT = 'docs/screenshots';

const pages = [
  { name: 'dashboard', path: '/', wait: 3000 },
  { name: 'sessions', path: '/sessions?project=C--Users-palle-Documents-GitHub-ada-encyclopedia', wait: 4000 },
  { name: 'memory', path: '/memory', wait: 3000 },
  { name: 'tree', path: '/tree', wait: 3000 },
];

const browser = await puppeteer.launch({
  headless: true,
  defaultViewport: { width: 1280, height: 800 },
  args: ['--no-sandbox'],
});

for (const p of pages) {
  const page = await browser.newPage();
  const url = `${BASE}${p.path}`;
  console.log(`Capturing ${p.name}: ${url}`);
  try {
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 15000 });
    await new Promise(r => setTimeout(r, p.wait));
    await page.screenshot({ path: `${OUT}/${p.name}.png`, fullPage: false });
    console.log(`  Saved ${OUT}/${p.name}.png`);
  } catch (e) {
    console.error(`  Error on ${p.name}: ${e.message}`);
  }
  await page.close();
}

await browser.close();
console.log('Done.');
