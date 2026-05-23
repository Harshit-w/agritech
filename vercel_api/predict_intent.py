import json

def handler(request):
    try:
        body = request.json() if callable(getattr(request, 'json', None)) else json.loads(request.body.decode())
    except Exception:
        body = {}
    try:
        from ml_service.intent import classify_intent
        text = body.get('text', '')
        lang = body.get('language', 'en')
        r = classify_intent(text, language=lang)
        return {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(r)}
    except Exception as e:
        return {"statusCode": 503, "headers": {"Content-Type": "application/json"}, "body": json.dumps({"error":"intent_unavailable","detail": str(e)})}
