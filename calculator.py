"""A simple interactive calculator."""


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b
    


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b


OPERATIONS = {
    "1": ("Addition", add),
    "2": ("Subtraction", subtract),
    "3": ("Multiplication", multiply),
    "4": ("Division", divide),
}


def get_number(prompt):
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Please enter a valid number.")


def main():
    print("Welcome to the Calculator!")

    while True:
        print("\nSelect an operation:")
        for key, (name, _) in OPERATIONS.items():
            print(f"  {key}. {name}")
        print("  5. Exit")

        choice = input("Enter your choice (1-5): ").strip()

        if choice == "5":
            print("Goodbye!")
            break

        if choice not in OPERATIONS:
            print("Invalid choice. Please select 1-5.")
            continue

        first = get_number("Enter the first number: ")
        second = get_number("Enter the second number: ")

        name, operation = OPERATIONS[choice]
        try:
            result = operation(first, second)
            print(f"{name} result: {result}")
        except ValueError as error:
            print(f"Error: {error}")


if __name__ == "__main__":
    main()
