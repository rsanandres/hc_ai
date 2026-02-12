
import ast
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def verify_imports_in_file(filepath: Path) -> list[str]:
    errors = []
    try:
        with open(filepath, "r") as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(filepath))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module
                level = node.level
                
                # Check absolute internal imports (api.*)
                if module and module.startswith("api."):
                    # Convert python path to file path
                    parts = module.split('.')
                    target_path = ROOT_DIR.joinpath(*parts)
                    
                    # Check if it exists as directory (package) or file (.py)
                    if not (target_path.exists() or target_path.with_suffix('.py').exists()):
                        errors.append(f"Broken absolute import: {module} (Line {node.lineno})")
                
                # Check relative imports (roughly)
                elif level > 0:
                    # This is harder to verify statically perfectly without simulating python's resolution
                    # But we can check if the implied directory exists
                    pass

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("api."):
                        parts = alias.name.split('.')
                        target_path = ROOT_DIR.joinpath(*parts)
                        if not (target_path.exists() or target_path.with_suffix('.py').exists()):
                            errors.append(f"Broken absolute import: {alias.name} (Line {node.lineno})")

    except Exception as e:
        errors.append(f"Failed to parse {filepath.relative_to(ROOT_DIR)}: {e}")
        
    return errors

def main():
    print(f"Scanning imports from ROOT: {ROOT_DIR}")
    print("Violations will be listed below.\n")
    
    issues_found = 0
    
    # Directories to scan
    scan_dirs = ["api", "scripts", "debug"]
    ignore_dirs = ["POC_agent", "POC_embeddings", "POC_retrieval", "POC_RAGAS", "postgres", "__pycache__"]
    
    for d in scan_dirs:
        start_dir = ROOT_DIR / d
        if not start_dir.exists():
            continue
            
        for root, dirs, files in os.walk(start_dir):
            # Filtering ignored dirs in place
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if file.endswith(".py"):
                    full_path = Path(root) / file
                    file_errors = verify_imports_in_file(full_path)
                    
                    if file_errors:
                        print(f"File: {full_path.relative_to(ROOT_DIR)}")
                        for err in file_errors:
                            print(f"  ❌ {err}")
                            issues_found += 1

    if issues_found == 0:
        print("\n✅ No broken internal imports found in scanned directories.")
    else:
        print(f"\n⚠️ Found {issues_found} potential broken imports.")

if __name__ == "__main__":
    main()
