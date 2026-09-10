def discounted_total(cents):
    if cents > 10000:
        return cents * 90 // 100
    return cents
