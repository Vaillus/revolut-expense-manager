"""
Centralized path management for the project
"""
from pathlib import Path
from typing import Union

def get_project_root() -> Path:
    """Get the project root directory"""
    return Path(__file__).resolve().parent.parent.parent

def get_data_dir() -> Path:
    """Get the data directory"""
    return get_project_root() / "data"

def get_raw_data_dir() -> Path:
    """Get the raw data directory"""
    return get_data_dir() / "raw"

def get_processed_data_dir() -> Path:
    """Get the processed data directory"""
    return get_data_dir() / "processed"

def get_config_dir() -> Path:
    """Get the configuration directory"""
    return get_data_dir() / "config"

def get_outputs_dir() -> Path:
    """Get the outputs directory"""
    return get_project_root() / "outputs"

def get_config_file(filename: str) -> Path:
    """Get a configuration file path"""
    return get_config_dir() / filename

def get_raw_file(filename: str) -> Path:
    """Get a raw data file path"""
    return get_raw_data_dir() / filename

def get_processed_file(filename: str) -> Path:
    """Get a processed data file path"""
    return get_processed_data_dir() / filename

def get_expenses_file() -> Path:
    """Get the unified expenses CSV file path"""
    return get_processed_data_dir() / "expenses.csv"

def ensure_dir_exists(path: Union[str, Path]) -> Path:
    """Ensure a directory exists, create if it doesn't"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path 