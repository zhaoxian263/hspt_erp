from .consumable import consumable_bp
from .stock import stock_bp
from .excel import excel_bp
from .department import dept_bp
from .category import category_bp
from .staff import staff_bp
from .inventory_check import check_bp


def register_blueprints(app):
    app.register_blueprint(consumable_bp, url_prefix='/api/consumables')
    app.register_blueprint(stock_bp, url_prefix='/api/stock')
    app.register_blueprint(excel_bp, url_prefix='/api/excel')
    app.register_blueprint(dept_bp, url_prefix='/api/departments')
    app.register_blueprint(category_bp, url_prefix='/api/categories')
    app.register_blueprint(staff_bp, url_prefix='/api/staff')
    app.register_blueprint(check_bp, url_prefix='/api/inventory-checks')