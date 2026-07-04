import fs from 'node:fs/promises';
import { readdir } from 'node:fs/promises';

const APIS = [
  {
    name: 'orders',
    url: 'https://bot.gowhats.in/api/admin/orders',
    token: process.env.GOWHATS_API_KEY || ''
  },
  {
    name: 'fulfillment',
    url: 'https://app.instaxbot.com/fullfillment',
    token: process.env.INSTAXBOT_API_KEY || ''
  },
  {
    name: 'f3engine',
    url: 'https://f3engine.com/api/external/orders',
    token: process.env.F3_API_KEY || ''
  },
];

const DATA_DIR = 'data';

function normalizePhone(phone) {
  if (!phone) return '';
  let p = String(phone).replace(/[\s\-\(\)]/g, '');
  if (p.startsWith('+91')) p = p.slice(3);
  else if (p.startsWith('91') && p.length === 12) p = p.slice(2);
  return p.replace(/^0+/, '');
}

async function ensureDir() {
  try { await fs.mkdir(DATA_DIR, { recursive: true }); } catch {}
}

async function fetchApi(api) {
  try {
    const res = await fetch(api.url.trim(), {
      headers: { Authorization: `Bearer ${api.token}` }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    try { return JSON.parse(text); } catch {
      throw new Error('Response is not JSON');
    }
  } catch (err) {
    return { error: err.message };
  }
}

function extractRecords(data) {
  if (data?.data?.orders && data.data.orders[0]?.customerPhone !== undefined) {
    return data.data.orders.map(o => ({
      phone: normalizePhone(o.customerPhone), source: 'WhatsApp Orders', id: o.orderId, record: o
    })).filter(r => r.phone);
  }
  if (data?.data && Array.isArray(data.data) && data.data[0]?.platform) {
    return data.data.map(o => ({
      phone: normalizePhone(o.customerPhone), source: 'F3 Fulfillment', id: o.orderId, record: o
    })).filter(r => r.phone);
  }
  if (data?.data?.orders && data.data.orders[0]?.billNo !== undefined) {
    return data.data.orders.map(o => ({
      phone: normalizePhone(o.customer?.phone), source: 'Bill Orders', id: o.orderId, record: o
    })).filter(r => r.phone);
  }
  return [];
}

async function runComparison() {
  try {
    const files = (await readdir(DATA_DIR)).filter(f => f.endsWith('.json'));
    const allRecords = [];
    for (const file of files) {
      const raw = await fs.readFile(`${DATA_DIR}/${file}`, 'utf-8');
      const data = JSON.parse(raw);
      const records = extractRecords(data);
      allRecords.push(...records.map(r => ({ ...r, file })));
    }

    const phoneMap = {};
    for (const r of allRecords) {
      if (!phoneMap[r.phone]) phoneMap[r.phone] = {};
      if (!phoneMap[r.phone][r.source]) phoneMap[r.phone][r.source] = [];
      phoneMap[r.phone][r.source].push(r);
    }

    const matched = {};
    for (const [phone, sources] of Object.entries(phoneMap)) {
      const sourceNames = Object.keys(sources);
      if (sourceNames.length >= 2) {
        matched[phone] = { phone, sourcesPresent: sourceNames, records: sources };
      }
    }

    const outFile = `${DATA_DIR}/matched_latest.json`;
    await fs.writeFile(outFile, JSON.stringify({
      generatedAt: new Date().toISOString(),
      matchCount: Object.keys(matched).length,
      matches: matched
    }, null, 2), 'utf-8');
    console.log(`  → ${Object.keys(matched).length} matching phones saved`);
  } catch (err) {
    console.error('  Comparison error:', err.message);
  }
}

async function cycle() {
  const ts = Date.now();
  console.log(`\n[${new Date().toLocaleTimeString()}] Fetching ${APIS.length} APIs...`);

  for (const api of APIS) {
    const result = await fetchApi(api);
    if (result.error) {
      console.log(`  ✗ ${api.name}: ${result.error}`);
      continue;
    }
    const filePath = `${DATA_DIR}/${api.name}.json`;
    await fs.writeFile(filePath, JSON.stringify(result, null, 2), 'utf-8');
    const count = extractRecords(result).length;
    console.log(`  ✓ ${api.name}: ${count} records`);
  }

  console.log('  Running comparison...');
  await runComparison();
}

async function main() {
  await ensureDir();
  console.log('Auto-fetch every 5 seconds. Press Ctrl+C to stop.');
  await cycle();
  setInterval(cycle, 5000);
}

main().catch(err => { console.error(err.message); process.exit(1); });
