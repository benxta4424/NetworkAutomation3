def prims():
    primes = []
    primes.append(2)

    all_vars = 0

    for i in range(3, 1001):
        counter = 0

        if i % 2 == 0:
            continue

        for j in range(2, i // 2 + 1):
            if i % j == 0:
                counter += 1

        if counter == 0:
            primes.append(i)
            all_vars += 1

        if all_vars == 100:
            return primes


print(prims())
