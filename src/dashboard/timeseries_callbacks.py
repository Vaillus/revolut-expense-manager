"""
Time series analysis callbacks for the dashboard
"""
import plotly.graph_objects as go
from dash import Input, Output, html
import pandas as pd

from ..utilities.data_loader import (
    load_config, load_all_processed_data, get_main_category,
    prepare_timeseries_data
)


def register_timeseries_callbacks(app):
    """Register time series analysis callbacks"""
    
    # Load data once when callbacks are registered
    try:
        main_categories = load_config('main_categories.json')
        all_data = load_all_processed_data()
        
        # Apply main categories to all data
        if not all_data.empty:
            all_data['main_category'] = all_data['parsed_tags'].apply(
                lambda tags: get_main_category(tags, main_categories)
            )
            
    except Exception as e:
        print(f"Error loading data: {e}")
        main_categories = []
        all_data = pd.DataFrame()

    @app.callback(
        Output('timeseries-stacked-area', 'figure'),
        Input('main-tabs', 'value')
    )
    def update_timeseries_stacked_area(active_tab):
        """Update the main timeseries stacked area chart"""
        if active_tab != 'timeseries-tab' or all_data.empty:
            return {}
            
        exceptional, regular, monthly_totals = prepare_timeseries_data(all_data)
        
        fig = go.Figure()
        
        # Add exceptional expenses
        if not exceptional.empty:
            fig.add_trace(go.Scatter(
                x=exceptional['month'],
                y=exceptional['amount_abs'],
                mode='lines+markers',
                name='Exceptional',
                line=dict(width=3, color='#FF6B6B'),
                marker=dict(size=10),
                hovertemplate='%{x}<br>Exceptional: %{y:.2f}€<extra></extra>'
            ))
        
        # Add regular expenses
        if not regular.empty:
            fig.add_trace(go.Scatter(
                x=regular['month'],
                y=regular['amount_abs'],
                mode='lines+markers',
                name='Regular',
                line=dict(width=3, color='#4ECDC4'),
                marker=dict(size=10),
                hovertemplate='%{x}<br>Regular: %{y:.2f}€<extra></extra>'
            ))
        
        # Add total line
        if not monthly_totals.empty:
            fig.add_trace(go.Scatter(
                x=monthly_totals['month'],
                y=monthly_totals['amount_abs'],
                mode='lines+markers',
                name='Total',
                line=dict(width=4, color='#45B7D1', dash='dash'),
                marker=dict(size=12),
                hovertemplate='%{x}<br>Total: %{y:.2f}€<extra></extra>'
            ))
        
        fig.update_layout(
            title="Monthly Expense Evolution",
            xaxis_title="Month",
            yaxis_title="Amount (€)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode='x unified',
            margin=dict(t=60, b=40, l=40, r=40)
        )
        
        return fig

    @app.callback(
        Output('timeseries-stats', 'children'),
        Input('main-tabs', 'value')
    )
    def update_timeseries_stats(active_tab):
        """Update timeseries statistics panel"""
        if active_tab != 'timeseries-tab' or all_data.empty:
            return []
            
        # Calculate statistics
        exceptional, regular, monthly_totals = prepare_timeseries_data(all_data)
        
        stats_components = [
            html.H4("📊 Statistics", className="text-primary mb-3"),
        ]
        
        if not monthly_totals.empty:
            avg_monthly = monthly_totals['amount_abs'].mean()
            max_monthly = monthly_totals['amount_abs'].max()
            min_monthly = monthly_totals['amount_abs'].min()
            
            stats_components.extend([
                html.P(f"📈 Average monthly: {avg_monthly:.2f}€"),
                html.P(f"🔼 Highest month: {max_monthly:.2f}€"),
                html.P(f"🔽 Lowest month: {min_monthly:.2f}€"),
                html.Hr()
            ])
        
        if not exceptional.empty:
            avg_exceptional = exceptional['amount_abs'].mean()
            stats_components.append(html.P(f"⚠️ Avg exceptional: {avg_exceptional:.2f}€"))
        
        if not regular.empty:
            avg_regular = regular['amount_abs'].mean()
            stats_components.append(html.P(f"🔄 Avg regular: {avg_regular:.2f}€"))
        
        # Add trend analysis
        if len(monthly_totals) >= 2:
            trend = monthly_totals['amount_abs'].iloc[-1] - monthly_totals['amount_abs'].iloc[-2]
            trend_icon = "📈" if trend > 0 else "📉"
            trend_word = "increase" if trend > 0 else "decrease"
            stats_components.extend([
                html.Hr(),
                html.P(f"{trend_icon} Last month {trend_word}: {abs(trend):.2f}€")
            ])
        
        return stats_components 