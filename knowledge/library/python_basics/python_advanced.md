# Python高级应用指南

## 目录

1. 面向对象高级特性
2. 元编程
3. 并发与并行编程
4. 性能优化技术
5. 高级函数式编程
6. 上下文管理器与装饰器
7. 内存管理与垃圾回收
8. C扩展与性能关键代码
9. 设计模式应用
10. 最佳实践与工程化

---

## 面向对象高级特性

### 1.1 描述符协议

描述符是实现了`__get__`、`__set__`、`__delete__`方法的类，用于控制属性访问。

```
class TypedDescriptor:
    def __init__(self, name, expected_type):
        self.name = name
        self.expected_type = expected_type
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.name)
    
    def __set__(self, obj, value):
        if not isinstance(value, self.expected_type):
            raise TypeError(f"Expected {self.expected_type.__name__}")
        obj.__dict__[self.name] = value

class Person:
    name = TypedDescriptor("name", str)
    age = TypedDescriptor("age", int)
    
    def __init__(self, name, age):
        self.name = name
        self.age = age
```

### 1.2 `__slots__`优化

使用`__slots__`可以限制类的属性，减少内存占用。

```
class OptimizedClass:
    __slots__ = ['x', 'y', 'z']
    
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
```

### 1.3 多重继承与MRO

```
class A:
    def method(self):
        print("A.method")

class B(A):
    def method(self):
        print("B.method")
        super().method()

class C(A):
    def method(self):
        print("C.method")
        super().method()

class D(B, C):
    def method(self):
        print("D.method")
        super().method()

# MRO: D -> B -> C -> A -> object
d = D()
d.method()
```

---

## 元编程

### 2.1 元类

元类是创建类的类，用于控制类的创建过程。

```
class SingletonMeta(type):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class DatabaseConnection(metaclass=SingletonMeta):
    def __init__(self):
        self.connection = "Connected to database"

# 使用元类实现API注册
class APIRegistry(type):
    _apis = {}
    
    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)
        if name != 'BaseAPI':
            cls._apis[name] = new_class
        return new_class
    
    @classmethod
    def get_api(cls, name):
        return cls._apis.get(name)

class BaseAPI(metaclass=APIRegistry):
    pass

class UserAPI(BaseAPI):
    def get_users(self):
        return ["user1", "user2"]
```

### 2.2 动态类创建

```
def create_class(class_name, base_classes, attributes):
    return type(class_name, base_classes, attributes)

# 动态创建类
MyClass = create_class(
    "MyClass",
    (object,),
    {
        "x": 10,
        "y": 20,
        "add": lambda self: self.x + self.y
    }
)
```

---

## 并发与并行编程

### 3.1 多线程编程

```
import threading
import time
from concurrent.futures import ThreadPoolExecutor

class ThreadSafeCounter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()
    
    def increment(self):
        with self._lock:
            self._value += 1
            return self._value

def worker(counter, results):
    for _ in range(1000):
        results.append(counter.increment())

counter = ThreadSafeCounter()
results = []
threads = []

for i in range(10):
    t = threading.Thread(target=worker, args=(counter, results))
    threads.append(t)
    t.start()

for t in threads:
    t.join()
```

### 3.2 多进程编程

```
import multiprocessing
from multiprocessing import Pool, Manager

def process_data(data_chunk):
    # 模拟CPU密集型任务
    return sum(x**2 for x in data_chunk)

if __name__ == '__main__':
    data = list(range(1000000))
    chunk_size = len(data) // multiprocessing.cpu_count()
    
    with Pool() as pool:
        chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
        results = pool.map(process_data, chunks)
    
    total = sum(results)
```

### 3.3 异步编程

```
import asyncio
import aiohttp
import asyncpg

async def fetch_data(session, url):
    async with session.get(url) as response:
        return await response.text()

async def process_items(items):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_data(session, item['url']) for item in items]
        return await asyncio.gather(*tasks)

async def database_operations():
    conn = await asyncpg.connect('postgresql://user:pass@localhost/dbname')
    await conn.execute('INSERT INTO users(name) VALUES($1)', 'John')
    users = await conn.fetch('SELECT * FROM users')
    await conn.close()
    return users
```

---

## 性能优化技术

### 4.1 算法优化

```
# 低效的O(n²)算法
def find_duplicates_slow(arr):
    duplicates = []
    for i in range(len(arr)):
        for j in range(i + 1, len(arr)):
            if arr[i] == arr[j] and arr[i] not in duplicates:
                duplicates.append(arr[i])
    return duplicates

# 高效的O(n)算法
def find_duplicates_fast(arr):
    seen = set()
    duplicates = set()
    for item in arr:
        if item in seen:
            duplicates.add(item)
        else:
            seen.add(item)
    return list(duplicates)

# 使用字典优化查找
def group_by_category(items):
    # O(n) instead of O(n²)
    grouped = {}
    for item in items:
        category = item['category']
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(item)
    return grouped
```

### 4.2 内存优化

