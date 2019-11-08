import asyncio

from functools import wraps
from collections import AsyncIterable, Iterable


from .utils import asyncinit, aenumerate


@asyncinit
class AiterableDeque(AsyncIterable):

    def async_task(f):
        """
        Task wrapper decorator for public deque methods.
        Such methods could be called either with or wthout 'await'
        """
        def tmp(self, *args, **kwargs):
            @wraps(f)
            async def task_wrapper():
                return await f(self, *args, **kwargs)

            def task_callback(task):
                if task in self._edit_tasks:
                    self._edit_tasks.remove(task)

            pending_task = self.loop.create_task(task_wrapper())
            self._edit_tasks.append(pending_task)
            pending_task.add_done_callback(task_callback)
            return pending_task

        return tmp

    class Node:
        __slots__ = ('val', 'prev', 'next')

        def __init__(self, val):
            self.val = val
            self.prev = None
            self.next = None

        def __repr__(self):
            nstr = repr(self.val)
            if self.val is None:
                if self.prev is None:
                    nstr = 'Right anchor'
                if self.next is None:
                    nstr = 'Left anchor'
            return f'Node - {nstr}'

    async def __ainit__(self, iterable=None, loop=None):
        self.loop = loop if loop else asyncio._get_running_loop()
        self._edit_mutex = asyncio.Lock()
        self._edit_tasks = []

        self.left_anchor = self.Node(None)
        self.right_anchor = self.Node(None)
        self.left_anchor.next = self.right_anchor
        self.right_anchor.prev = self.left_anchor

        self._nodes = set()
        self._nodes.add(self.left_anchor)
        self._nodes.add(self.right_anchor)

        if iterable:
            if not isinstance(iterable, Iterable):
                raise TypeError('Iterable instance is expected!')

            for el in iterable:
                await self.append(el)

    def _attach_node(self, prev_node, new_node, next_node):
        prev_node.next = new_node
        next_node.prev = new_node
        new_node.prev = prev_node
        new_node.next = next_node
        self._nodes.add(new_node)

    def _detach_node(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev
        self._nodes.remove(node)

    @async_task
    async def append(self, val):
        async with self._edit_mutex:
            self._attach_node(
                self.right_anchor.prev,
                self.Node(val),
                self.right_anchor)

    @async_task
    async def pop(self):
        if not len(self):
            raise IndexError('Pop from empty list!')

        async with self._edit_mutex:
            node = self.right_anchor.prev
            self._detach_node(node)
            return node.val

    @async_task
    async def popleft(self):
        if not len(self):
            raise IndexError('Pop from empty list!')

        async with self._edit_mutex:
            node = self.left_anchor.next
            self._detach_node(node)
            return node.val

    @async_task
    async def appendleft(self, val):
        async with self._edit_mutex:
            self._attach_node(
                self.left_anchor,
                self.Node(val),
                self.left_anchor.next)

    @async_task
    async def insert(self, ix, val):
        prev_node = (await self.__getitem__(ix, invoker_task='insert')).prev
        async with self._edit_mutex:
            new_node = self.Node(val)
            next_node = prev_node.next
            self._attach_node(prev_node, new_node, next_node)

    @async_task
    async def remove(self, expected_val):
        async with self._edit_mutex:
            for node in self._nodes:
                if node.val == expected_val:
                    self._detach_node(node)
                    break

    @async_task
    async def flattern(self):
        q_list = []
        async for node in self._walk_nodes(invoker_task='flattern'):
            q_list.append(node.val)

        return q_list

    async def _walk_nodes(self, invoker_task=''):
        node = self.left_anchor.next
        while node is not self.right_anchor:
            while self._edit_tasks:
                task = self._edit_tasks.pop()
                if not task.done() and not task._coro.__name__ == invoker_task:  # preventing self-invoke
                    await task

            async with self._edit_mutex:  # in case edit tasks from another thread
                while node not in self._nodes:
                    node = node.next
                    if node is self.right_anchor:
                        return

            yield node
            node = node.next
            await asyncio.sleep(0)

    def __len__(self):
        return len(self._nodes) - 2

    def __getitem__(self, expected_ix, invoker_task=''):
        if isinstance(expected_ix, slice):
            raise TypeError('Slices are not supported!')

        if expected_ix < 0:
            expected_ix = len(self) + expected_ix

        async def task_wrapper():
            # when edit queue while iterating you can get new value at the same ix
            async for ix, node in aenumerate(self._walk_nodes(invoker_task)):
                if expected_ix > len(self) - 1 or expected_ix < 0:
                    raise IndexError('Index out of range!')

                if ix == expected_ix:
                    return node.val if not invoker_task else node

        return self.loop.create_task(task_wrapper())

    def __contains__(self, expected_val):
        for node in self._nodes:
            if node.val == expected_val:
                return True
        else:
            return False

    async def __aiter__(self):
        if len(self):
            async for node in self._walk_nodes():
                yield node.val
