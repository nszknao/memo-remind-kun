import base64
import hashlib
import hmac
import os
import datetime
from flask import Flask, abort
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

# TODO: access tokenはDB管理、バッチで更新
line_bot_api = LineBotApi(os.environ['LINE_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])

db = firestore.Client()


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
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    """
        TODO: Transaction
    """
    message_sent_time = datetime.datetime.fromtimestamp(event.timestamp)
    # create memo
    _, memo_ref = db.collection('memos').add({
        "userId": event.source.user_id,
        "text": event.message.text,
        "created_at": message_sent_time
    })
    # if exists user
    user_ref = db.collection('users').document(event.source.user_id)
    if not user_ref.get().exists:
        user_ref.create({
            "created_at": message_sent_time
        })
    # if exists today's memo
    user_memo_ref = user_ref.collection('memos').document(message_sent_time.strftime('%Y-%m-%d'))
    if not user_memo_ref.get().exists:
        user_ref.collection('memos').add(
            document_data={
                memo_ref.id: memo_ref
            },
            document_id=message_sent_time.strftime("%Y-%m-%d")
        )
    else:
        user_memo_ref.set(
            document_data={
                memo_ref.id: memo_ref
            },
            merge=True
        )
    # completion message
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="登録しました。")
    )
