import os
import sys
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


def init_db(app):
    """初始化数据库（创建表 + 默认科室）"""
    with app.app_context():
        os.makedirs(os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')), exist_ok=True)
        db.create_all()
        # 首次运行时初始化默认科室
        from models import Department
        if Department.query.count() == 0:
            defaults = ['门诊检验科', '住院部', '手术室', '急诊科', 'ICU', '儿科',
                        '妇产科', '骨科', '内科', '外科', '药房', '行政后勤']
            for idx, name in enumerate(defaults):
                db.session.add(Department(name=name, sort_order=idx))
            db.session.commit()
            print('✅ 已初始化默认科室')
        print('✅ 数据库初始化完成')


if __name__ == '__main__':
    app = create_app()
    init_db(app)
    print('🏥 安居镇中心卫生院护理部耗材管理系统已启动 → http://localhost:5000')
    app.run(host='0.0.0.0', port=5000, debug=True)