// Advanced Calculator - C++ Version
// Supports multiple operations: add, subtract, multiply, divide, power, modulo, sqrt

#include <iostream>
#include <string>
#include <cmath>
#include <algorithm>

int main() {
    std::string operation;
    std::getline(std::cin, operation);

    // Convert to lowercase
    std::transform(operation.begin(), operation.end(), operation.begin(), ::tolower);
    // Trim whitespace
    operation.erase(0, operation.find_first_not_of(" \t\n\r"));
    operation.erase(operation.find_last_not_of(" \t\n\r") + 1);

    if (operation == "sqrt") {
        std::string numStr;
        std::getline(std::cin, numStr);
        try {
            double num = std::stod(numStr);
            if (num < 0) {
                std::cout << "Error: Invalid input" << std::endl;
            } else {
                std::cout << static_cast<int>(std::sqrt(num)) << std::endl;
            }
        } catch (...) {
            std::cout << "Error: Invalid input" << std::endl;
        }
        return 0;
    }

    std::string input1, input2;
    std::getline(std::cin, input1);
    std::getline(std::cin, input2);

    int a, b;
    try {
        a = std::stoi(input1);
        b = std::stoi(input2);
    } catch (...) {
        std::cout << "Error: Invalid input" << std::endl;
        return 0;
    }

    if (operation == "add") {
        std::cout << a + b << std::endl;
    } else if (operation == "subtract") {
        std::cout << a - b << std::endl;
    } else if (operation == "multiply") {
        std::cout << a * b << std::endl;
    } else if (operation == "divide") {
        if (b == 0) {
            std::cout << "Error: Division by zero" << std::endl;
        } else {
            std::cout << a / b << std::endl;
        }
    } else if (operation == "power") {
        std::cout << static_cast<int>(std::pow(a, b)) << std::endl;
    } else if (operation == "modulo") {
        std::cout << a % b << std::endl;
    } else {
        std::cout << "Error: Unknown operation" << std::endl;
    }

    return 0;
}

