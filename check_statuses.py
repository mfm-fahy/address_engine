import asyncio, json
from motor.motor_asyncio import AsyncIOMotorClient

async def test():
    client = AsyncIOMotorClient('mongodb+srv://mfmfahy_db_user:VptvmFUSppUEAVgV@cluster0.zgzgecw.mongodb.net/?appName=Cluster0')
    db = client['customer360']
    
    for src in ['gowhats', 'instaxbot', 'f3']:
        docs = await db['raw_orders'].find({'source': src}).to_list(None)
        statuses = {}
        for d in docs:
            raw = d.get('raw_data', {})
            s = str(raw.get('status', ''))
            statuses[s] = statuses.get(s, 0) + 1
        
        print(f'\n=== {src} (total: {len(docs)}) ===')
        for s, count in sorted(statuses.items(), key=lambda x: -x[1]):
            # Sample an order with this status
            sample = await db['raw_orders'].find_one({'source': src, 'raw_data.status': s})
            raw = sample.get('raw_data', {})
            amount = 0
            for f in ['totalAmount', 'amount', 'total', 'totalPrice', 'orderAmount']:
                amount = raw.get(f, 0)
                if amount:
                    break
            print(f'  status={repr(s)}: {count} orders, sample_amount={amount}')

asyncio.run(test())
