'''
pypi setup.py for apocrypha
'''

from os import path
from setuptools import setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst')) as f:
    long_description = f.read()

version = '2.0.3'
download = \
    'https://github.com/Gandalf-/apocrypha/archive/' + version + 'tar.gz'

setup(
    name='apocrypha',
    packages=['apocrypha'],
    version=version,
    description='A lightweight, flexible JSON server and client',
    long_description=long_description,
    author='Austin Voecks',
    author_email='austin.voecks@gmail.com',
    url='https://github.com/Gandalf-/apocrypha',
    download_url=download,
    keywords=['database', 'json'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3',
    ],
)
