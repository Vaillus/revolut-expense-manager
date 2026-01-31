#!/usr/bin/env python3
"""
Script pour trouver toutes les lignes contenant 'public' dans la colonne tags
"""

import csv
from pathlib import Path


def find_public_tags(csv_file: Path):
    """
    Lit un fichier CSV et affiche toutes les lignes contenant 'public' dans les tags
    
    Args:
        csv_file: Chemin vers le fichier CSV à analyser
    """
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        print(f"\nRecherche de 'public' dans {csv_file.name}")
        print("=" * 80)
        
        count = 0
        total = 0.0
        
        for row in reader:
            tags = row['tags']
            if 'public' in tags:
                count += 1
                amount = float(row['Amount'])
                total += amount
                
                print(f"\nLigne {count}:")
                print(f"  Date: {row['Date']}")
                print(f"  Description: {row['Description']}")
                print(f"  Montant: {row['Amount']} {row['Currency']}")
                print(f"  État: {row['State']}")
                print(f"  Tags: {row['tags']}")
        
        print("\n" + "=" * 80)
        print(f"Total: {count} transactions trouvées")
        print(f"Montant total: {total:.2f} EUR")


if __name__ == "__main__":
    # Chemin vers le fichier CSV
    csv_file = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "2025-11.csv"
    
    if not csv_file.exists():
        print(f"Erreur: Le fichier {csv_file} n'existe pas")
    else:
        find_public_tags(csv_file)


