const API_URL = '  https://f3engine.com/api/external/orders';
const API_KEY = 'f3_ff5e10id2rnmpjfwp4xt1';

async function fetchData() {
  try {
    const res = await fetch(API_URL, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = await res.json();
    const filename = `fulfillment_${Date.now()}.json`;
    await fs.writeFile(filename, JSON.stringify(data, null, 2), 'utf-8');
    console.log(`Saved ${filename}`);
  } catch (err) {
    console.error('Failed:', err.message);
    process.exit(1);
  }
}

import fs from 'node:fs/promises';
fetchData();
