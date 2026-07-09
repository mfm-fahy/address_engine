import asyncio
import hashlib

from config.settings import API_KEYS
from repositories.order_repo import RawOrderRepository
from repositories.bill_repo import BillTransactionRepository
from pipeline.logging import PipelineLogger
from pipeline.base import IngestionResult
from pipeline.validators import validate_order, validate_bill_customer, validate_bill_tx
from pipeline.normalizers import normalize_phone, extract_source_phone, extract_source_name
from pipeline.deduplicators import Deduplicator
from pipeline.connectors import fetch_paginated, fetch_billzzy_all
from services.cache_manager import cache_manager


class OrderService:
    def __init__(self, order_repo=None, bill_repo=None):
        self._order_repo = order_repo or RawOrderRepository()
        self._bill_repo = bill_repo or BillTransactionRepository()
        self._dedup = Deduplicator(self._order_repo, self._bill_repo)

    async def fetch_and_store_all(self) -> dict:
        all_results = {}

        for source_name, config in API_KEYS.items():
            logger = PipelineLogger(source_name)
            source_timeout = config.get("timeout", 60)
            per_request_timeout = config.get("per_request_timeout", 60)

            if source_name == "bill":
                result = await self._process_bill(source_name, config, source_timeout, per_request_timeout, logger)
                all_results[source_name] = result
                logger.done(result)
                continue

            result = await self._process_source(source_name, config, source_timeout, per_request_timeout, logger)
            all_results[source_name] = result
            logger.done(result)

        await cache_manager.invalidate("dash:stats")

        return {
            k: (
                -1 if v.error else (
                    {"customers": v.inserted_count, "transactions": v.updated_count}
                    if k == "bill" else v.valid_count
                )
            )
            for k, v in all_results.items()
        }

    async def _process_source(self, source_name: str, config: dict, source_timeout: int,
                               per_request_timeout: int, logger: PipelineLogger) -> IngestionResult:
        result = IngestionResult(source=source_name)
        try:
            orders = await asyncio.wait_for(
                fetch_paginated(source_name, config["url"], config["key"], per_request_timeout=per_request_timeout),
                timeout=source_timeout,
            )
        except asyncio.TimeoutError:
            result.error = "SKIPPED (timeout)"
            return result
        except Exception as e:
            result.error = f"ERROR: {e}"
            return result

        result.total_fetched = len(orders) if orders else 0
        if not orders:
            logger.log("0 orders fetched")
            return result

        for order in orders:
            validation_errors = validate_order(order, source_name)
            if validation_errors:
                for err in validation_errors:
                    result.validation_errors.append(f"[{source_name}] {err}")
                continue
            result.valid_count += 1

            phone = normalize_phone(extract_source_phone(source_name, order))
            order_id = order.get("id") or order.get("transactionId") or order.get("_id") or order.get("orderId", "")
            if not order_id and source_name == "f3":
                raw = f"{order.get('orderDate','')}_{order.get('orderValue','')}_{order.get('customerName','')}_{phone}"
                order_id = f"f3_{hashlib.md5(raw.encode()).hexdigest()[:12]}"

            is_dup = await self._dedup.is_duplicate_order(source_name, str(order_id))
            if is_dup:
                result.duplicate_count += 1
                continue

            await self._order_repo.upsert_generic_order(
                source_name, order_id, order, phone,
                extract_source_name(source_name, order),
            )
            result.inserted_count += 1

        logger.log(f"fetched={result.total_fetched} valid={result.valid_count} inserted={result.inserted_count} dupes={result.duplicate_count}")
        return result

    async def _process_bill(self, source_name: str, config: dict, source_timeout: int,
                            per_request_timeout: int, logger: PipelineLogger) -> IngestionResult:
        result = IngestionResult(source=source_name)
        try:
            raw = await asyncio.wait_for(
                fetch_billzzy_all(config["url"], config["key"], per_request_timeout=per_request_timeout),
                timeout=source_timeout,
            )
        except asyncio.TimeoutError:
            result.error = "SKIPPED (timeout)"
            return result
        except Exception as e:
            result.error = f"ERROR: {e}"
            return result

        customers, transactions = raw
        result.total_fetched = len(customers) + len(transactions)

        await self._order_repo.delete_by_source("bill")
        await self._bill_repo.delete_all()

        for cust in customers:
            errs = validate_bill_customer(cust)
            if errs:
                for err in errs:
                    result.validation_errors.append(f"[bill/customer] {err}")
                continue
            result.valid_count += 1
            await self._order_repo.upsert_bill_customer(cust)
            result.inserted_count += 1

        for tx in transactions:
            errs = validate_bill_tx(tx)
            if errs:
                for err in errs:
                    result.validation_errors.append(f"[bill/tx] {err}")
                continue
            result.valid_count += 1

            is_dup = await self._dedup.is_duplicate_bill_tx(tx["order_id"])
            if is_dup:
                result.duplicate_count += 1
                continue

            await self._bill_repo.upsert(tx)
            result.updated_count += 1

        logger.log(f"fetched={result.total_fetched} valid={result.valid_count} "
                   f"customers={result.inserted_count} txs={result.updated_count} dupes={result.duplicate_count}")
        return result
