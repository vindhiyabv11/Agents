from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .logging_config import get_logger

T = TypeVar("T", bound = BaseModel)
log = get_logger()

def validate_payload(model : type[T], data: Any, *, source:str, attempt:int) -> T:
    """Validate data against a Pydantic model; log and re_raise on failure."""
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        log.warning(
            f"Validation failed for {model.__name__} from {source}",
            extra={
                "extra_data" : {
                    "schema" : model.__name__,
                    "source" : source,
                    "attempt" : attempt,
                    "errors" : exc.errors(include_url=False),
                    "payload" : data,
                    
                }
            },
        )
        raise
    
def format_errors(exc: ValidationError)-> str:
    """Compact, model-friendly error description for the retry prompt."""
    lines = []
    for err in exc.errors(include_url=False):
        loc = ".".join(str(p) for p in err["loc"]) or "<root>"
        lines.append(f"- {loc}: {err['msg']}")
    return "Validation errors:\n"+ "\n".join(lines)
    


