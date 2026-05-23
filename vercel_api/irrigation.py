import json

def handler(request):
    try:
        from services.irrigation import get_zones, update_zone
    except Exception as e:
        return {
            "statusCode": 503,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "irrigation_unavailable", "detail": str(e)}),
        }

    method = request.method.upper() if hasattr(request, 'method') else 'GET'
    path = getattr(request, 'path', '')

    if method == 'GET':
        zones = get_zones()
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(zones)}

    if method == 'POST':
        try:
            payload = request.json() if callable(getattr(request, 'json', None)) else {}
        except Exception:
            try:
                payload = json.loads(request.body.decode())
            except Exception:
                payload = {}
        zone_id = payload.get('zone_id')
        data = payload.get('data', {})
        if not zone_id:
            return {"statusCode": 400, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error":"missing_zone_id"})}
        res = update_zone(zone_id, data)
        if res is None:
            return {"statusCode": 404, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error":"zone_not_found"})}
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(res)}

    return {"statusCode": 405, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error":"method_not_allowed"})}
