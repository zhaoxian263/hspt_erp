from flask import Blueprint, request, jsonify
from models import db, Category, Consumable

category_bp = Blueprint('category', __name__)


@category_bp.route('', methods=['GET'])
def list_categories():
    """类别列表"""
    categories = Category.query.order_by(Category.sort_order, Category.id).all()
    return jsonify([c.to_dict() for c in categories])


@category_bp.route('', methods=['POST'])
def create_category():
    """新增类别"""
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': '类别名称为必填项'}), 400

    name = data['name'].strip()
    if Category.query.filter_by(name=name).first():
        return jsonify({'error': f'类别 "{name}" 已存在'}), 400

    cat = Category(
        name=name,
        sort_order=data.get('sort_order', 0),
    )
    db.session.add(cat)
    db.session.commit()
    return jsonify(cat.to_dict()), 201


@category_bp.route('/<int:cat_id>', methods=['PUT'])
def update_category(cat_id):
    """更新类别"""
    cat = Category.query.get_or_404(cat_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': '请提供更新数据'}), 400

    if 'name' in data:
        name = data['name'].strip()
        if name != cat.name and Category.query.filter_by(name=name).first():
            return jsonify({'error': f'类别 "{name}" 已存在'}), 400
        cat.name = name

    if 'sort_order' in data:
        cat.sort_order = data['sort_order']

    db.session.commit()
    return jsonify(cat.to_dict())


@category_bp.route('/<int:cat_id>', methods=['DELETE'])
def delete_category(cat_id):
    """删除类别"""
    cat = Category.query.get_or_404(cat_id)
    consumable_count = Consumable.query.filter_by(category=cat.name).count()
    if consumable_count > 0:
        return jsonify({'error': f'该类别下存在 {consumable_count} 个耗材，无法删除'}), 400
    db.session.delete(cat)
    db.session.commit()
    return jsonify({'message': '删除成功'})