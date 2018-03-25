from distutils.core import setup
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

version = '1.0.0'
download = \
    'https://github.com/Gandalf-/apocrypha/archive/' + version + 'tar.gz'

setup(
    name='apocrypha',
    packages=['apocrypha'],
    version=version,
    description='A lightweight, flexible JSON server and client',
    long_description=long_description,
    python_requires='>=3',
    author='Austin Voecks',
    author_email='austin.voecks@gmail.com',
    url='https://github.com/Gandalf-/apocrypha',
    download_url=download,
    keywords=['database', 'json'],
    classifiers=[
        'Development Status :: 2 - Beta',
        'Programming Language :: Python :: 3',
    ],
    project_urls={
        'Bug Reports': 'https://github.com/Gandalf-/apocrypha/issues',
        'Source': 'https://github.com/Gandalf-/apocrypha',
    },
)
