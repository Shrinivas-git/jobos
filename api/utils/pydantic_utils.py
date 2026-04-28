from typing import Any, Annotated
from bson import ObjectId
from pydantic import BeforeValidator, PlainSerializer

def validate_object_id(v: Any) -> ObjectId:
    if isinstance(v, ObjectId):
        return v
    if not ObjectId.is_valid(v):
        raise ValueError("Invalid ObjectId")
    return ObjectId(v)

PyObjectId = Annotated[
    ObjectId | str,
    BeforeValidator(validate_object_id),
    PlainSerializer(lambda v: str(v), return_type=str),
]
