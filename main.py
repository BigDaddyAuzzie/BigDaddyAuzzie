import os
import json
import requests
from flask import Flask, render_template, request, redirect, url_for, session
import openai

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'secret-key')
openai.api_key = os.getenv('OPENAI_API_KEY')

rsi_data = {
    'BTC': 40,
    'ETH': 60,
    'ADA': 55,
    'SOL': 30,
}

SYSTEM_PROMPT = (
    "You are a smart and calm AI crypto trader. "
    "Answer concisely and use markdown when helpful."
)


@app.route('/')
def index():
    if 'messages' not in session:
        session['messages'] = [{'role': 'system', 'content': 'Welcome to the trading terminal.'}]
    return render_template('index.html', messages=session['messages'])


def call_openai(user_msg):
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    for m in session.get('messages', []):
        if m['role'] != 'system':
            messages.append({'role': m['role'], 'content': m['content']})
    messages.append({'role': 'user', 'content': user_msg})
    rsi_json = json.dumps(rsi_data)
    messages.append({'role': 'system', 'content': f'Current RSI data: {rsi_json}'})
    try:
        res = openai.ChatCompletion.create(
            model='gpt-4o',
            messages=messages,
        )
        reply = res.choices[0].message.content
        return reply
    except Exception as e:
        return f"Error communicating with GPT: {e}"


def send_trade(pair):
    url = 'https://app.3commas.io/trade_signal/trading_view'
    payload = {
        'message_type': 'bot',
        'bot_id': int(os.getenv('BOT_ID', '0')),
        'email_token': os.getenv('EMAIL_TOKEN', ''),
        'delay_seconds': 0,
        'pair': pair,
    }
    try:
        r = requests.post(url, json=payload)
        r.raise_for_status()
        return True
    except Exception as e:
        session['messages'].append({'role': 'system', 'content': f'Error sending trade: {e}'})
        return False


def send_telegram(text):
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    try:
        requests.post(url, data={'chat_id': chat_id, 'text': text})
    except Exception:
        pass


@app.route('/chat', methods=['POST'])
def chat():
    msg = request.form.get('message')
    if not msg:
        return redirect(url_for('index'))
    session.setdefault('messages', []).append({'role': 'user', 'content': msg})

    reply = call_openai(msg)
    session['messages'].append({'role': 'system', 'content': reply})

    # Look for trading pair in reply like USD_TOKEN
    pair = None
    for word in reply.split():
        if word.startswith('USD_'):
            pair = word
            break
    if pair:
        if send_trade(pair):
            confirm = f'Trade sent for {pair}'
            session['messages'].append({'role': 'system', 'content': confirm})
            send_telegram(confirm)

    session.modified = True
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
