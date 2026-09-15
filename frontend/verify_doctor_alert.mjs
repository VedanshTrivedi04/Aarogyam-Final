import { chromium } from 'playwright';

const browser = await chromium.launch({ args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1400, height: 1100 } });

page.on('requestfinished', async (req) => {
  if (req.url().includes('/notifications/') && req.method()==='GET') {
    const res = await req.response();
    console.log('URL:', req.url());
    console.log('STATUS:', res.status());
    console.log('BODY:', (await res.text()).slice(0, 800));
    console.log('---');
  }
});

await page.goto('http://localhost:5173/login', { waitUntil: 'domcontentloaded', timeout: 20000 });
await page.waitForSelector('input[type="email"]', { timeout: 15000 });
await page.click('button:has-text("Doctor")');
await page.fill('input[type="email"]', 'dr.priya.nair@medadhere.test');
await page.fill('input[type="password"]', 'TestPass123!');
await page.click('button:has-text("Sign In")');
await page.waitForURL('**/doctor/home', { timeout: 20000 });
await page.waitForTimeout(3000);
await page.click('a:has-text("Patient Alerts")');
await page.waitForURL('**/notifications', { timeout: 10000 });
await page.waitForTimeout(3000);

await browser.close();
