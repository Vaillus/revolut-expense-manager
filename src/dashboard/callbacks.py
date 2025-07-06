"""
Dashboard callbacks and interactions - Main registration file
"""
from .core_callbacks import register_core_callbacks
from .categories_callbacks import register_categories_callbacks
from .timeseries_callbacks import register_timeseries_callbacks
from .tagging_callbacks import register_tagging_callbacks


def register_callbacks(app):
    """Register all dashboard callbacks from separate modules"""
    
    # Register callbacks from each module
    register_core_callbacks(app)
    register_categories_callbacks(app)
    register_timeseries_callbacks(app)
    register_tagging_callbacks(app) 