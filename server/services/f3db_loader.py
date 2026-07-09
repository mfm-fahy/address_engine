import hashlib
import json
import os

from config.settings import API_KEYS
from pipeline.base import IngestionResult
from pipeline.logging import PipelineLogger
from pipeline.normalizers import normalize_phone, extract_source_phone, extract_source_name
from pipeline.validators import validate_order
from repositories.order_repo import RawOrderRepository


F3DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "f3db")


class F3DbLoader:
    def __init__(self, order_repo=None):
        self._order_repo = order_repo or RawOrderRepository()
        self._source_name = "f3"

    async def load_all_files(self) -> IngestionResult:
        logger = PipelineLogger("f3db")
        result = IngestionResult(source="f3db")

        if not os.path.isdir(F3DB_DIR):
            logger.log(f"Directory not found: {F3DB_DIR}")
            return result

        files = [f for f in os.listdir(F3DB_DIR) if f.endswith(".json")]
        if not files:
            logger.log("No JSON files found in f3db/")
            return result

        for filename in sorted(files):
            filepath = os.path.join(F3DB_DIR, filename)
            logger.log(f"Processing {filename}...")
            records = self._read_file(filepath)
            if records is None:
                logger.log(f"  Skipped {filename} (parse error)")
                continue

            file_result = await self._process_records(records, logger)
            result.total_fetched += file_result.total_fetched
            result.valid_count += file_result.valid_count
            result.inserted_count += file_result.inserted_count
            result.duplicate_count += file_result.duplicate_count
            result.validation_errors.extend(file_result.validation_errors)
            logger.log(f"  {filename}: {file_result.valid_count} valid, {file_result.inserted_count} inserted")

        logger.done(result)
        return result

    def _read_file(self, filepath: str):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[f3db] Error reading {filepath}: {e}")
            return None

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data", data.get("orders", []))
        return None

    async def _process_records(self, records: list, logger: PipelineLogger) -> IngestionResult:
        result = IngestionResult(source="f3db")
        for order in records:
            result.total_fetched += 1
            validation_errors = validate_order(order, "f3")
            if validation_errors:
                for err in validation_errors:
                    result.validation_errors.append(f"[f3db] {err}")
                continue
            result.valid_count += 1

            phone = normalize_phone(extract_source_phone("f3", order))
            order_id = order.get("id") or order.get("transactionId") or order.get("_id") or order.get("orderId", "")
            if not order_id:
                raw = f"{order.get('orderDate','')}_{order.get('orderValue','')}_{order.get('customerName','')}_{phone}"
                order_id = f"f3_{hashlib.md5(raw.encode()).hexdigest()[:12]}"

            await self._order_repo.upsert_generic_order(
                "f3", order_id, order, phone,
                extract_source_name("f3", order),
            )
            result.inserted_count += 1

        return result
