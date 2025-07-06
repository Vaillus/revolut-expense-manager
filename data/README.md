# Data Directory

This directory contains the Revolut expense data organized by processing stage.

## Structure

- **`raw/`** - Raw CSV files downloaded from Revolut
- **`processed/`** - Tagged CSV files ready for dashboard analysis  
- **`config/`** - Configuration files (categories, tags, associations)

## Workflow

```
raw/ → [tagging] → processed/ → [dashboard]
```

**Note:** All data files are excluded from git for privacy. 