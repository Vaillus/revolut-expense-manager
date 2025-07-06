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
    
    # Step 1: Select and rename columns
    required_columns = ['Type', 'Started Date', 'Description', 'Amount', 'Currency', 'State']
    df = df[required_columns].copy()
    
    # Step 2: Process date column
    df['Started Date'] = pd.to_datetime(df['Started Date']).dt.date
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
    if not selected_vendors or (not selected_tags and not new_tags):
        return df, 0
    
    # Combine selected tags and new tags
    all_tags = list(set(selected_tags + new_tags))
    
    # Filter untagged transactions for selected vendors
    mask_untagged = df["tags"].apply(lambda tags: len(tags) == 0)
    mask_vendors = df["Description"].isin(selected_vendors)
    mask = mask_untagged & mask_vendors
    
    # Apply tags to matching transactions
    df.loc[mask, "tags"] = df.loc[mask, "tags"].apply(lambda old_tags: list(set(old_tags + all_tags)))
    
    # Count affected transactions
    affected_count = mask.sum()
    
    return df, affected_count


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


def get_daily_context_for_transaction(df: pd.DataFrame, transaction_id: str) -> Dict:
    """Get all transactions from the same day as the selected transaction"""
    if not transaction_id:
        return {'transactions': [], 'summary': {}}
    
    try:
        # Extract df_index from transaction_id (format: "trans_123")
        df_index = int(transaction_id.split('_')[1])
        
        # Check if the transaction exists
        if df_index not in df.index:
            return {'transactions': [], 'summary': {}}
        
        # Get the date of the selected transaction
        selected_date = pd.to_datetime(df.loc[df_index, 'Date']).date()
        
        # Find all transactions from the same day (convert dates for comparison)
        df_with_dates = df.copy()
        df_with_dates['Date'] = pd.to_datetime(df_with_dates['Date'])
        same_day_mask = df_with_dates['Date'].dt.date == selected_date
        same_day_transactions = df_with_dates[same_day_mask].copy()
        
        # Sort by amount (largest first) for better overview
        same_day_transactions = same_day_transactions.sort_values('amount_abs', ascending=False)
        
        # Format transactions for display
        transactions_list = []
        total_amount = 0
        
        for idx, (df_idx, trans) in enumerate(same_day_transactions.iterrows()):
            is_selected = df_idx == df_index
            tags = trans.get('tags', [])
            has_tags = len(tags) > 0 if isinstance(tags, list) else False
            
            transaction_info = {
                'id': f"trans_{df_idx}",
                'df_index': df_idx,
                'vendor': trans['Description'],
                'amount': trans['amount_abs'],
                'display_amount': f"{trans['amount_abs']:.2f}€",
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


def get_tagging_progress(df: pd.DataFrame) -> Dict:
    """Get current tagging progress statistics"""
    total_transactions = len(df)
    untagged_mask = df["tags"].apply(lambda tags: len(tags) == 0)
    untagged_count = untagged_mask.sum()
    tagged_count = total_transactions - untagged_count
    
    return {
        'total_transactions': total_transactions,
        'tagged_transactions': tagged_count,
        'untagged_transactions': untagged_count,
        'progress_percentage': (tagged_count / total_transactions * 100) if total_transactions > 0 else 0
    }


def save_tagged_file(df: pd.DataFrame, filename: str) -> bool:
    """Save the tagged DataFrame to processed directory"""
    try:
        from .paths import get_processed_file
        
        # Prepare DataFrame for saving
        save_df = df.copy()
        
        # Convert tags list to string representation for CSV
        save_df['tags'] = save_df['tags'].apply(lambda tags: str(tags) if tags else '[]')
        
        # Remove temporary columns
        cols_to_remove = ['amount_numeric', 'amount_abs']
        save_df = save_df.drop(columns=[col for col in cols_to_remove if col in save_df.columns])
        
        # Save to processed directory
        processed_file_path = get_processed_file(filename)
        save_df.to_csv(processed_file_path, index=False)
        
        return True
        
    except Exception as e:
        print(f"Error saving tagged file: {e}")
        return False 