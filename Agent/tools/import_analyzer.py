import os
import ast
import jedi
import logging
import sys
import site
import importlib.util
from pathlib import Path

# Set up logging to help with debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImportAnalyzer:
    def __init__(self, file_path: str, project_root_path: str):
        self.file_path = file_path
        self.project_root_path = project_root_path

    def analyze(self):
        """Analyze imports in the file and return results."""
        with open(self.file_path, "r") as file:
            source_code = file.read()

        tree = ast.parse(source_code, filename=self.file_path)
        imports = self._collect_imports(tree)
        
        results = []
        for import_statement, line, column in imports:
            definition_path, code_snippet = self._resolve_import_with_jedi(line, column)
            if definition_path:
                if Path(definition_path).resolve().is_relative_to(Path(self.project_root_path).resolve()):
                    # Import defined within the project
                    results.append({
                        "import": import_statement,
                        "code": code_snippet
                    })
                else:
                    # Import from third-party or standard library
                    results.append({
                        "import": import_statement,
                        "code": "Third-party library or standard library"
                    })
            else:
                # Definition not found
                results.append({
                    "import": import_statement,
                    "code": "Definition not found"
                })
        
        return results

    def _collect_imports(self, tree):
        imports = []
        with open(self.file_path, "r") as file:
            source_code_lines = file.readlines()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    import_statement = source_code_lines[node.lineno - 1].strip()
                    imports.append((import_statement, alias.lineno, alias.col_offset))
            elif isinstance(node, ast.ImportFrom):
                import_statement = source_code_lines[node.lineno - 1].strip()
                module_name = node.module if node.module else ""
                for alias in node.names:
                    imports.append((import_statement, alias.lineno, alias.col_offset))
        return imports

    def _resolve_import_with_jedi(self, line, column):
        script = jedi.Script(path=self.file_path)
        definitions = script.goto(line=line, column=column, follow_imports=True, follow_builtin_imports=True)
        if definitions:
            for definition in definitions:
                if definition.module_path:
                    # Read the relevant code snippet for the definition
                    if definition.type == "module":
                        with open(definition.module_path, "r") as f:
                            code_snippet = f.read()
                    else:
                        start_line, start_column = definition.get_definition_start_position()
                        end_line, end_column = definition.get_definition_end_position()
                        with open(definition.module_path, "r") as f:
                            lines = f.readlines()
                        code_snippet = "\n".join(lines[start_line - 1:end_line]).strip()
                    return definition.module_path, code_snippet
        return None, None

# If you need to test the file separately, keep the following code
if __name__ == "__main__":
    project_root_path = "/home/shixianjie/codegraph/codegraph/DevEval/Source_Code/Text-Processing/mistune"
    target_file_path = "/home/shixianjie/codegraph/codegraph/DevEval/Source_Code/Text-Processing/mistune/src/mistune/toc.py"
    analyzer = ImportAnalyzer(target_file_path, project_root_path)
    results = analyzer.analyze()
    for result in results:
        print(result)
