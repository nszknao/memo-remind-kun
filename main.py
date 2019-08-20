import os
import requests
import json
import datetime
from linebot import (
  LineBotApi, WebhookHandler
)
from linebot.exceptions import (
  InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
)
from google.cloud import firestore
from google.oauth2 import id_token
from google.auth import transport

db = firestore.Client()
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])


def _auth(bearer_token):
    token = bearer_token.split(' ')[1]
    # Verify and decode the JWT. `verify_oauth2_token` verifies
    # the JWT signature, the `aud` claim, and the `exp` claim.
    claim = id_token.verify_oauth2_token(token, transport.requests.Request())

    if claim['email'] != os.environ['GCP_APP_ENGINE_DEFAULT_SERVICE_ACCOUNT']:
        raise ValueError('Wrong service account.')

def callback(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.
    """
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature. Please check your channel access token/channel secret.", 400

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    message_sent_time = datetime.datetime.fromtimestamp(event.timestamp/1000)

    batch = db.batch()
    # create memo
    memo_ref = db.collection('memos').document()
    batch.set(memo_ref, {
        "userId": event.source.user_id,
        "text": event.message.text,
        "created_at": message_sent_time
    })
    # if exists user
    user_ref = db.collection('users').document(event.source.user_id)
    if not user_ref.get().exists:
        batch.set(user_ref, {
            "created_at": message_sent_time
        })
    # if exists today's memo
    user_memo_ref = user_ref.collection('memos').document(message_sent_time.strftime('%Y-%m-%d'))
    if not user_memo_ref.get().exists:
        batch.create(
            user_ref.collection('memos').document(message_sent_time.strftime("%Y-%m-%d")),
            { memo_ref.id: memo_ref }
        )
    else:
        batch.set(
            user_memo_ref,
            { memo_ref.id: memo_ref },
            merge=True
        )
    batch.commit()
    # completion message
    access_token = db.collection('config').document('access_token').get().to_dict()['access_token']
    line_bot_api = LineBotApi(access_token)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="登録しました。")
    )

def remind(request):
    # TODO: テキストの整形
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
        _auth(bearer_token)
    except Exception as e:
        return 'Invalid token', 400

    access_token = db.collection('config').document('access_token').get().to_dict()['access_token']
    line_bot_api = LineBotApi(access_token)

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

    return 'OK'

def renew(request):
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
        _auth(bearer_token)
    except Exception as e:
        return 'Invalid token', 400

    payload = {
        'grant_type': 'client_credentials',
        'client_id': os.environ['LINE_CHANNEL_ID'],
        'client_secret': os.environ['LINE_CHANNEL_SECRET']
    }
    res = requests.post(
        'https://api.line.me/v2/oauth/accessToken',
        data=payload,
    )
    body = res.json()
    body['updated_at'] = datetime.datetime.now()
    db.collection('config').document('access_token').update(body)

    return 'OK'
