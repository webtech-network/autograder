// Advanced Calculator - Java Version
// Supports multiple operations: add, subtract, multiply, divide, power, modulo, sqrt

import java.util.Scanner;

public class AdvancedCalculator {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        try {
            String operation = scanner.nextLine().trim().toLowerCase();

            if (operation.equals("sqrt")) {
                double num = Double.parseDouble(scanner.nextLine().trim());
                if (num < 0) {
                    System.out.println("Error: Invalid input");
                } else {
                    System.out.println((int) Math.sqrt(num));
                }
                scanner.close();
                return;
            }

            String input1 = scanner.nextLine().trim();
            String input2 = scanner.nextLine().trim();

            int a, b;
            try {
                a = Integer.parseInt(input1);
                b = Integer.parseInt(input2);
            } catch (NumberFormatException e) {
                System.out.println("Error: Invalid input");
                scanner.close();
                return;
            }

            switch (operation) {
                case "add":
                    System.out.println(a + b);
                    break;
                case "subtract":
                    System.out.println(a - b);
                    break;
                case "multiply":
                    System.out.println(a * b);
                    break;
                case "divide":
                    if (b == 0) {
                        System.out.println("Error: Division by zero");
                    } else {
                        System.out.println(a / b);
                    }
                    break;
                case "power":
                    System.out.println((int) Math.pow(a, b));
                    break;
                case "modulo":
                    System.out.println(a % b);
                    break;
                default:
                    System.out.println("Error: Unknown operation");
            }
        } catch (Exception e) {
            System.out.println("Error: " + e.getMessage());
        }

        scanner.close();
    }
}

