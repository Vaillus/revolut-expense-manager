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
    apply_tags_to_transaction, apply_tags_to_transactions, get_daily_context_for_transaction,
    get_tagging_progress, save_tagged_file, update_configurations_on_disk,
    restore_dataframe_from_store, prepare_dataframe_for_store,
    remove_transactions_from_raw, get_remaining_raw_count,
    mark_month_as_completed, save_expenses,
    spread_transaction_over_months
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
            
            # Extract month from filename (assuming format: YYYY-MM.csv)
            month = filename.replace('.csv', '')
            
            # Add month column to expenses
            expenses_df['month'] = month
            
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
        
        # Calculate progress percentage (now based on amount)
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
                    html.P(f"💰 Tagged: {progress_info['tagged_amount']:.2f}€ / {progress_info['total_amount']:.2f}€ ({progress_info['tagged_transactions']}/{progress_info['total_transactions']} transactions)", 
                           className="mb-1"),
                    html.P(f"⏳ Remaining: {progress_info['untagged_amount']:.2f}€ ({progress_info['untagged_transactions']} transactions)", 
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
        [Output('selected-vendors-store', 'data'),
         Output('selected-transaction-store', 'data', allow_duplicate=True),
         Output('selected-tags-store', 'data', allow_duplicate=True),
         Output({'type': 'vendor-card', 'index': ALL}, 'style')],
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
                
                # Update card styles based on selection
                card_styles = []
                for card_id in card_ids:
                    vendor_name = card_id['index']
                    if vendor_name in selected_vendors:
                        style = {
                            'border': '2px solid #007bff',
                            'border-radius': '8px',
                            'background-color': '#e7f3ff',
                            'transition': 'all 0.2s ease',
                            'cursor': 'pointer',
                            'transform': 'scale(1.02)'
                        }
                    else:
                        style = {
                            'border': '1px solid #dee2e6',
                            'border-radius': '8px',
                            'transition': 'all 0.2s ease',
                            'cursor': 'pointer'
                        }
                    card_styles.append(style)
                
                # Reset selected transactions and tags when vendor selection changes
                return selected_vendors, [], [], card_styles
        
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
    def handle_transaction_selection(n_clicks_list, selected_transactions, card_ids):
        """Handle transaction card selection for multi-selection"""
        if not ctx.triggered or not any(n_clicks > 0 for n_clicks in n_clicks_list if n_clicks is not None):
            raise PreventUpdate
        
        triggered_id = ctx.triggered[0]['prop_id']
        
        if '"type":"transaction-card"' in triggered_id:
            import re
            match = re.search(r'"index":"([^"]*)"', triggered_id)
            if match:
                clicked_transaction_id = match.group(1)
                
                if selected_transactions is None:
                    selected_transactions = []
                
                # Toggle selection
                if clicked_transaction_id in selected_transactions:
                    selected_transactions.remove(clicked_transaction_id)
                else:
                    selected_transactions.append(clicked_transaction_id)
                
                # Update card styles
                card_styles = []
                for card_id in card_ids:
                    transaction_id = card_id['index']
                    if transaction_id in selected_transactions:
                        style = {
                            'border': '2px solid #007bff', 'border-radius': '8px',
                            'background-color': '#e7f3ff', 'transition': 'all 0.2s ease',
                            'cursor': 'pointer', 'transform': 'scale(1.02)'
                        }
                    else:
                        style = {
                            'border': '1px solid #dee2e6', 'border-radius': '8px',
                            'transition': 'all 0.2s ease', 'cursor': 'pointer'
                        }
                    card_styles.append(style)
                
                return selected_transactions, card_styles
        
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
         Input('selected-tags-store', 'data')],
        [State('dataframe-store', 'data')]  # Add dataframe as state
    )
    def update_tag_cloud(selected_transactions, selected_vendors, tags_config, vendor_tags_config, selected_tags, df_data):
        """Update tag cloud based on current selection"""
        if not tags_config or not vendor_tags_config:
            return [html.P("Loading tags...", className="text-muted")]
        
        # Determine which vendors to use for suggestions
        vendors_for_suggestions = []
        if selected_transactions and df_data:
            # Mode 1: One or more transactions are selected
            df = restore_dataframe_from_store(df_data)
            vendors = set()
            for trans_id in selected_transactions:
                try:
                    trans_index = int(trans_id.split('_')[1])
                    if trans_index in df.index:
                        vendor = df.loc[trans_index, 'Description']
                        vendors.add(vendor)
                except (ValueError, IndexError, KeyError):
                    continue
            vendors_for_suggestions = list(vendors)
        elif selected_vendors:
            # Mode 2: One or more vendors are selected
            vendors_for_suggestions = selected_vendors

        # Get suggested tags based on the determined vendors
        from ..utilities.data_loader import get_suggested_tags_for_vendors
        suggested_tags = get_suggested_tags_for_vendors(
            vendors_for_suggestions, tags_config, vendor_tags_config
        )
        
        return [create_tag_cloud(suggested_tags, selected_tags or [])]

    @app.callback(
        Output('tagging-panel-content', 'children'),
        [Input('selected-transaction-store', 'data'),
         Input('selected-vendors-store', 'data')]
    )
    def update_tagging_panel(selected_transactions, selected_vendors):
        """Update tagging panel based on selection."""
        # This panel is active if vendors or transactions are selected
        if selected_vendors or selected_transactions:
            return html.Div([
                html.Div(id='tag-cloud-container', className="mb-3"),
                dbc.Input(id='new-tags-input', placeholder='Enter new tags, comma-separated...', className="mb-3"),
                dbc.Button("Apply Tags", id='apply-tags-btn', color="primary", className="w-100")
            ])
        
        # Default view when nothing is selected
        return html.Div([
            html.I(className="fas fa-hand-pointer fa-2x text-muted"),
            html.P("Select vendors or transactions to start tagging", className="text-muted mt-2 mb-0")
        ], className="text-center py-4")


    @app.callback(
        Output('daily-context', 'children'),
        [Input('selected-transaction-store', 'data'),
         Input('dataframe-store', 'data')]
    )
    def update_daily_context(selected_transactions, df_data):
        """Update daily context display."""
        # Daily context is only shown for a single selected transaction
        if df_data and selected_transactions and len(selected_transactions) == 1:
            df = restore_dataframe_from_store(df_data)
            transaction_id = selected_transactions[0]  # Get the single ID from the list
            daily_context_data = get_daily_context_for_transaction(df, transaction_id)
            
            if not daily_context_data['transactions']:
                return html.P("No other transactions on this day.", className="text-muted")
            
            # Create a list of transactions for display
            transaction_list = []
            for trans in daily_context_data['transactions']:
                style = {'font-weight': 'bold', 'color': '#007bff'} if trans['is_selected'] else {}
                transaction_list.append(html.Div([
                    html.Span(f"{trans['time']} - {trans['vendor']} - {trans['display_amount']}", style=style),
                    dbc.Badge(trans['tags_display'], color="info", pill=True, className="ms-2") if trans['has_tags'] else None
                ], className="d-flex justify-content-between align-items-center mb-1"))

            return html.Div([
                html.H6(f"Transactions for {daily_context_data['summary']['date_display']}", className="mb-2"),
                html.P(f"Total: {daily_context_data['summary']['total_amount']:.2f}€ over {daily_context_data['summary']['total_transactions']} transactions", className="text-muted small"),
                *transaction_list
            ])
        
        # Default view
        return html.P("Select a single transaction to see daily context", className="text-muted mb-0")

    @app.callback(
        [
            Output('dataframe-store', 'data', allow_duplicate=True),
            Output('tagging-feedback', 'children', allow_duplicate=True),
            Output('selected-vendors-store', 'data', allow_duplicate=True),
            Output('selected-tags-store', 'data', allow_duplicate=True),
            Output('new-tags-input', 'value'),
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
    def apply_tags(n_clicks, df_data, selected_vendors, selected_tags, new_tags_input, tags_config, vendor_tags_config, selected_transactions):
        
        if not n_clicks:
            raise PreventUpdate
            
        from dash import no_update
        df = restore_dataframe_from_store(df_data)

        # Prepare tags
        new_tags = []
        if new_tags_input:
            new_tags = [tag.strip() for tag in new_tags_input.split(',') if tag.strip()]
        
        all_tags = (selected_tags or []) + new_tags
        if not all_tags:
            return no_update, dbc.Alert("No tags selected or entered.", color="warning"), no_update, no_update, "", no_update

        # Determine mode: multi-transaction or vendor-based
        if selected_transactions:
            # --- Multi-transaction Tagging ---
            df_updated, affected_count, tagged_vendors = apply_tags_to_transactions(
                df, selected_transactions, all_tags
            )
            
            if affected_count > 0:
                update_configurations_on_disk(all_tags, list(tagged_vendors))
                feedback = dbc.Alert(f"✅ Successfully tagged {affected_count} transaction(s).", color="success")
                return df_updated.to_dict('records'), feedback, no_update, [], "", []
            else:
                feedback = dbc.Alert("⚠️ No transactions were tagged (they may already be tagged).", color="warning")
                return no_update, feedback, no_update, no_update, no_update, no_update
        
        elif selected_vendors:
            # --- Vendor-based Tagging ---
            df_updated, affected_count = apply_tags_to_vendors(df, selected_vendors, selected_tags or [], new_tags)
            
            if affected_count > 0:
                update_configurations_on_disk(all_tags, selected_vendors)
                feedback = dbc.Alert(f"✅ Successfully tagged {affected_count} transactions for {len(selected_vendors)} vendor(s).", color="success")
                return df_updated.to_dict('records'), feedback, [], [], "", []
            else:
                feedback = dbc.Alert("⚠️ No untagged transactions found for the selected vendor(s).", color="warning")
        
        else:
            feedback = dbc.Alert("Select vendors or transactions first.", color="info")

        # Fallback return for cases that don't update the dataframe
        return no_update, feedback, no_update, no_update, no_update, no_update

    @app.callback(
        [Output('save-file-btn', 'children'),
         Output('save-file-btn', 'color'),
         Output('save-file-btn', 'disabled'),
         Output('finish-month-btn', 'disabled')],
        [Input('dataframe-store', 'data')]
    )
    def update_save_button(df_data):
        """Update save button appearance based on tagging progress"""
        if not df_data:
            return "💾 Save Tagged File", "secondary", True, True
        
        # Restore DataFrame from store
        df = restore_dataframe_from_store(df_data)
        
        # Get progress information
        progress_info = get_tagging_progress(df)
        
        if progress_info['tagged_transactions'] == 0:
            return "💾 Save Tagged File", "secondary", True, False  # Enable finish month even if nothing tagged
        elif progress_info['progress_percentage'] == 100:
            return f"🎉 Save Complete File ({progress_info['tagged_transactions']} tagged)", "success", False, False
        else:
            return f"💾 Save Progress ({progress_info['tagged_transactions']} tagged)", "primary", False, False

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
        """Save the tagged file to processed directory and remove saved transactions from raw"""
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
        
        # Filter only tagged transactions for saving
        tagged_mask = df["tags"].apply(lambda tags: len(tags) > 0)
        tagged_df = df[tagged_mask].copy()
        
        # Save only tagged transactions
        save_result = save_tagged_file(tagged_df, filename)
        
        if save_result['success']:
            # Remove saved transactions from raw file
            remove_success = remove_transactions_from_raw(filename, tagged_df)
            
            # Get remaining count
            remaining_count = get_remaining_raw_count(filename)
            
            # Increment refresh counter to trigger visualization updates
            new_refresh = current_refresh + 1
            
            # Build success message
            message_parts = [
                html.H5("✅ Progress saved successfully!", className="mb-2"),
                html.P(f"📊 Saved {save_result['saved_count']} tagged transactions to expenses.csv"),
            ]
            
            if remove_success:
                message_parts.append(html.P(f"🗑️ Removed saved transactions from raw file"))
            
            if remaining_count > 0:
                message_parts.append(html.P(f"⏳ {remaining_count} transactions remain to tag", className="text-info"))
            else:
                message_parts.append(html.P(f"🎉 All transactions processed! You can finish the month.", className="text-success"))
            
            return dbc.Alert(message_parts, color="success", dismissable=True), new_refresh
        else:
            return dbc.Alert(
                "❌ Error saving file. Please check the file permissions and try again.",
                color="danger",
                dismissable=True
            ), current_refresh

    @app.callback(
        [Output('tagging-feedback', 'children', allow_duplicate=True),
         Output('refresh-visualizations-store', 'data', allow_duplicate=True),
         Output('raw-files-list', 'children', allow_duplicate=True)],
        [Input('finish-month-btn', 'n_clicks')],
        [State('dataframe-store', 'data'),
         State('current-filename-store', 'data'),
         State('refresh-visualizations-store', 'data')],
        prevent_initial_call=True
    )
    def finish_month_callback(n_clicks, df_data, filename, current_refresh):
        """Finish month: save all remaining transactions and mark as completed"""
        if not n_clicks or not df_data or not filename:
            raise PreventUpdate
        
        # Restore DataFrame from store
        df = restore_dataframe_from_store(df_data)
        
        if df.empty:
            return dbc.Alert(
                "⚠️ No transactions to save.",
                color="warning",
                dismissable=True
            ), current_refresh, []
        
        # Extract month from filename
        month = filename.replace('.csv', '')
        
        # Save ALL transactions (tagged + untagged)
        # Ensure untagged transactions have empty tags list
        save_df = df.copy()
        save_df['tags'] = save_df['tags'].apply(lambda tags: tags if isinstance(tags, list) and len(tags) > 0 else [])
        
        # Save all transactions
        save_result = save_expenses(save_df, month=month)
        
        if not save_result['success']:
            return dbc.Alert(
                "❌ Error saving transactions. Please try again.",
                color="danger",
                dismissable=True
            ), current_refresh, []
        
        # Mark month as completed
        mark_success = mark_month_as_completed(month)
        
        # Remove all transactions from raw file (since we saved everything)
        remove_success = remove_transactions_from_raw(filename, save_df)
        
        # Increment refresh counter
        new_refresh = current_refresh + 1
        
        # Build success message
        message_parts = [
            html.H5("🎉 Month completed successfully!", className="mb-2"),
            html.P(f"✅ Saved {save_result['saved_count']} transactions to expenses.csv"),
        ]
        
        if mark_success:
            message_parts.append(html.P(f"📅 Month {month} marked as completed", className="text-success"))
        
        if remove_success:
            message_parts.append(html.P(f"🗑️ Raw file cleared"))
        
        # Refresh raw files list
        try:
            raw_files = get_raw_files()
            
            if not raw_files:
                raw_files_display = html.Div([
                    html.P("No raw files found in data/raw/ directory", className="text-muted"),
                    html.P("Place your Revolut CSV files in the data/raw/ folder to start tagging", 
                          className="text-info")
                ])
            else:
                # Create a table with file information
                table_data = []
                for file_info in raw_files:
                    size_mb = file_info['size'] / (1024 * 1024)
                    size_str = f"{size_mb:.2f} MB"
                    mod_date = datetime.fromtimestamp(file_info['modified']).strftime('%Y-%m-%d %H:%M')
                    
                    table_data.append({
                        'filename': file_info['filename'],
                        'rows': file_info['num_rows'] if file_info['readable'] else 'Error',
                        'size': size_str,
                        'modified': mod_date,
                        'status': 'Ready' if file_info['readable'] else 'Error'
                    })
                
                from dash import dash_table
                raw_files_display = html.Div([
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
            raw_files_display = html.Div([
                html.P(f"Error loading raw files: {str(e)}", className="text-danger"),
                html.P("Please check that the data/raw/ directory exists", className="text-muted")
            ])
        
        return dbc.Alert(message_parts, color="success", dismissable=True), new_refresh, raw_files_display

    # Callbacks for spread functionality
    
    @app.callback(
        Output('spread-options-div', 'style'),
        [Input('spread-months-checkbox', 'value')]
    )
    def toggle_spread_options(is_checked):
        """Show/hide spread options based on checkbox"""
        if is_checked:
            return {'display': 'block'}
        return {'display': 'none'}

    @app.callback(
        [Output('spread-start-month', 'options'),
         Output('spread-start-month', 'value', allow_duplicate=True),
         Output('spread-end-month', 'options')],
        [Input('edit-transaction-modal', 'is_open')],
        [State('dataframe-store', 'data'),
         State('selected-transaction-store', 'data')],
        prevent_initial_call=True
    )
    def populate_month_selectors(is_open, df_data, selected_transactions):
        """Populate month dropdowns with transaction's month as default"""
        if not is_open or not selected_transactions or not df_data:
            return [], None, []
        
        try:
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            
            # Get transaction date
            df = restore_dataframe_from_store(df_data)
            trans_id = selected_transactions[0]
            df_index = int(trans_id.split('_')[1])
            trans_date = pd.to_datetime(df.loc[df_index, 'Date'])
            trans_month = trans_date.strftime('%Y-%m')
            
            # Generate month options (6 months before to 12 months after)
            months = []
            current = trans_date - relativedelta(months=6)
            for i in range(24):  # 6 before + current + 12 after
                month_str = current.strftime('%Y-%m')
                months.append({'label': month_str, 'value': month_str})
                current += relativedelta(months=1)
            
            return months, trans_month, months
        except Exception as e:
            print(f"Error populating month selectors: {e}")
            return [], None, []

    @app.callback(
        Output('spread-preview', 'children'),
        [Input('spread-start-month', 'value'),
         Input('spread-end-month', 'value'),
         Input('edit-amount-input', 'value')]
    )
    def update_spread_preview(start_month, end_month, amount):
        """Show preview: 'N months × X€ = Y€'"""
        if not start_month or not end_month:
            return "Sélectionnez les mois de début et de fin"
        
        if not amount or amount <= 0:
            return "Entrez un montant valide"
        
        try:
            from datetime import datetime
            from dateutil.relativedelta import relativedelta
            
            start = datetime.strptime(start_month, '%Y-%m')
            end = datetime.strptime(end_month, '%Y-%m')
            
            if end < start:
                return html.Span(
                    "⚠️ Le mois de fin doit être après ou égal au mois de début",
                    className="text-danger"
                )
            
            # Calculate months
            months = []
            current = start
            while current <= end:
                months.append(current.strftime('%Y-%m'))
                current += relativedelta(months=1)
            
            num_months = len(months)
            monthly_amount = amount / num_months
            
            return [
                html.P([
                    html.Strong(f"{num_months} mois"),
                    f" × {monthly_amount:.2f}€ = {amount:.2f}€"
                ], className="mb-0")
            ]
        except Exception as e:
            return html.Span(f"Erreur: {str(e)}", className="text-danger")

    # Nouveaux callbacks pour l'édition et suppression des transactions
    
    @app.callback(
        [Output({'type': 'edit-transaction-btn', 'index': ALL}, 'style'),
         Output({'type': 'delete-transaction-btn', 'index': ALL}, 'style')],
        [Input('selected-transaction-store', 'data')],
        [State({'type': 'edit-transaction-btn', 'index': ALL}, 'id'),
         State({'type': 'delete-transaction-btn', 'index': ALL}, 'id')],
        prevent_initial_call=True
    )
    def toggle_action_buttons_visibility(selected_transactions, edit_btn_ids, delete_btn_ids):
        """Show/hide action buttons based on transaction selection"""
        # Buttons are only shown when exactly one transaction is selected
        show_buttons = selected_transactions is not None and len(selected_transactions) == 1
        
        edit_styles = []
        delete_styles = []
        
        single_selected_id = selected_transactions[0] if show_buttons else None
        
        for btn_id in edit_btn_ids:
            # Show button only if it corresponds to the single selected transaction
            if show_buttons and btn_id['index'] == single_selected_id:
                style = {'display': 'inline-block'}
            else:
                style = {'display': 'none'}
            edit_styles.append(style)
        
        for btn_id in delete_btn_ids:
            if show_buttons and btn_id['index'] == single_selected_id:
                style = {'display': 'inline-block'}
            else:
                style = {'display': 'none'}
            delete_styles.append(style)
        
        return edit_styles, delete_styles

    @app.callback(
        [Output('edit-transaction-modal', 'is_open'),
         Output('edit-amount-input', 'value'),
         Output('edit-amount-feedback', 'children'),
         Output('selected-transaction-store', 'data', allow_duplicate=True),
         Output('spread-months-checkbox', 'value'),
         Output('spread-start-month', 'value'),
         Output('spread-end-month', 'value')],
        [Input({'type': 'edit-transaction-btn', 'index': ALL}, 'n_clicks'),
         Input('cancel-edit-btn', 'n_clicks'),
         Input('confirm-edit-btn', 'n_clicks')],
        [State('dataframe-store', 'data'),
         State({'type': 'edit-transaction-btn', 'index': ALL}, 'id'),
         State('edit-amount-input', 'value'),
         State('selected-transaction-store', 'data')],
        prevent_initial_call=True
    )
    def handle_edit_modal(edit_clicks, cancel_clicks, confirm_clicks, df_data, btn_ids, new_amount, selected_transactions):
        """Handle edit modal opening, closing, and confirmation"""
        if not ctx.triggered:
            raise PreventUpdate
            
        triggered_id = ctx.triggered[0]['prop_id']
        
        # Ouvrir le modal quand un bouton d'édition est cliqué
        if '"type":"edit-transaction-btn"' in triggered_id and any(edit_clicks):
            # Ensure only one transaction is selected for editing
            if not df_data or not selected_transactions or len(selected_transactions) != 1:
                raise PreventUpdate
            
            # Obtenir le montant actuel
            single_transaction_id = selected_transactions[0]
            df_index = int(single_transaction_id.split('_')[1])
            df = restore_dataframe_from_store(df_data)
            current_amount = abs(df.loc[df_index, 'Amount'])
            
            # Get transaction date for default month
            trans_date = pd.to_datetime(df.loc[df_index, 'Date'])
            trans_month = trans_date.strftime('%Y-%m')
            
            # Garder la transaction sélectionnée, reset spread fields
            return True, current_amount, "", selected_transactions, False, trans_month, trans_month
        
        # Fermer le modal (annuler)
        elif 'cancel-edit-btn' in triggered_id:
            # Garder la transaction sélectionnée, reset spread fields
            return False, None, "", selected_transactions, False, None, None
        
        # Confirmer l'édition
        elif 'confirm-edit-btn' in triggered_id:
            if not new_amount or new_amount <= 0:
                return True, new_amount, dbc.Alert("Le montant doit être positif", color="danger", dismissable=True), selected_transactions, False, None, None
            # Le modal se fermera et l'édition sera traitée par un autre callback
            # Garder la transaction sélectionnée, reset spread fields
            return False, None, "", selected_transactions, False, None, None
        
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
         State('selected-vendors-store', 'data'),
         State('spread-months-checkbox', 'value'),
         State('spread-start-month', 'value'),
         State('spread-end-month', 'value')],
        prevent_initial_call=True
    )
    def confirm_edit_transaction(n_clicks, df_data, selected_transactions, new_amount, selected_vendors,
                                spread_enabled, start_month, end_month):
        """Confirm transaction edit (with optional spreading)"""
        # Ensure only one transaction is selected for editing
        if not n_clicks or not df_data or not selected_transactions or len(selected_transactions) != 1 or not new_amount:
            raise PreventUpdate
        
        if new_amount <= 0:
            raise PreventUpdate
        
        single_transaction_id = selected_transactions[0]
        df_index = int(single_transaction_id.split('_')[1])
        df = restore_dataframe_from_store(df_data)
        
        if spread_enabled and start_month and end_month:
            # SPREAD MODE: Create multiple transactions
            try:
                original_trans = df.loc[df_index].copy()
                # Restore sign for expenses (should be negative)
                original_amount = original_trans['Amount']
                sign = 1 if original_amount >= 0 else -1
                original_trans['Amount'] = sign * new_amount
                
                # Spread it
                new_transactions_df = spread_transaction_over_months(original_trans, start_month, end_month)
                
                # Remove original transaction from buffer
                df = df.drop(df_index).reset_index(drop=True)
                
                # Add new transactions to buffer
                df = pd.concat([df, new_transactions_df], ignore_index=True)
                
                # Recalculate derived columns
                df['amount_numeric'] = pd.to_numeric(df['Amount'], errors='coerce')
                df['amount_abs'] = df['amount_numeric'].abs()
                
                # Sort by date
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date').reset_index(drop=True)
                
                num_months = len(new_transactions_df)
                monthly_amount = new_amount / num_months
                
                feedback = dbc.Alert(
                    f"✅ Dépense étalée sur {num_months} mois ({monthly_amount:.2f}€ par mois)",
                    color="success",
                    dismissable=True
                )
            except Exception as e:
                feedback = dbc.Alert(
                    f"❌ Erreur lors de l'étalement: {str(e)}",
                    color="danger",
                    dismissable=True
                )
                return prepare_dataframe_for_store(df), feedback, selected_transactions, selected_vendors
        else:
            # SIMPLE EDIT MODE: Just change amount
            original_amount = df.loc[df_index, 'Amount']
            sign = 1 if original_amount >= 0 else -1
            df.at[df_index, 'Amount'] = sign * new_amount
            df.at[df_index, 'amount_abs'] = new_amount
            
            feedback = dbc.Alert(
                f"✏️ Montant modifié avec succès: {new_amount}€",
                color="success",
                dismissable=True
            )
        
        # Garder les vendeurs sélectionnés mais réinitialiser la transaction sélectionnée
        # pour forcer le rafraîchissement de l'affichage
        return prepare_dataframe_for_store(df), feedback, [], selected_vendors

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