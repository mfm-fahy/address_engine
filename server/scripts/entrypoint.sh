#!/bin/bash
set -e

echo "=== Entrypoint: Starting ==="

# Wait for PostgreSQL using python + asyncpg
echo "Waiting for PostgreSQL..."
python -c "
import asyncio, asyncpg, os, sys
url = os.environ.get('DATABASE_URL', '')
async def wait():
    for i in range(30):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            print('PostgreSQL is ready.')
            return
        except Exception:
            await asyncio.sleep(2)
    print('ERROR: PostgreSQL not ready after 60s', file=sys.stderr)
    sys.exit(1)
asyncio.run(wait())
"

# Create schema using asyncpg
echo "Creating schema..."
python -c "
import asyncio, asyncpg, os
async def init():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    with open('config/schema.sql') as f:
        sql = f.read()
    await conn.execute(sql)
    await conn.close()
    print('Schema created successfully.')
asyncio.run(init())
"

# Check if customers table has data
CUSTOMER_COUNT=$(python -c "
import asyncio, asyncpg, os
async def count():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    val = await conn.fetchval('SELECT count(*) FROM customers')
    await conn.close()
    print(val)
asyncio.run(count())
" 2>/dev/null || echo "0")

echo "Current customer count: $CUSTOMER_COUNT"

if [ "$CUSTOMER_COUNT" -lt 100 ]; then
  echo "Running loader scripts (first run or empty DB)..."

  echo "  [1/5] load_db_files.py"
  python scripts/load_db_files.py 2>&1 || echo "  WARNING: load_db_files.py had errors"

  echo "  [2/5] load_all_sql_files.py"
  python scripts/load_all_sql_files.py 2>&1 || echo "  WARNING: load_all_sql_files.py had errors"

  echo "  [3/5] load_customer_data.py"
  python scripts/load_customer_data.py 2>&1 || echo "  WARNING: load_customer_data.py had errors"

  echo "  [4/5] load_remaining.py"
  python scripts/load_remaining.py 2>&1 || echo "  WARNING: load_remaining.py had errors"

  echo "  [5/5] load_jsonsql.py"
  python scripts/load_jsonsql.py 2>&1 || echo "  WARNING: load_jsonsql.py had errors"

  echo "All loader scripts completed."
else
  echo "DB already has $CUSTOMER_COUNT customers, skipping loaders."
fi

echo "=== Entrypoint: Starting server ==="
exec uvicorn main:app --host 0.0.0.0 --port 8000
