from datetime import datetime, date
from flask import Blueprint, request, jsonify
from models import db, Consumable, StockBatch, InboundRecord, OutboundRecord

stock_bp = Blueprint('stock', __name__)


# ======================== 入库管理 ========================

@stock_bp.route('/inbound', methods=['GET'])
def list_inbound():
    """入库记录列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    keyword = request.args.get('keyword', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = InboundRecord.query
    if keyword:
        query = query.join(Consumable).filter(
            db.or_(
                Consumable.code.contains(keyword),
                Consumable.name.contains(keyword),
                InboundRecord.batch_number.contains(keyword),
                InboundRecord.operator.contains(keyword),
            )
        )
    if start_date:
        query = query.filter(InboundRecord.inbound_time >= start_date)
    if end_date:
        query = query.filter(InboundRecord.inbound_time <= end_date + ' 23:59:59')

    query = query.order_by(InboundRecord.inbound_time.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    items = [r.to_dict(include_consumable=True) for r in pagination.items]
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.per_page,
        'pages': pagination.pages,
    })


@stock_bp.route('/inbound', methods=['POST'])
def create_inbound():
    """新增入库记录（同时更新库存批次）"""
    data = request.get_json()
    if not data or not data.get('consumable_id') or not data.get('quantity'):
        return jsonify({'error': '耗材和数量为必填项'}), 400

    consumable_id = data['consumable_id']
    quantity = int(data['quantity'])
    batch_number = data.get('batch_number', '')

    # 验证耗材存在
    consumable = Consumable.query.get(consumable_id)
    if not consumable:
        return jsonify({'error': '耗材不存在'}), 404

    # 解析日期
    production_date = _parse_date(data.get('production_date'))
    expiry_date = _parse_date(data.get('expiry_date'))
    inbound_time = _parse_datetime(data.get('inbound_time'))

    # 创建入库记录
    record = InboundRecord(
        consumable_id=consumable_id,
        batch_number=batch_number,
        production_date=production_date,
        expiry_date=expiry_date,
        quantity=quantity,
        operator=data.get('operator'),
        inbound_time=inbound_time,
        remark=data.get('remark'),
    )
    db.session.add(record)

    # 更新库存批次：查找相同批号+耗材的批次，有则累加，无则新建
    batch = StockBatch.query.filter_by(
        consumable_id=consumable_id,
        batch_number=batch_number,
    ).first()

    if batch:
        batch.quantity += quantity
        batch.updated_at = datetime.now()
    else:
        batch = StockBatch(
            consumable_id=consumable_id,
            batch_number=batch_number,
            production_date=production_date,
            expiry_date=expiry_date,
            quantity=quantity,
            remark=data.get('remark'),
        )
        db.session.add(batch)

    db.session.commit()
    return jsonify(record.to_dict(include_consumable=True)), 201


@stock_bp.route('/inbound/<int:record_id>', methods=['DELETE'])
def delete_inbound(record_id):
    """删除入库记录（同时扣减库存批次）"""
    record = InboundRecord.query.get_or_404(record_id)
    # 扣减对应批次库存
    batch = StockBatch.query.filter_by(
        consumable_id=record.consumable_id,
        batch_number=record.batch_number,
    ).first()
    if batch:
        batch.quantity -= record.quantity
        if batch.quantity <= 0:
            db.session.delete(batch)
    db.session.delete(record)
    db.session.commit()
    return jsonify({'message': '删除成功'})


# ======================== 出库管理 ========================

@stock_bp.route('/outbound', methods=['GET'])
def list_outbound():
    """出库记录列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)
    keyword = request.args.get('keyword', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = OutboundRecord.query
    if keyword:
        query = query.join(Consumable).filter(
            db.or_(
                Consumable.code.contains(keyword),
                Consumable.name.contains(keyword),
                OutboundRecord.batch_number.contains(keyword),
                OutboundRecord.recipient.contains(keyword),
                OutboundRecord.department.contains(keyword),
            )
        )
    if start_date:
        query = query.filter(OutboundRecord.outbound_time >= start_date)
    if end_date:
        query = query.filter(OutboundRecord.outbound_time <= end_date + ' 23:59:59')

    query = query.order_by(OutboundRecord.outbound_time.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    items = [r.to_dict(include_consumable=True) for r in pagination.items]
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': pagination.page,
        'page_size': pagination.per_page,
        'pages': pagination.pages,
    })


