# Python Lesson: Installing and Using Pylint

## 1. Introduction
**Pylint** is a popular Python tool for:
- **Linting** (checking code for errors, bugs, and style issues).
- **Enforcing coding standards** (PEP 8).
- **Improving code quality** with suggestions and warnings.

Using Pylint helps developers write **clean, consistent, and error-free code**.

---

## 2. Installation
Install Pylint using `pip`:

```bash
pip install pylint
```

Verify installation:

```bash
pylint --version
```

---

## 3. Basic Usage
Run Pylint on a Python file:

```bash
pylint my_script.py
```

Output example:

```
************* Module my_script
my_script.py:1:0: C0114: Missing module docstring (missing-module-docstring)
my_script.py:3:0: C0116: Missing function or method docstring (missing-function-docstring)

------------------------------------------------------------------
Your code has been rated at 7.50/10 (previous run: 7.50/10, +0.00)
```

---

## 4. Example Script
```python
# bad_script.py

def add(x,y):
 return x+y
```

Run:
```bash
pylint bad_script.py
```

Pylint will complain about:
- Missing docstring.
- Bad indentation.
- Bad spacing around operators.

---

## 5. Fixing the Code
```python
# good_script.py

def add(x: int, y: int) -> int:
    """Return the sum of x and y."""
    return x + y
```

Re-run Pylint:
```bash
pylint good_script.py
```

Now you’ll get a much better score.

---

## 6. Configuration
You can customize Pylint rules with a configuration file.

Generate a `.pylintrc` file:
```bash
pylint --generate-rcfile > .pylintrc
```

Edit `.pylintrc` to:
- Disable specific warnings.
- Adjust naming conventions.
- Set maximum line length.

Example disabling missing docstrings:
```
disable=C0114,C0115,C0116
```

---

## 7. Using with Editors/IDEs
Most editors support Pylint integration:
- **VS Code**: Install the “Python” extension and enable linting.
- **PyCharm**: Supports Pylint via plugins.
- **Vim/Neovim**: Use ALE or other linters.

---

## 8. Continuous Integration
Add Pylint to CI/CD pipelines (GitHub Actions, GitLab CI, Jenkins, etc.) to enforce style checks automatically.

Example GitHub Actions snippet:
```yaml
- name: Run Pylint
  run: pylint my_project/
```

---

## 9. Conclusion
Pylint is a powerful tool for:
- Catching errors early.
- Enforcing PEP 8 compliance.
- Improving maintainability of code.

By integrating Pylint into your workflow, you ensure **clean, consistent, and professional Python code**.

---

## 10. References
- Official docs: [https://pylint.pycqa.org](https://pylint.pycqa.org)  
- PyPI: [Pylint on PyPI](https://pypi.org/project/pylint/)  
- PEP 8 (Python style guide): [https://peps.python.org/pep-0008/](https://peps.python.org/pep-0008/)  
