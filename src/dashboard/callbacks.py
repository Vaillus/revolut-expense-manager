"""
Dashboard callbacks and interactions
"""
import plotly.graph_objects as go
from dash import Input, Output, html, dash_table, State, callback_context
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
    get_tagging_progress, save_tagged_file, update_configurations_on_disk
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
        """Update tagging progress display"""
        if not df_data:
            return html.Div()
        
        try:
            # Convert dict back to DataFrame
            df = pd.DataFrame(df_data)
            
            # Get progress stats
            progress = get_tagging_progress(df)
            
            return html.Div([
                html.Div([
                    html.H6(f"📊 Progress: {progress['tagged_transactions']}/{progress['total_transactions']} transactions tagged", 
                           className="text-primary mb-2"),
                    html.Div([
                        html.Div(
                            style={
                                'width': f"{progress['progress_percentage']:.1f}%",
                                'height': '20px',
                                'backgroundColor': '#28a745',
                                'borderRadius': '10px',
                                'transition': 'width 0.3s ease'
                            }
                        )
                    ], style={
                        'width': '100%',
                        'height': '20px',
                        'backgroundColor': '#e9ecef',
                        'borderRadius': '10px',
                        'overflow': 'hidden'
                    }),
                    html.P(f"🏷️ {progress['untagged_transactions']} transactions remaining", 
                          className="text-muted mt-2 mb-0")
                ], className="p-3 border rounded", style={'background-color': '#f8f9fa'})
            ])
            
        except Exception as e:
            return html.Div([
                html.P(f"Error updating progress: {str(e)}", className="text-danger")
            ])

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
            # Convert dict back to DataFrame
            df = pd.DataFrame(df_data)
            
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
        """Update transaction details for selected vendors"""
        if not selected_vendors or not df_data:
            return html.P("Select vendors to see transaction details", className="text-muted")
        
        try:
            # Convert dict back to DataFrame
            df = pd.DataFrame(df_data)
            
            # Get transaction details
            details = get_transaction_details_for_vendors(df, selected_vendors)
            
            if not details['transactions']:
                return html.P("No untagged transactions found for selected vendors", className="text-muted")
            
            # Create display
            vendor_displays = []
            for vendor, info in details['summary'].items():
                vendor_displays.append(html.Div([
                    html.H6(f"🏪 {vendor}", className="text-primary mb-2"),
                    html.P(f"💰 Total: {info['total']:.2f}€ ({info['count']} transactions)", className="mb-2"),
                    html.Div([
                        html.P(f"• {trans['amount']:.2f}€ - {trans['date']}", className="mb-1 ms-3")
                        for trans in info['transactions']
                    ])
                ], className="mb-3"))
            
            return html.Div(vendor_displays)
            
        except Exception as e:
            return html.P(f"Error loading transaction details: {str(e)}", className="text-danger")

    @app.callback(
        [
            Output('current-dataframe', 'data'),
            Output('tagging-progress', 'value'),
            Output('tagging-progress', 'label'),
            Output('tagging-alert', 'children'),
            Output('tagging-alert', 'is_open'),
            Output('vendor-selection', 'value'),
            Output('tag-selection', 'value'),
            Output('new-tag-input', 'value'),
            Output('tags-config', 'data'),
            Output('vendor-tags-config', 'data'),
            Output('vendor-selection', 'options'),
            Output('tag-selection', 'options'),
        ],
        [
            Input('apply-tags-button', 'n_clicks'),
        ],
        [
            State('current-dataframe', 'data'),
            State('vendor-selection', 'value'),
            State('tag-selection', 'value'),
            State('new-tag-input', 'value'),
            State('tags-config', 'data'),
            State('vendor-tags-config', 'data'),
        ],
        prevent_initial_call=True
    )
    def apply_tags(n_clicks, current_dataframe, selected_vendors, selected_tags, new_tag_input, tags_config, vendor_tags_config):
        """Apply tags to selected vendors and update configurations on disk"""
        if n_clicks is None or not current_dataframe:
            raise PreventUpdate
        
        # Convert data back to DataFrame
        df = pd.DataFrame(current_dataframe)
        
        # Parse new tags
        new_tags = [tag.strip() for tag in (new_tag_input or '').split(',') if tag.strip()]
        
        # Apply tags to DataFrame
        updated_df, affected_count = apply_tags_to_vendors(
            df, 
            selected_vendors or [], 
            selected_tags or [], 
            new_tags
        )
        
        # Get all tags being applied
        all_tags = list(set((selected_tags or []) + new_tags))
        
        # Update JSON configurations on disk and get updated configs
        updated_tags_config, updated_vendor_tags_config = update_configurations_on_disk(
            all_tags, 
            selected_vendors or []
        )
        
        # Calculate progress
        progress = get_tagging_progress(updated_df)
        
        # Update vendor list (remove vendors that are now fully tagged)
        vendor_options = get_untagged_vendors_from_df(updated_df, updated_vendor_tags_config)
        
        # Update tag options with new configurations
        tag_options = get_suggested_tags_for_vendors(
            [], 
            updated_tags_config, 
            updated_vendor_tags_config
        )
        
        # Create success message
        alert_message = dbc.Alert(
            f"✅ {affected_count} transaction(s) tagged successfully with {', '.join(all_tags)}",
            color="success",
            dismissable=True
        )
        
        return (
            updated_df.to_dict('records'),
            progress['progress_percentage'],
            f"{progress['untagged_transactions']} transactions remaining",
            alert_message,
            True,
            [],  # Clear vendor selection
            [],  # Clear tag selection
            '',  # Clear new tag input
            updated_tags_config,
            updated_vendor_tags_config,
            vendor_options,
            tag_options
        )

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
            # Convert dict back to DataFrame
            df = pd.DataFrame(df_data)
            
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