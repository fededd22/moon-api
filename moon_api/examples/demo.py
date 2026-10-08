"""مثال لمشروع تجريبي — ارفعه للبوت لتجربة النظام."""


def secret_formula(x, y):
    return (x ** 2 + y ** 3) * 42


def fib(n):
    a, b, out = 0, 1, []
    for _ in range(n):
        out.append(a)
        a, b = b, a + b
    return out


if __name__ == "__main__":
    name = input().strip() or "world"
    print(f"hello {name}")
