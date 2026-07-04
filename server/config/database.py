from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import MONGODB_URL, DB_NAME
from config.postgres import connect as pg_connect
from config.postgres import close as pg_close
from config.postgres import init_schema as pg_init_schema

client = None
db = None

async def connect_db():
    global client, db
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DB_NAME]
    print(f"Connected to MongoDB: {DB_NAME}")
    await db["raw_orders"].create_index([("source", 1), ("order_id", 1)], background=True)
    print("Created index on raw_orders(source, order_id)")
    await pg_connect()
    await pg_init_schema()

async def close_db():
    global client
    if client:
        client.close()
    await pg_close()

def get_db():
    return db
