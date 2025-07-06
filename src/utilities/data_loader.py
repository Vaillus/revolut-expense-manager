"""
Data loading and processing utilities
"""
import pandas as pd
import json
from typing import List, Dict, Any, Optional
from collections import defaultdict
from pathlib import Path

from .paths import get_config_file, get_processed_file


def load_config(filename: str) -> Dict[str, Any]:
    """Load a configuration file"""
    config_path = get_config_file(filename)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_tags(tags: Any) -> List[str]:
    """Parse tags from various formats into a list of strings"""
    if pd.isna(tags) or not tags:
        return []
    if isinstance(tags, str) and tags.strip():
        try:
            tag_list = eval(tags)
            if isinstance(tag_list, list):
                return tag_list
        except:
            return [t.strip() for t in tags.split(',') if t.strip()]
    elif isinstance(tags, list):
        return tags
    return []


def load_month_data(filename: str) -> pd.DataFrame:
    """Load and process data for a specific month"""
    file_path = get_processed_file(filename)
    df = pd.read_csv(file_path)
    df['parsed_tags'] = df['tags'].apply(parse_tags)
    df['amount_numeric'] = pd.to_numeric(df['Amount'], errors='coerce')
    
    # Only keep expenses (negative amounts)
    expenses_df = df[df['amount_numeric'] < 0].copy()
    expenses_df['amount_abs'] = expenses_df['amount_numeric'].abs()
    
    return expenses_df


def load_all_processed_data() -> pd.DataFrame:
    """Load all processed data files and combine them"""
    from .paths import get_processed_data_dir
    processed_dir = get_processed_data_dir()
    csv_files = list(processed_dir.glob("*.csv"))
    
    all_data = []
    for csv_file in csv_files:
        try:
            df = load_month_data(csv_file.name)
            # Extract month from filename (assuming format: YYYY-MM.csv)
            month = csv_file.stem
            df['month'] = month
            all_data.append(df)
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")
    
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()


def get_main_category(tags: List[str], main_categories: List[str]) -> str:
    """Determine the main category from a list of tags"""
    tags_set = set(tags)
    for category in main_categories:
        if category in tags_set:
            return category
    return 'Autre' if tags else 'Sans tag'


def get_subtags_for_category(category_name: str, month_data: pd.DataFrame) -> Dict[str, float]:
    """Get subtags and their amounts for a given category"""
    if category_name in ['Sans tag', 'Autre']:
        return {}
    
    # Filter transactions for this category
    category_transactions = month_data[month_data['main_category'] == category_name]
    
    # Count amounts by subtag (excluding the main tag)
    subtag_amounts = defaultdict(float)
    
    for _, row in category_transactions.iterrows():
        tags = row['parsed_tags']
        amount = row['amount_abs']
        
        # Add all tags EXCEPT the main tag
        for tag in tags:
            if tag != category_name:
                subtag_amounts[tag] += amount
    
    return dict(sorted(subtag_amounts.items(), key=lambda x: x[1], reverse=True))


def get_monthly_trend(category_name: str, all_data: pd.DataFrame) -> pd.DataFrame:
    """Get monthly evolution for a category"""
    monthly_data = all_data[all_data['main_category'] == category_name].groupby('month')['amount_abs'].sum().reset_index()
    return monthly_data


def prepare_timeseries_data(all_data: pd.DataFrame) -> tuple:
    """Prepare data for timeseries analysis"""
    # Group by month and expense type (exceptional vs others)
    all_data_copy = all_data.copy()
    all_data_copy['is_exceptional'] = all_data_copy['main_category'] == 'exceptionnel'
    
    monthly_summary = all_data_copy.groupby(['month', 'is_exceptional'])['amount_abs'].sum().reset_index()
    
    # Separate exceptional and regular expenses
    exceptional = monthly_summary[monthly_summary['is_exceptional']].copy()
    regular = monthly_summary[~monthly_summary['is_exceptional']].copy()
    
    # Calculate monthly totals
    monthly_totals = all_data_copy.groupby('month')['amount_abs'].sum().reset_index()
    
    return exceptional, regular, monthly_totals 