#!/bin/sh

echo "Running tests..."
npm test -- --json --outputFile=./tests/test-results.json

echo "Parsing tests..."
python tests/result-parser.py

echo "Running autograder..."
python qualquer-coisa-na-real.py