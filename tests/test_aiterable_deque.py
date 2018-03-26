from tests.test_asyncio_prepare import *
from collections import deque
from random import random


@async_test
async def test_public_methods():
    from_list = [1, 2, 3, 4, 5, 6, 7]
    test_deque = deque(from_list)
    q = await AiterableDeque(from_list)

    assert await q.flattern() == from_list

    await q.remove(5)
    test_deque.remove(5)
    assert list(test_deque) == await q.flattern()

    await q.append(8)
    test_deque.append(8)
    assert list(test_deque) == await q.flattern()

    await q.appendleft(0)
    test_deque.appendleft(0)
    assert list(test_deque) == await q.flattern()

    await q.insert(1, 55)
    test_deque.insert(1, 55)
    assert list(test_deque) == await q.flattern()

    assert await q[-1] == test_deque[-1]
    assert (3 in q) == (3 in test_deque)


@async_test
async def test_append_pop_while_iterating():
    q = await AiterableDeque([1, 2, 3, 4, 5, 6, 7, 8])
    edits_count = 2

    before_len = len(q)
    async for i, value in aenumerate(q):
        if i < edits_count:
            await q.popleft()
    assert len(q) == before_len - edits_count

    before_len = len(q)
    async for i, value in aenumerate(q):
        if i < edits_count:
            await q.appendleft(i)
    assert len(q) == before_len + edits_count

    b = await q.flattern()

    before_len = len(q)
    async for i, value in aenumerate(q):
        if i < edits_count:
            await q.pop()
    assert len(q) == before_len - edits_count

    before_len = len(q)
    async for i, value in aenumerate(q):
        if i < edits_count:
            await q.append(random())
            await q.append(random())
    assert len(q) == before_len + edits_count*2


@async_test
async def test_remove_while_iterating():
    q = await AiterableDeque([1, 2, 3, 4, 5, 6, 7, 8])

    q.remove(4)
    async for i, value in aenumerate(q, start_from=5):
        await q.remove(i)

    assert [1, 2, 3] == await q.flattern()


@async_test
async def test_insert_while_iterating():
    q = await AiterableDeque([1, 2, 3, 4, 5, 6, 7, 8])
    test_deque = deque(await q.flattern())

    test_deque.insert(1, 44)
    q.insert(1, 44)
    async for _ in q:
        val = random()
        await q.insert(4, val)
        test_deque.insert(4, val)

    assert list(test_deque) == await q.flattern()
