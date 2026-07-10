import sys
from operations import add, subtract, multiply, divide

def main():
    print("=== Advanced Python Calculator ===")
    print("Enter operations in the format: 5 + 3")
    print("Type 'exit' or 'quit' to close.")
    
    while True:
        try:
            user_input = input(">> ").strip()
            if user_input.lower() in ['exit', 'quit']:
                break
                
            if not user_input:
                continue
                
            parts = user_input.split()
            if len(parts) != 3:
                print("Error: Invalid format. Use 'number operator number' (e.g. 5 * 2)")
                continue
                
            a = float(parts[0])
            op = parts[1]
            b = float(parts[2])
            
            if op == '+':
                res = add(a, b)
            elif op == '-':
                res = subtract(a, b)
            elif op == '*':
                res = multiply(a, b)
            elif op == '/':
                res = divide(a, b)
            else:
                print(f"Error: Unknown operator '{op}'")
                continue
                
            print(f"Result: {res}")
            
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    main()
