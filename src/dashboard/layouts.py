"""
Dashboard layouts and UI components
"""
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table


def create_tag_cloud(tags_options, selected_tags=None):
    """Create a responsive tag cloud with clickable badges"""
    if not tags_options:
        return html.P("No tags available", className="text-muted")
    
    if selected_tags is None:
        selected_tags = []
    
    tag_badges = []
    for tag_option in tags_options:
        tag_value = tag_option['value']
        tag_label = tag_option['label']
        is_selected = tag_value in selected_tags
        
        # Check if it's a suggested tag (starts with ⭐)
        is_suggested = tag_label.startswith('⭐')
        
        # Determine badge style based on state
        if is_selected:
            badge_color = "primary"
            badge_style = {
                'margin': '2px',
                'cursor': 'pointer',
                'border': '2px solid #007bff',
                'transform': 'scale(1.05)',
                'transition': 'all 0.2s ease'
            }
        elif is_suggested:
            badge_color = "warning"
            badge_style = {
                'margin': '2px',
                'cursor': 'pointer',
                'border': '1px solid #ffc107',
                'transition': 'all 0.2s ease'
            }
        else:
            badge_color = "secondary"
            badge_style = {
                'margin': '2px',
                'cursor': 'pointer',
                'border': '1px solid #6c757d',
                'transition': 'all 0.2s ease'
            }
        
        badge = dbc.Badge(
            tag_label,
            id={'type': 'tag-badge', 'index': tag_value},
            color=badge_color,
            pill=True,
            style=badge_style,
            className="tag-badge"
        )
        tag_badges.append(badge)
    
    return html.Div(
        tag_badges,
        style={
            'display': 'flex',
            'flexWrap': 'wrap',
            'gap': '2px',
            'alignItems': 'center',
            'minHeight': '60px',
            'padding': '10px',
            'border': '1px solid #dee2e6',
            'borderRadius': '8px',
            'backgroundColor': '#f8f9fa'
        },
        className="tag-cloud-container"
    )


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
        html.Div(id='tab-content'),
        
        # Global stores accessible to all callbacks
        dcc.Store(id='refresh-visualizations-store', data=0),
    ])


def create_categories_layout():
    """Layout for the categories analysis tab"""
    return dbc.Container([
        # Month selector
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Label("Select Month:", className="form-label fw-bold"),
                    dcc.Dropdown(
                        id='month-selector',
                        placeholder="Select a month...",
                        className="mb-3"
                    )
                ])
            ], width=4)
        ]),
        
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
        dcc.Store(id='selected-transaction-store', data=[]),
        dcc.Store(id='selected-tags-store', data=[]),
        dcc.Store(id='selected-vendors-store', data=[]),
        
        # Global feedback element that's always present
        html.Div(id='tagging-feedback', className="mb-3"),
        
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
    """Modern layout for the interactive tagging interface"""
    return html.Div([
        # Progress Bar Section
        dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.H4("🏷️ Interactive Tagging", className="mb-0 text-primary"),
                    html.Div(id='tagging-progress', className="mt-2")
                ])
            ])
        ], className="mb-4", style={'background-color': '#f8f9fa', 'border': '2px solid #007bff'}),
        
        dbc.Row([
            # Left Panel: Workflow Steps
            dbc.Col([
                # Step 1: Vendor Selection
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("🔸 STEP 1: Select Vendors", className="mb-0 text-primary")
                    ]),
                    dbc.CardBody([
                        html.P("Click on vendors to select them", className="text-muted mb-3"),
                        html.Div(id='vendor-cards-container', style={'maxHeight': '250px', 'overflowY': 'auto'})
                    ])
                ], className="mb-3"),
                
                # Step 2: Transaction List
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("🔸 STEP 2: Select Transaction", className="mb-0 text-primary")
                    ]),
                    dbc.CardBody([
                        html.P("Click on a transaction to select it for tagging", className="text-muted mb-3"),
                        html.Div(id='transaction-details', style={'maxHeight': '300px', 'overflowY': 'auto'})
                    ])
                ], className="mb-3"),
                
                # Step 3: Action Buttons
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dbc.Button(
                                "💾 Save Progress", 
                                id='save-file-btn', 
                                color="success", 
                                size="lg",
                                disabled=True,
                                className="w-100"
                            )
                        ])
                    ])
                ], className="mb-3")
            ], width=5),
            
            # Right Panel: Tagging & Context
            dbc.Col([
                # Tagging Panel
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("🔸 STEP 3: Apply Tags", className="mb-0 text-success")
                    ]),
                    dbc.CardBody([
                        html.Div(id='tagging-panel-content', children=[
                            html.Div([
                                html.I(className="fas fa-hand-pointer fa-2x text-muted"),
                                html.P("Select a transaction to start tagging", className="text-muted mt-2 mb-0")
                            ], className="text-center py-4")
                        ])
                    ])
                ], className="mb-3"),
                
                # Daily Context Panel  
                dbc.Card([
                    dbc.CardHeader([
                        html.H5("📅 Daily Context", className="mb-0 text-info")
                    ]),
                    dbc.CardBody([
                        html.Div(id='daily-context', children=[
                            html.P("Select a transaction to see what else happened that day", className="text-muted mb-0")
                        ])
                    ])
                ], className="mb-3"),
                

            ], width=7)
        ]),
        
        # Modal pour l'édition du montant
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("✏️ Modifier le montant de la transaction")),
            dbc.ModalBody([
                html.P("Entrez le nouveau montant pour cette transaction:", className="mb-3"),
                dbc.Input(
                    id="edit-amount-input",
                    type="number",
                    step="0.01",
                    placeholder="Montant...",
                    className="mb-3"
                ),
                html.Div(id="edit-amount-feedback")
            ]),
            dbc.ModalFooter([
                dbc.Button("Annuler", id="cancel-edit-btn", className="me-1", color="secondary"),
                dbc.Button("Confirmer", id="confirm-edit-btn", color="primary")
            ])
        ], id="edit-transaction-modal", is_open=False, backdrop=True, keyboard=True)
    ]) 