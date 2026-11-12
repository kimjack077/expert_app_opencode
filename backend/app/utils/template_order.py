"""移动节点时同步重排新旧两组兄弟节点，保留稳定、连续的顺序。"""


def move_template_item(items, item_id, parent_id, position):
    by_id = {item.id: item for item in items}
    item = by_id.get(item_id)
    if item is None:
        raise ValueError("检查项不属于当前模板")
    ancestor = parent_id
    visited = {item_id}
    while ancestor is not None:
        if ancestor in visited:
            raise ValueError("不能将节点移动到自己或其子节点下")
        visited.add(ancestor)
        parent = by_id.get(ancestor)
        if parent is None:
            raise ValueError("父节点不属于当前模板")
        ancestor = parent.parent_id
    old_parent = item.parent_id
    ordered = sorted(items, key=lambda node: (node.sort_order or 0, str(node.id)))
    siblings = [node for node in ordered if node.parent_id == parent_id and node.id != item_id]
    siblings.insert(min(position, len(siblings)), item)
    item.parent_id = parent_id
    for index, sibling in enumerate(siblings):
        sibling.sort_order = index
    if old_parent != parent_id:
        for index, sibling in enumerate(node for node in ordered if node.parent_id == old_parent):
            sibling.sort_order = index
    return by_id.get(parent_id)
