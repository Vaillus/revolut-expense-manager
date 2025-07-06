import pandas as pd
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from collections import defaultdict
import dash
from dash import dcc, html, Input, Output, callback
import dash_bootstrap_components as dbc

# Charger les catégories principales
with open('data/config/main_categories.json', 'r', encoding='utf-8') as f:
    main_categories = json.load(f)

print(f"Catégories principales: {main_categories}")

# Fonction pour parser les tags
def parse_tags(tags):
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

# Charger les données des deux mois
def load_month_data(filename):
    """Charger et traiter les données d'un mois"""
    df = pd.read_csv(f'data/processed/{filename}')
    df['parsed_tags'] = df['tags'].apply(parse_tags)
    df['amount_numeric'] = pd.to_numeric(df['Amount'], errors='coerce')
    
    # Ne garder que les dépenses (montants négatifs)
    expenses_df = df[df['amount_numeric'] < 0].copy()
    expenses_df['amount_abs'] = expenses_df['amount_numeric'].abs()
    
    return expenses_df

# Charger les données
df_2024_04 = load_month_data('2025-04.csv')
df_2025_05 = load_month_data('2025-05.csv')

# Ajouter une colonne mois
df_2024_04['month'] = '2025-04'
df_2025_05['month'] = '2025-05'

# Combiner les données
all_data = pd.concat([df_2024_04, df_2025_05], ignore_index=True)

# Fonction pour déterminer la catégorie principale
def get_main_category(tags):
    tags_set = set(tags)
    for category in main_categories:
        if category in tags_set:
            return category
    return 'Autre' if tags else 'Sans tag'

# Classifier toutes les transactions
all_data['main_category'] = all_data['parsed_tags'].apply(get_main_category)

# Calculer les données pour le mois actuel (2025-05)
current_month_data = df_2025_05.copy()
current_month_data['main_category'] = current_month_data['parsed_tags'].apply(get_main_category)

# Fonction pour obtenir les sous-tags d'une catégorie
def get_subtags_for_category(category_name, month_data):
    """Obtenir les sous-tags et leurs montants pour une catégorie donnée"""
    if category_name in ['Sans tag', 'Autre']:
        return {}
    
    # Filtrer les transactions de cette catégorie
    category_transactions = month_data[month_data['main_category'] == category_name]
    
    # Compter les montants par sous-tag (excluant le tag principal)
    subtag_amounts = defaultdict(float)
    
    for _, row in category_transactions.iterrows():
        tags = row['parsed_tags']
        amount = row['amount_abs']
        
        # Ajouter tous les tags SAUF le tag principal
        for tag in tags:
            if tag != category_name:
                subtag_amounts[tag] += amount
    
    return dict(sorted(subtag_amounts.items(), key=lambda x: x[1], reverse=True))

# Fonction pour obtenir l'historique mensuel d'une catégorie
def get_monthly_trend(category_name):
    """Obtenir l'évolution mensuelle d'une catégorie"""
    monthly_data = all_data[all_data['main_category'] == category_name].groupby('month')['amount_abs'].sum().reset_index()
    return monthly_data

# Préparer les données pour la série temporelle
def prepare_timeseries_data():
    """Préparer les données pour l'analyse de série temporelle"""
    # Grouper par mois et type de dépense (exceptionnel vs autres)
    all_data['is_exceptional'] = all_data['main_category'] == 'exceptionnel'
    
    monthly_summary = all_data.groupby(['month', 'is_exceptional'])['amount_abs'].sum().reset_index()
    
    # Séparer exceptionnelles et courantes
    exceptional = monthly_summary[monthly_summary['is_exceptional']].copy()
    regular = monthly_summary[~monthly_summary['is_exceptional']].copy()
    
    # Calculer les totaux par mois
    monthly_totals = all_data.groupby('month')['amount_abs'].sum().reset_index()
    
    return exceptional, regular, monthly_totals

# Initialiser l'app Dash
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Layout principal avec onglets
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Dashboard Financier Interactif", className="text-center mb-4"),
            html.P("Analyse complète de tes dépenses avec navigation par onglets", className="text-center text-muted mb-4")
        ], width=12)
    ]),
    
    # Système d'onglets
    dbc.Row([
        dbc.Col([
            dcc.Tabs(id="main-tabs", value='categories-tab', children=[
                dcc.Tab(label='📊 Analyse par Catégories', value='categories-tab', className='custom-tab'),
                dcc.Tab(label='📈 Série Temporelle', value='timeseries-tab', className='custom-tab'),
            ], className='mb-4')
        ], width=12)
    ]),
    
    # Contenu dynamique selon l'onglet
    html.Div(id='tab-content')
])

