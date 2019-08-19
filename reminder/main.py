import os
import datetime
from linebot import LineBotApi
from google.cloud import firestore
from google.oauth2 import id_token
from google.auth.transport import requests
from linebot.models import TextSendMessage

line_bot_api = LineBotApi(os.environ['LINE_ACCESS_TOKEN'])

db = firestore.Client()


def remind(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    # Auth
    try:
        # Get the Cloud Scheduler-generated JWT in the "Authorization" header.
        bearer_token = request.headers.get('Authorization')
        token = bearer_token.split(' ')[1]
        # Verify and decode the JWT. `verify_oauth2_token` verifies
        # the JWT signature, the `aud` claim, and the `exp` claim.
        claim = id_token.verify_oauth2_token(token, requests.Request())

        if claim['email'] != os.environ['GCP_APP_ENGINE_DEFAULT_SERVICE_ACCOUNT']:
            raise ValueError('Wrong service account.')
    except Exception as e:
        return 'Invalid token', 400

    today = datetime.datetime.now().strftime('%Y-%m-%d')
    for user_snap in db.collection('users').stream():
        today_memo_snap = db.collection('users').document(user_snap.id).collection('memos').document(today).get()
        if today_memo_snap.exists:
            remind_memo = ''
            today_memo_dict = today_memo_snap.to_dict()
            for memo_ref in today_memo_dict.values():
                remind_memo += memo_ref.get().to_dict()['text']
            # remind
            line_bot_api.push_message(
                user_snap.id,
                TextSendMessage(text=remind_memo)
            )
