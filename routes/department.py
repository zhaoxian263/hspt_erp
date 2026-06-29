from flask import Blueprint, request, jsonify
from models import db, Department

dept_bp = Blueprint('department', __name__)


@dept_bp.route('', methods=['GET'])
def list_departments():
    """科室列表"""
    departments = Department.query.order_by(Department.sort_order, Department.id).all()
    return jsonify([d.to_dict() for d in departments])


@dept_bp.route('', methods=['POST'])
def create_department():
    """新增科室"""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': '科室名称为必填项'}), 400

    name = data['name'].strip()
    if Department.query.filter_by(name=name).first():
        return jsonify({'error': f'科室 "{name}" 已存在'}), 400

    dept = Department(
        name=name,
        sort_order=data.get('sort_order', 0),
    )
    db.session.add(dept)
    db.session.commit()
    return jsonify(dept.to_dict()), 201


@dept_bp.route('/<int:dept_id>', methods=['PUT'])
def update_department(dept_id):
    """更新科室"""
    dept = Department.query.get_or_404(dept_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': '请提供更新数据'}), 400

    if 'name' in data:
        name = data['name'].strip()
        if name != dept.name and Department.query.filter_by(name=name).first():
            return jsonify({'error': f'科室 "{name}" 已存在'}), 400
        dept.name = name

    if 'sort_order' in data:
        dept.sort_order = data['sort_order']

    db.session.commit()
    return jsonify(dept.to_dict())


@dept_bp.route('/<int:dept_id>', methods=['DELETE'])
def delete_department(dept_id):
    """删除科室"""
    dept = Department.query.get_or_404(dept_id)
    db.session.delete(dept)
    db.session.commit()
    return jsonify({'message': '删除成功'})


@dept_bp.route('/init', methods=['POST'])
def init_default_departments():
    """初始化默认科室（仅在没有科室时执行）"""
    if Department.query.count() > 0:
        return jsonify({'message': '科室已存在，跳过初始化'})

    defaults = ['门诊检验科', '住院部', '手术室', '急诊科', 'ICU', '儿科',
                '妇产科', '骨科', '内科', '外科', '药房', '行政后勤']
    for idx, name in enumerate(defaults):
        db.session.add(Department(name=name, sort_order=idx))
    db.session.commit()
    return jsonify({'message': f'已初始化 {len(defaults)} 个默认科室'})