# Layout pour l'onglet catégories (existant)
categories_layout = dbc.Container([
    html.P("Cliquez sur une tranche du camembert pour voir les détails", className="text-center text-muted mb-4"),
    
    dbc.Row([
        # Camembert principal
        dbc.Col([
            dcc.Graph(id='pie-chart', style={'height': '600px'})
        ], width=6),
        
        # Graphiques secondaires
        dbc.Col([
            dcc.Graph(id='subtags-bar', style={'height': '300px'}),
            dcc.Graph(id='monthly-trend', style={'height': '300px'})
        ], width=6)
    ]),
    
    # Zone d'information
    dbc.Row([
        dbc.Col([
            html.Div(id='category-info', className="mt-3 p-3 border rounded", style={'background-color': '#f8f9fa'})
        ], width=12)
    ])
])

# Layout pour l'onglet série temporelle (nouveau)
timeseries_layout = dbc.Container([
    html.P("Évolution mensuelle des dépenses générales", className="text-center text-muted mb-4"),
    
    dbc.Row([
        # Graphique série temporelle principal (aires empilées)
        dbc.Col([
            dcc.Graph(id='timeseries-stacked-area', style={'height': '600px'})
        ], width=8),
        
        # Statistiques générales
        dbc.Col([
            html.Div(id='timeseries-stats', className="p-3 border rounded", style={'background-color': '#f8f9fa'})
        ], width=4)
    ])
])

# Callback pour gérer les onglets
@app.callback(Output('tab-content', 'children'),
              Input('main-tabs', 'value'))
def render_tab_content(active_tab):
    if active_tab == 'categories-tab':
        return categories_layout
    elif active_tab == 'timeseries-tab':
        return timeseries_layout

# Callback pour créer le camembert initial
@app.callback(
    Output('pie-chart', 'figure'),
    Input('main-tabs', 'value')
)
def create_pie_chart(active_tab):
    if active_tab != 'categories-tab':
        return {}
        
    # 1. Données pour le camembert principal (mois actuel)
    category_sums = current_month_data.groupby('main_category')['amount_abs'].sum().sort_values(ascending=False)
    
    # Couleurs personnalisées
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', 
              '#FF8C94', '#A8E6CF', '#FFD93D', '#6BCF7F', '#FF6B9D', '#C44569']
    
    fig = go.Figure(data=[go.Pie(
        labels=category_sums.index,
        values=category_sums.values,
        name="Catégories",
        marker_colors=colors[:len(category_sums)],
        textinfo='label+percent+value',
        texttemplate='%{label}<br>%{percent}<br>%{value:.0f}€',
        hovertemplate='%{label}<br>Montant: %{value:.2f}€<br>Pourcentage: %{percent}<br><extra></extra>',
        showlegend=True
    )])
    
    fig.update_layout(
        title="Catégories principales (Mai 2025)",
        title_x=0.5,
        font=dict(size=12),
        margin=dict(t=60, b=20, l=20, r=20)
    )
    
    return fig

