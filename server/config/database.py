from config.postgres import connect as pg_connect
from config.postgres import close as pg_close
from config.postgres import init_schema as pg_init_schema

async def connect_db():
    await pg_connect()
    await pg_init_schema()

async def close_db():
    await pg_close()
