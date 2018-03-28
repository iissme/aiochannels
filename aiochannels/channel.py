import asyncio
import weakref
import logging

from collections import deque, AsyncIterable

from .aiterable_deque import AiterableDeque
from .utils import asyncinit, asynclshift

log = logging.getLogger(__name__)


class ChannelError(Exception):
    pass


@asyncinit
class Channel(AsyncIterable):

    @asynclshift
    class Sender:
        __slots__ = ('channel', '_send_queue', '_pending_channel_task', '_pending_self_task')

        def __init__(self, channel, bs):
            self.channel = channel
            self._send_queue = asyncio.Queue(maxsize=bs)
            self._pending_channel_task = None
            self._pending_self_task = None

        async def send(self, data):
            self._pending_self_task = self.channel.loop.create_task(self._send_queue.put(data))
            await self._pending_self_task

            if self.channel._run_channel_task.done():
                raise ChannelError('Channe loop stopped with error!') from self.channel._loop_task_exception

        @property
        def is_attached(self):
            return self in self.channel._senders

        async def detach(self):
            if self.is_attached:
                if self._pending_self_task and not self._pending_self_task.done():
                    self._pending_self_task.cancel()

                if self._pending_channel_task and not self._pending_channel_task.done():
                    self._pending_channel_task.cancel()

                await self.channel._senders.remove(self)

        async def attach(self):
            if not self.is_attached:
                await self.channel._senders.append(self)

        async def __alshift__(self, data):
            await self.send(data)

    class Getter(AsyncIterable):
        __slots__ = ('channel', '_received_queue', '_pending_channel_task',
                     '_pending_self_task', '_callbacks', '_silent_task')

        def __init__(self, channel, bs, silent):
            self.channel = channel
            self._received_queue = asyncio.Queue(maxsize=bs)
            self._callbacks = []
            self._pending_channel_task = None
            self._pending_self_task = None
            self._silent_task = channel.loop.create_task(self._get_silently()) if silent else None

        async def _get_silently(self):
            await asyncio.sleep(0)  # let getter to finish init and attach
            while self.is_attached:
                await self.get()

        async def get_forever(self):
            while self.is_attached:
                yield await self.get()

        async def get(self):
            self.channel._getters_awaiting.set()
            self._pending_self_task = self.channel.loop.create_task(self._received_queue.get())
            for cb in self._callbacks:
                self._pending_self_task.add_done_callback(cb)
            
            data = await self._pending_self_task
            self._received_queue.task_done()

            if self.channel._run_channel_task.done():
                raise ChannelError('Channe loop stopped with error!') from self.channel._loop_task_exception
            else:
                return data

        @property
        def is_attached(self):
            return self in self.channel._getters

        async def attach(self):
            if not self.is_attached:
                await self.channel._getters.append(self)
                if self._silent_task:
                    self._silent_task = self.channel.loop.create_task(self._get_silently())

        async def detach(self):
            if self.is_attached:
                if self._pending_self_task and not self._pending_self_task.done():
                    self._pending_self_task.cancel()

                if self._pending_channel_task and not self._pending_channel_task.done():
                    self._pending_channel_task.cancel()

                if self._silent_task:
                    self._silent_task.cancel()

                await self.channel._getters.remove(self)

        def add_callback(self, callback):
            def get_wrapper(cb):
                def wrapper(task):
                    try:
                        res = task.result()
                        if asyncio.iscoroutinefunction(cb):
                            self.channel.loop.create_task(cb(res))
                        else:
                            cb(res)
                    except asyncio.CancelledError:  # getter is detached
                        pass
                    except Exception:
                        raise

                wrapper.cb = cb
                return wrapper

            self._callbacks.append(get_wrapper(callback))

        def remove_callback(self, callback):
            for cb_wrapper in self._callbacks:
                if cb_wrapper.cb is callback:
                    self._callbacks.remove(cb_wrapper)
                    break

        async def __aiter__(self):
            while not self._received_queue.empty():
                data = await self._received_queue.get()
                self._received_queue.task_done()
                yield data

    async def __ainit__(self, buffer_size=1):
        # AiterableDeque can be edited while async iteration so no aditional mutex is needed
        self._senders = await AiterableDeque()
        self._getters = await AiterableDeque()
        
        self._getters_awaiting = asyncio.Event()
        self.buffer_size = buffer_size
        self.loop = asyncio.get_event_loop()
        
        self._run_channel_task = self.loop.create_task(self._run_channel())
        self._run_channel_task.add_done_callback(self._handle_channel_loop_stop)
        self._loop_task_exception = ChannelError()

        self._finalizer = weakref.finalize(self, self._cancel_pipe_task)

    async def new_sender(self):
        sender = Channel.Sender(self, self.buffer_size)
        await self._senders.append(sender)
        return sender

    async def new_getter(self, *, silent=False):
        getter = Channel.Getter(self, self.buffer_size, silent)
        await self._getters.append(getter)
        return getter

    def close(self):
        self._cancel_pipe_task()

    async def _run_channel(self):
        while await self._getters_awaiting.wait():
            async for sender in self._senders:
                if sender._send_queue.empty():
                    if sender._pending_self_task and not sender._pending_self_task.done():
                        await sender._pending_self_task
                    else:
                        continue

                sender._pending_channel_task = self.loop.create_task(sender._send_queue.get())
                data = await sender._pending_channel_task
                sender._send_queue.task_done()

                self._getters_awaiting.clear()
                async for getter in self._getters:
                    getter._pending_channel_task = self.loop.create_task(getter._received_queue.put(data))
                    await getter._pending_channel_task

            await asyncio.sleep(0)

    def _handle_channel_loop_stop(self, future):
        async def detach_all():
            async for node in self._senders:
                await node.detach()
            async for node in self._getters:
                await node.detach()

        try:
            future.result()
        except Exception as e:
            self._loop_task_exception = e
            trace = getattr(future, '_source_traceback', None)
            full_trace = ''.join(trace.format()) if trace else 'Not available.'
            log.error(f'Channel loop error!\nFull traceback:\n{full_trace}\n'
                      f'Exc info:\n', exc_info=e)
            self.loop.create_task(detach_all())

    def _cancel_pipe_task(self):
        if not self.loop.is_closed():
            self._run_channel_task.cancel()

    async def __aiter__(self):
        async for sender in self._senders:
            if sender._send_queue.empty():
                continue
            data = await sender._send_queue.get()
            sender._send_queue.task_done()
            yield data