# Callback pour les graphiques secondaires et info (catégories)
@app.callback(
    [Output('subtags-bar', 'figure'),
     Output('monthly-trend', 'figure'),
     Output('category-info', 'children')],
    [Input('pie-chart', 'clickData'),
     Input('main-tabs', 'value')]
)
def update_secondary_charts(clickData, active_tab):
    if active_tab != 'categories-tab':
        return {}, {}, []
        
    if clickData is None:
        # Graphiques vides par défaut
        empty_bar = go.Figure()
        empty_bar.update_layout(
            title="Sous-tags (cliquez sur une catégorie)",
            xaxis_title="Sous-tags",
            yaxis_title="Montant (€)",
            margin=dict(t=40, b=40, l=40, r=40)
        )
        
        empty_line = go.Figure()
        empty_line.update_layout(
            title="Évolution mensuelle (cliquez sur une catégorie)",
            xaxis_title="Mois",
            yaxis_title="Montant (€)",
            margin=dict(t=40, b=40, l=40, r=40)
        )
        
        info_text = html.P("Sélectionnez une catégorie dans le camembert pour voir les détails")
        
        return empty_bar, empty_line, info_text
    
    # Récupérer la catégorie cliquée
    category = clickData['points'][0]['label']
    
    # 1. Graphique des sous-tags
    subtags = get_subtags_for_category(category, current_month_data)
    
    if subtags:
        subtag_names = list(subtags.keys())[:10]  # Top 10
        subtag_amounts = [subtags[name] for name in subtag_names]
        
        bar_fig = go.Figure(data=[go.Bar(
            x=subtag_names,
            y=subtag_amounts,
            marker_color='#45B7D1',
            text=[f'{amt:.0f}€' for amt in subtag_amounts],
            textposition='auto'
        )])
        
        bar_fig.update_layout(
            title=f"Sous-tags de '{category}' (Mai 2025)",
            xaxis_title="Sous-tags",
            yaxis_title="Montant (€)",
            margin=dict(t=40, b=40, l=40, r=40),
            xaxis={'tickangle': 45}
        )
    else:
        bar_fig = go.Figure()
        bar_fig.update_layout(
            title=f"Aucun sous-tag pour '{category}'",
            xaxis_title="Sous-tags",
            yaxis_title="Montant (€)",
            margin=dict(t=40, b=40, l=40, r=40)
        )
    
    # 2. Évolution mensuelle
    monthly_data = get_monthly_trend(category)
    
    if not monthly_data.empty:
        line_fig = go.Figure(data=[go.Scatter(
            x=monthly_data['month'],
            y=monthly_data['amount_abs'],
            mode='lines+markers',
            name=category,
            line=dict(width=3, color='#FF6B6B'),
            marker=dict(size=10)
        )])
        
        line_fig.update_layout(
            title=f"Évolution mensuelle - {category}",
            xaxis_title="Mois",
            yaxis_title="Montant (€)",
            margin=dict(t=40, b=40, l=40, r=40),
            showlegend=False
        )
    else:
        line_fig = go.Figure()
        line_fig.update_layout(
            title=f"Pas de données historiques pour '{category}'",
            xaxis_title="Mois",
            yaxis_title="Montant (€)",
            margin=dict(t=40, b=40, l=40, r=40)
        )
    
    # 3. Informations détaillées
    total_current = current_month_data[current_month_data['main_category'] == category]['amount_abs'].sum()
    nb_transactions = len(current_month_data[current_month_data['main_category'] == category])
    
    info_components = [
        html.H4(f"📊 Détails - {category}", className="text-primary"),
        html.P(f"💰 Montant total (Mai 2025): {total_current:.2f}€"),
        html.P(f"📝 Nombre de transactions: {nb_transactions}"),
    ]
    
    if subtags:
        info_components.append(html.P(f"🏷️ Nombre de sous-tags: {len(subtags)}"))
        top_subtag = max(subtags, key=subtags.get)
        info_components.append(html.P(f"🥇 Principal sous-tag: {top_subtag} ({subtags[top_subtag]:.0f}€)"))
    
    if not monthly_data.empty and len(monthly_data) > 1:
        evolution = monthly_data['amount_abs'].iloc[-1] - monthly_data['amount_abs'].iloc[0]
        evolution_pct = (evolution / monthly_data['amount_abs'].iloc[0]) * 100
        trend = "📈" if evolution > 0 else "📉"
        info_components.append(html.P(f"{trend} Évolution: {evolution:+.0f}€ ({evolution_pct:+.1f}%)"))
    
    return bar_fig, line_fig, info_components

