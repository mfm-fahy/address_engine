const API_URL = 'https://app.instaxbot.com/fullfillment';
const API_KEY = process.env.INSTAXBOT_API_KEY || '';

async function fetchOrders() {
  try {
    const res = await fetch(API_URL, {
      headers: { Authorization: `Bearer ${API_KEY}` }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const data = await res.json();
    const filename = `orders_${Date.now()}.json`;
    await fs.writeFile(filename, JSON.stringify(data, null, 2), 'utf-8');
    console.log(`Saved ${filename} (${data.length ?? '?'} records)`);
  } catch (err) {
    console.error('Failed:', err.message);                                                                                                 
    process.exit(1);
  }
}

import fs from 'node:fs/promises';
fetchOrders();
