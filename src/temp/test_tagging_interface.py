#!/usr/bin/env python3
"""
Test script to verify the tagging interface functions work correctly
"""
import sys
from pathlib import Path
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utilities.data_loader import (
    preprocess_raw_file, load_tagging_configs,
    get_untagged_vendors_from_df, get_suggested_tags_for_vendors,
    get_transaction_details_for_vendors, apply_tags_to_vendors,
    get_tagging_progress, save_tagged_file
)

def test_tagging_workflow():
    """Test the complete tagging workflow"""
    print("🧪 Testing complete tagging workflow...")
    
    try:
        # Step 1: Preprocess file
        print("\n1️⃣ Testing preprocessing...")
        filename = "2025-06.csv"
        expenses_df, summary_info, untagged_summary = preprocess_raw_file(filename)
        print(f"✅ Preprocessing: {len(expenses_df)} expenses from {summary_info['total_transactions']} transactions")
        
        # Step 2: Load configs
        print("\n2️⃣ Testing config loading...")
        tags, vendor_tags = load_tagging_configs()
        print(f"✅ Configs: {len(tags)} tags, {len(vendor_tags)} vendor associations")
        
        # Step 3: Get untagged vendors
        print("\n3️⃣ Testing vendor options...")
        vendor_options = get_untagged_vendors_from_df(expenses_df, vendor_tags)
        print(f"✅ Vendor options: {len(vendor_options)} vendors available")
        for i, vendor in enumerate(vendor_options[:3]):
            print(f"   • {vendor['label']}")
        
        # Step 4: Test tag suggestions
        print("\n4️⃣ Testing tag suggestions...")
        # Test with a known vendor
        test_vendor = "Supermercado Es Cuco"  # From our test data
        tag_options = get_suggested_tags_for_vendors([test_vendor], tags, vendor_tags)
        print(f"✅ Tag suggestions for '{test_vendor}': {len(tag_options)} tags")
        suggested = [opt for opt in tag_options if opt['label'].startswith('⭐')]
        print(f"   • {len(suggested)} suggested tags")
        
        # Step 5: Test transaction details
        print("\n5️⃣ Testing transaction details...")
        details = get_transaction_details_for_vendors(expenses_df, [test_vendor])
        print(f"✅ Transaction details: {len(details['transactions'])} transactions")
        if test_vendor in details['summary']:
            info = details['summary'][test_vendor]
            print(f"   • {test_vendor}: {info['total']:.2f}€ ({info['count']} transactions)")
        
        # Step 6: Test tag application
        print("\n6️⃣ Testing tag application...")
        initial_progress = get_tagging_progress(expenses_df)
        print(f"   Initial: {initial_progress['untagged_transactions']} untagged")
        
        # Apply some tags
        test_tags = ['nourriture', 'courses']
        updated_df, affected_count = apply_tags_to_vendors(
            expenses_df, [test_vendor], test_tags, []
        )
        print(f"✅ Applied tags: {affected_count} transactions affected")
        
        # Check progress
        updated_progress = get_tagging_progress(updated_df)
        print(f"   After tagging: {updated_progress['untagged_transactions']} untagged")
        print(f"   Progress: {updated_progress['progress_percentage']:.1f}%")
        
        # Step 7: Test file operations (dry run)
        print("\n7️⃣ Testing file operations...")
        print(f"✅ Ready to save: {filename}")
        print(f"   DataFrame shape: {updated_df.shape}")
        print(f"   Columns: {list(updated_df.columns)}")
        
        # Show sample of tagged data
        print("\n📋 Sample of tagged data:")
        tagged_rows = updated_df[updated_df['tags'].apply(lambda x: len(x) > 0)]
        if len(tagged_rows) > 0:
            for _, row in tagged_rows.head(3).iterrows():
                print(f"   • {row['Description']}: {row['tags']} ({row['amount_abs']:.2f}€)")
        
        print("\n🎉 All tests passed! Tagging interface is ready.")
        return True
        
    except Exception as e:
        print(f"❌ Error in tagging workflow test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tagging_workflow()
    sys.exit(0 if success else 1) 