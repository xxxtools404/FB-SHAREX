from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests, os, re, json, time, random, threading
from datetime import datetime
from time import sleep
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Change in production

# Global variables (use DB in production)
tokens = []
cookies_list = []
logs = []
event_settings = {'event': 'none', 'greeting': 'Welcome to ShareBooster!'}
premium_key = 'vina'
admin_username = 'vina'
admin_password = 'vinababy'
user_trials = {}  # Track trials by IP

ses = requests.Session()
ua_list = [
    "Mozilla/5.0 (Linux; Android 10; Wildfire E Lite Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/105.0.5195.136 Mobile Safari/537.36[FBAN/EMA;FBLC/en_US;FBAV/298.0.0.10.115;]",
    "Mozilla/5.0 (Linux; Android 11; KINGKONG 5 Pro Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/87.0.4280.141 Mobile Safari/537.36[FBAN/EMA;FBLC/fr_FR;FBAV/320.0.0.12.108;]",
    "Mozilla/5.0 (Linux; Android 11; G91 Pro Build/RP1A.200720.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/106.0.5249.126 Mobile Safari/537.36[FBAN/EMA;FBLC/fr_FR;FBAV/325.0.1.4.108;]"
]
ua = random.choice(ua_list)

def load_data():
    global tokens, cookies_list
    try:
        with open("tokens.txt", "r") as f:
            tokens = json.load(f)
        with open("cookies.txt", "r") as f:
            cookies_list = json.load(f)
    except:
        tokens = []
        cookies_list = []

def save_data():
    with open("tokens.txt", "w") as f:
        json.dump(tokens, f)
    with open("cookies.txt", "w") as f:
        json.dump(cookies_list, f)

def share_post(token, cookie, link, n, start_time, delay=0):
    sleep(delay / 1000)
    try:
        post = ses.post(
            f"https://graph.facebook.com/v13.0/me/feed?link={link}&published=0&access_token={token}",
            headers={
                "authority": "graph.facebook.com",
                "cache-control": "max-age=0",
                "sec-ch-ua-mobile": "?0",
                "user-agent": ua
            }, cookies=cookie, timeout=10
        ).text
        data = json.loads(post)
        if "id" in data:
            elapsed = str(datetime.now() - start_time).split('.')[0]
            logs.append(f"Share {n} successful ({elapsed})")
            return True
        else:
            logs.append(f"Share {n} failed: {data}")
            return False
    except Exception as e:
        logs.append(f"Share {n} error: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html', event=event_settings)

@app.route('/share')
def share():
    return render_template('share.html', event=event_settings)

@app.route('/admin')
def admin():
    if 'admin' in session:
        return render_template('admin.html', logs=logs, key=premium_key, event=event_settings)
    return redirect(url_for('admin_login'))

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == admin_username and password == admin_password:
            session['admin'] = True
            return redirect(url_for('admin'))
        return "Invalid credentials"
    return render_template('admin_login.html')

@app.route('/admin_logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))

@app.route('/tutorial')
def tutorial():
    return render_template('tutorial.html')

@app.route('/api/share', methods=['POST'])
def api_share():
    data = request.json
    mode = data['mode']
    link = data['link']
    limit = int(data['limit'])
    delay = int(data.get('delay', 0)) if mode == 'normal' else 0
    user_ip = request.remote_addr

    if not tokens:
        return jsonify({'error': 'No valid cookies. Please set up in admin.'})

    if mode == 'premium':
        if user_ip not in user_trials:
            user_trials[user_ip] = 0
        if user_trials[user_ip] >= 3 and data.get('key') != premium_key:
            return jsonify({'error': 'Premium key required after 3 trials.'})
        user_trials[user_ip] += 1

    start_time = datetime.now()
    chunk_size = 40
    cooldown = 10

    with ThreadPoolExecutor(max_workers=50) as executor:
        n = 1
        while n <= limit:
            futures = []
            for _ in range(min(chunk_size, limit - n + 1)):
                token = random.choice(tokens)
                cookie = cookies_list[tokens.index(token)]
                futures.append(executor.submit(share_post, token, cookie, link, n, start_time, delay))
                n += 1
            for future in as_completed(futures):
                pass
            if n <= limit and mode == 'premium':
                logs.append(f"Cooldown for {cooldown} seconds after {n-1} shares...")
                sleep(cooldown)

    return jsonify({'message': 'Sharing completed!'})

@app.route('/api/admin/update_key', methods=['POST'])
def update_key():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'})
    global premium_key
    premium_key = request.json['key']
    return jsonify({'message': 'Key updated'})

@app.route('/api/admin/update_event', methods=['POST'])
def update_event():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'})
    global event_settings
    event_settings = request.json
    return jsonify({'message': 'Event updated'})

@app.route('/api/admin/clear_logs', methods=['POST'])
def clear_logs():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'})
    logs.clear()
    return jsonify({'message': 'Logs cleared'})

@app.route('/api/admin/set_cookies', methods=['POST'])
def set_cookies():
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'})
    global tokens, cookies_list
    cookies_input = request.json['cookies']
    tokens = []
    cookies_list = []
    for cookie_str in cookies_input:
        cookies = {j.split("=")[0]: j.split("=")[1] for j in cookie_str.split("; ") if "=" in j}
        try:
            data = ses.get("https://business.facebook.com/business_locations", headers={"user-agent": ua}, cookies=cookies, timeout=10)
            find_token = re.search(r"(EAAG\w+)", data.text)
            if find_token:
                tokens.append(find_token.group(1))
                cookies_list.append(cookies)
        except:
            pass
    save_data()
    return jsonify({'message': f'{len(tokens)} tokens loaded'})

@app.route('/api/logs')
def api_logs():
    return jsonify(logs[-10:])

if __name__ == '__main__':
    load_data()
    app.run(debug=True)