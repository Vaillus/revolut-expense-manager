"""
Data loading and processing utilities
"""
import pandas as pd
import json
from typing import List, Dict, Any, Optional
from collections import defaultdict
from pathlib import Path

from .paths import get_config_file, get_processed_file, get_expenses_file


def _detect_and_map_columns(columns: List[str]) -> Dict[str, str]:
    """
    Detect column language and map French/English column names to standard English names
    Returns a mapping dictionary for renaming columns
    """
    # Mapping from French/English variants to standard English names
    column_mappings = {
        # French to English
        'Date de début': 'Started Date',
        'Montant': 'Amount',
        'Devise': 'Currency',
        'État': 'State',
        'Date de fin': 'Completed Date',
        'Produit': 'Product',
        # English variants (in case of different formats)
        'Started Date': 'Started Date',  # Keep as is
        'Amount': 'Amount',  # Keep as is
        'Currency': 'Currency',  # Keep as is
        'State': 'State',  # Keep as is
        'Type': 'Type',  # Keep as is
        'Description': 'Description',  # Keep as is
    }
    
    # Create mapping for existing columns
    mapping = {}
    for col in columns:
        if col in column_mappings:
            mapping[col] = column_mappings[col]
        # If column not in mapping, keep original name
    
    return mapping


def load_config(filename: str) -> Dict[str, Any]:
    """Load a configuration file"""
    config_path = get_config_file(filename)
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_completed_months() -> Dict[str, Any]:
    """Load completed months configuration"""
    try:
        return load_config('completed_months.json')
    except FileNotFoundError:
        # Return empty structure if file doesn't exist
        return {"completed_months": [], "last_completed": None}
    except Exception as e:
        print(f"Error loading completed_months.json: {e}")
        return {"completed_months": [], "last_completed": None}


def get_completed_months() -> List[str]:
    """Get list of completed months"""
    config = load_completed_months()
    return config.get("completed_months", [])


def get_last_completed_month() -> Optional[str]:
    """Get the most recently completed month"""
    config = load_completed_months()
    return config.get("last_completed")


