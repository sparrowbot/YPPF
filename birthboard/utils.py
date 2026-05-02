MODE_COST = [35, 60, 1000]
MIN_COST_PER_SENDER = 2


def calculate_per_cost(mode: int, sender_count: int) -> int:
    """根据投放模式和送出人数计算每人扣费。"""
    if mode < 0 or mode >= len(MODE_COST):
        mode = 0
    if sender_count <= 0:
        sender_count = 1
    per = MODE_COST[mode] // sender_count
    if per < MIN_COST_PER_SENDER:
        per = MIN_COST_PER_SENDER
    return per