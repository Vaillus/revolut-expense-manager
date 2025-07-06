"""
Main dashboard application
"""
import dash
import dash_bootstrap_components as dbc

from .layouts import create_main_layout
from .callbacks import register_callbacks


def create_app():
    """Create and configure the Dash application"""
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
    
    # Set layout
    app.layout = create_main_layout()
    
    # Register callbacks
    register_callbacks(app)
    
    return app


def run_dashboard(debug=True, host='127.0.0.1', port=8050):
    """Run the dashboard application"""
    app = create_app()
    
    print("\n" + "="*80)
    print("🚀 REVOLUT EXPENSE DASHBOARD")
    print("="*80)
    print(f"📡 Application available at: http://{host}:{port}")
    print("🔄 Features:")
    print("   • 📊 Category Analysis - Interactive pie chart with details")
    print("   • 📈 Time Series - Monthly expense evolution")
    print("   • 🎯 Regular vs Exceptional expense comparison")
    print("   • 📋 Statistics and trends")
    print("="*80)
    
    app.run(debug=debug, host=host, port=port) 