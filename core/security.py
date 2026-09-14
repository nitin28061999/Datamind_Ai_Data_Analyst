import ast

PYTHON_BLOCKLIST = {
    "import", "from", "open", "exec", "eval", "compile", "__import__",
    "subprocess", "os", "sys", "socket", "shutil", "pathlib", "requests",
    "httpx", "pickle", "input"
}

def validate_python(code):
    tree = ast.parse(code, mode="exec")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Imports are not allowed in generated analysis code.")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in PYTHON_BLOCKLIST:
                raise ValueError(f"Blocked operation: {node.func.id}")
        if isinstance(node, ast.Name) and node.id in PYTHON_BLOCKLIST:
            raise ValueError(f"Blocked name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Dunder attribute access is not allowed.")
    return True

def validate_sql(sql):
    normalized = sql.strip().lower()
    if ";" in normalized.rstrip(";"):
        raise ValueError("Only one SQL statement is allowed.")
    if not normalized.startswith(("select", "with")):
        raise ValueError("Only read-only SELECT/WITH SQL is allowed.")
    blocked = ["insert ", "update ", "delete ", "drop ", "alter ", "create ", "copy ", "attach ", "install ", "load "]
    if any(x in normalized for x in blocked):
        raise ValueError("Unsafe SQL operation detected.")
    return True
