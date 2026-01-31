# 📦 Source Code Structure

## 📁 Directories

### `dashboard/`
Dash application for the interactive expense dashboard.

| File | Description |
|------|-------------|
| `app.py` | App creation and `run_dashboard()` entry point |
| `layouts.py` | UI components and page layouts |
| `callbacks.py` | Main callback registration |
| `core_callbacks.py` | Tab navigation callbacks |
| `categories_callbacks.py` | Category Analysis tab logic |
| `timeseries_callbacks.py` | Time Series tab logic |
| `tagging_callbacks.py` | Tagging tab logic |

### `utilities/`
Data loading and path management.

| File | Description |
|------|-------------|
| `paths.py` | Centralized path functions (`get_data_dir()`, etc.) |
| `data_loader.py` | CSV loading, tag parsing, data preparation |

### `temp/`
Temporary scripts for testing and exploration. Can be deleted.
