"""数据库公共工具函数"""


def escape_like(val):
    """转义 LIKE 通配符，防止 % 和 _ 被当作通配符"""
    return val.replace('%', '\\%').replace('_', '\\_')


def ilike_filter(column, keyword):
    """安全的模糊查询，转义 LIKE 通配符"""
    escaped = escape_like(keyword)
    return column.ilike(f'%{escaped}%', escape='\\')