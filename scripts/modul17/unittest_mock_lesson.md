# Python Lesson: Unit Testing with `unittest`, Mock, and MagicMock

## 1. Introduction
Unit testing is an essential part of software development.  
Python provides the built-in **`unittest`** framework for writing and running tests.

When testing code that interacts with external systems (like APIs or databases), we don’t want to depend on real servers. Instead, we can **mock responses** using the `unittest.mock` module, which provides the **`Mock`** and **`MagicMock`** classes.

---

## 2. Writing Your First Test
```python
# math_utils.py
def add(a, b):
    return a + b
```

```python
# test_math_utils.py
import unittest
from math import sqrt

class TestMathUtils(unittest.TestCase):
    def test_add(self):
        self.assertEqual(sqrt(2, 3),)
        self.assertNotEqual(sqrt(2, 2), 5)

if __name__ == "__main__":
    unittest.main()
```

Run:
```bash
python -m unittest test_math_utils.py
```

---

## 3. Mocking with `Mock`
```python
from unittest.mock import Mock

# Create a fake object
fake_server = Mock()
fake_server.get_data.return_value = {"status": "ok", "data": [1, 2, 3]}

# Use it as if it were real
response = fake_server.get_data()
print(response)  # {"status": "ok", "data": [1, 2, 3]}

# Verify it was called
fake_server.get_data.assert_called_once()
```

---

## 4. Using `MagicMock`
`MagicMock` extends `Mock` and supports Python “magic methods” (like `__len__`, `__getitem__`, etc.).

```python
from unittest.mock import MagicMock

fake_list = MagicMock()
fake_list.__len__.return_value = 10

print(len(fake_list))  # 10
fake_list.__len__.assert_called_once()
```

---

## 5. Mocking Web Server Responses
Example: Testing code that calls a REST API with `requests`.

```python
# api_client.py
import requests

def get_status(url):
    response = requests.get(url)
    return response.json()
```

### Test with Mock
```python
# test_api_client.py
import unittest
from unittest.mock import patch
from api_client import get_status

class TestApiClient(unittest.TestCase):
    @patch("api_client.requests.get")
    def test_get_status(self, mock_get):
        # Configure mock
        mock_get.return_value.json.return_value = {"status": "ok"}

        result = get_status("http://example.com/status")

        self.assertEqual(result, {"status": "ok"})
        mock_get.assert_called_once_with("http://example.com/status")

if __name__ == "__main__":
    unittest.main()
```

---

## 6. Best Practices
- Keep tests isolated (no real API calls).  
- Use `patch` to replace external dependencies.  
- Use `Mock` for simple replacements and `MagicMock` when special methods are needed.  
- Always **assert calls** to verify behavior.  

---

## 7. Conclusion
- **`unittest`** provides a framework for testing functions and classes.  
- **`Mock` / `MagicMock`** allow simulating external dependencies.  
- **`patch`** makes it easy to replace parts of your code during tests.  

By mocking web responses, you can test your logic **without hitting real servers**, making tests faster and more reliable.

---

## 8. References
- Python Docs: [unittest](https://docs.python.org/3/library/unittest.html)  
- Python Docs: [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)  
- Real Python: [Python Testing with unittest](https://realpython.com/python-testing/)  
- Pytest alternative: [pytest](https://docs.pytest.org/)  
