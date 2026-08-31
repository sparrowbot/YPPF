from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from app.models import User
from birthboard.models import BirthboardRecord
from birthboard.utils import calculate_per_cost

@csrf_protect
@login_required(redirect_field_name='origin')
@require_POST
    """
    前端传递 senders（用户名列表）和 record_id 或 mode，返回每个用户当前余额和是否足够。
    若提供 record_id，则优先按记录中的 per_cost 作为所需值。
    """
    import json
    try:
        data = json.loads(request.body.decode())
        senders = data.get('senders', [])
        record_id = data.get('record_id')

        per = None
        if record_id is not None:
            try:
                record_id = int(record_id)
                record = BirthboardRecord.objects.filter(id=record_id).only('per_cost').first()
                if record:
                    per = int(record.per_cost)
            except (TypeError, ValueError):
                per = None

        if per is None:
            mode = int(data.get('mode', 0))
            sender_count = data.get('sender_count', None)
            try:
                sender_count = int(sender_count)
            except (TypeError, ValueError):
                sender_count = None
            divisor = sender_count if sender_count and sender_count > 0 else max(len(senders), 1)
            per = calculate_per_cost(mode, divisor)

        users = User.objects.filter(username__in=senders)
        result = {}
        for u in users:
            result[u.username] = {
                'balance': u.YQpoint,
                'enough': u.YQpoint >= per,
                'need': per
            }
        # 补全不存在的用户
        for s in senders:
            if s not in result:
                result[s] = {'balance': 0, 'enough': False, 'need': per}
        return JsonResponse({'ok': True, 'result': result})
    except Exception as e:
        return JsonResponse({'ok': False, 'msg': str(e)})
