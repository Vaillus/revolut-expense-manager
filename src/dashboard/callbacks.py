"""
Dashboard callbacks and interactions
"""
import plotly.graph_objects as go
from dash import Input, Output, html
import pandas as pd

from .layouts import create_categories_layout, create_timeseries_layout
from ..utilities.data_loader import (
    load_config, load_all_processed_data, get_main_category,
    get_subtags_for_category, get_monthly_trend, prepare_timeseries_data
)


def register_callbacks(app):
    """Register all dashboard callbacks"""
    
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
        Output('tab-content', 'children'),
        Input('main-tabs', 'value')
    )
    def render_tab_content(active_tab):
        """Render content based on selected tab"""
        if active_tab == 'categories-tab':
            return create_categories_layout()
        elif active_tab == 'timeseries-tab':
            return create_timeseries_layout()
        return html.Div("Tab not found")

    @app.callback(
        Output('pie-chart', 'figure'),
        Input('main-tabs', 'value')
    )
    def create_pie_chart(active_tab):
        """Create the main pie chart for categories"""
        if active_tab != 'categories-tab' or current_month_data.empty:
            return {}
            
        # Data for the main pie chart (current month)
        category_sums = current_month_data.groupby('main_category')['amount_abs'].sum().sort_values(ascending=False)
        
        # Custom colors
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', 
                  '#FF8C94', '#A8E6CF', '#FFD93D', '#6BCF7F', '#FF6B9D', '#C44569']
        
        fig = go.Figure(data=[go.Pie(
            labels=category_sums.index,
            values=category_sums.values,
            name="Categories",
            marker_colors=colors[:len(category_sums)],
            textinfo='label+percent+value',
            texttemplate='%{label}<br>%{percent}<br>%{value:.0f}€',
            hovertemplate='%{label}<br>Amount: %{value:.2f}€<br>Percentage: %{percent}<br><extra></extra>',
            showlegend=True
        )])
        
        fig.update_layout(
            title=f"Main Categories ({current_month_data['month'].iloc[0] if not current_month_data.empty else 'No data'})",
            title_x=0.5,
            font=dict(size=12),
            margin=dict(t=60, b=20, l=20, r=20)
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
        """Update secondary charts and info when category is clicked"""
        if active_tab != 'categories-tab' or current_month_data.empty:
            return {}, {}, []
            
        if clickData is None:
            # Empty charts by default
            empty_bar = go.Figure()
            empty_bar.update_layout(
                title="Subtags (click on a category)",
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
        
        if not monthly_data.empty and len(monthly_data) > 1:
            evolution = monthly_data['amount_abs'].iloc[-1] - monthly_data['amount_abs'].iloc[0]
            evolution_pct = (evolution / monthly_data['amount_abs'].iloc[0]) * 100
            trend = "📈" if evolution > 0 else "📉"
            info_components.append(html.P(f"{trend} Evolution: {evolution:+.0f}€ ({evolution_pct:+.1f}%)"))
        
        return bar_fig, line_fig, info_components

    @app.callback(
        Output('timeseries-stacked-area', 'figure'),
        Input('main-tabs', 'value')
    )
    def update_timeseries_stacked_area(active_tab):
        """Update the timeseries stacked area chart"""
        if active_tab != 'timeseries-tab' or all_data.empty:
            return {}
        
        exceptional, regular, monthly_totals = prepare_timeseries_data(all_data)
        
        # Create complete DataFrame for stacked areas
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
        
        # Bottom area: regular expenses
        fig.add_trace(go.Scatter(
            x=months,
            y=regular_amounts,
            mode='lines',
            name='Regular Expenses',
            line=dict(color='rgba(69, 183, 209, 0.8)', width=2),
            fill='tozeroy',
            fillcolor='rgba(69, 183, 209, 0.6)',
            hovertemplate='<b>Regular Expenses</b><br>Month: %{x}<br>Amount: %{y:.0f}€<extra></extra>'
        ))
        
        # Top area: exceptional expenses (stacked)
        fig.add_trace(go.Scatter(
            x=months,
            y=total_amounts,
            mode='lines',
            name='Exceptional Expenses',
            line=dict(color='rgba(255, 107, 107, 0.8)', width=2),
            fill='tonexty',  # Fill to previous trace
            fillcolor='rgba(255, 107, 107, 0.6)',
            hovertemplate='<b>Exceptional Expenses</b><br>Month: %{x}<br>Amount: %{customdata:.0f}€<extra></extra>',
            customdata=exceptional_amounts  # To show only the exceptional part
        ))
        
        # Total line (optional)
        fig.add_trace(go.Scatter(
            x=months,
            y=total_amounts,
            mode='lines+markers',
            name='Total',
            line=dict(color='#2E8B57', width=3, dash='dot'),
            marker=dict(size=8, color='#2E8B57'),
            hovertemplate='<b>Total Expenses</b><br>Month: %{x}<br>Amount: %{y:.0f}€<extra></extra>',
            showlegend=True
        ))
        
        fig.update_layout(
            title="Monthly Evolution - Stacked Expense Areas",
            xaxis_title="Month",
            yaxis_title="Amount (€)",
            legend=dict(x=0, y=1, bgcolor='rgba(255,255,255,0.8)'),
            margin=dict(t=60, b=40, l=40, r=40),
            height=600,
            hovermode='x unified'  # Grouped hover display
        )
        
        return fig

    @app.callback(
        Output('timeseries-stats', 'children'),
        Input('main-tabs', 'value')
    )
    def update_timeseries_stats(active_tab):
        """Update timeseries statistics"""
        if active_tab != 'timeseries-tab' or all_data.empty:
            return []
        
        exceptional, regular, monthly_totals = prepare_timeseries_data(all_data)
        
        # Statistical calculations
        total_exceptional = exceptional['amount_abs'].sum() if not exceptional.empty else 0
        total_regular = regular['amount_abs'].sum() if not regular.empty else 0
        total_overall = monthly_totals['amount_abs'].sum()
        
        avg_monthly = total_overall / len(monthly_totals) if len(monthly_totals) > 0 else 0
        
        # Evolution between months
        if len(monthly_totals) >= 2:
            evolution = monthly_totals['amount_abs'].iloc[-1] - monthly_totals['amount_abs'].iloc[0]
            evolution_pct = (evolution / monthly_totals['amount_abs'].iloc[0]) * 100
            trend_icon = "📈" if evolution > 0 else "📉"
        else:
            evolution = 0
            evolution_pct = 0
            trend_icon = "➖"
        
        # Percentage of exceptional expenses
        exceptional_pct = (total_exceptional / total_overall * 100) if total_overall > 0 else 0
        
        stats_components = [
            html.H4("📊 General Statistics", className="text-primary mb-3"),
            
            html.Div([
                html.H5("💰 Totals", className="text-secondary"),
                html.P(f"Overall total: {total_overall:.0f}€"),
                html.P(f"Regular expenses: {total_regular:.0f}€"),
                html.P(f"Exceptional expenses: {total_exceptional:.0f}€"),
            ], className="mb-3"),
            
            html.Div([
                html.H5("📈 Averages", className="text-secondary"),
                html.P(f"Monthly average: {avg_monthly:.0f}€"),
                html.P(f"Exceptional share: {exceptional_pct:.1f}%"),
            ], className="mb-3"),
            
            html.Div([
                html.H5("🔄 Evolution", className="text-secondary"),
                html.P(f"{trend_icon} Change: {evolution:+.0f}€"),
                html.P(f"Percentage: {evolution_pct:+.1f}%"),
            ])
        ]
        
        return stats_components 