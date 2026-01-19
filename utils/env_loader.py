"""Utility for loading .env files recursively from root and subfolders.

This module provides a function to load environment variables from:
1. Root .env file (loaded first)
2. All .env files in subfolders (loaded after, so they can override root values)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_env_recursive(root_dir: Optional[Path | str] = None) -> None:
    """Load .env files recursively from root and all subfolders.
    
    Loads environment variables in the following order:
    1. Root .env file (if exists)
    2. All .env files in subfolders (in alphabetical order by path)
    
    Subfolder .env files will override values from root .env file.
    
    Args:
        root_dir: Root directory to search from. If None, uses the project root
                  (assumes this file is in utils/ and project root is one level up).
    """
    if root_dir is None:
        # Assume this file is in utils/ and project root is one level up
        root_dir = Path(__file__).resolve().parents[1]
    else:
        root_dir = Path(root_dir).resolve()
    
    # First, load root .env file if it exists
    root_env = root_dir / ".env"
    if root_env.exists():
        load_dotenv(root_env, override=False)
    
    # Then, find and load all .env files in subfolders
    # Exclude common directories that shouldn't have .env files
    exclude_dirs = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "venv",
        "env",
        ".env",
        "dist",
        "build",
    }
    
    env_files = []
    for root, dirs, files in os.walk(root_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        # Check for .env file in current directory
        env_path = Path(root) / ".env"
        if env_path.exists() and env_path != root_env:
            env_files.append(env_path)
    
    # Sort by path to ensure consistent loading order
    env_files.sort()
    
    # Load subfolder .env files (these will override root values)
    for env_file in env_files:
        load_dotenv(env_file, override=True)
