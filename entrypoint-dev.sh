#!/bin/sh

echo "Running tests"
npm test -- --json --outputFile=./tests/test-results.json

node ./tests/results-parser.js

#python dev-test.py
#if [ $? -ne 0 ]; then
#    echo "There was a problem running the dev-test.py file. Terminating process..."
#    exit 1
#else 
#   echo "Autograder finished successfully!"
#fi