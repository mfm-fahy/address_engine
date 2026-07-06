import asyncio, json
from motor.motor_asyncio import AsyncIOMotorClient

async def test():
    client = AsyncIOMotorClient('mongodb+srv://mfmfahy_db_user:VptvmFUSppUEAVgV@cluster0.zgzgecw.mongodb.net/?appName=Cluster0')
    db = client['customer360']
    
    for src in ['gowhats', 'instaxbot', 'f3']:
        pipeline = [
            {'$match': {'source': src}},
            {'$group': {'_id': '$raw_data.status', 'count': {'$sum': 1}}}
        ]
        results = await db['raw_orders'].aggregate(pipeline).to_list(None)
        print(f'\n=== {src} ===')
        for r in results:
            print(f'  status={repr(r["_id"])}: {r["count"]}')

asyncio.run(test())
