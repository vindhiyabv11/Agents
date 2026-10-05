import json
import logging
from datetime import UTC, datetime
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self,record : logging.LogRecord)-> str:
        payload = {
            "ts" : datetime.now(UTC).isoformat(),
            "level" : record.levelname,
            "msg" : record.getMessage(),
            **getattr(record, "extra_data", {}),
        }
        return json.dumps(payload, default=str)
    
def get_logger() -> logging.Logger:
    logger = logging.getLogger("schemaguard")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    
    
    Path("logs").mkdir(exist_ok=True)
    file_handler = logging.FileHandler("logs/validation_failures.jsonl",encoding="utf-8")
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)
    
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(console)
    return logger