@stock_bp.route('/outbound', methods=['POST'])
def create_outbound():
    """新增出库记录（同时扣减库存批次）"""
    data = request.get_json()
    if not data or not data.get('consumable_id') or not data.get('quantity'):
        return jsonify({'error': '耗材和数量为必填项'}), 400

    consumable_id = data['consumable_id']
    quantity = int(data['quantity'])

    consumable = Consumable.query.get(consumable_id)
    if not consumable:
        return jsonify({'error': '耗材不存在'}), 404

    # 检查总库存是否足够
    if consumable.total_stock < quantity:
        return jsonify({'error': f'库存不足，当前库存 {consumable.total_stock}，申请出库 {quantity}'}), 400

    batch_number = data.get('batch_number', '')
    outbound_time = _parse_datetime(data.get('outbound_time'))

    # 如果指定了批号，从该批次扣减；否则按先进先出扣减
    if batch_number:
        batches = [StockBatch.query.filter_by(
            consumable_id=consumable_id, batch_number=batch_number
        ).first()]
        if not batches[0] or batches[0].quantity < quantity:
            return jsonify({'error': f'批号 {batch_number} 库存不足'}), 400
    else:
        # 先进先出：按失效日期升序扣减
        batches = StockBatch.query.filter(
            StockBatch.consumable_id == consumable_id,
            StockBatch.quantity > 0,
        ).order_by(StockBatch.expiry_date.asc().nullslast(), StockBatch.created_at.asc()).all()

    # 创建出库记录
    record = OutboundRecord(
        consumable_id=consumable_id,
        batch_number=batch_number,
        quantity=quantity,
        recipient=data.get('recipient'),
        department=data.get('department'),
        operator=data.get('operator'),
        outbound_time=outbound_time,
        remark=data.get('remark'),
    )
    db.session.add(record)

    # 扣减批次库存
    remaining = quantity
    for batch in batches:
        if remaining <= 0:
            break
        if batch.quantity <= remaining:
            remaining -= batch.quantity
            batch.quantity = 0
        else:
            batch.quantity -= remaining
            remaining = 0

    # 删除库存为0的批次
    for batch in StockBatch.query.filter(
        StockBatch.consumable_id == consumable_id,
        StockBatch.quantity <= 0,
    ).all():
        db.session.delete(batch)

    # 更新出库记录中的实际出库批号（取最后扣减的批号）
    if not batch_number and batches:
        used_batches = [b.batch_number or '' for b in batches if b.quantity >= 0]
        record.batch_number = ', '.join(filter(None, used_batches))[:100]

    db.session.commit()
    return jsonify(record.to_dict(include_consumable=True)), 201


@stock_bp.route('/outbound/<int:record_id>', methods=['DELETE'])
def delete_outbound(record_id):
    """删除出库记录（同时恢复库存批次）"""
    record = OutboundRecord.query.get_or_404(record_id)
    # 恢复批次库存：查找同批号批次，有则加回，无则新建
    for bn in (record.batch_number or '').split(','):
        bn = bn.strip()
        if not bn:
            continue
        batch = StockBatch.query.filter_by(
            consumable_id=record.consumable_id,
            batch_number=bn,
        ).first()
        if batch:
            batch.quantity += record.quantity
        else:
            batch = StockBatch(
                consumable_id=record.consumable_id,
                batch_number=bn,
                quantity=record.quantity,
            )
            db.session.add(batch)
            break  # 只处理第一个批号

    db.session.delete(record)
    db.session.commit()
    return jsonify({'message': '删除成功'})


# ======================== 库存查询与预警 ========================

