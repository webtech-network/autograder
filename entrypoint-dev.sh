#!/bin/sh

echo "Starting autograder tests"

cd tests

for test_file in test_*.js; do
    echo "--- Running $test_file ---"
    node $test_file
    if [ $? -ne 0 ]; then
        echo "Tests running failed in $test_file, exiting the process..."
        exit 1
    fi
done

cd ..

python dev-test.py
if [ $? -ne 0 ]; then
    echo "There was a problem running the dev-test.py file. Terminating process"
    exit 1
fi

echo "Autograding completed successfully!"