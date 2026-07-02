import os
import sys
import sqlite3
import shutil
import traceback
from datetime import datetime
from flask import Flask, render_template, send_from_directory, jsonify
from config import SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS, SECRET_KEY, MAX_CONTENT_LENGTH
from models import db


def create_app(testing=False):
    """创建 Flask 应用实例

    Args:
        testing: 若为 True，使用内存数据库（仅供测试使用，防止测试销毁生产数据）
    """
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))

    if testing:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

    db.init_app(app)

    from routes import register_blueprints
    register_blueprints(app)

    # 全局错误处理：API 请求返回 JSON，页面请求返回友好提示
    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(500)
    def handle_error(e):
        if request_wants_json():
            return jsonify({'error': e.description if hasattr(e, 'description') else str(e)}), e.code
        return render_template('index.html'), e.code

    def request_wants_json():
        """判断请求是否期望 JSON 响应"""
        from flask import request as req
        best = req.accept_mimetypes.best_match(['application/json', 'text/html'])
        return best == 'application/json' and req.accept_mimetypes[best] > req.accept_mimetypes.get('text/html', 0)

    @app.errorhandler(Exception)
    def handle_unhandled_exception(e):
        """捕获未处理异常，返回 JSON 而非 500 HTML 页面"""
        if request_wants_json():
            return jsonify({'error': '服务器内部错误'}), 500
        return render_template('index.html'), 500

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    return app


def _migrate_legacy_columns(cursor, conn):
    """将旧列名的数据复制到新列名（旧版数据库字段名不一致时的迁移）"""
    # 获取各表现有列名
    def get_columns(table):
        cursor.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}

    # inbound_record: inbound_date → inbound_time, create_time → created_at
    cols = get_columns('inbound_record')
    if 'inbound_date' in cols and 'inbound_time' in cols:
        cursor.execute("UPDATE inbound_record SET inbound_time = inbound_date WHERE inbound_time IS NULL AND inbound_date IS NOT NULL")
        print('  ✅ inbound_record: inbound_date → inbound_time 数据迁移')
    if 'create_time' in cols and 'created_at' in cols:
        cursor.execute("UPDATE inbound_record SET created_at = create_time WHERE created_at IS NULL AND create_time IS NOT NULL")
        print('  ✅ inbound_record: create_time → created_at 数据迁移')

    # outbound_record: create_time → created_at
    cols = get_columns('outbound_record')
    if 'create_time' in cols and 'created_at' in cols:
        cursor.execute("UPDATE outbound_record SET created_at = create_time WHERE created_at IS NULL AND create_time IS NOT NULL")
        print('  ✅ outbound_record: create_time → created_at 数据迁移')

    # stock_batch: create_time → created_at
    cols = get_columns('stock_batch')
    if 'create_time' in cols and 'created_at' in cols:
        cursor.execute("UPDATE stock_batch SET created_at = create_time WHERE created_at IS NULL AND create_time IS NOT NULL")
        print('  ✅ stock_batch: create_time → created_at 数据迁移')

    # consumable: create_time → created_at
    cols = get_columns('consumable')
    if 'create_time' in cols and 'created_at' in cols:
        cursor.execute("UPDATE consumable SET created_at = create_time WHERE created_at IS NULL AND create_time IS NOT NULL")
        print('  ✅ consumable: create_time → created_at 数据迁移')