```
import sys
from collections import namedtuple
from typing import NamedTuple

# 普通类
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

# 命名元组 - 更节省内存
PointNT = namedtuple('PointNT', ['x', 'y'])

# 类型注解的命名元组
class PointTyped(NamedTuple):
    x: float
    y: float

# 使用__slots__优化
class PointSlots:
    __slots__ = ['x', 'y']
    
    def __init__(self, x, y):
        self.x = x
        self.y = y
```

### 4.3 性能分析工具

```
import cProfile
import pstats
from memory_profiler import profile

@profile
def memory_intensive_function():
    data = []
    for i in range(100000):
        data.append(i * i)
    return sum(data)

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # 要分析的代码
    result = memory_intensive_function()
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)
```

---

## 高级函数式编程

### 5.1 高阶函数

```
from functools import partial, reduce, wraps
from typing import Callable, Any

# 函数柯里化
def curry(func):
    @wraps(func)
    def curried(*args, **kwargs):
        if len(args) + len(kwargs) >= func.__code__.co_argcount:
            return func(*args, **kwargs)
        return partial(curried, *args, **kwargs)
    return curried

@curry
def add(a, b, c):
    return a + b + c

add5 = add(5)  # 固定第一个参数
add5_10 = add5(10)  # 固定前两个参数
result = add5_10(15)  # 30
```

### 5.2 函数式数据处理

```
from operator import add, mul
from functools import reduce

# 使用map-reduce模式
def process_data_functional(data):
    # 过滤有效数据
    valid_data = filter(lambda x: x > 0, data)
    
    # 转换数据
    squared = map(lambda x: x**2, valid_data)
    
    # 聚合结果
    total = reduce(add, squared, 0)
    
    return total

# 管道模式
def pipe(*functions):
    def composed_function(data):
        result = data
        for func in functions:
            result = func(result)
        return result
    return composed_function

# 创建数据处理管道
pipeline = pipe(
    lambda x: filter(lambda y: y > 0, x),
    lambda x: map(lambda y: y**2, x),
    lambda x: reduce(add, x, 0)
)
```

---

## 上下文管理器与装饰器

### 6.1 高级装饰器

```
import time
import functools
from typing import Callable, Any

def timing_decorator(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} executed in {end_time - start_time:.4f} seconds")
        return result
    return wrapper

def retry_decorator(max_attempts: int = 3, delay: float = 1.0):
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay * (2 ** attempt))  # 指数退避
            raise last_exception
        return wrapper
    return decorator

@timing_decorator
@retry_decorator(max_attempts=3, delay=0.5)
def fetch_data_with_retry(url):
    # 模拟网络请求
    import random
    if random.random() < 0.7:  # 70%失败率
        raise ConnectionError("Network error")
    return f"Data from {url}"
```

### 6.2 上下文管理器

```
from contextlib import contextmanager
import sqlite3

@contextmanager
def database_connection(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        yield conn
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

@contextmanager
def timer():
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        print(f"Operation took {end_time - start_time:.4f} seconds")

# 使用嵌套上下文管理器
with database_connection('example.db') as conn, timer():
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
```

---

## 内存管理与垃圾回收

### 7.1 引用计数与循环引用

```
import sys
import weakref

class Node:
    def __init__(self, value):
        self.value = value
        self.parent = None
        self.children = []
    
    def add_child(self, child):
        child.parent = self
        self.children.append(child)

# 循环引用问题
def create_cycle():
    a = Node(1)
    b = Node(2)
    a.add_child(b)
    b.add_child(a)  # 创建循环引用
    return a, b

# 使用弱引用来解决循环引用
class WeakNode:
    def __init__(self, value):
        self.value = value
        self.parent = None
        self.children = []
    
    def add_child(self, child):
        child.parent = weakref.ref(self)  # 使用弱引用
        self.children.append(child)
```

### 7.2 内存泄漏检测

```
import tracemalloc
import gc

def detect_memory_leak():
    tracemalloc.start()
    
    # 拍摄初始快照
    initial_snapshot = tracemalloc.take_snapshot()
    
    # 执行可能泄漏的代码
    leaked_objects = []
    for i in range(1000):
        leaked_objects.append([i] * 100)
    
    # 拍摄最终快照
    final_snapshot = tracemalloc.take_snapshot()
    
    # 比较快照
    top_stats = final_snapshot.compare_to(initial_snapshot, 'lineno')
    
    for stat in top_stats[:10]:
        print(stat)
    
    tracemalloc.stop()
```

---

## C扩展与性能关键代码

### 8.1 使用Cython

```
# example.pyx
def fib(int n):
    cdef int a = 0
    cdef int b = 1
    cdef int i
    for i in range(n):
        a, b = a + b, a
    return a

# setup.py
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules = cythonize("example.pyx")
)
```

### 8.2 使用ctypes调用C库

```
import ctypes
import numpy as np

# 加载C库
libc = ctypes.CDLL("libc.so.6")

# 定义函数原型
libc.sqrt.argtypes = [ctypes.c_double]
libc.sqrt.restype = ctypes.c_double

def fast_sqrt(x):
    return libc.sqrt(x)

# 使用numpy进行高效数组操作
def vectorized_operations():
    # 创建大型数组
    a = np.random.rand(1000000)
    b = np.random.rand(1000000)
    
    # 向量化操作
    result = np.sqrt(a**2 + b**2)
    return result
```

