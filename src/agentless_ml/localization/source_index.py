"""Declaration visibility for localization, plus offline import-map diagnostics.

The index lists declarations recognized by the existing language adapters,
supplemented by Python module assignments. Dependencies are *file imports*, not
a resolved call graph. An import edge is syntactic evidence, not proof that a
file executes or that every implementation of a dynamic API has been found.
"""

from __future__ import annotations

import ast
import json
import posixpath
import re
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from agentless_ml.adapters.languages import source_adapter
from agentless_ml.schemas import FileNode, SymbolNode
from agentless_ml.structure.engine import TreeSitterLanguage, parse


@dataclass(frozen=True, slots=True)
class IndexDiagnostic:
    path: str
    kind: str
    detail: str


@dataclass(frozen=True, slots=True)
class ImportLink:
    path: str
    line: int
    kind: str
    module: str
    targets: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class ExpansionStep:
    path: str
    via: str | None
    line: int | None
    kind: str


@dataclass(frozen=True, slots=True)
class SourceIndex:
    files: tuple[FileNode, ...]
    links: tuple[ImportLink, ...]
    diagnostics: tuple[IndexDiagnostic, ...]

    def expand(self, seed_files: Sequence[str]) -> tuple[ExpansionStep, ...]:
        """Reach the fixed point of known outgoing imports; no hop/file cutoff.

        Every added path has an import witness. Unresolved links remain in the
        index; reaching a fixed point does not certify semantic completeness.
        """
        known = {file.path for file in self.files}
        unknown = set(seed_files) - known
        if unknown:
            raise ValueError(f"seed files absent from source index: {sorted(unknown)}")
        outgoing: dict[str, list[ImportLink]] = {}
        for link in self.links:
            outgoing.setdefault(link.path, []).append(link)
        found = {path: ExpansionStep(path, None, None, "seed") for path in sorted(set(seed_files))}
        pending = deque(found)
        while pending:
            path = pending.popleft()
            for link in outgoing.get(path, ()):
                for target in link.targets:
                    if target not in found:
                        found[target] = ExpansionStep(target, path, link.line, link.kind)
                        pending.append(target)
        return tuple(found[path] for path in sorted(found))

    def render(self, paths: Sequence[str] | None = None) -> str:
        """All indexed names and source spans, without bodies or truncation."""
        return self._render(paths, import_notice=True)

    def render_declarations(self) -> str:
        """Declaration-only view used by the fixed controller."""
        return self._render(None, import_notice=False)

    def _render(self, paths, *, import_notice):
        selected = None if paths is None else set(paths)
        known = {file.path for file in self.files}
        if selected is not None and selected - known:
            raise ValueError("render paths absent from source index")
        lines = [
            "Repository declaration index (names and spans, not function bodies).",
        ]
        if import_notice:
            lines.append("Import links are syntactic file dependencies, not a complete call graph.")
        else:
            lines.append("Names and line ranges are for discovery; later localization determines editable regions.")
        for file in self.files:
            if selected is not None and file.path not in selected:
                continue
            lines.append(f"\n{file.path} [{file.language}; {file.line_count} lines]")
            symbols = tuple(walk_symbols(file.symbols))
            lines.extend(
                f"  {symbol.start_line}-{symbol.end_line} {symbol.kind} {symbol.qualified_name}"
                for symbol in symbols
            )
            if not symbols:
                lines.append("  (no recognized declarations)")
        for diagnostic in self.diagnostics:
            if diagnostic.path in known and (selected is None or diagnostic.path in selected):
                lines.append(f"\n! {diagnostic.path}: {diagnostic.kind}: {diagnostic.detail}")
        return "\n".join(lines) + "\n"


def walk_symbols(symbols: Sequence[SymbolNode]):
    for symbol in symbols:
        yield symbol
        yield from walk_symbols(symbol.children)


def _python_globals(tree: ast.Module) -> tuple[SymbolNode, ...]:
    """Assignments at module scope, including conditional/type-checking blocks.

    Do not enter function/class scopes and mistake their locals for globals.
    The production Python representation is left unchanged for parity.
    """
    result = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store):
                        result.append(SymbolNode(
                            "variable", name.id, name.id, name.id,
                            node.lineno, node.end_lineno or node.lineno,
                        ))
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return tuple(result)


