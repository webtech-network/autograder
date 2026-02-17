# Advanced Calculator - Python Version
# Supports multiple operations: add, subtract, multiply, divide, power, modulo, sqrt

import sys
import math

def main():
    try:
        operation = input().strip().lower()

        if operation == "sqrt":
            num = float(input())
            if num < 0:
                print("Error: Invalid input")
            else:
                result = int(math.sqrt(num))
                print(result)
            return

        num1 = input().strip()
        num2 = input().strip()

        # Validate inputs are numbers
        try:
            a = int(num1)
            b = int(num2)
        except ValueError:
            print("Error: Invalid input")
            return

        if operation == "add":
            print(a + b)
        elif operation == "subtract":
            print(a - b)
        elif operation == "multiply":
            print(a * b)
        elif operation == "divide":
            if b == 0:
                print("Error: Division by zero")
            else:
                print(a // b)
        elif operation == "power":
            print(a ** b)
        elif operation == "modulo":
            print(a % b)
        else:
            print("Error: Unknown operation")

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()

