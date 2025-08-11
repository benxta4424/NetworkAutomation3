cart = {'apple': 10, 'plums': 15, 'bananas': 5}

shop_K = {'apple': 1.2, 'plums': 4, 'bananas': 5.5}
shop_P = {'apple': 1.3, 'plums': 3, 'bananas': 8}
shop_L = {'apple': 1.4, 'plums': 2, 'bananas': 10}
shop_B = {'apple': 1.2, 'plums': 3}

shops = {'pro': shop_P, 'lil': shop_L, 'kau': shop_K}
prices = {}

for values in shops.keys():
    get_shop = shops[values]
    price_per_shop = 0

    if len(get_shop) < 3:
        continue

    for element in get_shop:
        if element not in cart:
            continue
        else:
            price_per_shop += get_shop[element] * cart[element]

    prices[values] = price_per_shop

print(f"All the shops and their value: {prices}\n")

cheapest_shop = sorted(prices.items(), key = lambda smallest: smallest[1])
print(f"The cheapest shop is  `{cheapest_shop[0][0]}` with a price of: {cheapest_shop[0][1]}")
