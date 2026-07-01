import fs from 'node:fs/promises';
import { readdir } from 'node:fs/promises';

function normalizePhone(phone) {
  if (!phone) return '';
  let p = String(phone).replace(/[\s\-\(\)]/g, '');
  if (p.startsWith('+91')) p = p.slice(3);
  else if (p.startsWith('91') && p.length === 12) p = p.slice(2);
  return p.replace(/^0+/, '');
}

async function loadJsonFiles() {
  const files = (await readdir('.')).filter(f => f.endsWith('.json') && !f.startsWith('matched'));
  const datasets = {};
  for (const file of files) {
    const raw = await fs.readFile(file, 'utf-8');
    datasets[file] = JSON.parse(raw);
    console.log(`  ${file}`);
  }
  return datasets;
}

function getRecords(data) {
  // orders_*.json from gowhats: { success, data: { orders: [...] } }
  if (data?.data?.orders && data?.data?.orders?.[0]?.customerPhone !== undefined) {
    return data.data.orders.map(o => ({
      phone: normalizePhone(o.customerPhone),
      source: 'WhatsApp Orders',
      id: o.orderId,
      record: o
    })).filter(r => r.phone);
  }

  // fulfillment_*.json from f3engine: { success, data: [...] }
  if (data?.data && Array.isArray(data.data) && data.data[0]?.platform) {
    return data.data.map(o => ({
      phone: normalizePhone(o.customerPhone),
      source: 'F3 Fulfillment',
      id: o.orderId,
      record: o
    })).filter(r => r.phone);
  }

  // fulfillment_*.json with { success, data: { orders: [...] } }
  if (data?.data?.orders && data?.data?.orders?.[0]?.billNo !== undefined) {
    return data.data.orders.map(o => ({
      phone: normalizePhone(o.customer?.phone),
      source: 'Bill Orders',
      id: o.orderId,
      record: o
    })).filter(r => r.phone);
  }

  // bill_*.json: { organisation, orders: [...] }
  if (data?.orders && Array.isArray(data.orders) && data.orders[0]?.customer?.mobile !== undefined) {
    return data.orders.map(o => ({
      phone: normalizePhone(o.customer.mobile),
      source: 'Billzzy',
      id: o.billNo,
      record: o
    })).filter(r => r.phone);
  }

  return [];
}

async function main() {
  console.log('Loading JSON files...');
  const datasets = await loadJsonFiles();

  const allRecords = [];
  for (const [file, data] of Object.entries(datasets)) {
    const records = getRecords(data);
    console.log(`  → ${records.length} records`);
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

  const phoneList = Object.keys(matched);
  console.log(`\nPhones found in 2+ sources: ${phoneList.length}`);

  const output = {
    generatedAt: new Date().toISOString(),
    matchCount: phoneList.length,
    matches: matched
  };

  const outFile = `matched_${Date.now()}.json`;
  await fs.writeFile(outFile, JSON.stringify(output, null, 2), 'utf-8');
  console.log(`Saved to ${outFile}`);
}

main().catch(err => { console.error(err.message); process.exit(1); });
