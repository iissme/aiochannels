from setuptools import setup
import re
import os

root = os.path.dirname(os.path.abspath(__file__))

about = {}
with open(os.path.join(root, 'aiochannels', '__version__.py'), 'r') as f:
    exec(f.read(), about)

readme = ''
with open(os.path.join(root, 'README.md')) as f:
    readme = f.read()

setup(name=about['__title__'],
      author=about['__author__'],
      author_email='ishlyakhov@gmail.com',
      url='http://github.com/isanich/aiochannels',
      version=about['__version__'],
      license=about['__license__'],
      description='Adds inspired by Golang channels interface for asyncio tasks.',
      long_description=readme,
      packages=['aiochannels'],
      setup_requires=['pytest-runner'],
      tests_require=['pytest'],
      include_package_data=True,
      platforms='any',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'License :: OSI Approved :: MIT License',
          'Intended Audience :: Developers',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: Software Development :: Libraries',
          'Topic :: Software Development :: Libraries :: Python Modules',
      ]
      )