# Nouveaux callbacks pour la série temporelle
@app.callback(
    Output('timeseries-stacked-area', 'figure'),
    Input('main-tabs', 'value')
)
def update_timeseries_stacked_area(active_tab):
    if active_tab != 'timeseries-tab':
        return {}
    
    exceptional, regular, monthly_totals = prepare_timeseries_data()
    
    # Créer un DataFrame complet pour les aires empilées
    months = monthly_totals['month'].tolist()
    
    regular_amounts = []
    exceptional_amounts = []
    total_amounts = []
    
    for month in months:
        reg_amount = regular[regular['month'] == month]['amount_abs'].sum()
        exc_amount = exceptional[exceptional['month'] == month]['amount_abs'].sum()
        
        regular_amounts.append(reg_amount)
        exceptional_amounts.append(exc_amount)
        total_amounts.append(reg_amount + exc_amount)
    
    fig = go.Figure()
    
    # Aire du bas : dépenses courantes
    fig.add_trace(go.Scatter(
        x=months,
        y=regular_amounts,
        mode='lines',
        name='Dépenses Courantes',
        line=dict(color='rgba(69, 183, 209, 0.8)', width=2),
        fill='tozeroy',
        fillcolor='rgba(69, 183, 209, 0.6)',
        hovertemplate='<b>Dépenses Courantes</b><br>Mois: %{x}<br>Montant: %{y:.0f}€<extra></extra>'
    ))
    
    # Aire du haut : dépenses exceptionnelles (empilées)
    fig.add_trace(go.Scatter(
        x=months,
        y=total_amounts,
        mode='lines',
        name='Dépenses Exceptionnelles',
        line=dict(color='rgba(255, 107, 107, 0.8)', width=2),
        fill='tonexty',  # Remplit jusqu'à la trace précédente
        fillcolor='rgba(255, 107, 107, 0.6)',
        hovertemplate='<b>Dépenses Exceptionnelles</b><br>Mois: %{x}<br>Montant: %{customdata:.0f}€<extra></extra>',
        customdata=exceptional_amounts  # Pour afficher seulement la partie exceptionnelle
    ))
    
    # Ligne de contour pour le total (optionnel)
    fig.add_trace(go.Scatter(
        x=months,
        y=total_amounts,
        mode='lines+markers',
        name='Total',
        line=dict(color='#2E8B57', width=3, dash='dot'),
        marker=dict(size=8, color='#2E8B57'),
        hovertemplate='<b>Total Dépenses</b><br>Mois: %{x}<br>Montant: %{y:.0f}€<extra></extra>',
        showlegend=True
    ))
    
    fig.update_layout(
        title="Évolution Mensuelle - Aires Empilées des Dépenses",
        xaxis_title="Mois",
        yaxis_title="Montant (€)",
        legend=dict(x=0, y=1, bgcolor='rgba(255,255,255,0.8)'),
        margin=dict(t=60, b=40, l=40, r=40),
        height=600,
        hovermode='x unified'  # Affichage groupé des hovers
    )
    
    return fig

@app.callback(
    Output('timeseries-stats', 'children'),
    Input('main-tabs', 'value')
)
def update_timeseries_stats(active_tab):
    if active_tab != 'timeseries-tab':
        return []
    
    exceptional, regular, monthly_totals = prepare_timeseries_data()
    
    # Calculs statistiques
    total_exceptional = exceptional['amount_abs'].sum() if not exceptional.empty else 0
    total_regular = regular['amount_abs'].sum() if not regular.empty else 0
    total_overall = monthly_totals['amount_abs'].sum()
    
    avg_monthly = total_overall / len(monthly_totals) if len(monthly_totals) > 0 else 0
    
    # Evolution entre les mois
    if len(monthly_totals) >= 2:
        evolution = monthly_totals['amount_abs'].iloc[-1] - monthly_totals['amount_abs'].iloc[0]
        evolution_pct = (evolution / monthly_totals['amount_abs'].iloc[0]) * 100
        trend_icon = "📈" if evolution > 0 else "📉"
    else:
        evolution = 0
        evolution_pct = 0
        trend_icon = "➖"
    
    # Pourcentage d'exceptionnelles
    exceptional_pct = (total_exceptional / total_overall * 100) if total_overall > 0 else 0
    
    stats_components = [
        html.H4("📊 Statistiques Générales", className="text-primary mb-3"),
        
        html.Div([
            html.H5("💰 Totaux", className="text-secondary"),
            html.P(f"Total général: {total_overall:.0f}€"),
            html.P(f"Dépenses courantes: {total_regular:.0f}€"),
            html.P(f"Dépenses exceptionnelles: {total_exceptional:.0f}€"),
        ], className="mb-3"),
        
        html.Div([
            html.H5("📈 Moyennes", className="text-secondary"),
            html.P(f"Moyenne mensuelle: {avg_monthly:.0f}€"),
            html.P(f"Part exceptionnelle: {exceptional_pct:.1f}%"),
        ], className="mb-3"),
        
        html.Div([
            html.H5("🔄 Évolution", className="text-secondary"),
            html.P(f"{trend_icon} Variation: {evolution:+.0f}€"),
            html.P(f"Pourcentage: {evolution_pct:+.1f}%"),
        ])
    ]
    
    return stats_components

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🚀 LANCEMENT DU DASHBOARD INTERACTIF AMÉLIORÉ")
    print("="*80)
    print("📡 L'application sera disponible sur: http://127.0.0.1:8050")
    print("🔄 Nouvelles fonctionnalités:")
    print("   • 📊 Onglet 'Analyse par Catégories' (existant)")
    print("   • 📈 Onglet 'Série Temporelle' (nouveau)")
    print("   • 🎯 Comparaison dépenses exceptionnelles vs courantes")
    print("   • 📋 Statistiques générales et évolutions")
    print("="*80)
    
    app.run(debug=True, host='127.0.0.1', port=8050) 