def build_source_index(
    sources: Mapping[str, str], *, metadata: Mapping[str, str] | None = None
) -> SourceIndex:
    """Index caller-supplied public base sources without executing any of them.

    Apply the production adapters' source/test filters, and account for every
    supplied path. Parse failures keep their file entry with an explicit warning.
    ``metadata`` currently supplies pinned go.mod files for module resolution.
    """
    return _build_index(sources, metadata=metadata, include_imports=True)


def build_declaration_index(sources: Mapping[str, str]) -> SourceIndex:
    """The production declaration index; never construct or expand import links."""
    return _build_index(sources, metadata=None, include_imports=False)


def _build_index(sources, *, metadata, include_imports):
    files = []
    diagnostics = []
    accepted = {}
    python_trees = {}
    syntax_trees = {}
    for path, source in sorted(sources.items()):
        pure = PurePosixPath(path)
        if (pure.is_absolute() or "\\" in path or any(part in {"", ".", ".."} for part in path.split("/"))):
            raise ValueError(f"expected repository-relative path: {path!r}")
        adapter = source_adapter(path)
        if adapter is None or adapter.is_test_path(path):
            diagnostics.append(IndexDiagnostic(path, "excluded", "source/test policy"))
            continue
        accepted[path] = source
        try:
            file = adapter.parse_file(path, source)
            if file.language == "python":
                tree = ast.parse(source, filename=path)
                python_trees[path] = tree
                symbols = (*file.symbols, *_python_globals(tree))
                file = FileNode(path, file.language, file.line_count, tuple(sorted(
                    symbols, key=lambda item: (item.start_line, item.end_line, item.qualified_name)
                )))
            elif include_imports and isinstance(adapter, TreeSitterLanguage):
                _, data, root = parse(adapter.spec, path, source)
                syntax_trees[path] = (data, root)
            files.append(file)
        except (ValueError, SyntaxError) as exc:
            files.append(FileNode(path, adapter.language, len(source.splitlines())))
            diagnostics.append(IndexDiagnostic(path, "parse-error", str(exc)))

    if not include_imports:
        return SourceIndex(tuple(files), (), tuple(diagnostics))

    python_modules: dict[str, set[str]] = {}
    go_packages: dict[str, list[str]] = {}
    for file in files:
        if file.language == "python":
            module = _python_module(file.path)
            python_modules.setdefault(module, set()).add(file.path)
        elif file.language == "go":
            go_packages.setdefault(posixpath.dirname(file.path), []).append(file.path)
        elif file.language == "rust":
            diagnostics.append(IndexDiagnostic(
                file.path, "unsupported-import-analysis", "Rust declarations indexed; imports not expanded"
            ))

    links = []
    for path, source in accepted.items():
        if path in python_trees:
            links.extend(_python_links(path, python_trees[path], python_modules))
        elif path in syntax_trees:
            data, root = syntax_trees[path]
            if path.endswith(".go"):
                links.extend(_go_links(path, data, root, go_packages, metadata or {}))
            elif not path.endswith(".rs"):
                links.extend(_javascript_links(path, data, root, set(accepted)))
    return SourceIndex(
        tuple(files),
        tuple(sorted(set(links), key=lambda link: (
            link.path, link.line, link.kind, link.module, link.targets, link.status
        ))),
        tuple(sorted(diagnostics, key=lambda item: (item.path, item.kind, item.detail))),
    )


