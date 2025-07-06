"""
Dashboard callbacks and interactions
"""
import plotly.graph_objects as go
from dash import Input, Output, html, dash_table, State, callback_context, ALL, dcc
import pandas as pd
from datetime import datetime
import json
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate

from .layouts import create_categories_layout, create_timeseries_layout, create_tagging_layout, create_interactive_tagging_layout
from ..utilities.data_loader import (
    load_config, load_all_processed_data, get_main_category,
    get_subtags_for_category, get_monthly_trend, prepare_timeseries_data,
    get_raw_files, preprocess_raw_file, load_tagging_configs,
    get_untagged_vendors_from_df, get_suggested_tags_for_vendors,
    get_transaction_details_for_vendors, apply_tags_to_vendors,
    apply_tags_to_transaction, get_daily_context_for_transaction,
    get_tagging_progress, save_tagged_file, update_configurations_on_disk,
    restore_dataframe_from_store
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
        elif active_tab == 'tagging-tab':
            return create_tagging_layout()
        return html.Div("Tab not found")

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
         Output('current-filename-store', 'data')],
        [Input('raw-files-table', 'selected_rows'),
         Input('raw-files-table', 'data')]
    )
    def update_tagging_interface(selected_rows, table_data):
        """Update tagging interface when a file is selected"""
        if not selected_rows or not table_data:
            return html.Div(), None, None, None, None
        
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
            
            return summary_display, df_dict, tags, vendor_tags, filename
            
        except Exception as e:
            return html.Div([
                html.Hr(),
                html.H4("❌ Error Processing File", className="text-danger"),
                html.P(f"Error preprocessing {filename}: {str(e)}", className="text-danger"),
                html.P("Please check the file format and try again.", className="text-muted")
            ]), None, None, None, None

    @app.callback(
        Output('tagging-progress', 'children'),
        [Input('dataframe-store', 'data')]
    )
    def update_tagging_progress(df_data):
        """Update modern tagging progress display"""
        if not df_data:
            return html.Div()
        
        try:
            # Convert dict back to DataFrame with proper date handling
            df = restore_dataframe_from_store(df_data)
            
            # Get progress stats
            progress = get_tagging_progress(df)
            percentage = progress['progress_percentage']
            
            # Choose color based on progress
            if percentage < 30:
                color = "#dc3545"  # Red
            elif percentage < 70:
                color = "#ffc107"  # Yellow
            else:
                color = "#28a745"  # Green
            
            return html.Div([
                html.Div([
                    html.Div([
                        html.Span(f"📊 {progress['tagged_transactions']}/{progress['total_transactions']} tagged", className="fw-bold"),
                        html.Span(f"{percentage:.0f}%", className="fw-bold")
                    ], className="d-flex justify-content-between mb-2"),
                    
                    # Modern progress bar
                    dbc.Progress(
                        value=percentage,
                        color="success" if percentage >= 70 else "warning" if percentage >= 30 else "danger",
                        style={'height': '8px'},
                        className="mb-2"
                    ),
                    
                    html.P(f"🎯 {progress['untagged_transactions']} transactions remaining", 
                          className="mb-0 small")
                ])
            ])
            
        except Exception as e:
            return html.P(f"Error: {str(e)}", className="text-danger small")

    @app.callback(
        Output('vendor-select', 'options'),
        [Input('dataframe-store', 'data'),
         Input('vendor-tags-config-store', 'data')]
    )
    def update_vendor_options(df_data, vendor_tags):
        """Update vendor dropdown options"""
        if not df_data or not vendor_tags:
            return []
        
        try:
            # Convert dict back to DataFrame with proper date handling
            df = restore_dataframe_from_store(df_data)
            
            # Get untagged vendors
            vendors_options = get_untagged_vendors_from_df(df, vendor_tags)
            
            return vendors_options
            
        except Exception as e:
            print(f"Error updating vendor options: {e}")
            return []

    @app.callback(
        Output('tag-select', 'options'),
        [Input('vendor-select', 'value'),
         Input('tags-config-store', 'data'),
         Input('vendor-tags-config-store', 'data')]
    )
    def update_tag_options(selected_vendors, tags, vendor_tags):
        """Update tag dropdown options based on selected vendors"""
        if not tags:
            return []
        
        try:
            selected_vendors = selected_vendors or []
            vendor_tags = vendor_tags or {}
            
            # Get suggested tags for selected vendors
            tag_options = get_suggested_tags_for_vendors(selected_vendors, tags, vendor_tags)
            
            return tag_options
            
        except Exception as e:
            print(f"Error updating tag options: {e}")
            return []

    @app.callback(
        Output('transaction-details', 'children'),
        [Input('vendor-select', 'value'),
         Input('dataframe-store', 'data')]
    )
    def update_transaction_details(selected_vendors, df_data):
        """Update transaction details for selected vendors - chronological view"""
        if not selected_vendors or not df_data:
            return html.P("Select vendors to see transaction details", className="text-muted")
        
        try:
            # Convert dict back to DataFrame with proper date handling
            df = restore_dataframe_from_store(df_data)
            
            # Get transaction details
            details = get_transaction_details_for_vendors(df, selected_vendors)
            
            if not details['transactions']:
                return html.P("No untagged transactions found for selected vendors", className="text-muted")
            
            # Create chronological display with selectable transactions
            transactions_display = []
            
            # Add header
            transactions_display.append(html.H6("📅 Transactions (chronological)", className="text-primary mb-3"))
            
            # Create selectable transaction list
            for trans in details['transactions']:
                transaction_card = html.Div([
                    html.Div([
                        # Transaction details
                        html.Div([
                            html.Strong(f"🏪 {trans['vendor']}", className="text-primary"),
                            html.Span(f" • {trans['display_amount']}", className="ms-2 text-success fw-bold"),
                            html.Span(f" • {trans['display_date']}", className="ms-2 text-muted")
                        ], className="transaction-content"),
                        
                        # Selection indicator (will be used later)
                        html.Div([
                            html.I(className="fas fa-circle-o", style={'color': '#6c757d'})
                        ], className="selection-indicator")
                    ], className="d-flex justify-content-between align-items-center p-2 border rounded mb-2",
                       style={
                           'cursor': 'pointer',
                           'transition': 'all 0.2s ease',
                           'backgroundColor': '#f8f9fa'
                       },
                       id={'type': 'transaction-card', 'index': trans['id']})
                ])
                transactions_display.append(transaction_card)
            
            # Add summary at the end
            total_amount = sum(trans['amount'] for trans in details['transactions'])
            total_count = len(details['transactions'])
            
            transactions_display.append(html.Div([
                html.Hr(),
                html.P(f"📊 Total: {total_amount:.2f}€ ({total_count} transactions)", 
                      className="text-muted mb-0")
            ], className="mt-3"))
            
            return html.Div(transactions_display)
            
        except Exception as e:
            return html.P(f"Error loading transaction details: {str(e)}", className="text-danger")

    @app.callback(
        [Output('selected-transaction-store', 'data'),
         Output({'type': 'transaction-card', 'index': ALL}, 'style')],
        [Input({'type': 'transaction-card', 'index': ALL}, 'n_clicks')],
        [State('selected-transaction-store', 'data'),
         State({'type': 'transaction-card', 'index': ALL}, 'id')],
        prevent_initial_call=True
    )
    def handle_transaction_selection(n_clicks_list, selected_transaction, card_ids):
        """Handle selection of individual transactions"""
        if not any(n_clicks_list) or not card_ids:
            return selected_transaction, [{}] * len(card_ids)
        
        # Use callback context to determine which button was clicked
        ctx = callback_context
        if not ctx.triggered:
            return selected_transaction, [{}] * len(card_ids)
        
        # Get the ID of the clicked element
        clicked_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        # Parse the clicked transaction ID
        import json
        try:
            clicked_card_id = json.loads(clicked_id)
            transaction_id = clicked_card_id['index']
        except:
            return selected_transaction, [{}] * len(card_ids)
        
        # Update selected transaction (toggle if same, otherwise select new)
        new_selected = transaction_id if selected_transaction != transaction_id else None
        
        # Update styles
        styles = []
        for card_id in card_ids:
            if card_id['index'] == new_selected:
                # Selected style
                styles.append({
                    'cursor': 'pointer',
                    'transition': 'all 0.2s ease',
                    'backgroundColor': '#e3f2fd',
                    'border': '2px solid #2196f3',
                    'boxShadow': '0 2px 4px rgba(33, 150, 243, 0.2)'
                })
            else:
                # Default style
                styles.append({
                    'cursor': 'pointer',
                    'transition': 'all 0.2s ease',
                    'backgroundColor': '#f8f9fa'
                })
        
        return new_selected, styles

    @app.callback(
        Output('tagging-panel-content', 'children'),
        [Input('selected-transaction-store', 'data'),
         Input('vendor-select', 'value'),
         Input('dataframe-store', 'data'),
         Input('tags-config-store', 'data'),
         Input('vendor-tags-config-store', 'data')]
    )
    def update_tagging_panel(selected_transaction, selected_vendors, df_data, tags_config, vendor_tags_config):
        """Update the tagging panel for both transaction and vendor tagging"""
        if not df_data:
            return html.Div([
                html.Div([
                    html.I(className="fas fa-hand-pointer fa-2x text-muted"),
                    html.P("Select vendors or a transaction to start tagging", className="text-muted mt-2 mb-0")
                ], className="text-center py-4")
            ])
        
        try:
            # Convert dict back to DataFrame with proper date handling
            df = restore_dataframe_from_store(df_data)
            tags = tags_config or {}
            vendor_tags = vendor_tags_config or {}
            
            # Determine tagging mode and get vendor(s)
            if selected_transaction:
                # Individual transaction tagging
                df_index = int(selected_transaction.split('_')[1])
                if df_index not in df.index:
                    return html.P("Transaction not found", className="text-danger")
                
                transaction = df.loc[df_index]
                vendor = transaction['Description']
                amount = transaction['amount_abs']
                date = pd.to_datetime(transaction['Date']).strftime('%Y-%m-%d')
                
                # Get suggested tags for this vendor
                suggested_tags = []
                if vendor in vendor_tags:
                    suggested_tags = [{'label': f"⭐ {tag}", 'value': tag} for tag in vendor_tags[vendor].keys()]
                
                other_tags = [{'label': tag, 'value': tag} for tag in tags.keys() if tag not in [t['value'] for t in suggested_tags]]
                other_tags.sort(key=lambda x: tags.get(x['value'], 0), reverse=True)
                
                all_tag_options = suggested_tags + other_tags
                
                # Transaction info and tagging interface
                return html.Div([
                    dbc.Alert([
                        html.H6(f"📋 Selected Transaction", className="mb-2"),
                        html.P([
                            html.Strong(f"🏪 {vendor}"),
                            html.Br(),
                            f"💰 {amount:.2f}€ • 📅 {date}"
                        ], className="mb-0")
                    ], color="info", className="mb-3"),
                    
                    html.Div([
                        html.Label("🏷️ Select Tags:", className="form-label fw-bold"),
                        html.P("⭐ = suggested for this vendor", className="text-muted small mb-2"),
                        dcc.Dropdown(
                            id='tag-select',
                            multi=True,
                            placeholder="Choose existing tags...",
                            options=all_tag_options,
                            style={'marginBottom': '15px'}
                        )
                    ]),
                    
                    html.Div([
                        html.Label("➕ Add New Tags:", className="form-label fw-bold"),
                        dcc.Input(
                            id='new-tags-input',
                            type='text',
                            placeholder="Enter new tags separated by commas",
                            className="form-control mb-3"
                        )
                    ]),
                    
                    html.Div([
                        dbc.Button(
                            "🏷️ Apply Tags to This Transaction",
                            id='apply-tags-btn',
                            color="success",
                            size="lg",
                            className="w-100"
                        )
                    ], className="d-grid")
                ])
                
            elif selected_vendors:
                # Vendor-based tagging
                vendor_list = selected_vendors if isinstance(selected_vendors, list) else [selected_vendors]
                
                # Get suggested tags for all selected vendors
                suggested_tags = []
                for vendor in vendor_list:
                    if vendor in vendor_tags:
                        for tag in vendor_tags[vendor].keys():
                            if not any(st['value'] == tag for st in suggested_tags):
                                suggested_tags.append({'label': f"⭐ {tag}", 'value': tag})
                
                other_tags = [{'label': tag, 'value': tag} for tag in tags.keys() if tag not in [t['value'] for t in suggested_tags]]
                other_tags.sort(key=lambda x: tags.get(x['value'], 0), reverse=True)
                
                all_tag_options = suggested_tags + other_tags
                
                # Vendor info and tagging interface
                return html.Div([
                    dbc.Alert([
                        html.H6(f"🏪 Selected Vendors ({len(vendor_list)})", className="mb-2"),
                        html.P([
                            html.Strong(", ".join(vendor_list[:2])),
                            f" {'and others...' if len(vendor_list) > 2 else ''}"
                        ], className="mb-0")
                    ], color="primary", className="mb-3"),
                    
                    html.Div([
                        html.Label("🏷️ Select Tags:", className="form-label fw-bold"),
                        html.P("⭐ = suggested for these vendors", className="text-muted small mb-2"),
                        dcc.Dropdown(
                            id='tag-select',
                            multi=True,
                            placeholder="Choose existing tags...",
                            options=all_tag_options,
                            style={'marginBottom': '15px'}
                        )
                    ]),
                    
                    html.Div([
                        html.Label("➕ Add New Tags:", className="form-label fw-bold"),
                        dcc.Input(
                            id='new-tags-input',
                            type='text',
                            placeholder="Enter new tags separated by commas",
                            className="form-control mb-3"
                        )
                    ]),
                    
                    html.Div([
                        dbc.Button(
                            f"🏷️ Apply Tags to All Transactions from {len(vendor_list)} Vendor(s)",
                            id='apply-tags-btn',
                            color="primary",
                            size="lg",
                            className="w-100"
                        )
                    ], className="d-grid")
                ])
                
            else:
                # No selection
                return html.Div([
                    html.Div([
                        html.I(className="fas fa-hand-pointer fa-2x text-muted"),
                        html.P("Select vendors or a transaction to start tagging", className="text-muted mt-2 mb-0")
                    ], className="text-center py-4")
                ])
            
        except Exception as e:
            return html.P(f"Error: {str(e)}", className="text-danger")

    @app.callback(
        Output('daily-context', 'children'),
        [Input('selected-transaction-store', 'data'),
         Input('dataframe-store', 'data')]
    )
    def update_daily_context(selected_transaction, df_data):
        """Update daily context when a transaction is selected"""
        if not selected_transaction or not df_data:
            return html.P("Select a transaction to see daily context", className="text-muted")
        
        try:
            # Convert dict back to DataFrame with proper date handling
            df = restore_dataframe_from_store(df_data)
            
            # Get daily context
            context = get_daily_context_for_transaction(df, selected_transaction)
            
            if not context['transactions']:
                return html.P("No context available for this transaction", className="text-muted")
            
            # Create display
            summary = context['summary']
            
            # Header with date and summary
            context_display = [
                html.Div([
                    html.H6(f"📅 {summary['date_display']}", className="text-primary mb-2"),
                    html.Div([
                        html.Span(f"💰 Total: {summary['total_amount']:.2f}€", className="me-3"),
                        html.Span(f"📊 {summary['total_transactions']} transactions", className="me-3"),
                        html.Span(f"🏷️ {summary['tagged_transactions']} tagged", className="text-success")
                    ], className="mb-3 text-muted")
                ], className="border-bottom pb-2 mb-3")
            ]
            
            # Transaction list
            for trans in context['transactions']:
                # Style based on status
                if trans['is_selected']:
                    card_style = {
                        'backgroundColor': '#e3f2fd',
                        'border': '2px solid #2196f3'
                    }
                    vendor_class = "text-primary fw-bold"
                elif trans['has_tags']:
                    card_style = {
                        'backgroundColor': '#e8f5e8',
                        'border': '1px solid #28a745'
                    }
                    vendor_class = "text-success"
                else:
                    card_style = {
                        'backgroundColor': '#fff3cd',
                        'border': '1px solid #ffc107'
                    }
                    vendor_class = "text-warning"
                
                transaction_card = html.Div([
                    html.Div([
                        html.Div([
                            html.Strong(
                                f"{'👆 ' if trans['is_selected'] else ''}🏪 {trans['vendor']}", 
                                className=vendor_class
                            ),
                            html.Div(f"{trans['display_amount']}", className="text-success fw-bold"),
                        ], className="d-flex justify-content-between align-items-center"),
                        
                        html.Div([
                            html.Small(
                                f"🕐 {trans.get('time', 'N/A')} • 🏷️ {trans['tags_display']}", 
                                className="text-muted"
                            )
                        ], className="mt-1")
                    ])
                ], className="p-2 rounded mb-2", style=card_style)
                
                context_display.append(transaction_card)
            
            return html.Div(context_display)
            
        except Exception as e:
            return html.P(f"Error loading daily context: {str(e)}", className="text-danger")

    @app.callback(
        [
            Output('dataframe-store', 'data', allow_duplicate=True),
            Output('tagging-feedback', 'children'),
            Output('vendor-select', 'value'),
            Output('tag-select', 'value'),
            Output('new-tags-input', 'value'),
            Output('save-file-btn', 'disabled'),
            Output('selected-transaction-store', 'data', allow_duplicate=True),
        ],
        [
            Input('apply-tags-btn', 'n_clicks'),
        ],
        [
            State('dataframe-store', 'data'),
            State('vendor-select', 'value'),
            State('tag-select', 'value'),
            State('new-tags-input', 'value'),
            State('tags-config-store', 'data'),
            State('vendor-tags-config-store', 'data'),
            State('selected-transaction-store', 'data'),
        ],
        prevent_initial_call=True
    )
    def apply_tags(n_clicks, df_data, selected_vendors, selected_tags, new_tags_input, tags_config, vendor_tags_config, selected_transaction):
        """Apply tags to selected vendors/transaction and update configurations on disk"""
        # Check if callback was triggered by actual button click
        if not callback_context.triggered or not n_clicks or not df_data:
            return df_data, html.Div(), selected_vendors or [], selected_tags or [], new_tags_input or "", True, selected_transaction
        
        # Verify the trigger was the apply button
        trigger_id = callback_context.triggered[0]['prop_id'].split('.')[0]
        if trigger_id != 'apply-tags-btn':
            return df_data, html.Div(), selected_vendors or [], selected_tags or [], new_tags_input or "", True, selected_transaction
        
        # Convert data back to DataFrame with proper date handling
        df = restore_dataframe_from_store(df_data)
        
        # Parse new tags
        new_tags = [tag.strip() for tag in (new_tags_input or '').split(',') if tag.strip()]
        
        # Determine tagging mode: individual transaction or vendors
        if selected_transaction:
            # Mode: Tag individual transaction
            updated_df, affected_count = apply_tags_to_transaction(
                df, 
                selected_transaction, 
                selected_tags or [], 
                new_tags
            )
            
            # Get vendor name for configuration update
            transaction_df_index = int(selected_transaction.split('_')[1])
            vendor_name = df.loc[transaction_df_index, 'Description']
            vendors_for_config = [vendor_name]
            
            tagging_target = f"transaction {selected_transaction}"
        else:
            # Mode: Tag all transactions for selected vendors
            updated_df, affected_count = apply_tags_to_vendors(
                df, 
                selected_vendors or [], 
                selected_tags or [], 
                new_tags
            )
            
            vendors_for_config = selected_vendors or []
            tagging_target = f"vendors {', '.join(vendors_for_config)}"
        
        # Get all tags being applied
        all_tags = list(set((selected_tags or []) + new_tags))
        
        # Update JSON configurations on disk for new tags and associations
        if all_tags and vendors_for_config:
            update_configurations_on_disk(all_tags, vendors_for_config)
        
        if affected_count > 0:
            # Check if tagging is complete for save button
            progress = get_tagging_progress(updated_df)
            save_btn_disabled = progress['untagged_transactions'] > 0
            
            # Create modern feedback message
            feedback = dbc.Alert([
                html.H5([
                    html.I(className="fas fa-check-circle me-2"),
                    "Tags Applied Successfully!"
                ], className="alert-heading mb-3"),
                html.P([
                    html.Strong(f"🎯 {affected_count} transaction tagged"),
                    html.Br(),
                    f"🏷️ Tags: {', '.join(all_tags)}",
                    html.Br(),
                    f"📋 Target: {tagging_target}"
                ], className="mb-0")
            ], color="success", dismissable=True, duration=4000)
            
            return (
                updated_df.to_dict('records'),
                feedback,
                [],  # Clear vendor selection
                [],  # Clear tag selection
                '',  # Clear new tag input
                save_btn_disabled,
                None  # Clear selected transaction
            )
        else:
            feedback = dbc.Alert([
                html.H6([
                    html.I(className="fas fa-exclamation-triangle me-2"),
                    "No Changes Made"
                ], className="alert-heading mb-2"),
                html.P("Please select tags or add new ones before applying.", className="mb-0")
            ], color="warning", dismissable=True)
            
            return df_data, feedback, selected_vendors, selected_tags, new_tags_input, True, selected_transaction



    @app.callback(
        [Output('save-file-btn', 'children'),
         Output('save-file-btn', 'color')],
        [Input('dataframe-store', 'data')]
    )
    def update_save_button(df_data):
        """Update save button appearance based on progress"""
        if not df_data:
            return "💾 Save Progress", "secondary"
        
        try:
            df = restore_dataframe_from_store(df_data)
            progress = get_tagging_progress(df)
            
            tagged_count = progress['tagged_transactions']
            total_count = progress['total_transactions']
            
            if tagged_count == 0:
                return "💾 Save Progress", "secondary"
            elif tagged_count == total_count:
                return [
                    html.I(className="fas fa-check-circle me-2"),
                    f"💾 Save Complete File ({tagged_count}/{total_count})"
                ], "success"
            else:
                return [
                    html.I(className="fas fa-save me-2"),
                    f"💾 Save Progress ({tagged_count}/{total_count})"
                ], "primary"
                
        except Exception:
            return "💾 Save Progress", "secondary"

    @app.callback(
        Output('tagging-feedback', 'children', allow_duplicate=True),
        [Input('save-file-btn', 'n_clicks')],
        [State('dataframe-store', 'data'),
         State('current-filename-store', 'data')],
        prevent_initial_call=True
    )
    def save_tagged_file_callback(n_clicks, df_data, filename):
        """Save the tagged file"""
        if not n_clicks or not df_data or not filename:
            return html.Div()
        
        try:
            # Convert dict back to DataFrame with proper date handling
            df = restore_dataframe_from_store(df_data)
            
            # Save file
            success = save_tagged_file(df, filename)
            
            if success:
                return html.Div([
                    html.Div([
                        html.H6("🎉 File Saved Successfully!", className="text-success mb-2"),
                        html.P(f"File saved to data/processed/{filename}", className="mb-1"),
                        html.P("You can now analyze this data in the other dashboard tabs.", className="mb-1")
                    ], className="p-3 border rounded", style={'background-color': '#d4edda'})
                ])
            else:
                return html.Div([
                    html.P("❌ Error saving file. Please try again.", className="text-danger")
                ])
                
        except Exception as e:
            return html.Div([
                html.P(f"❌ Error saving file: {str(e)}", className="text-danger")
            ])

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
        
        return bar_fig, line_fig, info_components

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