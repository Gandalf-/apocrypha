#!/bin/bash

coverage erase
coverage run --branch -a --source apocrypha/ test/test_database_action.py
coverage run --branch -a --source apocrypha/ test/test_database_unit.py
coverage run --branch -a --source apocrypha/ test/test_server.py
coverage run --branch -a --source apocrypha/ test/test_node.py
coverage run --branch -a --source apocrypha/ test/test_network.py
coverage run --branch -a --source apocrypha/ test/test_datum.py

coverage html
