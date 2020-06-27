#!/bin/bash

. ./removemigrations.sh

rm *.sqlite3

python manage.py makemigrations

python manage.py migrate

python manage.py populate all
