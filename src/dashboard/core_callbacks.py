"""
Core dashboard callbacks for main navigation
"""
from dash import Input, Output, html
from .layouts import create_categories_layout, create_timeseries_layout, create_tagging_layout


def register_core_callbacks(app):
    """Register core navigation callbacks"""
    
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