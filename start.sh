#!/bin/bash

source activate nyc_bus
gunicorn --bind 0.0.0.0:$PORT wsgi