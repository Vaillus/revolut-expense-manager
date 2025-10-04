"""
Tagging workflow callbacks for the dashboard
"""
from dash import Input, Output, html, dash_table, State, ctx as ctx, ALL, dcc
import pandas as pd
from datetime import datetime
import json
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate

from .layouts import create_interactive_tagging_layout, create_tag_cloud
from ..utilities.data_loader import (
    get_raw_files, preprocess_raw_file, load_tagging_configs,
    get_untagged_vendors_from_df, get_suggested_tags_for_vendors,
    get_transaction_details_for_vendors, apply_tags_to_vendors,
    apply_tags_to_transaction, get_daily_context_for_transaction,
    get_tagging_progress, save_tagged_file, update_configurations_on_disk,
    restore_dataframe_from_store, prepare_dataframe_for_store
)


def register_tagging_callbacks(app):
    """Register tagging workflow callbacks"""
    
    @app.callback(
        Output('raw-files-list', 'children'),
        Input('main-tabs', 'value')
    )
    def update_raw_files_list(active_tab):
        """Update raw files list when tagging tab is selected"""
        if active_tab != 'tagging-tab':
            return []
        
        try:
            raw_files = get_raw_files()
            
            if not raw_files:
                return html.Div([
                    html.P("No raw files found in data/raw/ directory", className="text-muted"),
                    html.P("Place your Revolut CSV files in the data/raw/ folder to start tagging", 
                          className="text-info")
                ])
            
            # Create a table with file information
            table_data = []
            for file_info in raw_files:
                # Format file size
                size_mb = file_info['size'] / (1024 * 1024)
                size_str = f"{size_mb:.2f} MB"
                
                # Format modification date
                mod_date = datetime.fromtimestamp(file_info['modified']).strftime('%Y-%m-%d %H:%M')
                
                table_data.append({
                    'filename': file_info['filename'],
                    'rows': file_info['num_rows'] if file_info['readable'] else 'Error',
                    'size': size_str,
                    'modified': mod_date,
                    'status': 'Ready' if file_info['readable'] else 'Error'
                })
            
            return html.Div([
                dash_table.DataTable(
                    id='raw-files-table',
                    columns=[
                        {"name": "📄 File Name", "id": "filename"},
                        {"name": "📊 Rows", "id": "rows"},
                        {"name": "💾 Size", "id": "size"},
                        {"name": "📅 Modified", "id": "modified"},
                        {"name": "🔍 Status", "id": "status"}
                    ],
                    data=table_data,
                    style_cell={'textAlign': 'left'},
                    style_data_conditional=[
                        {
                            'if': {'filter_query': '{status} = Error'},
                            'backgroundColor': '#ffebee',
                            'color': 'black',
                        },
                        {
                            'if': {'filter_query': '{status} = Ready'},
                            'backgroundColor': '#e8f5e8',
                            'color': 'black',
                        }
                    ],
                    style_header={
                        'backgroundColor': '#f8f9fa',
                        'fontWeight': 'bold'
                    },
                    row_selectable='single',
                    selected_rows=[],
                    page_size=10
                ),
                html.P(f"Found {len(raw_files)} raw file(s)", className="text-muted mt-2")
            ])
        
        except Exception as e:
            return html.Div([
                html.P(f"Error loading raw files: {str(e)}", className="text-danger"),
                html.P("Please check that the data/raw/ directory exists", className="text-muted")
            ])

    @app.callback(
        [Output('tagging-interface', 'children'),
         Output('dataframe-store', 'data'),
         Output('tags-config-store', 'data'),
         Output('vendor-tags-config-store', 'data'),
         Output('current-filename-store', 'data'),
         Output('selected-vendors-store', 'data', allow_duplicate=True)],
        [Input('raw-files-table', 'selected_rows'),
         Input('raw-files-table', 'data')],
        prevent_initial_call='initial_duplicate'
    )
    def update_tagging_interface(selected_rows, table_data):
        """Update tagging interface when a file is selected"""
        if not selected_rows or not table_data:
            return html.Div(), None, None, None, None, []
        
        # Get selected file
        selected_file = table_data[selected_rows[0]]
        filename = selected_file['filename']
        
        try:
            # Preprocess the selected file
            expenses_df, summary_info, untagged_summary = preprocess_raw_file(filename)
            
            # Load tagging configurations
            tags, vendor_tags = load_tagging_configs()
            
            # Convert DataFrame to dict for storage
            df_dict = expenses_df.to_dict('records')
            
            # Create summary display
            summary_display = html.Div([
                html.Hr(),
                html.H4(f"📊 File Analysis: {filename}", className="text-primary mb-3"),
                
                # Summary statistics
                html.Div([
                    html.H5("📈 Summary Statistics", className="text-secondary mb-2"),
                    html.Div([
                        html.Div([
                            html.P(f"📄 Total transactions: {summary_info['total_transactions']}", className="mb-1"),
                            html.P(f"💸 Total expenses: {summary_info['total_expenses']}", className="mb-1"),
                            html.P(f"💰 Total amount: {summary_info['total_amount']:.2f}€", className="mb-1")
                        ], className="col-md-6"),
                        html.Div([
                            html.P(f"🏪 Vendors to tag: {summary_info['untagged_vendors']}", className="mb-1"),
                            html.P(f"🟢 Known vendors: {summary_info['known_vendors']}", className="mb-1"),
                            html.P(f"❓ Unknown vendors: {summary_info['unknown_vendors']}", className="mb-1")
                        ], className="col-md-6")
                    ], className="row")
                ], className="p-3 border rounded mb-3", style={'background-color': '#f8f9fa'}),
                
                # Interactive tagging interface
                create_interactive_tagging_layout()
            ])
            
            return summary_display, df_dict, tags, vendor_tags, filename, []
            
        except Exception as e:
            return html.Div([
                html.P(f"Error processing file: {str(e)}", className="text-danger"),
                html.P("Please check that the file is a valid CSV file", className="text-muted")
            ]), None, None, None, None, []

    @app.callback(
        Output('tagging-progress', 'children'),
        [Input('dataframe-store', 'data')]
    )
    def update_tagging_progress(df_data):
        """Update tagging progress display"""
        if not df_data:
            return []
        
        # Restore DataFrame from store
        df = restore_dataframe_from_store(df_data)
        
        # Get progress information
        progress_info = get_tagging_progress(df)
        
        # Calculate progress percentage
        progress_percentage = progress_info['progress_percentage']
        
        # Create progress bar
        progress_bar = html.Div([
            html.Div([
                html.H5("📊 Tagging Progress", className="text-primary mb-3"),
                html.Div([
                    html.Div([
                        html.Div(
                            className="progress-bar",
                            style={
                                'width': f"{progress_percentage:.1f}%",
                                'background': 'linear-gradient(90deg, #4CAF50, #45a049)',
                                'height': '100%',
                                'border-radius': '10px',
                                'transition': 'width 0.6s ease'
                            }
                        )
                    ], className="progress", style={'height': '20px', 'border-radius': '10px', 'background-color': '#f0f0f0'}),
                    html.P(f"{progress_percentage:.1f}% Complete", className="text-center mt-2 mb-0")
                ]),
                html.Div([
                    html.P(f"📝 Tagged: {progress_info['tagged_transactions']}/{progress_info['total_transactions']} transactions", 
                           className="mb-1"),
                    html.P(f"⏳ Remaining: {progress_info['untagged_transactions']} transactions", 
                           className="mb-1")
                ], className="mt-3")
            ], className="p-3 border rounded", style={'background-color': '#f8f9fa'})
        ])
        
        return progress_bar

    @app.callback(
        Output('vendor-cards-container', 'children', allow_duplicate=True),
        [Input('dataframe-store', 'data'),
         Input('vendor-tags-config-store', 'data'),
         Input('selected-vendors-store', 'data')],
        prevent_initial_call='initial_duplicate'
    )
    def update_vendor_cards(df_data, vendor_tags, selected_vendors):
        """Create clickable vendor cards"""
        if not df_data or not vendor_tags:
            return []
        
        # Restore DataFrame from store
        df = restore_dataframe_from_store(df_data)
        
        # Get untagged vendors
        vendors_data = get_untagged_vendors_from_df(df, vendor_tags)
        
        if not vendors_data:
            return [html.P("No vendors to tag", className="text-muted")]
        
        if selected_vendors is None:
            selected_vendors = []
        
        # Create vendor cards
        vendor_cards = []
        for vendor_info in vendors_data:
            vendor_name = vendor_info['value']
            vendor_label = vendor_info['label']
            is_selected = vendor_name in selected_vendors
            
            # Card styling based on selection
            if is_selected:
                card_style = {
                    'border': '2px solid #007bff',
                    'border-radius': '8px',
                    'background-color': '#e7f3ff',
                    'transition': 'all 0.2s ease',
                    'cursor': 'pointer',
                    'transform': 'scale(1.02)'
                }
                card_class = "card mb-2 vendor-card selected"
            else:
                card_style = {
                    'border': '1px solid #dee2e6',
                    'border-radius': '8px',
                    'transition': 'all 0.2s ease',
                    'cursor': 'pointer'
                }
                card_class = "card mb-2 vendor-card"
            
            card_content = html.Div([
                html.Div([
                    html.H6(vendor_label, className="mb-0")
                ], className="card-body p-2")
            ], 
            id={'type': 'vendor-card', 'index': vendor_name}, 
            className=card_class,
            style=card_style)
            
            vendor_cards.append(card_content)
        
        return vendor_cards

    @app.callback(
        Output('selected-vendors-store', 'data'),
        [Input({'type': 'vendor-card', 'index': ALL}, 'n_clicks')],
        [State('selected-vendors-store', 'data'),
         State({'type': 'vendor-card', 'index': ALL}, 'id')],
        prevent_initial_call=True
    )
    def handle_vendor_selection(n_clicks_list, selected_vendors, card_ids):
        """Handle vendor card clicks to toggle selection"""
        # Condition renforcée : ne s'exécute que si un bouton a été cliqué (n_clicks > 0)
        if not ctx.triggered or not any(n_clicks > 0 for n_clicks in n_clicks_list if n_clicks is not None):
            raise PreventUpdate
        
        # Find which card was clicked
        triggered_id = ctx.triggered[0]['prop_id']
        
        # Extract vendor name from the triggered prop_id
        if '"type":"vendor-card"' in triggered_id:
            # Parse the vendor name from the triggered prop_id
            import re
            match = re.search(r'"index":"([^"]*)"', triggered_id)
            if match:
                clicked_vendor = match.group(1)
                
                if selected_vendors is None:
                    selected_vendors = []
                
                # Toggle vendor selection
                if clicked_vendor in selected_vendors:
                    # Remove vendor if already selected
                    selected_vendors.remove(clicked_vendor)
                else:
                    # Add vendor if not selected
                    selected_vendors.append(clicked_vendor)
                
                return selected_vendors
        
        raise PreventUpdate


    @app.callback(
        Output('transaction-details', 'children'),
        [Input('selected-vendors-store', 'data'),
         Input('dataframe-store', 'data')]
    )
    def update_transaction_details(selected_vendors, df_data):
        """Update transaction details display"""
        if not df_data:
            return []
        
        # Vérifier explicitement si des vendeurs sont sélectionnés
        if not selected_vendors or len(selected_vendors) == 0:
            return html.P("Select vendors to see transaction details", className="text-muted")
        
        # Restore DataFrame from store
        df = restore_dataframe_from_store(df_data)
        
        # Get transaction details for selected vendors
        transaction_info = get_transaction_details_for_vendors(df, selected_vendors)
        
        if not transaction_info['transactions']:
            return html.P("Select vendors to see transaction details", className="text-muted")
        
        # Create transaction cards
        transaction_cards = []
        for idx, transaction in enumerate(transaction_info['transactions']):
            card_content = html.Div([
                html.Div([
                    # Contenu principal de la transaction
                    html.Div([
                        html.H6(f"🏪 {transaction['vendor']}", className="mb-1"),
                        html.P(f"💰 {transaction['display_amount']}", className="mb-1"),
                        html.P(f"📅 {transaction['display_date']}", className="mb-0 text-muted")
                    ], style={'flex': '1'}),
                    
                    # Icônes d'action (visibles uniquement si sélectionné)
                    html.Div([
                        dbc.Button(
                            "✏️", 
                            id={'type': 'edit-transaction-btn', 'index': transaction['id']},
                            size="sm", 
                            color="warning", 
                            outline=True,
                            className="me-1",
                            style={'display': 'none'}  # Caché par défaut
                        ),
                        dbc.Button(
                            "🗑️", 
                            id={'type': 'delete-transaction-btn', 'index': transaction['id']},
                            size="sm", 
                            color="danger", 
                            outline=True,
                            style={'display': 'none'}  # Caché par défaut
                        )
                    ], className="action-buttons", style={'display': 'flex', 'align-items': 'center'})
                ], className="card-body p-2 d-flex justify-content-between align-items-center")
            ], 
            id={'type': 'transaction-card', 'index': transaction['id']}, 
            className="card transaction-card mb-2 cursor-pointer",
            style={
                'border': '1px solid #dee2e6',
                'border-radius': '8px',
                'transition': 'all 0.2s ease',
                'cursor': 'pointer'
            })
            
            transaction_cards.append(card_content)
        
        return html.Div([
            html.H6(f"📋 Transaction Details ({len(transaction_info['transactions'])} transactions)", 
                   className="text-primary mb-3"),
            html.Div(transaction_cards, className="transaction-details-container")
        ])

    @app.callback(
        [Output('selected-transaction-store', 'data'),
         Output({'type': 'transaction-card', 'index': ALL}, 'style')],
        [Input({'type': 'transaction-card', 'index': ALL}, 'n_clicks')],
        [State('selected-transaction-store', 'data'),
         State({'type': 'transaction-card', 'index': ALL}, 'id')],
        prevent_initial_call=True
    )
    def handle_transaction_selection(n_clicks_list, selected_transaction, card_ids):
        """Handle transaction card selection"""
        if not ctx.triggered or not any(n_clicks > 0 for n_clicks in n_clicks_list if n_clicks is not None):
            raise PreventUpdate
        
        # Find which card was clicked
        triggered_id = ctx.triggered[0]['prop_id']
        
        # Extract transaction ID from the triggered prop_id
        if '"type":"transaction-card"' in triggered_id:
            # Parse the ID from the triggered prop_id
            import re
            match = re.search(r'"index":"([^"]*)"', triggered_id)
            if match:
                clicked_transaction_id = match.group(1)
                
                # Toggle selection
                if selected_transaction == clicked_transaction_id:
                    # Deselect if already selected
                    new_selected = None
                else:
                    # Select the clicked transaction
                    new_selected = clicked_transaction_id
                
                # Update card styles
                card_styles = []
                for card_id in card_ids:
                    transaction_id = card_id['index']
                    if transaction_id == new_selected:
                        # Selected style
                        style = {
                            'border': '2px solid #007bff',
                            'border-radius': '8px',
                            'background-color': '#e7f3ff',
                            'transition': 'all 0.2s ease',
                            'cursor': 'pointer',
                            'transform': 'scale(1.02)'
                        }
                    else:
                        # Default style
                        style = {
                            'border': '1px solid #dee2e6',
                            'border-radius': '8px',
                            'transition': 'all 0.2s ease',
                            'cursor': 'pointer'
                        }
                    card_styles.append(style)
                
                return new_selected, card_styles
        
        raise PreventUpdate

    @app.callback(
        Output('selected-tags-store', 'data'),
        [Input({'type': 'tag-badge', 'index': ALL}, 'n_clicks')],
        [State('selected-tags-store', 'data'),
         State({'type': 'tag-badge', 'index': ALL}, 'id')],
        prevent_initial_call=True
    )
    def handle_tag_selection(n_clicks_list, selected_tags, badge_ids):
        """Handle tag badge clicks to toggle selection"""
        if not ctx.triggered or not any(n_clicks > 0 for n_clicks in n_clicks_list if n_clicks is not None):
            raise PreventUpdate
        
        # Find which badge was clicked
        triggered_id = ctx.triggered[0]['prop_id']
        
        # Extract tag value from the triggered prop_id
        if '"type":"tag-badge"' in triggered_id:
            # Parse the tag value from the triggered prop_id
            import re
            match = re.search(r'"index":"([^"]*)"', triggered_id)
            if match:
                clicked_tag = match.group(1)
                
                # Toggle tag selection
                if clicked_tag in selected_tags:
                    # Remove tag if already selected
                    selected_tags.remove(clicked_tag)
                else:
                    # Add tag if not selected
                    selected_tags.append(clicked_tag)
                
                return selected_tags
        
        raise PreventUpdate

    @app.callback(
        Output('tag-cloud-container', 'children'),
        [Input('selected-transaction-store', 'data'),
         Input('selected-vendors-store', 'data'),
         Input('tags-config-store', 'data'),
         Input('vendor-tags-config-store', 'data'),
         Input('selected-tags-store', 'data')]
    )
    def update_tag_cloud(selected_transaction, selected_vendors, tags_config, vendor_tags_config, selected_tags):
        """Update tag cloud based on current selection"""
        if not tags_config or not vendor_tags_config:
            return [html.P("Loading tags...", className="text-muted")]
        
        # Get appropriate tags based on selection
        if selected_transaction or selected_vendors:
            # Get suggested tags based on vendors
            vendors = []
            if selected_transaction:
                # Individual transaction mode - we need the dataframe to extract vendor
                # For now, show all tags - this will be improved in the main callback
                vendors = []
            elif selected_vendors:
                vendors = selected_vendors
            
            from ..utilities.data_loader import get_suggested_tags_for_vendors
            suggested_tags = get_suggested_tags_for_vendors(vendors, tags_config, vendor_tags_config)
        else:
            # No selection - show all tags sorted by frequency
            all_tags = sorted(tags_config.items(), key=lambda x: x[1], reverse=True)
            suggested_tags = [{'label': tag, 'value': tag} for tag, _ in all_tags]
        
        return [create_tag_cloud(suggested_tags, selected_tags or [])]

    @app.callback(
        Output('tagging-panel-content', 'children'),
        [Input('selected-transaction-store', 'data'),
         Input('selected-vendors-store', 'data'),
         Input('dataframe-store', 'data'),
         Input('tags-config-store', 'data'),
         Input('vendor-tags-config-store', 'data')]
    )
    def update_tagging_panel(selected_transaction, selected_vendors, df_data, tags_config, vendor_tags_config):
        """Update tagging panel content based on selection mode"""
        if not df_data:
            return []
        
        # Restore DataFrame from store
        df = restore_dataframe_from_store(df_data)
        
        # Determine mode and create appropriate interface
        if selected_transaction:
            # Individual transaction tagging mode
            try:
                # Extract df_index from transaction_id
                df_index = int(selected_transaction.split('_')[1])
                transaction = df.loc[df_index]
                
                # Get suggested tags for this vendor
                vendor_name = transaction['Description']
                suggested_tags = get_suggested_tags_for_vendors([vendor_name], tags_config, vendor_tags_config)
                
                return html.Div([
                    html.H5("🎯 Tag Individual Transaction", className="text-primary mb-3"),
                    html.Div([
                        html.P(f"🏪 Vendor: {vendor_name}", className="mb-1"),
                        html.P(f"💰 Amount: {transaction['amount_abs']:.2f}€", className="mb-1"),
                        html.P(f"📅 Date: {pd.to_datetime(transaction['Date']).strftime('%Y-%m-%d')}", className="mb-3")
                    ], className="alert alert-info"),
                    
                    html.Div([
                        html.Label("🏷️ Select Tags:", className="form-label"),
                        html.Div(id='tag-cloud-container', children=[
                            create_tag_cloud(suggested_tags, [])
                        ])
                    ], className="mb-3"),
                    
                    html.Div([
                        html.Label("➕ Add New Tags:", className="form-label"),
                        dcc.Input(
                            id='new-tags-input',
                            type='text',
                            placeholder='Enter new tags (comma-separated)',
                            className='form-control'
                        )
                    ], className="mb-3"),
                    
                    html.Div([
                        dbc.Button(
                            "🏷️ Tag Transaction",
                            id='apply-tags-btn',
                            color='primary',
                            className='me-2'
                        ),
                        dbc.Button(
                            "🔄 Clear Selection",
                            id='clear-selection-btn',
                            color='secondary',
                            outline=True
                        )
                    ], className="d-flex gap-2")
                ])
            except (ValueError, KeyError, IndexError):
                return html.Div([
                    html.P("⚠️ Error: Invalid transaction selected", className="text-danger")
                ])
        
        elif selected_vendors:
            # Vendor-based tagging mode
            suggested_tags = get_suggested_tags_for_vendors(selected_vendors, tags_config, vendor_tags_config)
            
            return html.Div([
                html.H5("🏪 Tag All Vendor Transactions", className="text-primary mb-3"),
                html.Div([
                    html.P(f"📊 Selected Vendors: {len(selected_vendors)}", className="mb-1"),
                    html.Ul([html.Li(vendor) for vendor in selected_vendors], className="mb-2")
                ], className="alert alert-info"),
                
                html.Div([
                    html.Label("🏷️ Select Tags:", className="form-label"),
                    html.Div(id='tag-cloud-container', children=[
                        create_tag_cloud(suggested_tags, [])
                    ])
                ], className="mb-3"),
                
                html.Div([
                    html.Label("➕ Add New Tags:", className="form-label"),
                    dcc.Input(
                        id='new-tags-input',
                        type='text',
                        placeholder='Enter new tags (comma-separated)',
                        className='form-control'
                    )
                ], className="mb-3"),
                
                dbc.Button(
                    "🏷️ Tag All Transactions",
                    id='apply-tags-btn',
                    color='primary',
                    size='lg'
                )
            ])
        
        else:
            # No selection mode
            return html.Div([
                html.H5("🎯 Choose Tagging Mode", className="text-primary mb-3"),
                html.Div([
                    html.P("👆 Select vendors or click on individual transactions to start tagging", 
                           className="text-muted mb-2"),
                    html.Hr(),
                    html.H6("🏪 Vendor Mode:", className="text-secondary"),
                    html.P("• Select one or more vendors to tag ALL their transactions at once", 
                           className="text-muted mb-2"),
                    html.H6("🎯 Individual Mode:", className="text-secondary"),
                    html.P("• Click on a specific transaction card to tag just that transaction", 
                           className="text-muted mb-2")
                ], className="alert alert-light")
            ])

    @app.callback(
        Output('daily-context', 'children'),
        [Input('selected-transaction-store', 'data'),
         Input('dataframe-store', 'data')]
    )
    def update_daily_context(selected_transaction, df_data):
        """Update daily context display when a transaction is selected"""
        if not selected_transaction or not df_data:
            return []
        
        # Restore DataFrame from store
        df = restore_dataframe_from_store(df_data)
        
        # Get daily context
        daily_context = get_daily_context_for_transaction(df, selected_transaction)
        
        if not daily_context['transactions']:
            return []
        
        summary = daily_context['summary']
        
        # Create transaction cards for the day
        transaction_cards = []
        for transaction in daily_context['transactions']:
            # Determine card styling based on status
            if transaction['is_selected']:
                card_class = "card mb-2 border-primary"
                card_style = {'background-color': '#e7f3ff'}
                prefix = "👆 "
            elif transaction['has_tags']:
                card_class = "card mb-2 border-success"
                card_style = {'background-color': '#e8f5e8'}
                prefix = "✅ "
            else:
                card_class = "card mb-2 border-warning"
                card_style = {'background-color': '#fff3cd'}
                prefix = "⏳ "
            
            card = html.Div([
                html.Div([
                    html.H6(f"{prefix}{transaction['vendor']}", className="mb-1"),
                    html.P(f"💰 {transaction['display_amount']}", className="mb-1"),
                    html.P(f"🕐 {transaction['time']}", className="mb-1 text-muted"),
                    html.P(f"🏷️ {transaction['tags_display']}", className="mb-0 text-muted")
                ], className="card-body p-2")
            ], className=card_class, style=card_style)
            
            transaction_cards.append(card)
        
        return html.Div([
            html.H6(f"📅 Daily Context - {summary['date_display']}", className="text-primary mb-3"),
            html.Div([
                html.P(f"📊 Total: {summary['total_amount']:.2f}€ • {summary['total_transactions']} transactions", 
                       className="mb-1"),
                html.P(f"✅ Tagged: {summary['tagged_transactions']} • ⏳ Remaining: {summary['untagged_transactions']}", 
                       className="mb-3 text-muted")
            ], className="alert alert-info"),
            html.Div(transaction_cards, className="daily-context-container")
        ])

    @app.callback(
        [
            Output('dataframe-store', 'data', allow_duplicate=True),
            Output('tagging-feedback', 'children'),
            Output('selected-vendors-store', 'data', allow_duplicate=True),
            Output('selected-tags-store', 'data', allow_duplicate=True),
            Output('new-tags-input', 'value'),
            Output('save-file-btn', 'disabled'),
            Output('selected-transaction-store', 'data', allow_duplicate=True),
        ],
        [
            Input('apply-tags-btn', 'n_clicks'),
        ],
        [
            State('dataframe-store', 'data'),
            State('selected-vendors-store', 'data'),
            State('selected-tags-store', 'data'),
            State('new-tags-input', 'value'),
            State('tags-config-store', 'data'),
            State('vendor-tags-config-store', 'data'),
            State('selected-transaction-store', 'data'),
        ],
        prevent_initial_call=True
    )
    def apply_tags(n_clicks, df_data, selected_vendors, selected_tags, new_tags_input, tags_config, vendor_tags_config, selected_transaction):
        """Apply tags to selected vendors or individual transaction"""
        if not n_clicks or not df_data:
            raise PreventUpdate
        
        # Prevent accidental triggering from UI updates
        if not ctx.triggered:
            raise PreventUpdate
        
        # Check if the callback was triggered by a real button click
        triggered_id = ctx.triggered[0]['prop_id']
        if 'apply-tags-btn' not in triggered_id:
            raise PreventUpdate
        
        # Restore DataFrame from store
        df = restore_dataframe_from_store(df_data)
        
        # Process new tags input
        new_tags = []
        if new_tags_input and new_tags_input.strip():
            new_tags = [tag.strip() for tag in new_tags_input.split(',') if tag.strip()]
        
        # Apply tags based on mode
        if selected_transaction:
            # Individual transaction mode
            df_updated, affected_count = apply_tags_to_transaction(
                df, selected_transaction, selected_tags or [], new_tags
            )
            
            if affected_count > 0:
                # Extract vendor name for configuration update
                df_index = int(selected_transaction.split('_')[1])
                vendor_name = df.loc[df_index, 'Description']
                
                # Update configurations on disk
                all_tags = (selected_tags or []) + new_tags
                updated_tags, updated_vendor_tags = update_configurations_on_disk(all_tags, [vendor_name])
                
                feedback = dbc.Alert(
                    f"✅ Successfully tagged 1 transaction with {len(all_tags)} tag(s)",
                    color="success",
                    dismissable=True
                )
                
                # Clear selection after successful tagging
                selected_transaction = None
            else:
                feedback = dbc.Alert(
                    "⚠️ No transactions were tagged. Transaction may already be tagged.",
                    color="warning",
                    dismissable=True
                )
        
        elif selected_vendors:
            # Vendor-based mode
            df_updated, affected_count = apply_tags_to_vendors(
                df, selected_vendors, selected_tags or [], new_tags
            )
            
            if affected_count > 0:
                # Update configurations on disk
                all_tags = (selected_tags or []) + new_tags
                updated_tags, updated_vendor_tags = update_configurations_on_disk(all_tags, selected_vendors)
                
                feedback = dbc.Alert(
                    f"✅ Successfully tagged {affected_count} transaction(s) with {len(all_tags)} tag(s)",
                    color="success",
                    dismissable=True
                )
            else:
                feedback = dbc.Alert(
                    "⚠️ No transactions were tagged. They may already be tagged.",
                    color="warning",
                    dismissable=True
                )
        
        else:
            feedback = dbc.Alert(
                "⚠️ Please select vendors or a transaction before applying tags",
                color="warning",
                dismissable=True
            )
            df_updated = df
        
        # Convert updated DataFrame back to dict for storage
        df_dict = df_updated.to_dict('records')
        
        # Check if save button should be enabled
        progress_info = get_tagging_progress(df_updated)
        save_disabled = progress_info['tagged_transactions'] == 0
        
        return df_dict, feedback, [], [], '', save_disabled, selected_transaction

    @app.callback(
        [Output('save-file-btn', 'children'),
         Output('save-file-btn', 'color')],
        [Input('dataframe-store', 'data')]
    )
    def update_save_button(df_data):
        """Update save button appearance based on tagging progress"""
        if not df_data:
            return "💾 Save Tagged File", "secondary"
        
        # Restore DataFrame from store
        df = restore_dataframe_from_store(df_data)
        
        # Get progress information
        progress_info = get_tagging_progress(df)
        
        if progress_info['tagged_transactions'] == 0:
            return "💾 Save Tagged File", "secondary"
        elif progress_info['progress_percentage'] == 100:
            return f"🎉 Save Complete File ({progress_info['tagged_transactions']} tagged)", "success"
        else:
            return f"💾 Save Progress ({progress_info['tagged_transactions']} tagged)", "primary"

    @app.callback(
        [Output('tagging-feedback', 'children', allow_duplicate=True),
         Output('refresh-visualizations-store', 'data', allow_duplicate=True)],
        [Input('save-file-btn', 'n_clicks')],
        [State('dataframe-store', 'data'),
         State('current-filename-store', 'data'),
         State('refresh-visualizations-store', 'data')],
        prevent_initial_call=True
    )
    def save_tagged_file_callback(n_clicks, df_data, filename, current_refresh):
        """Save the tagged file to processed directory"""
        if not n_clicks or not df_data or not filename:
            raise PreventUpdate
        
        # Restore DataFrame from store
        df = restore_dataframe_from_store(df_data)
        
        # Get progress information
        progress_info = get_tagging_progress(df)
        
        if progress_info['tagged_transactions'] == 0:
            return dbc.Alert(
                "⚠️ No transactions have been tagged yet. Please tag some transactions before saving.",
                color="warning",
                dismissable=True
            ), current_refresh
        
        # Save the file
        success = save_tagged_file(df, filename)
        
        if success:
            # Increment refresh counter to trigger visualization updates
            new_refresh = current_refresh + 1
            return dbc.Alert([
                html.H5("🎉 File saved successfully!", className="mb-2"),
                html.P(f"📁 Saved to: data/processed/{filename}"),
                html.P(f"📊 Progress: {progress_info['tagged_transactions']}/{progress_info['total_transactions']} transactions tagged ({progress_info['progress_percentage']:.1f}%)")
            ], color="success", dismissable=True), new_refresh
        else:
            return dbc.Alert(
                "❌ Error saving file. Please check the file permissions and try again.",
                color="danger",
                dismissable=True
            ), current_refresh

    # Nouveaux callbacks pour l'édition et suppression des transactions
    
    @app.callback(
        [Output({'type': 'edit-transaction-btn', 'index': ALL}, 'style'),
         Output({'type': 'delete-transaction-btn', 'index': ALL}, 'style')],
        [Input('selected-transaction-store', 'data')],
        [State({'type': 'edit-transaction-btn', 'index': ALL}, 'id'),
         State({'type': 'delete-transaction-btn', 'index': ALL}, 'id')],
        prevent_initial_call=True
    )
    def toggle_action_buttons_visibility(selected_transaction, edit_btn_ids, delete_btn_ids):
        """Show/hide action buttons based on transaction selection"""
        edit_styles = []
        delete_styles = []
        
        for btn_id in edit_btn_ids:
            transaction_id = btn_id['index']
            if selected_transaction == transaction_id:
                # Montrer les boutons pour la transaction sélectionnée
                style = {'display': 'inline-block'}
            else:
                # Cacher les boutons pour les autres transactions
                style = {'display': 'none'}
            edit_styles.append(style)
        
        for btn_id in delete_btn_ids:
            transaction_id = btn_id['index']
            if selected_transaction == transaction_id:
                style = {'display': 'inline-block'}
            else:
                style = {'display': 'none'}
            delete_styles.append(style)
        
        return edit_styles, delete_styles

    @app.callback(
        [Output('edit-transaction-modal', 'is_open'),
         Output('edit-amount-input', 'value'),
         Output('edit-amount-feedback', 'children'),
         Output('selected-transaction-store', 'data', allow_duplicate=True)],
        [Input({'type': 'edit-transaction-btn', 'index': ALL}, 'n_clicks'),
         Input('cancel-edit-btn', 'n_clicks'),
         Input('confirm-edit-btn', 'n_clicks')],
        [State('dataframe-store', 'data'),
         State({'type': 'edit-transaction-btn', 'index': ALL}, 'id'),
         State('edit-amount-input', 'value'),
         State('selected-transaction-store', 'data')],
        prevent_initial_call=True
    )
    def handle_edit_modal(edit_clicks, cancel_clicks, confirm_clicks, df_data, btn_ids, new_amount, selected_transaction):
        """Handle edit modal opening, closing, and confirmation"""
        if not ctx.triggered:
            raise PreventUpdate
            
        triggered_id = ctx.triggered[0]['prop_id']
        
        # Ouvrir le modal quand un bouton d'édition est cliqué
        if '"type":"edit-transaction-btn"' in triggered_id and any(edit_clicks):
            if not df_data or not selected_transaction:
                raise PreventUpdate
            
            # Obtenir le montant actuel
            df_index = int(selected_transaction.split('_')[1])
            df = restore_dataframe_from_store(df_data)
            current_amount = abs(df.loc[df_index, 'Amount'])
            # Garder la transaction sélectionnée
            return True, current_amount, "", selected_transaction
        
        # Fermer le modal (annuler)
        elif 'cancel-edit-btn' in triggered_id:
            # Garder la transaction sélectionnée
            return False, None, "", selected_transaction
        
        # Confirmer l'édition
        elif 'confirm-edit-btn' in triggered_id:
            if not new_amount or new_amount <= 0:
                return True, new_amount, dbc.Alert("Le montant doit être positif", color="danger", dismissable=True), selected_transaction
            # Le modal se fermera et l'édition sera traitée par un autre callback
            # Garder la transaction sélectionnée
            return False, None, "", selected_transaction
        
        raise PreventUpdate

    @app.callback(
        [Output('dataframe-store', 'data', allow_duplicate=True),
         Output('tagging-feedback', 'children', allow_duplicate=True),
         Output('selected-transaction-store', 'data', allow_duplicate=True),
         Output('selected-vendors-store', 'data', allow_duplicate=True)],
        [Input('confirm-edit-btn', 'n_clicks')],
        [State('dataframe-store', 'data'),
         State('selected-transaction-store', 'data'),
         State('edit-amount-input', 'value'),
         State('selected-vendors-store', 'data')],
        prevent_initial_call=True
    )
    def confirm_edit_transaction(n_clicks, df_data, selected_transaction, new_amount, selected_vendors):
        """Confirm transaction amount edit"""
        if not n_clicks or not df_data or not selected_transaction or not new_amount:
            raise PreventUpdate
        
        if new_amount <= 0:
            raise PreventUpdate
            
        # Modifier le montant dans le DataFrame
        df_index = int(selected_transaction.split('_')[1])
        df = restore_dataframe_from_store(df_data)
        
        # Conserver le signe original (positif ou négatif)
        original_amount = df.loc[df_index, 'Amount']
        sign = 1 if original_amount >= 0 else -1
        df.at[df_index, 'Amount'] = sign * new_amount
        # Mettre à jour amount_abs pour l'affichage
        df.at[df_index, 'amount_abs'] = new_amount
        
        feedback = dbc.Alert(
            f"✏️ Montant modifié avec succès: {new_amount}€",
            color="success",
            dismissable=True
        )
        
        # Garder les vendeurs sélectionnés mais réinitialiser la transaction sélectionnée
        # pour forcer le rafraîchissement de l'affichage
        return prepare_dataframe_for_store(df), feedback, None, selected_vendors

    @app.callback(
        [Output('dataframe-store', 'data', allow_duplicate=True),
         Output('tagging-feedback', 'children', allow_duplicate=True),
         Output('selected-transaction-store', 'data', allow_duplicate=True),
         Output('selected-vendors-store', 'data', allow_duplicate=True)],
        [Input({'type': 'delete-transaction-btn', 'index': ALL}, 'n_clicks')],
        [State('dataframe-store', 'data'),
         State({'type': 'delete-transaction-btn', 'index': ALL}, 'id'),
         State('selected-vendors-store', 'data')],
        prevent_initial_call=True
    )
    def delete_transaction(n_clicks_list, df_data, btn_ids, selected_vendors):
        """Delete transaction when delete button is clicked"""
        if not any(n_clicks_list) or not df_data:
            raise PreventUpdate
        
        # Trouver quel bouton a été cliqué
        triggered_id = ctx.triggered[0]['prop_id']
        if '"type":"delete-transaction-btn"' in triggered_id:
            import re
            match = re.search(r'"index":"([^"]*)"', triggered_id)
            if match:
                transaction_id = match.group(1)
                df_index = int(transaction_id.split('_')[1])
                df = restore_dataframe_from_store(df_data)
                
                # Supprimer la transaction
                df = df.drop(index=df_index)
                
                feedback = dbc.Alert(
                    "🗑️ Transaction supprimée avec succès",
                    color="info",
                    dismissable=True
                )
                
                # Garder les vendeurs sélectionnés pour maintenir le contexte
                # mais forcer la mise à jour de l'affichage
                return prepare_dataframe_for_store(df), feedback, None, selected_vendors
        
        raise PreventUpdate 