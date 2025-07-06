#!/usr/bin/env python3
"""
Test script to verify the preprocessing function works correctly
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utilities.data_loader import preprocess_raw_file

def test_preprocessing():
    """Test the preprocessing function"""
    print("Testing preprocess_raw_file function...")
    
    try:
        # Test with the available raw file
        filename = "2025-06.csv"
        
        print(f"Processing {filename}...")
        expenses_df, summary_info, untagged_summary = preprocess_raw_file(filename)
        
        print(f"\n✅ Preprocessing successful!")
        print(f"📊 DataFrame shape: {expenses_df.shape}")
        print(f"📊 Columns: {list(expenses_df.columns)}")
        
        print(f"\n📈 Summary Statistics:")
        for key, value in summary_info.items():
            print(f"   {key}: {value}")
        
        print(f"\n🏪 Vendor Analysis:")
        print(f"   Total vendors: {len(untagged_summary['vendors'])}")
        print(f"   Known vendors: {len(untagged_summary['known_vendors'])}")
        print(f"   Unknown vendors: {len(untagged_summary['unknown_vendors'])}")
        
        print(f"\n🔝 Top 5 vendors:")
        for i, vendor in enumerate(untagged_summary['vendors'][:5], 1):
            print(f"   {i}. {vendor['display_name']}: {vendor['amount']:.2f}€")
        
        print(f"\n💸 Sample expenses:")
        print(expenses_df[['Description', 'Amount', 'Date', 'tags']].head())
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing preprocessing: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_preprocessing()
    sys.exit(0 if success else 1) 