import os
import pandas as pd
from pathlib import Path
from io import StringIO

def convert_excel_to_standard_csv(input_file):
    # Lire le fichier Excel (même si l'extension est .csv)
    df_excel = pd.read_excel(input_file, header=None)
    # Extraire la première colonne (qui contient tout le CSV sous forme de texte)
    csv_text = "\n".join(df_excel.iloc[:, 0].dropna().astype(str))
    # Parser ce texte comme un vrai CSV
    df = pd.read_csv(StringIO(csv_text))
    # Sauvegarder le CSV propre
    output_file = input_file.replace('.csv', '_converted.csv')
    df.to_csv(output_file, index=False)
    return output_file

if __name__ == "__main__":
    # Example usage
    input_file = 'data/raw/2025-05.csv'
    converted_file = convert_excel_to_standard_csv(input_file)
    print(f"Fichier converti sauvegardé dans : {converted_file}") 