@stock_bp.route('/inventory', methods=['GET'])
def list_inventory():
    """库存总览（含预警状态）"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 50, type=int)
    keyword = request.args.get('keyword', '').strip()
    status_filter = request.args.get('status', '').strip()  # all/normal/warning/low/expiry_warning/expired

    query = Consumable.query
    if keyword:
        query = query.filter(
            db.or_(
                Consumable.code.contains(keyword),
                Consumable.name.contains(keyword),
                Consumable.brand.contains(keyword),
                Consumable.manufacturer.contains(keyword),
            )
        )

    items = query.order_by(Consumable.code).all()
    result = []
    for c in items:
        item = c.to_dict(include_stock=True)
        item['stock_batches'] = [b.to_dict() for b in c.stock_batches.filter(StockBatch.quantity > 0).all()]
        # 状态过滤
        if status_filter == 'normal' and item['stock_status'] != '库存正常':
            continue
        elif status_filter == 'warning' and item['stock_status'] != '库存预警':
            continue
        elif status_filter == 'low' and item['stock_status'] != '库存不足':
            continue
        elif status_filter == 'expiry_warning' and item['expiry_status'] != '近效期':
            continue
        elif status_filter == 'expired' and item['expiry_status'] != '已过期':
            continue
        result.append(item)

    # 分页
    total = len(result)
    start = (page - 1) * page_size
    end = start + page_size
    paged = result[start:end]

    return jsonify({
        'items': paged,
        'total': total,
        'page': page,
        'page_size': page_size,
    })


@stock_bp.route('/batches', methods=['GET'])
def list_batches():
    """库存批次明细"""
    consumable_id = request.args.get('consumable_id', type=int)
    query = StockBatch.query.filter(StockBatch.quantity > 0)
    if consumable_id:
        query = query.filter_by(consumable_id=consumable_id)
    query = query.order_by(StockBatch.expiry_date.asc().nullslast())
    items = [b.to_dict(include_consumable=True) for b in query.all()]
    return jsonify({'items': items, 'total': len(items)})


@stock_bp.route('/dashboard', methods=['GET'])
def dashboard():
    """首页仪表盘数据"""
    total_consumables = Consumable.query.count()
    total_inbound = db.session.query(db.func.sum(InboundRecord.quantity)).scalar() or 0
    total_outbound = db.session.query(db.func.sum(OutboundRecord.quantity)).scalar() or 0
    total_stock = db.session.query(db.func.sum(StockBatch.quantity)).scalar() or 0

    # 库存预警
    warning_items = []
    expired_items = []
    for c in Consumable.query.all():
        stock_status = c.stock_status
        expiry_status = c.expiry_status
        if stock_status in ('库存预警', '库存不足'):
            warning_items.append({
                'code': c.code, 'name': c.name,
                'total_stock': c.total_stock,
                'stock_warning_value': c.stock_warning_value,
                'status': stock_status,
            })
        if expiry_status in ('近效期', '已过期'):
            expired_items.append({
                'code': c.code, 'name': c.name,
                'expiry_status': expiry_status,
            })

    # 最近出库记录
    recent_outbound = OutboundRecord.query.order_by(
        OutboundRecord.outbound_time.desc()
    ).limit(5).all()
    recent_out = [r.to_dict(include_consumable=True) for r in recent_outbound]

    # 科室出库统计
    dept_stats = db.session.query(
        OutboundRecord.department,
        db.func.sum(OutboundRecord.quantity).label('total')
    ).filter(OutboundRecord.department.isnot(None), OutboundRecord.department != '') \
     .group_by(OutboundRecord.department).all()
    dept_data = [{'department': d, 'total': int(t)} for d, t in dept_stats]

    return jsonify({
        'total_consumables': total_consumables,
        'total_inbound': int(total_inbound),
        'total_outbound': int(total_outbound),
        'total_stock': int(total_stock),
        'warning_count': len(warning_items),
        'expired_count': len(expired_items),
        'warning_items': warning_items[:10],
        'expired_items': expired_items[:10],
        'recent_outbound': recent_out,
        'dept_stats': dept_data,
    })


# ======================== 工具函数 ========================

def _parse_date(value):
    """解析日期字符串"""
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            # Excel 数字日期格式
            from datetime import timedelta
            return date(1899, 12, 30) + timedelta(days=int(value))
        s = str(value).split('.')[0].strip()
        for fmt in ('%Y-%m-%d', '%Y%m%d', '%Y/%m/%d'):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    except Exception:
        pass
    return None


def _parse_datetime(value):
    """解析日期时间字符串"""
    if not value:
        return datetime.now()
    try:
        s = str(value).strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y%m%d'):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
    except Exception:
        pass
    return datetime.now()