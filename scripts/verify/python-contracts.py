"""Extract only declared contracts using stdlib AST; never import application settings."""
import ast
import json
from pathlib import Path
import sys


def parse_source(source):
    result = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                result.setdefault("__imports__", {})[alias.asname or alias.name] = [node.module, alias.name]
        if not isinstance(node, ast.ClassDef):
            continue
        values, fields = [], {}
        for child in node.body:
            if isinstance(child, ast.Assign) and isinstance(child.value, ast.Constant):
                if isinstance(child.value.value, str):
                    values.append(child.value.value)
            if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                fields[child.target.id] = {
                    "annotation": ast.unparse(child.annotation),
                    "atoms": atoms(child.annotation),
                }
        result[node.name] = {"values": sorted(values), "fields": fields,
                             "is_enum": any(ast.unparse(base).split(".")[-1] in {"Enum", "StrEnum"} for base in node.bases)}
    return result


def atoms(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return sorted(set(atoms(node.left) + atoms(node.right)))
    if isinstance(node, ast.Constant):
        if node.value is None:
            return ["null"]
        if isinstance(node.value, bool):
            return [f"literal_boolean:{str(node.value).lower()}"]
        if isinstance(node.value, (int, float)):
            return [f"literal_number:{node.value}"]
        return [f"literal:{node.value}"]
    if isinstance(node, ast.Name):
        return [{"str": "string", "UUID": "string", "datetime": "string",
                 "AwareDatetime": "string", "date": "string", "time": "string",
                 "int": "number", "float": "number", "bool": "boolean",
                 "Any": "unknown"}.get(node.id, f"ref:{node.id}")]
    if isinstance(node, ast.Subscript):
        name = ast.unparse(node.value).split(".")[-1]
        values = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        if name == "Literal":
            return sorted({atom for value in values for atom in atoms(value)})
        if name == "Annotated":
            return atoms(values[0])
        if name == "Union":
            return sorted({atom for value in values for atom in atoms(value)})
        if name == "Optional":
            return sorted(set(atoms(values[0]) + ["null"]))
        if name in {"list", "set", "tuple", "List", "Set", "Tuple"}:
            return ["array"]
        if name in {"dict", "Dict"}:
            return ["object"]
    return [f"unsupported:{ast.unparse(node)}"]


def snapshot(root, paths):
    return {name: parse_source((root / name).read_text(encoding="utf-8-sig")) for name in paths}


if __name__ == "__main__":
    manifest = json.load(sys.stdin)
    root = Path(__file__).resolve().parents[2]
    result = {name: parse_source(source) for name, source in manifest["sources"].items()} if "sources" in manifest else snapshot(root, manifest["paths"])
    print(json.dumps(result, ensure_ascii=False))