def _python_module(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if len(parts) > 1 and parts[0] == "src":
        parts.pop(0)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _python_links(path: str, tree: ast.Module, modules: Mapping[str, set[str]]):
    for node in ast.walk(tree):
        requests = []
        if isinstance(node, ast.Import):
            requests = [(alias.name, ()) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                package = _python_module(path).split(".")
                if not path.endswith("/__init__.py") and path != "__init__.py":
                    package.pop()
                if node.level > len(package):
                    yield ImportLink(path, node.lineno, "python-import", ast.unparse(node), (), "unresolved")
                    continue
                prefix = package[:len(package) - node.level + 1]
                base = ".".join([*prefix, *([base] if base else [])])
            requests = [(base, tuple(alias.name for alias in node.names if alias.name != "*"))]
        elif isinstance(node, ast.Call) and (
            isinstance(node.func, ast.Name) and node.func.id == "__import__"
            or isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"
        ):
            yield ImportLink(
                path, node.lineno, "python-dynamic-import", ast.unparse(node.func), (), "dynamic"
            )
        for module, members in requests:
            # Include package initializers as well as a possible from-imported
            # submodule. A name could instead be an attribute; this is a set of
            # possible files, not an assertion about runtime name binding.
            names = [".".join(module.split(".")[:count]) for count in range(1, len(module.split(".")) + 1)]
            names.extend(f"{module}.{member}" if module else member for member in members)
            targets = tuple(sorted({
                target for name in names for target in modules.get(name, ()) if target != path
            }))
            ambiguous = any(len(modules.get(name, ())) > 1 for name in names)
            yield ImportLink(
                path, node.lineno, "python-import", module, targets,
                "ambiguous" if ambiguous else "syntactic-candidates" if targets else "unresolved",
            )


def _nodes(root):
    pending = [root]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(reversed(node.named_children))


def _literal(data: bytes, node) -> str | None:
    if node is None or node.type not in {
        "string", "template_string", "interpreted_string_literal", "raw_string_literal"
    }:
        return None
    text = data[node.start_byte:node.end_byte].decode("utf-8")
    if text.startswith('"'):
        try:
            return json.loads(text)
        except ValueError:
            return None
    if text.startswith(("'", "`")) and text.endswith(text[0]) and "\\" not in text and "${" not in text:
        return text[1:-1]
    return None


def _javascript_links(path: str, data: bytes, root, known: set[str]):
    extensions = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
    for node in _nodes(root):
        literal = None
        kind = "javascript-import"
        if node.type in {"import_statement", "export_statement"}:
            literal = node.child_by_field_name("source")
            if literal is None:
                continue
        elif node.type == "call_expression":
            function = node.child_by_field_name("function")
            if function is None or data[function.start_byte:function.end_byte] not in {b"require", b"import"}:
                continue
            arguments = node.child_by_field_name("arguments")
            if arguments is not None and arguments.named_child_count == 1:
                literal = arguments.named_children[0]
            kind = "javascript-literal-call"
        else:
            continue
        module = _literal(data, literal)
        if module is None:
            yield ImportLink(path, node.start_point.row + 1, kind, "<computed>", (), "dynamic")
            continue
        candidates = set()
        if module.startswith("."):
            stem = posixpath.normpath(posixpath.join(posixpath.dirname(path), module))
            if stem in known:
                candidates.add(stem)
            else:
                candidates.update(stem + extension for extension in extensions)
                candidates.update(stem + "/index" + extension for extension in extensions)
                # Common TS source convention: .js import specifier, .ts file.
                if stem.endswith((".js", ".mjs", ".cjs")):
                    translated = {".js": ".ts", ".mjs": ".mts", ".cjs": ".cts"}
                    candidates.add(stem.rsplit(".", 1)[0] + translated[PurePosixPath(stem).suffix])
        candidates = {posixpath.normpath(candidate) for candidate in candidates}
        targets = tuple(sorted(candidates & known - {path}))
        yield ImportLink(
            path, node.start_point.row + 1, kind, module, targets,
            "ambiguous" if len(targets) > 1 else "syntactic-candidates" if targets else "unresolved",
        )


def _go_links(path: str, data: bytes, root, packages: Mapping[str, list[str]], metadata: Mapping[str, str]):
    directory = posixpath.dirname(path)
    siblings = tuple(sorted(set(packages.get(directory, ())) - {path}))
    if siblings:
        yield ImportLink(path, 1, "go-package", directory or ".", siblings, "syntactic-candidates")
    module = None
    module_directory = ""
    for config, source in sorted(metadata.items(), key=lambda item: len(item[0]), reverse=True):
        parent = posixpath.dirname(config)
        if PurePosixPath(config).name == "go.mod" and (not parent or path.startswith(parent + "/")):
            match = re.search(r'^module\s+(\S+)', source, flags=re.MULTILINE)
            if match:
                module, module_directory = match[1].strip('"'), parent
            break
    for node in _nodes(root):
        if node.type != "import_spec":
            continue
        target = _literal(data, node.child_by_field_name("path"))
        candidates = ()
        if module and target and (target == module or target.startswith(module + "/")):
            suffix = target[len(module):].lstrip("/")
            candidates = tuple(sorted(packages.get(posixpath.join(module_directory, suffix).rstrip("/"), ())))
        yield ImportLink(path, node.start_point.row + 1, "go-import", target or "<computed>", candidates,
                         "syntactic-candidates" if candidates else "unresolved")
