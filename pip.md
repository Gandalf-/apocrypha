$ git tag 1.0.0 -m 'version 1.0.0'
$ git push --tags
$ python3 setup.py sdist
$ twine upload dist/*
