"""
Main dashboard application
"""
import dash
import dash_bootstrap_components as dbc

from .layouts import create_main_layout
from .callbacks import register_callbacks


def create_app():
    """Create and configure the Dash application"""
    app = dash.Dash(__name__, 
                    external_stylesheets=[
                        dbc.themes.BOOTSTRAP,
                        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
                    ],
                    suppress_callback_exceptions=True)
    
    # Custom CSS for enhanced styling
    app.index_string = '''
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>{%title%}</title>
            {%favicon%}
            {%css%}
            <style>
                .card {
                    border-radius: 15px !important;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
                    transition: all 0.3s ease !important;
                }
                
                .card:hover {
                    transform: translateY(-2px) !important;
                    box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15) !important;
                }
                
                .card-header {
                    border-radius: 15px 15px 0 0 !important;
                    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%) !important;
                    border-bottom: 2px solid #dee2e6 !important;
                }
                
                .btn {
                    border-radius: 25px !important;
                    font-weight: 500 !important;
                    transition: all 0.3s ease !important;
                }
                
                .btn:hover {
                    transform: translateY(-1px) !important;
                }
                
                .progress {
                    border-radius: 10px !important;
                    background-color: rgba(255, 255, 255, 0.3) !important;
                }
                
                .progress-bar {
                    border-radius: 10px !important;
                    transition: width 0.6s ease !important;
                }
                
                .alert {
                    border-radius: 15px !important;
                    border: none !important;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
                }
                
                .dropdown {
                    border-radius: 10px !important;
                }
                
                .form-control {
                    border-radius: 10px !important;
                    border: 2px solid #e9ecef !important;
                    transition: all 0.3s ease !important;
                }
                
                .form-control:focus {
                    border-color: #80bdff !important;
                    box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.25) !important;
                }
                
                .transaction-card {
                    cursor: pointer !important;
                    transition: all 0.3s ease !important;
                }
                
                .transaction-card:hover {
                    background-color: #f8f9fa !important;
                }
                
                .transaction-card.selected {
                    background-color: #e3f2fd !important;
                    border-left: 4px solid #2196f3 !important;
                }
                
                .text-gradient {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(20px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                
                .fade-in {
                    animation: fadeIn 0.5s ease-out !important;
                }
            </style>
        </head>
        <body>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
            </footer>
        </body>
    </html>
    '''
    
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