def _migrate_db(db_path):
    """对已有 SQLite 数据库执行增量迁移（添加新列）"""
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # 安全检查：如果数据库没有表则跳过
    cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
    if cursor.fetchone()[0] == 0:
        conn.close()
        return
    # 需要添加的新列: {表名: [(列名, 列类型), ...]}
    migrations = {
        'consumable': [
            ('category', 'VARCHAR(100)'),
            ('storage_location', 'VARCHAR(200)'),
            ('initial_stock', 'INTEGER DEFAULT 0'),
            ('manufacturer', 'VARCHAR(200)'),
            ('remark', 'TEXT'),
            ('created_at', 'DATETIME'),
            ('updated_at', 'DATETIME'),
        ],
        'inbound_record': [
            ('document_number', 'VARCHAR(50)'),
            ('storage_location', 'VARCHAR(200)'),
            ('production_date', 'DATE'),
            ('expiry_date', 'DATE'),
            ('inbound_time', 'DATETIME'),
        ],
        'outbound_record': [
            ('document_number', 'VARCHAR(50)'),
            ('batch_detail', 'TEXT'),
            ('outbound_time', 'DATETIME'),
        ],
        'stock_batch': [
            ('storage_location', 'VARCHAR(200)'),
            ('remark', 'TEXT'),
            ('inbound_record_id', 'INTEGER'),
            ('created_at', 'DATETIME'),
            ('updated_at', 'DATETIME'),
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
    # 旧字段数据迁移：将旧列名的数据复制到新列名
    _migrate_legacy_columns(cursor, conn)
    conn.commit()
    conn.close()
    # 去掉 document_number 的 unique 约束（SQLite 需重建表）
    _drop_document_number_unique(db_path)


def _drop_document_number_unique(db_path):
    """去掉 inbound_record / outbound_record 的 document_number unique 约束
    SQLite 不支持 DROP CONSTRAINT，需要重建表"""
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # 安全检查：如果数据库没有表则跳过
    cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
    if cursor.fetchone()[0] == 0:
        conn.close()
        return

    for table in ('inbound_record', 'outbound_record'):
        # 检查 document_number 列是否有 unique 约束
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
        row = cursor.fetchone()
        if not row or 'UNIQUE' not in row[0].upper():
            continue
        # 获取列定义
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        col_defs = []
        col_names = []
        for col in columns:
            col_names.append(col[1])
            base = f'{col[1]} {col[2]}'
            if col[3]:  # notnull
                base += ' NOT NULL'
            if col[4] is not None:  # default
                base += f' DEFAULT {col[4]}'
            # 跳过原表 SQL 中的 UNIQUE 约束（在列定义里）
            col_defs.append(base)

        # 获取外键信息
        cursor.execute(f"PRAGMA foreign_key_list({table})")
        fks = cursor.fetchall()
        fk_defs = []
        for fk in fks:
            fk_defs.append(f'FOREIGN KEY({fk[3]}) REFERENCES {fk[2]}({fk[4]})')

        cols_str = ', '.join(col_names)
        all_defs = ', '.join(col_defs + fk_defs)

        new_table = f'_tmp_{table}'
        cursor.execute(f'CREATE TABLE {new_table} ({all_defs})')
        cursor.execute(f'INSERT INTO {new_table} ({cols_str}) SELECT {cols_str} FROM {table}')
        cursor.execute(f'DROP TABLE {table}')
        cursor.execute(f'ALTER TABLE {new_table} RENAME TO {table}')
        print(f'  ✅ {table}.document_number unique 约束已移除')

    conn.commit()
    conn.close()


def _patch_initial_stock_batches():
    """为已有耗材补充期初库存批次：initial_stock > 0 且无'期初库存'批次时补建"""
    from models import Consumable, StockBatch
    patched = 0
    for c in Consumable.query.filter(Consumable.initial_stock > 0).all():
        exists = StockBatch.query.filter_by(
            consumable_id=c.id, batch_number='期初库存'
        ).first()
        if not exists:
            batch = StockBatch(
                consumable_id=c.id,
                batch_number='期初库存',
                quantity=c.initial_stock,
                storage_location=c.storage_location,
                remark='系统自动创建（期初库存）',
            )
            db.session.add(batch)
            patched += 1
    if patched:
        db.session.commit()
        print(f'  ✅ 已为 {patched} 条耗材补充期初库存批次')


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
        # 为已有耗材补充期初库存批次（initial_stock > 0 但无对应批次时补建）
        _patch_initial_stock_batches()
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

        # 初始化完成后备份数据库（备份有效数据的数据库）
        if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
            backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(backup_dir, f'erp_{timestamp}.db')
            shutil.copy2(db_path, backup_path)
            # 只保留最近20个备份
            backups = sorted(
                [f for f in os.listdir(backup_dir) if f.startswith('erp_') and f.endswith('.db')],
                reverse=True
            )
            for old_backup in backups[20:]:
                os.remove(os.path.join(backup_dir, old_backup))
            print(f'✅ 数据库已备份 → {backup_path}')


if __name__ == '__main__':
    app = create_app()
    init_db(app)
    print('🏥 安居镇中心卫生院护理部耗材管理系统已启动 → http://localhost:5000')
    # use_reloader=False 防止双进程并发写 SQLite 导致数据库损坏
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)