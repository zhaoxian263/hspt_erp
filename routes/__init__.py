from .consumable import consumable_bp
from .stock import stock_bp
from .excel import excel_bp
from .department import dept_bp

def register_blueprints(app):
    app.register_blueprint(consumable_bp, url_prefix='/api/consumables')
    app.register_blueprint(stock_bp, url_prefix='/api/stock')
    app.register_blueprint(excel_bp, url_prefix='/api/excel')
    app.register_blueprint(dept_bp, url_prefix='/api/departments')