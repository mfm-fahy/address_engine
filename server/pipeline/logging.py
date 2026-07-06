import time

from pipeline.base import IngestionResult


class PipelineLogger:
    def __init__(self, source: str):
        self.source = source
        self._start = time.time()

    def log(self, msg: str):
        print(f"[pipeline:{self.source}] {msg}")

    def done(self, result: IngestionResult):
        elapsed = time.time() - self._start
        result.duration_seconds = elapsed
        status = result.error if result.error else "OK"
        print(
            f"[pipeline:{self.source}] {status} in {elapsed:.2f}s | "
            f"fetched={result.total_fetched} valid={result.valid_count} "
            f"inserted={result.inserted_count} updated={result.updated_count} "
            f"dupes={result.duplicate_count} val_errors={len(result.validation_errors)}"
        )
