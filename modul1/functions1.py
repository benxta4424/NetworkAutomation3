j = 3
i = 3

while True:
    var = i + j + 1
    space = " " * (i * j)
    print(var * "* " + space)
    i -= 1
    j -= 1

    if j == 0 or i == 0:
        break
print("*")