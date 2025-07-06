"""
Dashboard layouts and UI components
"""
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table


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
                    dcc.Tab(label='🏷️ Tagging', value='tagging-tab', className='custom-tab'),
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


def create_tagging_layout():
    """Layout for the tagging tab"""
    return dbc.Container([
        html.P("Process raw expense files and add tags", className="text-center text-muted mb-4"),
        
        # Hidden stores for state management
        dcc.Store(id='dataframe-store'),
        dcc.Store(id='tags-config-store'),
        dcc.Store(id='vendor-tags-config-store'),
        dcc.Store(id='current-filename-store'),
        
        dbc.Row([
            dbc.Col([
                html.H4("📁 Raw Files Available", className="text-primary mb-3"),
                html.P("Select a raw file to start tagging expenses:", className="text-muted mb-3"),
                html.Div(id='raw-files-list', className="mb-4"),
                html.Div(id='tagging-interface', className="mt-4")
            ], width=12)
        ])
    ])


def create_interactive_tagging_layout():
    """Layout for the interactive tagging interface"""
    return html.Div([
        html.Hr(),
        
        # Progress section
        html.Div([
            html.H4("🏷️ Interactive Tagging", className="text-success mb-3"),
            html.Div(id='tagging-progress', className="mb-3")
        ]),
        
        dbc.Row([
            # Left column: Vendor and Tag selection
            dbc.Col([
                html.H5("🏪 Select Vendors", className="text-primary mb-2"),
                html.P("Choose vendors to tag (🟢 = known vendor):", className="text-muted mb-2"),
                dcc.Dropdown(
                    id='vendor-select',
                    multi=True,
                    placeholder="Select vendors...",
                    style={'marginBottom': '20px'}
                ),
                
                html.H5("🏷️ Select Tags", className="text-primary mb-2"),
                html.P("Choose existing tags (⭐ = suggested for selected vendors):", className="text-muted mb-2"),
                dcc.Dropdown(
                    id='tag-select',
                    multi=True,
                    placeholder="Select tags...",
                    style={'marginBottom': '20px'}
                ),
                
                html.H5("➕ Add New Tags", className="text-primary mb-2"),
                dcc.Input(
                    id='new-tags-input',
                    type='text',
                    placeholder="Enter new tags separated by commas",
                    style={'width': '100%', 'marginBottom': '20px'}
                ),
                
                html.Div([
                    dbc.Button("Apply Tags", id='apply-tags-btn', color="success", className="me-2"),
                    dbc.Button("Save File", id='save-file-btn', color="primary", disabled=True)
                ], className="d-flex mb-3")
            ], width=6),
            
            # Right column: Transaction details and feedback
            dbc.Col([
                html.H5("📋 Transaction Details", className="text-primary mb-2"),
                html.Div(id='transaction-details', className="mb-3"),
                
                html.H5("💬 Feedback", className="text-primary mb-2"),
                html.Div(id='tagging-feedback', className="mb-3")
            ], width=6)
        ])
    ]) 