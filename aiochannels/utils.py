from collections import Iterable, AsyncIterable, AsyncIterator


def asyncinit(cls):
    """
    class decorator for __ainit__ support
    """
    __cnew__ = cls.__new__

    async def init(obj, *args, **kwargs):
        await obj.__ainit__(*args, **kwargs)
        return obj

    def new(cls, *args, **kwargs):
        obj = __cnew__(cls)
        coro = init(obj, *args, **kwargs)
        return coro

    cls.__new__ = new
    return cls


def asynclshift(cls):
    def lshift_wrapper(obj, *args, **kwargs):
        async def alshift(obj, *args, **kwargs):
            return await obj.__alshift__(*args, **kwargs)
        return alshift(obj, *args, **kwargs)

    cls.__lshift__ = lshift_wrapper
    return cls


class aenumerate(AsyncIterator):
    """
    'async for' enumerate replacement
    """
    def __init__(self, aiterable, start_from=0):
        if not isinstance(aiterable, AsyncIterable):
            raise TypeError('Async iterable is expected!')

        self._aiterable = aiterable
        self._aiterator = None
        self.ix = start_from - 1

    def __aiter__(self):
        self._aiterator = self._aiterable.__aiter__()
        return self

    async def __anext__(self):
        self.ix += 1
        return self.ix, await self._aiterator.__anext__()
