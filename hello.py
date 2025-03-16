import json

import msgspec


class Foo(msgspec.Struct):
	a: int
	b: str


class Bar(msgspec.Struct):
	baz: str


baz_builtins = msgspec.to_builtins(Bar(baz="hello"))

dumped = json.dumps(baz_builtins, indent=2)
print(dumped)
decoded = msgspec.json.decode(dumped, type=Bar)
print(decoded)
