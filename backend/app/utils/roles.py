"""集中定义角色集合。

历史问题：各路由分别硬编码 `role != "admin"` / `role not in ("admin", "super_admin")`，
导致同一语义在不同端点行为不一致（例如超管在记录列表看不到全部数据）。
所有角色判断统一引用本模块，避免再次漂移。
"""

# 平台级管理角色：拥有跨组织的全局管理权
ADMIN_ROLES = frozenset({"admin", "super_admin"})

# 最高管理角色：可执行管理员无法执行的操作（如删除其他管理员、改系统配置）
SUPER_ADMIN_ROLES = frozenset({"super_admin"})

# 只读复核角色：可查看全部业务数据但不应执行写操作
REVIEWER_ROLES = frozenset({"auditor"})

# 可查看全部检查记录/任务的角色（管理 + 只读复核）
RECORD_VIEW_ALL_ROLES = ADMIN_ROLES | REVIEWER_ROLES

# 现场执行角色：数据可见范围限定为「分配给自己的」
FIELD_ROLES = frozenset({"expert"})


def is_admin(role: str | None) -> bool:
    return role in ADMIN_ROLES


def is_super_admin(role: str | None) -> bool:
    return role in SUPER_ADMIN_ROLES


def can_view_all_records(role: str | None) -> bool:
    return role in RECORD_VIEW_ALL_ROLES
