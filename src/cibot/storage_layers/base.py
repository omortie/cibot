from typing import Protocol

import msgspec


class BaseStorage(Protocol):
    def get[T](self, key: str, type_: type[T]) -> T: ...
    def set(self, key: str, value: msgspec.Struct) -> None: ...
