# 💰 Revolut Expense Manager

A simple tool to categorize and analyze monthly Revolut expenses.

## 🎯 Purpose

This tool processes Revolut's monthly CSV expense reports to:
- Add custom categories/tags to transactions
- Visualize spending patterns through an interactive dashboard
- Track monthly expense evolution

## 🚀 Usage

**Monthly workflow:**
1. Download your monthly CSV report from Revolut
2. Place it in `data/raw/`
3. Launch the dashboard and use the Tagging tab to categorize expenses
4. Analyze your spending in the Category Analysis and Time Series tabs

### Launch Dashboard
```bash
python main.py
```
→ Available at http://127.0.0.1:8050

## 📁 Project Structure

```
├── data/
│   ├── raw/           # Raw CSV files from Revolut
│   ├── processed/     # Tagged CSV files ready for analysis
│   └── config/        # Tags and vendor-tags configuration
├── src/
│   ├── dashboard/     # Dash application (layouts, callbacks)
│   └── utilities/     # Data loading and path management
├── notebooks/         # Jupyter notebooks for exploration
└── main.py            # Main entry point
```

## 📊 Dashboard Tabs

| Tab | Description |
|-----|-------------|
| 📊 Category Analysis | Pie chart of expenses by category with click-to-detail |
| 📈 Time Series | Monthly expense evolution (regular vs exceptional) |
| 🏷️ Tagging | Interface to tag new expenses from raw files |

## 🔒 Privacy

All financial data is excluded from git for privacy protection.
