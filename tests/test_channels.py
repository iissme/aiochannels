from tests.test_asyncio_prepare import *


async def simple_getter_generator(ch):
    getter = await ch.new_getter()
    for _ in range(10):
        yield await getter.get()
    await getter.detach()


async def simple_pinger(ch):
    msg = 'ping'
    sender = await ch.new_sender()
    while True:
        await sender.send(msg)


async def simple_ponger(ch):
    msg = 'pong'
    sender = await ch.new_sender()
    while True:
        await (sender << msg)


@async_test
async def test_simple_getters():
    ch = await Channel()

    pinger_task = loop.create_task(simple_pinger(ch))
    ponger_task = loop.create_task(simple_ponger(ch))

    last_msg = ''
    async for res in simple_getter_generator(ch):
        if last_msg is 'ping':
            assert res == 'pong'
        elif last_msg is 'pong':
            assert res == 'ping'
        last_msg = res

    getter_1 = await ch.new_getter()
    getter_2 = await ch.new_getter()

    for _ in range(50):
        msg_1 = await getter_1.get()
        msg_2 = await getter_2.get()
        assert msg_1 == msg_2

    pinger_task.cancel()
    ponger_task.cancel()


@async_test
async def test_get_forever():

    async def forever_getter(channel):
        getter = await channel.new_getter()
        async for ix, msg in aenumerate(getter.get_forever()):
            if ix > 5:
                await getter.detach()
            assert msg == 'ping'

    ch = await Channel()
    pinger_task = loop.create_task(simple_pinger(ch))
    await forever_getter(ch)
    pinger_task.cancel()


@async_test
async def test_buffered_channel():
    ch = await Channel(2)
    pinger_task = loop.create_task(simple_pinger(ch))
    getter = await ch.new_getter()

    async for ix, msg in aenumerate(getter.get_forever()):
        if ix > 50:
            await getter.detach()
        assert msg == 'ping'

    pinger_task.cancel()


@async_test
async def test_buffered_channel_iteration():
    ch = await Channel(5)
    sender = await ch.new_sender()
    getter_1 = await ch.new_getter()
    getter_2 = await ch.new_getter()

    for i in range(5):
        await sender.send('ping')

    for i in range(5):
        await getter_1.get()

    async for data in getter_2:
        assert data == 'ping'


@async_test
async def test_buffered_channel():
    ch = await Channel(50)
    sender = await ch.new_sender()
    msg = 'buff_ping'

    for i in range(50):
        await sender.send(msg)

    async for data in ch:
        assert data == msg


@async_test
async def test_callback_getter():
    ch = await Channel()
    pinger_task = loop.create_task(simple_pinger(ch))

    def cb_1(res):
        assert res == 'ping'
        cb_1.fired = True

    async def cb_2(res):
        assert res == 'ping'
        cb_2.fired = True

    getter = await ch.new_getter()
    getter.add_callback(cb_1)
    getter.add_callback(cb_2)
    await getter.get()
    getter.remove_callback(cb_1)

    await asyncio.sleep(0)  # let handle async cb
    getter.remove_callback(cb_2)
    pinger_task.cancel()

    assert cb_1.fired is True
    assert cb_2.fired is True


@async_test
async def test_silent_getter():
    def cb(res):
        assert res == 'ping'
        cb_fired.set()

    ch = await Channel(10)
    cb_fired = asyncio.Event()
    pinger_task = loop.create_task(simple_pinger(ch))
    getter = await ch.new_getter(silent=True)
    getter.add_callback(cb)

    await cb_fired.wait()
    await getter.detach()
    cb_fired.clear()

    await getter.attach()
    await cb_fired.wait()

    await getter.detach()
    pinger_task.cancel()
