#!/bin/sh

echo "Starting autograder tests"

npm test -- --json --outputFile=./tests/test-results.json

#python dev-test.py
#if [ $? -ne 0 ]; then
#    echo "There was a problem running the dev-test.py file. Terminating process"
#    exit 1
#fi

echo "Autograding completed successfully!"