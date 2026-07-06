import asyncio, json
from motor.motor_asyncio import AsyncIOMotorClient

async def test():
    client = AsyncIOMotorClient('mongodb+srv://mfmfahy_db_user:VptvmFUSppUEAVgV@cluster0.zgzgecw.mongodb.net/?appName=Cluster0')
    db = client['customer360']
    
    # Check a few records from each source
    for src in ['gowhats', 'instaxbot', 'f3']:
        docs = await db['raw_orders'].find({'source': src}).limit(2).to_list(2)
        print(f'\n=== {src} ===')
        for d in docs:
            raw = d.get('raw_data', {})
            print(f'  Top keys: {list(raw.keys())[:15]}')
            # Check status field
            status = raw.get('status', '')
            print(f'  status: {repr(status)}')
            # Check amount fields
            for field in ['totalAmount', 'amount', 'total', 'totalPrice', 'total_price', 'grandTotal', 'subTotal', 'orderTotal']:
                val = raw.get(field, 'MISSING')
                if val != 'MISSING':
                    print(f'  {field}: {val}')
            # Check items for price info
            items = raw.get('items', [])
            if items:
                print(f'  items[0] keys: {list(items[0].keys()) if items else "none"}')

asyncio.run(test())
