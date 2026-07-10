def calculate_total(items):
    # Bug: sum is broken if items is empty, or maybe we just have a logical flaw
    total = 0
    for item in items:
        total += item  # Fixed: addition
    return total

if __name__ == "__main__":
    prices = [10, 20, 30]
    print(f"Total: {calculate_total(prices)}")
