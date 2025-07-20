#!/bin/sh

npm test -- --json --outputFile=./validation/test-results.json

echo "Parsing tests..."
python validation/result_parser.py