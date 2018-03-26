"""
aiochannels
~~~~~~~~~~~~~~~~~~~
Adds inspired by Golang channels interface for asyncio tasks.
:copyright: (c) 2018 isanich
:license: MIT, see LICENSE for more details.
"""
import logging
from .channel import Channel
from .aiterable_deque import AiterableDeque
from .utils import aenumerate

logging.getLogger(__name__).addHandler(logging.NullHandler())