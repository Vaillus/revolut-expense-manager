"""
Category analysis callbacks for the dashboard
"""
import plotly.graph_objects as go
from dash import Input, Output, html
import pandas as pd

from ..utilities.data_loader import (
    load_config, load_all_processed_data, get_main_category,
    get_subtags_for_category, get_monthly_trend
)


def register_categories_callbacks(app):
    """Register category analysis callbacks"""
    
    # Load data once when callbacks are registered
    try:
        main_categories = load_config('main_categories.json')
        all_data = load_all_processed_data()
        
        # Apply main categories to all data
        if not all_data.empty:
            all_data['main_category'] = all_data['parsed_tags'].apply(
                lambda tags: get_main_category(tags, main_categories)
            )
        
        # Get current month data (most recent)
        current_month_data = pd.DataFrame()
        if not all_data.empty:
            latest_month = all_data['month'].max()
            current_month_data = all_data[all_data['month'] == latest_month].copy()
            
    except Exception as e:
        print(f"Error loading data: {e}")
        main_categories = []
        all_data = pd.DataFrame()
        current_month_data = pd.DataFrame()

    @app.callback(
        Output('pie-chart', 'figure'),
        Input('main-tabs', 'value')
    )
    def create_pie_chart(active_tab):
        """Create pie chart for category analysis"""
        if active_tab != 'categories-tab' or current_month_data.empty:
            return {}
        
        # Group by category and calculate sums
        category_amounts = current_month_data.groupby('main_category')['amount_abs'].sum().reset_index()
        category_amounts = category_amounts.sort_values('amount_abs', ascending=False)
        
        # Create the pie chart
        fig = go.Figure(data=[go.Pie(
            labels=category_amounts['main_category'],
            values=category_amounts['amount_abs'],
            hole=0.3,
            textinfo='label+percent',
            textposition='auto',
            hovertemplate='<b>%{label}</b><br>Amount: %{value:.2f}€<br>Percentage: %{percent}<extra></extra>'
        )])
        
        fig.update_layout(
            title=f"Expenses by Category ({current_month_data['month'].iloc[0]})",
            showlegend=True,
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05),
            margin=dict(t=40, b=40, l=40, r=40)
        )
        
        return fig

    @app.callback(
        [Output('subtags-bar', 'figure'),
         Output('monthly-trend', 'figure'),
         Output('category-info', 'children')],
        [Input('pie-chart', 'clickData'),
         Input('main-tabs', 'value')]
    )
    def update_secondary_charts(clickData, active_tab):
        """Update secondary charts when category is clicked"""
        if active_tab != 'categories-tab' or current_month_data.empty:
            return {}, {}, []
        
        if not clickData:
            # Default empty charts
            empty_bar = go.Figure()
            empty_bar.update_layout(
                title="Subtags breakdown (click on a category)",
                xaxis_title="Subtags",
                yaxis_title="Amount (€)",
                margin=dict(t=40, b=40, l=40, r=40)
            )
            
            empty_line = go.Figure()
            empty_line.update_layout(
                title="Monthly evolution (click on a category)",
                xaxis_title="Month",
                yaxis_title="Amount (€)",
                margin=dict(t=40, b=40, l=40, r=40)
            )
            
            info_text = html.P("Select a category in the pie chart to see details")
            
            return empty_bar, empty_line, info_text
        
        # Get clicked category
        category = clickData['points'][0]['label']
        
        # 1. Subtags chart
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
                title=f"Subtags of '{category}' ({current_month_data['month'].iloc[0]})",
                xaxis_title="Subtags",
                yaxis_title="Amount (€)",
                margin=dict(t=40, b=40, l=40, r=40),
                xaxis={'tickangle': 45}
            )
        else:
            bar_fig = go.Figure()
            bar_fig.update_layout(
                title=f"No subtags for '{category}'",
                xaxis_title="Subtags",
                yaxis_title="Amount (€)",
                margin=dict(t=40, b=40, l=40, r=40)
            )
        
        # 2. Monthly evolution
        monthly_data = get_monthly_trend(category, all_data)
        
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
                title=f"Monthly Evolution - {category}",
                xaxis_title="Month",
                yaxis_title="Amount (€)",
                margin=dict(t=40, b=40, l=40, r=40),
                showlegend=False
            )
        else:
            line_fig = go.Figure()
            line_fig.update_layout(
                title=f"No historical data for '{category}'",
                xaxis_title="Month",
                yaxis_title="Amount (€)",
                margin=dict(t=40, b=40, l=40, r=40)
            )
        
        # 3. Detailed information
        total_current = current_month_data[current_month_data['main_category'] == category]['amount_abs'].sum()
        nb_transactions = len(current_month_data[current_month_data['main_category'] == category])
        
        info_components = [
            html.H4(f"📊 Details - {category}", className="text-primary"),
            html.P(f"💰 Total amount ({current_month_data['month'].iloc[0]}): {total_current:.2f}€"),
            html.P(f"📝 Number of transactions: {nb_transactions}"),
        ]
        
        if subtags:
            info_components.append(html.P(f"🏷️ Number of subtags: {len(subtags)}"))
            top_subtag = max(subtags, key=subtags.get)
            info_components.append(html.P(f"🥇 Main subtag: {top_subtag} ({subtags[top_subtag]:.0f}€)"))
        
        return bar_fig, line_fig, info_components 