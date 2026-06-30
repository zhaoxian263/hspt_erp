from flask import Blueprint, request, jsonify
from models import db, Staff, Department

staff_bp = Blueprint('staff', __name__)


@staff_bp.route('', methods=['GET'])
def list_staff():
    """人员列表（支持按科室/角色筛选）"""
    department_id = request.args.get('department_id', type=int)
    role = request.args.get('role', '').strip()

    query = Staff.query
    if department_id:
        query = query.filter_by(department_id=department_id)
    if role:
        query = query.filter(Staff.role.contains(role))

    staffs = query.order_by(Staff.sort_order, Staff.id).all()
    return jsonify([s.to_dict() for s in staffs])


@staff_bp.route('', methods=['POST'])
def create_staff():
    """新增人员"""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': '姓名为必填项'}), 400

    staff = Staff(
        name=data['name'].strip(),
        department_id=data.get('department_id'),
        role=data.get('role', ''),
        sort_order=data.get('sort_order', 0),
    )
    db.session.add(staff)
    db.session.commit()
    return jsonify(staff.to_dict()), 201


@staff_bp.route('/<int:staff_id>', methods=['PUT'])
def update_staff(staff_id):
    """更新人员"""
    staff = Staff.query.get_or_404(staff_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': '请提供更新数据'}), 400

    if 'name' in data:
        staff.name = data['name'].strip()
    if 'department_id' in data:
        staff.department_id = data['department_id'] or None
    if 'role' in data:
        staff.role = data['role']
    if 'sort_order' in data:
        staff.sort_order = data['sort_order']

    db.session.commit()
    return jsonify(staff.to_dict())


@staff_bp.route('/<int:staff_id>', methods=['DELETE'])
def delete_staff(staff_id):
    """删除人员"""
    staff = Staff.query.get_or_404(staff_id)
    db.session.delete(staff)
    db.session.commit()
    return jsonify({'message': '删除成功'})