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
2. Use the tagging interface to categorize expenses
3. Launch the dashboard to analyze your spending

### Launch Dashboard
```bash
python3 interactive_dashboard.py
```
→ Available at http://127.0.0.1:8050

## 📁 Project Structure

```
├── data/
│   ├── raw/           # Raw CSV files from Revolut
│   ├── processed/     # Tagged CSV files ready for analysis
│   └── config/        # Configuration files
├── script/            # Utility scripts
├── outputs/           # Generated reports and charts
└── interactive_dashboard.py  # Main dashboard
```

## 🔒 Privacy

All financial data is excluded from git for privacy protection. 