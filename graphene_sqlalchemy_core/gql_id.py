import base64
import json
from typing import NamedTuple, Tuple, Union


def decode_gql_id(encoded_id: str) -> Tuple[str, Union[str, int]]:
    type_name, id_text = base64.b64decode(encoded_id).decode().split(":")
    return type_name, json.loads(id_text)


def encode_gql_id(type_: str, id_: Union[str, int]) -> str:
    text = f"{type_}:{json.dumps(id_)}"
    return base64.b64encode(text.encode()).decode()


class ResolvedGlobalId(NamedTuple):
    type: str
    id: Union[str, int]

    def encode(self) -> str:
        return encode_gql_id(*self)

    @classmethod
    def decode(cls, global_id: str) -> "ResolvedGlobalId":
        return cls(*decode_gql_id(global_id))
