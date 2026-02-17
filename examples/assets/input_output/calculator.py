#!/usr/bin/env python3
"""
Simple Calculator Program
Reads operation and two numbers from stdin and outputs the result.
"""

import sys


def main():
    try:
        # Read inputs from stdin
        operation = input().strip()
        num1 = float(input().strip())
        num2 = float(input().strip())
        
        # Perform calculation based on operation
        if operation == "add":
            result = num1 + num2
        elif operation == "subtract":
            result = num1 - num2
        elif operation == "multiply":
            result = num1 * num2
        elif operation == "divide":
            if num2 == 0:
                print("Error: Division by zero")
                return
            result = num1 / num2
        else:
            print(f"Error: Unknown operation '{operation}'")
            return
        
        # Print result (integer if whole number, otherwise float)
        if result == int(result):
            print(int(result))
        else:
            print(result)
            
    except ValueError:
        print("Error: Invalid input")
    except EOFError:
        print("Error: Unexpected end of input")


if __name__ == "__main__":
    main()
