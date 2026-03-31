# Python 基础

## Python 变量与基础数据类型

Python 使用等号进行赋值，例如 `name = "Alice"`、`age = 18`。

常见基础数据类型：
- `int`：整数，例如 `1`、`42`
- `float`：浮点数，例如 `3.14`
- `str`：字符串，例如 `"hello"`
- `bool`：布尔值，只有 `True` 和 `False`

Python 是动态类型语言，不需要提前声明变量类型。

```python
name = "Alice"
age = 18
height = 1.68
is_student = True
```

如果想查看变量类型，可以使用 `type()` 函数。

```python
print(type(name))
print(type(age))
```

## Python 常见数据结构

Python 内置了多种常见数据结构，最常用的是列表、元组、字典和集合。

列表 `list` 是有序、可修改的序列：

```python
numbers = [1, 2, 3]
numbers.append(4)
```

元组 `tuple` 是有序但不可修改的序列：

```python
point = (10, 20)
```

字典 `dict` 使用键值对存储数据：

```python
user = {"name": "Alice", "age": 20}
print(user["name"])
```

集合 `set` 常用于去重：

```python
unique_numbers = {1, 2, 2, 3}
print(unique_numbers)
```

## Python 函数基础

函数使用 `def` 定义，用来封装可复用逻辑。

最简单的函数示例：

```python
def greet(name):
    return f"你好，{name}"
```

调用函数时，传入参数即可：

```python
result = greet("小明")
print(result)
```

函数可以有默认参数：

```python
def power(base, exponent=2):
    return base ** exponent
```

`power(3)` 会返回 `9`，`power(3, 3)` 会返回 `27`。

函数也可以返回多个值，本质上是返回一个元组：

```python
def get_user():
    return "Tom", 20
```




