import msgspec


class Foo(msgspec.Struct):
    a: int
    b: str


class Bar(msgspec.Struct):
    baz: str


baz_enc = msgspec.json.encode(Bar(baz="hello"))
print(baz_enc)
foo_enc = msgspec.json.encode(Foo(a=1, b=baz_enc.decode()))
print(foo_enc)

foo_dec = msgspec.json.decode(foo_enc, type=Foo)
print(foo_dec)
bar_dec = msgspec.json.decode(foo_dec.b, type=Bar)
print(bar_dec)
