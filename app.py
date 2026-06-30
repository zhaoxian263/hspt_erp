import os
import sys
import sqlite3
from flask import Flask, render_template, send_from_directory
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS, SECRET_KEY, MAX_CONTENT_LENGTH
from models import db


def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))

    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    db.init_app(app)

    from routes import register_blueprints
    register_blueprints(app)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    return app


def _migrate_db(db_path):
    """对已有 SQLite 数据库执行增量迁移（添加新列）"""
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # 需要添加的新列: {表名: [(列名, 列类型), ...]}
    migrations = {
        'consumable': [
            ('category', 'VARCHAR(100)'),
            ('storage_location', 'VARCHAR(200)'),
            ('initial_stock', 'INTEGER DEFAULT 0'),
        ],
        'inbound_record': [
            ('document_number', 'VARCHAR(50)'),
            ('storage_location', 'VARCHAR(200)'),
        ],
        'outbound_record': [
            ('document_number', 'VARCHAR(50)'),
        ],
        'stock_batch': [
            ('storage_location', 'VARCHAR(200)'),
        ],
    }
    for table, columns in migrations.items():
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if cursor.fetchone() is None:
            continue
        # 获取已有列名
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        for col_name, col_type in columns:
            if col_name not in existing:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                    print(f'  ✅ {table}.{col_name} 已添加')
                except sqlite3.OperationalError:
                    pass
    conn.commit()
    conn.close()


def init_db(app):
    """初始化数据库（创建表 + 迁移 + 默认数据）"""
    with app.app_context():
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # 确保所有模型已加载，db.create_all() 才能创建对应表
        from models import (db, Consumable, StockBatch, InboundRecord, OutboundRecord,
                            Department, Category, Staff, InventoryCheck, InventoryCheckItem)
        db.create_all()
        # 对已有数据库执行增量迁移
        _migrate_db(db_path)
        # 首次运行时初始化默认科室
        if Department.query.count() == 0:
            defaults = ['门诊检验科', '住院部', '手术室', '急诊科', 'ICU', '儿科',
                        '妇产科', '骨科', '内科', '外科', '药房', '行政后勤']
            for idx, name in enumerate(defaults):
                db.session.add(Department(name=name, sort_order=idx))
            db.session.commit()
            print('✅ 已初始化默认科室')
        # 首次运行时初始化默认类别
        if Category.query.count() == 0:
            defaults = ['一次性耗材', '试剂耗材', '敷料耗材', '器械耗材', '药品耗材', '其他耗材']
            for idx, name in enumerate(defaults):
                db.session.add(Category(name=name, sort_order=idx))
            db.session.commit()
            print('✅ 已初始化默认类别')
        print('✅ 数据库初始化完成')


if __name__ == '__main__':
    app = create_app()
    init_db(app)
    print('🏥 安居镇中心卫生院护理部耗材管理系统已启动 → http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, debug=True)