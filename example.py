import asyncio
from aiochannels import Channel, aenumerate


async def simple_pinger(ch):
    sender = await ch.new_sender()
    while sender.is_attached:
        # sender can be detached from Channel with `sender.detach`
        await sender.send('ping')


async def simple_ponger(ch):
    sender = await ch.new_sender()
    while sender.is_attached:
        await (sender << 'pong')  # another variant of `sender.send`


async def main():
    channel = await Channel(buffer_size=10)
    # Channel without buffer_size argument or buffer_size=1 leads to Go-like behavior
    # meaning that senders can send only if getters have already received previously sent
    # data with `getter.get` or `getter.get_forever`. buffer_size>1 behavior is also similar to Go.
    pinger_task = loop.create_task(simple_pinger(channel))
    ponger_task = loop.create_task(simple_ponger(channel))

    # pinger and ponger are created with asyncio.Task and will be running asynchronously until their tasks
    # are cancelled or senders detached (you should reference those senders elsewhere for this).
    getter = await channel.new_getter()

    # getters can receive with `getter.get` manually
    print(await getter.get())  # ping
    print(await getter.get())  # pong
    print(await getter.get())  # ping

    # and with async generator `getter.get_forever`
    async for ix, data in aenumerate(getter.get_forever()):  # aenumerate is async `enumerate` analogue
        if ix >= 5:
            # await getter.detach() - could cause to similar effect as `break`, but getter will no longer receive
            break
        print(f'Received from `getter.get_forever` - {data}')

    # Sync/async callbacks are supported too
    def cb_1(msg):
        print(f'Sync callback got - {msg}')

    async def cb_2(msg):
        print(f'Async callback got - {msg}')

    getter.add_callback(cb_1)
    getter.add_callback(cb_2)
    # If you getter is not `silent` (see `silent_getter` below) callbacks should be
    # triggered with `getter.get` or `getter.get_forever`
    await getter.get()  # `cb_1` fired and `cb_2` task is put into asyncio loop
    await asyncio.sleep(0)  # let async callback fire
    getter.remove_callback(cb_1)
    getter.remove_callback(cb_2)

    await getter.detach()  # getter can be detached and will no longer receive
    # await getter.attach() - and attached again

    silent_getter = await channel.new_getter(silent=True)
    # You can pass silent=True argument to `new_getter()` if you are planning to use this getter with
    # callbacks only without explicit `getter.get` or `getter.get_forever`).
    getter.add_callback(cb_1)
    print('Calbacks from silent getter:')
    await asyncio.sleep(0.1)  # callbacks will be triggered during sleep
    await silent_getter.detach()
    # As Channel buffer_size is 10 and there is no more getters
    # pinger/ponger tasks are asleep now, but we can cancel them anyway.
    pinger_task.cancel()
    ponger_task.cancel()

loop = asyncio.get_event_loop()
loop.run_until_complete(main())
