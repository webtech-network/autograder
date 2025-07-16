#!/bin/sh

npm test -- --json --outputFile=./tests/test-results.json

echo "Parsing tests..."
python tests/result_parser.py