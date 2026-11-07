try:
    a = int(input())
    b = int(input())
except ValueError:
    print("Please enter whole numbers.")
else:
    print(a + b)