---

## 设计模式应用

### 9.1 工厂模式

```
from abc import ABC, abstractmethod
from typing import Dict, Type

class Product(ABC):
    @abstractmethod
    def operation(self) -> str:
        pass

class ConcreteProductA(Product):
    def operation(self) -> str:
        return "Product A operation"

class ConcreteProductB(Product):
    def operation(self) -> str:
        return "Product B operation"

class Factory:
    _product_map: Dict[str, Type[Product]] = {
        "A": ConcreteProductA,
        "B": ConcreteProductB
    }
    
    @classmethod
    def create_product(cls, product_type: str) -> Product:
        product_class = cls._product_map.get(product_type)
        if not product_class:
            raise ValueError(f"Unknown product type: {product_type}")
        return product_class()
```

### 9.2 策略模式

```
from abc import ABC, abstractmethod
from typing import List

class SortStrategy(ABC):
    @abstractmethod
    def sort(self, data: List[int]) -> List[int]:
        pass

class QuickSortStrategy(SortStrategy):
    def sort(self, data: List[int]) -> List[int]:
        if len(data) <= 1:
            return data
        pivot = data[len(data) // 2]
        left = [x for x in data if x < pivot]
        middle = [x for x in data if x == pivot]
        right = [x for x in data if x > pivot]
        return self.sort(left) + middle + self.sort(right)

class MergeSortStrategy(SortStrategy):
    def sort(self, data: List[int]) -> List[int]:
        if len(data) <= 1:
            return data
        
        mid = len(data) // 2
        left = self.sort(data[:mid])
        right = self.sort(data[mid:])
        
        return self._merge(left, right)
    
    def _merge(self, left: List[int], right: List[int]) -> List[int]:
        result = []
        i = j = 0
        
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                result.append(left[i])
                i += 1
            else:
                result.append(right[j])
                j += 1
        
        result.extend(left[i:])
        result.extend(right[j:])
        return result

class SortContext:
    def __init__(self, strategy: SortStrategy):
        self._strategy = strategy
    
    def set_strategy(self, strategy: SortStrategy):
        self._strategy = strategy
    
    def sort(self, data: List[int]) -> List[int]:
        return self._strategy.sort(data)
```

---

## 最佳实践与工程化

### 10.1 代码质量工具

```
# .pre-commit-config.yaml
"""
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.0.1
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
  
  - repo: https://github.com/psf/black
    rev: 22.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/flake8
    rev: 4.0.1
    hooks:
      - id: flake8
"""

# 使用mypy进行类型检查
"""
def greet(name: str) -> str:
    return f"Hello, {name}!"

# mypy会检查类型错误
greet(123)  # 类型错误
"""
```

### 10.2 测试策略

```
import unittest
from unittest.mock import Mock, patch
import pytest

# 单元测试
class TestCalculator(unittest.TestCase):
    def setUp(self):
        self.calc = Calculator()
    
    def test_add(self):
        result = self.calc.add(2, 3)
        self.assertEqual(result, 5)
    
    @patch('module.external_service')
    def test_with_mock(self, mock_service):
        mock_service.return_value = True
        result = self.calc.process_with_external()
        self.assertTrue(result)

# 集成测试
@pytest.mark.integration
def test_database_connection():
    conn = DatabaseConnection()
    result = conn.query("SELECT 1")
    assert result == 1

# 性能测试
import timeit

def performance_benchmark():
    setup_code = "from module import function"
    test_code = "function(data)"
    
    times = timeit.repeat(setup=setup_code, stmt=test_code, 
                         repeat=5, number=1000)
    print(f"Min time: {min(times)}")
```

### 10.3 配置管理

```
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class DatabaseConfig:
    host: str
    port: int
    username: str
    password: str
    database: str

@dataclass
class AppConfig:
    debug: bool
    secret_key: str
    database: DatabaseConfig

class ConfigLoader:
    @staticmethod
    def load_config() -> AppConfig:
        db_config = DatabaseConfig(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            username=os.getenv('DB_USER', 'user'),
            password=os.getenv('DB_PASSWORD', 'password'),
            database=os.getenv('DB_NAME', 'app_db')
        )
        
        return AppConfig(
            debug=os.getenv('DEBUG', 'False').lower() == 'true',
            secret_key=os.getenv('SECRET_KEY', 'default_key'),
            database=db_config
        )
```

---

## 结语

Python的高级应用涵盖了从底层内存管理到高级设计模式的广泛领域。掌握这些高级特性不仅能够提升代码质量，还能在性能关键场景中发挥重要作用。

在实际项目中，应该根据具体需求选择合适的技术，避免过度设计。同时，良好的工程实践（如测试、代码质量检查、配置管理）是保证项目长期成功的关键。

通过深入学习这些高级主题，开发者能够更好地理解Python的内部机制，写出更高效、更可靠的代码。

