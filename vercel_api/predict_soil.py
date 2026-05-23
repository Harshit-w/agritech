import json

def handler(request):
    try:
        body = request.json() if callable(getattr(request, 'json', None)) else json.loads(request.body.decode())
    except Exception:
        body = {}
    try:
        from ml_service.soil import analyze_soil
        # Expecting parameters: nitrogen, phosphorus, potassium, ph_level, organic_matter
        params = [body.get('nitrogen', 70), body.get('phosphorus', 35), body.get('potassium', 150), body.get('ph_level', 6.5), body.get('organic_matter', 2.5)]
        r = analyze_soil(*params)
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(r)}
    except Exception as e:
        return {"statusCode": 503, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error":"soil_unavailable","detail": str(e)})}
