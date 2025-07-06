"""
Dashboard layouts and UI components
"""
import dash_bootstrap_components as dbc
from dash import dcc, html


def create_main_layout():
    """Create the main dashboard layout with tabs"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H1("Revolut Expense Dashboard", className="text-center mb-4"),
                html.P("Analyze and categorize your monthly expenses", className="text-center text-muted mb-4")
            ], width=12)
        ]),
        
        # Tab system
        dbc.Row([
            dbc.Col([
                dcc.Tabs(id="main-tabs", value='categories-tab', children=[
                    dcc.Tab(label='📊 Category Analysis', value='categories-tab', className='custom-tab'),
                    dcc.Tab(label='📈 Time Series', value='timeseries-tab', className='custom-tab'),
                ], className='mb-4')
            ], width=12)
        ]),
        
        # Dynamic content based on selected tab
        html.Div(id='tab-content')
    ])


def create_categories_layout():
    """Layout for the categories analysis tab"""
    return dbc.Container([
        html.P("Click on a pie chart slice to see details", className="text-center text-muted mb-4"),
        
        dbc.Row([
            # Main pie chart
            dbc.Col([
                dcc.Graph(id='pie-chart', style={'height': '600px'})
            ], width=6),
            
            # Secondary charts
            dbc.Col([
                dcc.Graph(id='subtags-bar', style={'height': '300px'}),
                dcc.Graph(id='monthly-trend', style={'height': '300px'})
            ], width=6)
        ]),
        
        # Information zone
        dbc.Row([
            dbc.Col([
                html.Div(id='category-info', className="mt-3 p-3 border rounded", 
                        style={'background-color': '#f8f9fa'})
            ], width=12)
        ])
    ])


def create_timeseries_layout():
    """Layout for the time series analysis tab"""
    return dbc.Container([
        html.P("Monthly expense evolution overview", className="text-center text-muted mb-4"),
        
        dbc.Row([
            # Main timeseries chart (stacked areas)
            dbc.Col([
                dcc.Graph(id='timeseries-stacked-area', style={'height': '600px'})
            ], width=8),
            
            # General statistics
            dbc.Col([
                html.Div(id='timeseries-stats', className="p-3 border rounded", 
                        style={'background-color': '#f8f9fa'})
            ], width=4)
        ])
    ]) 