def mark_month_as_completed(month: str) -> bool:
    """Mark a month as completed and update JSON file"""
    try:
        config = load_completed_months()
        completed_months = config.get("completed_months", [])
        
        # Add month if not already in list
        if month not in completed_months:
            completed_months.append(month)
            completed_months.sort(reverse=True)  # Most recent first
        
        # Update config
        config["completed_months"] = completed_months
        config["last_completed"] = month
        
        # Save to file
        config_path = get_config_file('completed_months.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error marking month as completed: {e}")
        return False


def is_month_completed(month: str) -> bool:
    """Check if a month is marked as completed"""
    completed_months = get_completed_months()
    return month in completed_months


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


def load_all_expenses() -> pd.DataFrame:
    """Load the unified expenses CSV file"""
    expenses_file = get_expenses_file()
    
    if not expenses_file.exists():
        print(f"Warning: {expenses_file} does not exist")
        return pd.DataFrame()
    
    df = pd.read_csv(expenses_file)
    df['parsed_tags'] = df['tags'].apply(parse_tags)
    df['amount_numeric'] = pd.to_numeric(df['Amount'], errors='coerce')
    
    # Only keep expenses (negative amounts)
    expenses_df = df[df['amount_numeric'] < 0].copy()
    expenses_df['amount_abs'] = expenses_df['amount_numeric'].abs()
    
    return expenses_df


def get_month_data(month: str) -> pd.DataFrame:
    """Get expenses for a specific month
    
    Args:
        month: Month in format YYYY-MM (e.g., '2025-04')
    
    Returns:
        DataFrame with expenses for that month
    """
    df = load_all_expenses()
    if df.empty:
        return df
    
    return df[df['month'] == month].copy()


def get_available_months() -> List[str]:
    """Get list of all months with expenses
    
    Returns:
        List of months in format YYYY-MM, sorted in reverse chronological order
    """
    df = load_all_expenses()
    if df.empty:
        return []
    
    return sorted(df['month'].unique().tolist(), reverse=True)


def get_latest_month() -> Optional[str]:
    """Get the most recent month with expenses
    
    Returns:
        Month string in format YYYY-MM, or None if no data
    """
    months = get_available_months()
    return months[0] if months else None


# DEPRECATED: Kept for backward compatibility during migration
def load_month_data(filename: str) -> pd.DataFrame:
    """Load and process data for a specific month (DEPRECATED)
    
    This function is deprecated. Use get_month_data(month) instead.
    """
    # Extract month from filename
    month = filename.replace('.csv', '')
    return get_month_data(month)


# DEPRECATED: Use get_latest_month() instead
def get_latest_processed_file() -> Optional[str]:
    """Get the filename of the most recent processed file (DEPRECATED)
    
    This function is deprecated. Use get_latest_month() instead.
    Returns a filename in format YYYY-MM.csv for backward compatibility.
    """
    month = get_latest_month()
    return f"{month}.csv" if month else None


# DEPRECATED: This function is no longer used with unified CSV structure
def get_all_processed_files() -> List[str]:
    """Get all processed file names (DEPRECATED)
    
    This function is deprecated. Use get_available_months() instead.
    """
    print("Warning: get_all_processed_files() is deprecated. Use get_available_months() instead.")
    months = get_available_months()
    return [f"{month}.csv" for month in months]


def load_all_processed_data() -> pd.DataFrame:
    """Load all processed expenses data (from unified CSV)"""
    return load_all_expenses()


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


def get_raw_files() -> List[Dict[str, Any]]:
    """Get list of raw data files available for tagging"""
    from .paths import get_raw_data_dir
    raw_dir = get_raw_data_dir()
    
    if not raw_dir.exists():
        return []
    
    csv_files = list(raw_dir.glob("*.csv"))
    
    raw_files = []
    for csv_file in csv_files:
        try:
            # Get file info
            file_info = {
                'filename': csv_file.name,
                'path': str(csv_file),
                'size': csv_file.stat().st_size,
                'modified': csv_file.stat().st_mtime
            }
            
            # Try to get basic CSV info
            try:
                df = pd.read_csv(csv_file)
                file_info['num_rows'] = len(df)
                file_info['columns'] = list(df.columns)
                file_info['readable'] = True
            except Exception as e:
                file_info['num_rows'] = 0
                file_info['columns'] = []
                file_info['readable'] = False
                file_info['error'] = str(e)
            
            raw_files.append(file_info)
        except Exception as e:
            print(f"Error processing {csv_file}: {e}")
    
    # Sort by modification time (newest first)
    raw_files.sort(key=lambda x: x['modified'], reverse=True)
    
    return raw_files


def load_tagging_configs() -> tuple:
    """Load tagging configuration files"""
    from .paths import get_config_file
    import os
    
    def load_json_file(filename: str) -> dict:
        """Load JSON file safely"""
        file_path = get_config_file(filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading {filename}: {e}")
                return {}
        return {}
    
    tags = load_json_file('tags.json')
    vendor_tags = load_json_file('vendor_tags.json')
    
    return tags, vendor_tags


def save_json_config(filename: str, data: dict) -> bool:
    """Save configuration data to JSON file"""
    try:
        from .paths import get_config_file
        config_path = get_config_file(filename)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving {filename}: {e}")
        return False


def update_tags_config(tags_config: dict, new_tags: List[str]) -> dict:
    """Update tags configuration with new tags and their usage counts"""
    updated_tags = tags_config.copy()
    
    for tag in new_tags:
        if tag in updated_tags:
            updated_tags[tag] += 1
        else:
            updated_tags[tag] = 1
    
    return updated_tags


def update_vendor_tags_config(vendor_tags_config: dict, vendors: List[str], tags: List[str]) -> dict:
    """Update vendor-tags associations configuration"""
    updated_vendor_tags = vendor_tags_config.copy()
    
    for vendor in vendors:
        if vendor not in updated_vendor_tags:
            updated_vendor_tags[vendor] = {}
        
        for tag in tags:
            if tag in updated_vendor_tags[vendor]:
                updated_vendor_tags[vendor][tag] += 1
            else:
                updated_vendor_tags[vendor][tag] = 1
    
    return updated_vendor_tags


def update_configurations_on_disk(new_tags: List[str], vendors: List[str]) -> tuple:
    """Update both tags.json and vendor_tags.json files on disk"""
    try:
        # Load current configurations
        tags_config, vendor_tags_config = load_tagging_configs()
        
        # Update configurations
        updated_tags = update_tags_config(tags_config, new_tags)
        updated_vendor_tags = update_vendor_tags_config(vendor_tags_config, vendors, new_tags)
        
        # Save updated configurations
        tags_saved = save_json_config('tags.json', updated_tags)
        vendor_tags_saved = save_json_config('vendor_tags.json', updated_vendor_tags)
        
        if tags_saved and vendor_tags_saved:
            return updated_tags, updated_vendor_tags
        else:
            print("Warning: Some configurations could not be saved")
            return tags_config, vendor_tags_config
            
    except Exception as e:
        print(f"Error updating configurations: {e}")
        # Return original configs if update fails
        return load_tagging_configs()


def preprocess_raw_file(filename: str) -> tuple:
    """
    Preprocess a raw file for tagging following the notebook workflow
    Returns: (processed_df, summary_info)
    """
    from .paths import get_raw_file
    
    # Load raw file
    file_path = get_raw_file(filename)
    df = pd.read_csv(file_path)
    
    # Step 1: Detect language and map columns
    column_mapping = _detect_and_map_columns(df.columns)
    
    # Rename columns to English standard
    df = df.rename(columns=column_mapping)
    
    # Select required columns (now all in English)
    required_columns = ['Type', 'Started Date', 'Description', 'Amount', 'Currency', 'State']
    df = df[required_columns].copy()
    
    # Step 2: Process date column (keep time information)
    df['Started Date'] = pd.to_datetime(df['Started Date'])
    df = df.rename(columns={'Started Date': 'Date'})
    
    # Step 3: Sort by date (chronological order) - more logical for tagging
    df = df.sort_values(by='Date', ascending=True)
    
    # Step 4: Initialize tags column
    df["tags"] = [[] for _ in range(len(df))]
    
    # Step 5: Convert Amount to numeric and filter for expenses only
    df['amount_numeric'] = pd.to_numeric(df['Amount'], errors='coerce')
    expenses_df = df[df['amount_numeric'] < 0].copy()
    
    # Step 6: Add absolute amount for display
    expenses_df['amount_abs'] = expenses_df['amount_numeric'].abs()
    
    # Step 7: Load tagging configurations
    tags, vendor_tags = load_tagging_configs()
    
    # Step 8: Analyze untagged vendors
    untagged_summary = analyze_untagged_vendors(expenses_df, vendor_tags)
    
    # Step 9: Create summary information
    summary_info = {
        'total_transactions': len(df),
        'total_expenses': len(expenses_df),
        'total_amount': expenses_df['amount_abs'].sum(),
        'untagged_vendors': len(untagged_summary['vendors']),
        'known_vendors': len(untagged_summary['known_vendors']),
        'unknown_vendors': len(untagged_summary['unknown_vendors']),
        'largest_expense': expenses_df['amount_abs'].max(),
        'smallest_expense': expenses_df['amount_abs'].min(),
        'tags_count': len(tags),
        'vendor_tags_count': len(vendor_tags)
    }
    
    return expenses_df, summary_info, untagged_summary


def remove_transactions_from_raw(filename: str, transactions_to_remove: pd.DataFrame) -> bool:
    """Remove specific transactions from raw file
    
    Match transactions by: Date + Amount + Description
    Rewrite the raw CSV without matched transactions
    
    Args:
        filename: Name of the raw file (e.g., '2025-12.csv')
        transactions_to_remove: DataFrame with transactions to remove (must have Date, Amount, Description columns)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        from .paths import get_raw_file
        
        raw_file_path = get_raw_file(filename)
        
        if not raw_file_path.exists():
            print(f"Raw file {filename} does not exist")
            return False
        
        # Load the raw file
        raw_df = pd.read_csv(raw_file_path)
        
        # Normalize dates for comparison
        raw_df['Date'] = pd.to_datetime(raw_df['Date'], format='mixed', errors='coerce')
        transactions_to_remove['Date'] = pd.to_datetime(transactions_to_remove['Date'], format='mixed', errors='coerce')
        
        # Normalize amounts (convert to numeric)
        raw_df['Amount'] = pd.to_numeric(raw_df['Amount'], errors='coerce')
        transactions_to_remove['Amount'] = pd.to_numeric(transactions_to_remove['Amount'], errors='coerce')
        
        # Create matching mask
        # Match on Date (same day), Amount, and Description
        mask = pd.Series([False] * len(raw_df))
        
        for _, trans in transactions_to_remove.iterrows():
            # Match transactions with same Date (day), Amount, and Description
            date_match = raw_df['Date'].dt.date == trans['Date'].date() if pd.notna(trans['Date']) else False
            amount_match = raw_df['Amount'] == trans['Amount']
            desc_match = raw_df['Description'] == trans['Description']
            
            # Combine matches
            combined_match = date_match & amount_match & desc_match
            mask = mask | combined_match
        
        # Keep only transactions that don't match
        remaining_df = raw_df[~mask].copy()
        
        # If no transactions remain, we could delete the file or leave it empty
        # For now, we'll save an empty file with headers
        if len(remaining_df) == 0:
            # Keep only headers
            remaining_df = pd.DataFrame(columns=raw_df.columns)
        
        # Save the updated raw file
        remaining_df.to_csv(raw_file_path, index=False)
        
        return True
        
    except Exception as e:
        print(f"Error removing transactions from raw file: {e}")
        import traceback
        traceback.print_exc()
        return False


def get_remaining_raw_count(filename: str) -> int:
    """Count how many transactions remain in raw file
    
    Args:
        filename: Name of the raw file (e.g., '2025-12.csv')
    
    Returns:
        Number of expense transactions remaining in the raw file
    """
    try:
        from .paths import get_raw_file
        
        raw_file_path = get_raw_file(filename)
        
        if not raw_file_path.exists():
            return 0
        
        # Load and count expenses
        df = pd.read_csv(raw_file_path)
        df['amount_numeric'] = pd.to_numeric(df['Amount'], errors='coerce')
        expenses_df = df[df['amount_numeric'] < 0]
        
        return len(expenses_df)
        
    except Exception as e:
        print(f"Error counting remaining transactions: {e}")
        return 0


def analyze_untagged_vendors(df: pd.DataFrame, vendor_tags: dict) -> dict:
    """
    Analyze untagged vendors and categorize them as known/unknown
    Following the notebook logic
    """
    # All vendors are untagged (tags column is empty lists)
    mask = df["tags"].apply(lambda tags: len(tags) == 0)
    untagged = df[mask]
    
    if len(untagged) == 0:
        return {
            'vendors': [],
            'known_vendors': [],
            'unknown_vendors': []
        }
    
    known_vendors = set(vendor_tags.keys())
    
    # Group by vendor and sum amounts
    vendor_amounts = untagged.groupby("Description")["amount_abs"].sum().sort_values(ascending=False)
    
    # Separate known and unknown vendors
    known_merchants = []
    unknown_merchants = []
    
    for vendor, amount in vendor_amounts.items():
        if vendor in known_vendors:
            known_merchants.append({
                'name': vendor,
                'display_name': f"🟢 {vendor}",
                'amount': amount,
                'is_known': True
            })
        else:
            unknown_merchants.append({
                'name': vendor,
                'display_name': vendor,
                'amount': amount,
                'is_known': False
            })
    
    # Combine known first, then unknown
    all_vendors = known_merchants + unknown_merchants
    
    return {
        'vendors': all_vendors,
        'known_vendors': known_merchants,
        'unknown_vendors': unknown_merchants
    }


def get_untagged_vendors_from_df(df: pd.DataFrame, vendor_tags: dict) -> List[Dict]:
    """Get list of untagged vendors from current DataFrame state"""
    # Filter untagged transactions
    mask = df["tags"].apply(lambda tags: len(tags) == 0)
    untagged = df[mask]
    
    if len(untagged) == 0:
        return []
    
    known_vendors = set(vendor_tags.keys())
    
    # Group by vendor and sum amounts
    vendor_amounts = untagged.groupby("Description")["amount_abs"].sum().sort_values(ascending=False)
    
    vendors_list = []
    for vendor, amount in vendor_amounts.items():
        if vendor in known_vendors:
            vendors_list.append({
                'label': f"🟢 {vendor} ({amount:.2f}€)",
                'value': vendor
            })
        else:
            vendors_list.append({
                'label': f"{vendor} ({amount:.2f}€)",
                'value': vendor
            })
    
    return vendors_list


def get_suggested_tags_for_vendors(selected_vendors: List[str], tags: dict, vendor_tags: dict) -> List[Dict]:
    """Get suggested tags for selected vendors"""
    if not selected_vendors:
        # Return all tags sorted by frequency
        all_tags = [{'label': tag, 'value': tag} for tag, _ in sorted(tags.items(), key=lambda x: x[1], reverse=True)]
        return all_tags
    
    # Get suggested tags for selected vendors
    suggested_tags = set()
    for vendor in selected_vendors:
        if vendor in vendor_tags:
            suggested_tags.update(vendor_tags[vendor].keys())
    
    # Sort tags: suggested first (with star), then others
    suggested_list = [{'label': f"⭐ {tag}", 'value': tag} for tag in suggested_tags]
    other_tags = [{'label': tag, 'value': tag} for tag in tags.keys() if tag not in suggested_tags]
    other_tags.sort(key=lambda x: tags.get(x['value'], 0), reverse=True)
    
    return suggested_list + other_tags


def get_transaction_details_for_vendors(df: pd.DataFrame, selected_vendors: List[str]) -> Dict:
    """Get transaction details for selected vendors - chronologically sorted"""
    if not selected_vendors:
        return {'transactions': [], 'summary': {}}
    
    # Filter untagged transactions for selected vendors
    mask_untagged = df["tags"].apply(lambda tags: len(tags) == 0)
    mask_vendors = df["Description"].isin(selected_vendors)
    transactions = df[mask_untagged & mask_vendors]
    
    if len(transactions) == 0:
        return {'transactions': [], 'summary': {}}
    
    # Sort transactions chronologically (oldest first for better memory context)
    # Convert Date to datetime for proper sorting, then sort by date AND amount as secondary key
    transactions_with_datetime = transactions.copy()
    transactions_with_datetime['Date'] = pd.to_datetime(transactions_with_datetime['Date'])
    # Sort by date first (oldest first), then by amount (descending) as secondary sort
    transactions_sorted = transactions_with_datetime.sort_values(['Date', 'amount_abs'], ascending=[True, False])
    
    # Create chronological transaction list with unique IDs
    transactions_list = []
    vendor_summary = {}
    
    for idx, (df_idx, trans) in enumerate(transactions_sorted.iterrows()):
        vendor = trans["Description"]
        transaction_info = {
            'id': f"trans_{df_idx}",  # Unique ID based on DataFrame index
            'df_index': df_idx,  # Original DataFrame index for targeting
            'vendor': vendor,
            'amount': trans["amount_abs"],
            'date': str(trans["Date"]),
            'description': trans["Description"],
            'display_date': trans["Date"].strftime('%Y-%m-%d') if isinstance(trans["Date"], pd.Timestamp) else pd.to_datetime(trans["Date"]).strftime('%Y-%m-%d'),
            'display_amount': f"{trans['amount_abs']:.2f}€"
        }
        transactions_list.append(transaction_info)
        
        # Build vendor summary
        if vendor not in vendor_summary:
            vendor_summary[vendor] = {
                'total': 0,
                'count': 0,
                'transactions': []
            }
        vendor_summary[vendor]['total'] += trans["amount_abs"]
        vendor_summary[vendor]['count'] += 1
        vendor_summary[vendor]['transactions'].append(transaction_info)
    
    return {
        'transactions': transactions_list,
        'summary': vendor_summary
    }


def apply_tags_to_vendors(df: pd.DataFrame, selected_vendors: List[str], selected_tags: List[str], new_tags: List[str]) -> tuple:
    """Apply tags to selected vendors in the DataFrame"""
    if not selected_vendors or (not (selected_tags or []) and not new_tags):
        return df, 0
    
    all_tags = list(set((selected_tags or []) + new_tags))
    
    # Find indices of untagged transactions for the selected vendors
    mask_untagged = df["tags"].apply(lambda tags: len(tags) == 0)
    mask_vendors = df["Description"].isin(selected_vendors)
    indices_to_update = df[mask_untagged & mask_vendors].index
    
    affected_count = len(indices_to_update)

    if affected_count > 0:
        df_copy = df.copy()
        # Use a loop with .at for safe, item-by-item assignment
        for idx in indices_to_update:
            df_copy.at[idx, 'tags'] = all_tags
        return df_copy, affected_count

    return df, 0


def apply_tags_to_transaction(df: pd.DataFrame, transaction_id: str, selected_tags: List[str], new_tags: List[str]) -> tuple:
    """Apply tags to a specific transaction by its ID"""
    if not transaction_id or (not selected_tags and not new_tags):
        return df, 0
    
    # Extract df_index from transaction_id (format: "trans_123")
    try:
        df_index = int(transaction_id.split('_')[1])
    except (ValueError, IndexError):
        return df, 0
    
    # Check if the transaction exists and is untagged
    if df_index not in df.index:
        return df, 0
    
    # Check if transaction is untagged
    current_tags = df.loc[df_index, "tags"]
    if len(current_tags) > 0:
        return df, 0  # Already tagged
    
    # Combine selected tags and new tags
    all_tags = list(set(selected_tags + new_tags))
    
    # Apply tags to the specific transaction
    df.at[df_index, "tags"] = all_tags
    
    return df, 1


def apply_tags_to_transactions(df: pd.DataFrame, transaction_ids: List[str], all_tags: List[str]) -> tuple:
    """Apply tags to a list of specific transactions by their IDs"""
    if not transaction_ids or not all_tags:
        return df, 0, set()

    affected_count = 0
    tagged_vendors = set()
    
    for transaction_id in transaction_ids:
        try:
            df_index = int(transaction_id.split('_')[1])
            if df_index in df.index and len(df.loc[df_index, "tags"]) == 0:
                df.at[df_index, "tags"] = all_tags
                affected_count += 1
                tagged_vendors.add(df.loc[df_index, 'Description'])
        except (ValueError, IndexError, KeyError):
            continue
            
    return df, affected_count, tagged_vendors


def get_daily_context_for_transaction(df: pd.DataFrame, transaction_id: str) -> Dict:
    """Get all transactions from the same day as the selected transaction, sorted by time"""
    if not transaction_id:
        return {'transactions': [], 'summary': {}}
    
    try:
        # Extract df_index from transaction_id (format: "trans_123")
        df_index = int(transaction_id.split('_')[1])
        
        # Check if the transaction exists
        if df_index not in df.index:
            return {'transactions': [], 'summary': {}}
        
        # Get the date of the selected transaction
        selected_datetime = pd.to_datetime(df.loc[df_index, 'Date'])
        selected_date = selected_datetime.date()
        
        # Find all transactions from the same day (convert dates for comparison)
        df_with_dates = df.copy()
        df_with_dates['Date'] = pd.to_datetime(df_with_dates['Date'])
        same_day_mask = df_with_dates['Date'].dt.date == selected_date
        same_day_transactions = df_with_dates[same_day_mask].copy()
        
        # Sort by time (chronological order within the day)
        same_day_transactions = same_day_transactions.sort_values('Date', ascending=True)
        
        # Format transactions for display
        transactions_list = []
        total_amount = 0
        
        for idx, (df_idx, trans) in enumerate(same_day_transactions.iterrows()):
            is_selected = df_idx == df_index
            tags = trans.get('tags', [])
            has_tags = len(tags) > 0 if isinstance(tags, list) else False
            
            # Extract time information
            trans_datetime = pd.to_datetime(trans['Date'])
            has_time = trans_datetime.time() != pd.Timestamp('00:00:00').time()
            
            transaction_info = {
                'id': f"trans_{df_idx}",
                'df_index': df_idx,
                'vendor': trans['Description'],
                'amount': trans['amount_abs'],
                'display_amount': f"{trans['amount_abs']:.2f}€",
                'datetime': trans_datetime,
                'time': trans_datetime.strftime('%H:%M') if has_time else 'N/A',
                'has_time': has_time,
                'tags': tags if isinstance(tags, list) else [],
                'has_tags': has_tags,
                'is_selected': is_selected,
                'tags_display': ', '.join(tags) if has_tags else 'No tags'
            }
            transactions_list.append(transaction_info)
            total_amount += trans['amount_abs']
        
        # Create summary
        summary = {
            'date': selected_date.strftime('%Y-%m-%d'),
            'date_display': selected_date.strftime('%A, %B %d, %Y'),
            'total_amount': total_amount,
            'total_transactions': len(transactions_list),
            'tagged_transactions': sum(1 for t in transactions_list if t['has_tags']),
            'untagged_transactions': sum(1 for t in transactions_list if not t['has_tags'])
        }
        
        return {
            'transactions': transactions_list,
            'summary': summary
        }
        
    except (ValueError, IndexError, KeyError) as e:
        return {'transactions': [], 'summary': {}}


def restore_dataframe_from_store(df_data: list) -> pd.DataFrame:
    """Restore DataFrame from store data, ensuring all columns are properly converted
    
    This function:
    1. Converts stored JSON data back to DataFrame
    2. Restores datetime format for Date column
    3. Recalculates numeric columns (amount_numeric, amount_abs)
    4. Ensures data consistency after modifications
    
    Args:
        df_data (list): List of dictionaries from Dash store
        
    Returns:
        pd.DataFrame: Restored DataFrame with all columns properly typed
    """
    if not df_data:
        return pd.DataFrame()
    
    # Convert dict back to DataFrame
    df = pd.DataFrame(df_data)
    
    # Ensure Date column is datetime with time information
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
    
    # Recalculate numeric columns
    if 'Amount' in df.columns:
        df['amount_numeric'] = pd.to_numeric(df['Amount'], errors='coerce')
        df['amount_abs'] = df['amount_numeric'].abs()
    
    return df


def get_tagging_progress(df: pd.DataFrame) -> Dict:
    """Get current tagging progress statistics based on amount"""
    total_transactions = len(df)
    untagged_mask = df["tags"].apply(lambda tags: len(tags) == 0)
    
    # Calculate totals based on amount
    total_amount = df['amount_abs'].sum()
    tagged_amount = df[~untagged_mask]['amount_abs'].sum()
    untagged_amount = df[untagged_mask]['amount_abs'].sum()
    
    # Count transactions (for display)
    untagged_count = untagged_mask.sum()
    tagged_count = total_transactions - untagged_count
    
    return {
        'total_transactions': total_transactions,
        'tagged_transactions': tagged_count,
        'untagged_transactions': untagged_count,
        'total_amount': total_amount,
        'tagged_amount': tagged_amount,
        'untagged_amount': untagged_amount,
        'progress_percentage': (tagged_amount / total_amount * 100) if total_amount > 0 else 0
    }


def prepare_dataframe_for_store(df: pd.DataFrame) -> list:
    """Prepare DataFrame for storage in Dash store
    Converts DataFrame to a format suitable for JSON serialization
    
    This function:
    1. Converts DataFrame to dict records for JSON serialization
    2. Handles datetime conversion to ISO format
    3. Ensures tags are properly formatted as lists
    4. Preserves numeric columns (Amount, amount_abs) as numbers
    
    Args:
        df (pd.DataFrame): DataFrame to prepare for storage
        
    Returns:
        list: List of dictionaries ready for JSON serialization and Dash store
    """
    if df.empty:
        return []
    
    # Convert DataFrame to dict records
    df_dict = df.to_dict('records')
    
    # Convert any non-serializable objects to strings
    for record in df_dict:
        # Convert datetime objects to string
        if 'Date' in record and pd.notnull(record['Date']):
            record['Date'] = pd.Timestamp(record['Date']).isoformat()
        
        # Convert tags to list if it's a string representation
        if 'tags' in record and isinstance(record['tags'], str):
            try:
                record['tags'] = eval(record['tags'])
            except:
                record['tags'] = []
    
    return df_dict


def save_expenses(df: pd.DataFrame, month: Optional[str] = None) -> Dict[str, Any]:
    """Save expenses to the unified CSV file
    
    Args:
        df: DataFrame with new/updated expenses
        month: If provided, will merge only this month's data with existing data.
               If None, will replace all data with df.
    
    Returns:
        dict with keys:
        - success: bool
        - saved_count: int (number of rows saved)
        - saved_df: pd.DataFrame (the DataFrame that was saved, for matching purposes)
    """
    try:
        # Prepare DataFrame for saving
        save_df = df.copy()
        
        # Store original indices for matching
        original_indices = save_df.index.tolist()
        
        # Convert tags list to string representation for CSV
        if 'tags' in save_df.columns:
            save_df['tags'] = save_df['tags'].apply(lambda tags: str(tags) if tags else '[]')
        
        # Remove temporary columns
        cols_to_remove = ['amount_numeric', 'amount_abs', 'parsed_tags']
        save_df = save_df.drop(columns=[col for col in cols_to_remove if col in save_df.columns])
        
        # Ensure month column exists
        if 'month' not in save_df.columns:
            if month:
                save_df['month'] = month
            else:
                # Extract month from Date column as fallback
                save_df['month'] = pd.to_datetime(save_df['Date'], format='mixed').dt.strftime('%Y-%m')
        
        # If month is specified, merge with existing data
        if month:
            expenses_file = get_expenses_file()
            if expenses_file.exists():
                # Load existing data
                existing_df = pd.read_csv(expenses_file)
                
                # Remove old data for this month
                existing_df = existing_df[existing_df['month'] != month]
                
                # Combine with new data
                save_df = pd.concat([existing_df, save_df], ignore_index=True)
                
                # Sort by date
                save_df['Date'] = pd.to_datetime(save_df['Date'], format='mixed')
                save_df = save_df.sort_values('Date')
        
        # Save to unified file
        expenses_file = get_expenses_file()
        save_df.to_csv(expenses_file, index=False)
        
        # Count how many rows were added (for this month)
        if month:
            saved_count = len(df)
        else:
            saved_count = len(save_df)
        
        # Return the saved DataFrame (only new rows) for matching
        # Extract only the rows that correspond to the input df
        if month:
            saved_df = save_df[save_df['month'] == month].copy()
        else:
            saved_df = save_df.copy()
        
        return {
            'success': True,
            'saved_count': saved_count,
            'saved_df': saved_df
        }
        
    except Exception as e:
        print(f"Error saving expenses: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'saved_count': 0,
            'saved_df': pd.DataFrame()
        }


# Keep old function name for backward compatibility
def save_tagged_file(df: pd.DataFrame, filename: str) -> Dict[str, Any]:
    """Save tagged file (backward compatibility wrapper)
    
    Args:
        df: DataFrame with tagged expenses
        filename: Original filename (e.g., '2025-12.csv'), used to extract month
    
    Returns:
        dict with save info (see save_expenses for structure)
    """
    # Extract month from filename
    month = filename.replace('.csv', '')
    return save_expenses(df, month=month) 