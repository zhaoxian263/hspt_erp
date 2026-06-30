from datetime import datetime, date
from flask import Blueprint, request, jsonify
from models import db, Consumable, StockBatch, InventoryCheck, InventoryCheckItem

check_bp = Blueprint('inventory_check', __name__)


@check_bp.route('', methods=['GET'])
def list_checks():
    """盘点列表"""
    checks = InventoryCheck.query.order_by(InventoryCheck.check_date.desc()).all()
    return jsonify([c.to_dict() for c in checks])


@check_bp.route('', methods=['POST'])
def create_check():
    """创建盘点（自动填充所有耗材的系统库存）"""
    data = request.get_json() or {}
    check_date_str = data.get('check_date')
    if check_date_str:
        try:
            check_date = datetime.strptime(check_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': '日期格式错误，请使用 YYYY-MM-DD'}), 400
    else:
        check_date = date.today()

    remark = data.get('remark', '')

    # 创建盘点主记录
    check = InventoryCheck(check_date=check_date, remark=remark, status='draft')
    db.session.add(check)
    db.session.flush()  # 获取 check.id

    # 自动填充所有耗材的系统库存
    consumables = Consumable.query.order_by(Consumable.code).all()
    for c in consumables:
        item = InventoryCheckItem(
            check_id=check.id,
            consumable_id=c.id,
            system_quantity=c.total_stock,
            actual_quantity=None,
            difference=0,
        )
        db.session.add(item)

    db.session.commit()
    return jsonify(check.to_dict(include_items=True)), 201


@check_bp.route('/<int:check_id>', methods=['GET'])
def get_check(check_id):
    """盘点详情（含明细）"""
    check = InventoryCheck.query.get_or_404(check_id)
    return jsonify(check.to_dict(include_items=True))


@check_bp.route('/<int:check_id>', methods=['PUT'])
def update_check(check_id):
    """更新盘点明细（录入实盘数量）"""
    check = InventoryCheck.query.get_or_404(check_id)
    if check.status == 'confirmed':
        return jsonify({'error': '已确认的盘点不能修改'}), 400

    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'error': '请提供盘点明细'}), 400

    for item_data in data['items']:
        item_id = item_data.get('id')
        if not item_id:
            continue
        item = InventoryCheckItem.query.get(item_id)
        if not item or item.check_id != check_id:
            continue
        if 'actual_quantity' in item_data:
            aq = item_data['actual_quantity']
            item.actual_quantity = int(aq) if aq is not None else None
            item.difference = (item.actual_quantity or 0) - item.system_quantity
        if 'remark' in item_data:
            item.remark = item_data['remark']

    db.session.commit()
    return jsonify(check.to_dict(include_items=True))


@check_bp.route('/<int:check_id>/confirm', methods=['POST'])
def confirm_check(check_id):
    """确认盘点并调整库存"""
    check = InventoryCheck.query.get_or_404(check_id)
    if check.status == 'confirmed':
        return jsonify({'error': '该盘点已确认'}), 400

    items = check.items.all()
    unconfirmed = [i for i in items if i.actual_quantity is None]
    if unconfirmed:
        return jsonify({'error': f'还有 {len(unconfirmed)} 条记录未录入实盘数量'}), 400

    # 按实盘数量调整库存
    for item in items:
        if item.difference == 0:
            continue
        # 获取该耗材所有有效批次
        batches = StockBatch.query.filter(
            StockBatch.consumable_id == item.consumable_id,
            StockBatch.quantity > 0,
        ).order_by(StockBatch.expiry_date.asc().nullslast()).all()

        if item.difference > 0:
            # 盘盈：创建或累加批次
            batch = StockBatch.query.filter_by(
                consumable_id=item.consumable_id,
                batch_number='盘盈调整',
            ).first()
            if batch:
                batch.quantity += item.difference
            else:
                batch = StockBatch(
                    consumable_id=item.consumable_id,
                    batch_number='盘盈调整',
                    quantity=item.difference,
                )
                db.session.add(batch)
        else:
            # 盘亏：扣减批次
            remaining = abs(item.difference)
            for batch in batches:
                if remaining <= 0:
                    break
                deduct = min(batch.quantity, remaining)
                batch.quantity -= deduct
                remaining -= deduct
            # 删除库存为0的批次
            for batch in StockBatch.query.filter(
                StockBatch.consumable_id == item.consumable_id,
                StockBatch.quantity <= 0,
            ).all():
                db.session.delete(batch)

    check.status = 'confirmed'
    db.session.commit()
    return jsonify(check.to_dict(include_items=True))


@check_bp.route('/<int:check_id>', methods=['DELETE'])
def delete_check(check_id):
    """删除盘点（仅草稿状态可删）"""
    check = InventoryCheck.query.get_or_404(check_id)
    if check.status == 'confirmed':
        return jsonify({'error': '已确认的盘点不能删除'}), 400

    db.session.delete(check)
    db.session.commit()
    return jsonify({'message': '删除成功'})