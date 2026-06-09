import telebot
import sqlite3
import threading
import requests
import json
import time
from pathlib import Path
from datetime import datetime
import queue
import random
from urllib.parse import quote
import re
import urllib3
import warnings

# ==================== SUPPRESS WARNINGS ====================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

# Bot Configuration
BOT_TOKEN = "8651402670:AAFIOsiDYCJk0G6dAVEc7gz5lW9E7C04XH0"
bot = telebot.TeleBot(BOT_TOKEN)

# Database Setup
DB_PATH = "facebook_checker.db"
UPLOAD_FOLDER = "uploads"
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)

# Global Variables
user_threads = {}
checking_queue = queue.Queue()
is_checking = {}
should_stop = {}
live_stats = {}
db_lock = threading.Lock()

# User Agent List
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59",
    "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; PPC Mac OS X 10_5_8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-S906B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36"
]

# Database Initialization
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                phone_number TEXT,
                status TEXT DEFAULT 'unchecked',
                has_id INTEGER DEFAULT 0,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                checked_at TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                thread_count INTEGER DEFAULT 20,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        pass

init_db()

# ==================== DATABASE FUNCTIONS ====================

def save_numbers_to_db(user_id, phone_numbers):
    """টেক্সট ফাইল থেকে নম্বর ডাটাবেসে সেভ করবে"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            
            count = 0
            for number in phone_numbers:
                number = number.strip()
                if number:
                    cursor.execute('''
                        INSERT INTO numbers (user_id, phone_number, status)
                        VALUES (?, ?, 'unchecked')
                    ''', (user_id, number))
                    count += 1
            
            conn.commit()
            conn.close()
            return count
    except Exception as e:
        return 0

def get_unchecked_numbers(user_id):
    """সমস্ত unchecked নম্বর fetch করবে"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, phone_number FROM numbers 
                WHERE user_id = ? AND status = 'unchecked'
                ORDER BY id
            ''', (user_id,))
            results = cursor.fetchall()
            conn.close()
            return results
    except Exception as e:
        return []

def update_number_status(number_id, has_id):
    """নম্বরের স্ট্যাটাস আপডেট করবে"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE numbers 
                SET status = 'checked', has_id = ?, checked_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (has_id, number_id))
            conn.commit()
            conn.close()
    except Exception as e:
        pass

def get_checked_numbers(user_id, has_id=None):
    """Checked নম্বর গুলো fetch করবে (Fresh/Unfresh)"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            
            if has_id is None:
                cursor.execute('''
                    SELECT phone_number FROM numbers 
                    WHERE user_id = ? AND status = 'checked'
                    ORDER BY id
                ''', (user_id,))
            else:
                cursor.execute('''
                    SELECT phone_number FROM numbers 
                    WHERE user_id = ? AND status = 'checked' AND has_id = ?
                    ORDER BY id
                ''', (user_id, has_id))
            
            results = [row[0] for row in cursor.fetchall()]
            conn.close()
            return results
    except Exception as e:
        return []

def get_all_numbers(user_id):
    """সব নম্বর fetch করবে"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT phone_number FROM numbers 
                WHERE user_id = ?
                ORDER BY id
            ''', (user_id,))
            results = [row[0] for row in cursor.fetchall()]
            conn.close()
            return results
    except Exception as e:
        return []

def delete_all_numbers(user_id):
    """সব নম্বর ডিলিট করবে"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM numbers WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
    except Exception as e:
        pass

def delete_checked_numbers(user_id):
    """শুধু চেক করা নম্বর ডিলিট করবে"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM numbers WHERE user_id = ? AND status = "checked"', (user_id,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            return deleted
    except Exception as e:
        return 0

def delete_unchecked_numbers(user_id):
    """শুধু আনচেক করা নম্বর ডিলিট করবে"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM numbers WHERE user_id = ? AND status = "unchecked"', (user_id,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            return deleted
    except Exception as e:
        return 0

def get_stats(user_id):
    """বর্তমান স্ট্যাট পান"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM numbers WHERE user_id = ? AND status = "checked" AND has_id = 1', (user_id,))
            with_id = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM numbers WHERE user_id = ? AND status = "checked" AND has_id = 0', (user_id,))
            without_id = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM numbers WHERE user_id = ? AND status = "checked"', (user_id,))
            total_checked = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM numbers WHERE user_id = ?', (user_id,))
            total = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'with_id': with_id,
                'without_id': without_id,
                'total_checked': total_checked,
                'total': total,
                'remaining': total - total_checked
            }
    except Exception as e:
        return {'with_id': 0, 'without_id': 0, 'total_checked': 0, 'total': 0, 'remaining': 0}

def get_user_thread_count(user_id):
    """ইউজারের থ্রেড কাউন্ট পান"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            cursor.execute('SELECT thread_count FROM user_settings WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0]
            return 20
    except Exception as e:
        return 20

def set_user_thread_count(user_id, thread_count):
    """ইউজারের থ্রেড কাউন্ট সেট করুন"""
    try:
        with db_lock:
            conn = sqlite3.connect(DB_PATH, timeout=10)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_settings (user_id, thread_count, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, thread_count))
            conn.commit()
            conn.close()
    except Exception as e:
        pass

# ==================== USER AGENT FUNCTION ====================

def get_random_user_agent():
    """প্রতিবার নতুন User-Agent generate করবে"""
    return random.choice(USER_AGENTS)

# ==================== FACEBOOK CHECK FUNCTION ====================

def check_facebook_number(phone_number):
    """Advanced Facebook নম্বর চেক - fb.com এর limited server থেকে"""
    try:
        user_agent = get_random_user_agent()
        
        url = "https://www.fb.com/login/identify"
        
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.fb.com/',
            'Origin': 'https://www.fb.com'
        }
        
        params = {
            'ctx': 'recover',
            'q': phone_number
        }
        
        session = requests.Session()
        response = session.get(url, params=params, headers=headers, timeout=15, verify=False)
        
        response_text = response.text.lower()
        
        has_id_indicators = [
            'identifier',
            'profile',
            'account',
            'found',
            'user_id',
            'uid',
            '"id"',
            'name":',
            'picture',
            'phone_number_warning',
            'facebook_id',
            'account_found',
            'recovery_code'
        ]
        
        found_id = False
        for indicator in has_id_indicators:
            if indicator in response_text:
                found_id = True
                break
        
        return found_id
        
    except:
        return False

# ==================== LIVE DASHBOARD ====================

def create_live_dashboard(user_id, stats):
    """লাইভ ড্যাশবোর্ড টেবিল তৈরি করবে"""
    
    with_id = stats['with_id']
    without_id = stats['without_id']
    total_checked = stats['total_checked']
    total = stats['total']
    remaining = stats['remaining']
    
    if total > 0:
        progress = (total_checked / total) * 100
    else:
        progress = 0
    
    filled = int(progress / 5)
    empty = 20 - filled
    progress_bar = "█" * filled + "░" * empty
    
    dashboard = (
        f"╔════════════════════════════════════════╗\n"
        f"║    📊 LIVE CHECKING DASHBOARD 📊     ║\n"
        f"╠════════════════════════════════════════╣\n"
        f"║ 🟢 ID FOUND (Fresh)    : {with_id:>8}     ║\n"
        f"║ 🔴 NO ID (Unfresh)    : {without_id:>8}     ║\n"
        f"║ ✓ Total Checked       : {total_checked:>8}     ║\n"
        f"║ ⏳ Remaining          : {remaining:>8}     ║\n"
        f"║ 📈 Total Numbers      : {total:>8}     ║\n"
        f"╠════════════════════════════════════════╣\n"
        f"║ 📊 Progress: {progress_bar} {progress:.1f}%  ║\n"
        f"╚════════════════════════════════════════╝"
    )
    
    return dashboard

# ==================== TELEGRAM BOT COMMANDS ====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """শুরু করার কমান্ড"""
    user_id = message.chat.id
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        telebot.types.KeyboardButton("📤 Upload"),
        telebot.types.KeyboardButton("✅ Check"),
        telebot.types.KeyboardButton("📊 Statistics"),
        telebot.types.KeyboardButton("⚙️ Settings"),
        telebot.types.KeyboardButton("📥 Download"),
        telebot.types.KeyboardButton("🗑️ Manage Data")
    )
    
    bot.send_message(
        user_id,
        "🎉 *Facebook Checker Bot v3.3*\n\n"
        "আমি আপনার Facebook নম্বরগুলি চেক করতে পারি।\n"
        "প্রতিটি চেক এ নতুন User-Agent ব্যবহার করব।\n"
        "লাইভ ড্যাশবোর্ড সহ রিয়েল টাইম আপডেট!\n\n"
        "নিচের বাটন গুলি ব্যবহার করুন:",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == "📤 Upload")
def handle_upload(message):
    """আপলোড অপশন"""
    user_id = message.chat.id
    bot.send_message(
        user_id,
        "📄 আপনার টেক্সট ফাইল পাঠান।\n"
        "ফাইলে প্রতিটি লাইনে একটি নম্বর থাকবে।\n\n"
        "উদাহরণ:\n```\n+8801700000001\n+8801700000002\n8801700000003\n```",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, process_file_upload)

def process_file_upload(message):
    """ফাইল আপলোড প্রসেস করবে"""
    user_id = message.chat.id
    
    try:
        if message.document:
            file_info = bot.get_file(message.document.file_id)
            file_path = file_info.file_path
            
            file_content = bot.download_file(file_path)
            
            local_file = f"{UPLOAD_FOLDER}/{user_id}_{message.document.file_name}"
            with open(local_file, 'wb') as f:
                f.write(file_content)
            
            with open(local_file, 'r', encoding='utf-8') as f:
                numbers = f.readlines()
            
            count = save_numbers_to_db(user_id, numbers)
            
            stats = get_stats(user_id)
            bot.send_message(
                user_id,
                f"✅ সফল!\n\n"
                f"📊 {count} টি নম্বর যোগ হয়েছে।\n"
                f"📈 মোট নম্বর: {stats['total']}",
                parse_mode='Markdown'
            )
        else:
            bot.send_message(user_id, "❌ দয়া করে একটি ফাইল পাঠান।")
            
    except Exception as e:
        bot.send_message(user_id, f"❌ ত্রুটি: {str(e)}")

@bot.message_handler(func=lambda message: message.text == "📊 Statistics")
def show_statistics(message):
    """স্ট্যাটিস্টিক্স দেখাবে"""
    user_id = message.chat.id
    stats = get_stats(user_id)
    
    if stats['total'] == 0:
        bot.send_message(user_id, "❌ এখনো কোনো নম্বর আপলোড করা হয়নি।")
        return
    
    dashboard = create_live_dashboard(user_id, stats)
    bot.send_message(
        user_id,
        f"```\n{dashboard}\n```",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == "⚙️ Settings")
def handle_thread_setup(message):
    """থ্রেড সেটআপ"""
    user_id = message.chat.id
    current_threads = get_user_thread_count(user_id)
    
    bot.send_message(
        user_id,
        f"🔧 *থ্রেড সেটআপ*\n\n"
        f"বর্তমান থ্রেড সংখ্যা: *{current_threads}*\n\n"
        f"নতুন থ্রেড সংখ্যা দিন (10-200):",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, process_thread_setup)

def process_thread_setup(message):
    """থ্রেড সংখ্যা সেট করবে"""
    user_id = message.chat.id
    
    try:
        thread_count = int(message.text)
        
        if 10 <= thread_count <= 200:
            set_user_thread_count(user_id, thread_count)
            bot.send_message(
                user_id,
                f"✅ থ্রেড সেটআপ সফল!\n"
                f"নতুন থ্রেড সংখ্যা: *{thread_count}*",
                parse_mode='Markdown'
            )
        else:
            bot.send_message(user_id, "❌ দয়া করে 10-200 এর মধ্যে একটি সংখ্যা দিন।")
            
    except ValueError:
        bot.send_message(user_id, "❌ দয়া করে একটি সংখ্যা দিন।")

@bot.message_handler(func=lambda message: message.text == "✅ Check")
def handle_check_numbers(message):
    """নম্বর চেক করা শুরু করবে"""
    user_id = message.chat.id
    
    unchecked = get_unchecked_numbers(user_id)
    
    if not unchecked:
        bot.send_message(user_id, "❌ কোনো নম্বর চেক করার নেই।")
        return
    
    if is_checking.get(user_id):
        bot.send_message(user_id, "⏳ চেকিং ইতিমধ্যে চলছে।")
        return
    
    is_checking[user_id] = True
    should_stop[user_id] = False
    thread_count = get_user_thread_count(user_id)
    total = len(unchecked)
    
    live_stats[user_id] = {
        'start_time': time.time(),
        'total': total,
        'checked': 0,
        'fresh': 0,
        'unfresh': 0
    }
    
    bot.send_message(
        user_id,
        f"🚀 চেকিং শুরু হয়েছে!\n\n"
        f"📊 মোট নম্বর: {total}\n"
        f"🔄 থ্রেড সংখ্যা: {thread_count}\n"
        f"🔀 প্রতিটি চেক এ নতুন User-Agent\n\n"
        f"⏳ এটি কিছু সময় নিতে পারে...",
        parse_mode='Markdown'
    )
    
    dashboard_msg = bot.send_message(
        user_id,
        "```\n" + create_live_dashboard(user_id, get_stats(user_id)) + "\n```",
        parse_mode='Markdown'
    )
    dashboard_msg_id = dashboard_msg.message_id
    
    # Stop/Start বাটন
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("⏸️ Stop Checking", callback_data=f"stop_check_{user_id}"),
        telebot.types.InlineKeyboardButton("🔄 Resume", callback_data=f"resume_check_{user_id}")
    )
    
    control_msg = bot.send_message(
        user_id,
        "চেকিং নিয়ন্ত্রণ:",
        reply_markup=markup
    )
    
    checked_count = [0]
    lock = threading.Lock()
    
    def thread_worker():
        while True:
            try:
                if should_stop.get(user_id):
                    time.sleep(1)
                    continue
                
                number_id, phone_number = checking_queue.get(timeout=1)
                
                has_id = 1 if check_facebook_number(phone_number) else 0
                update_number_status(number_id, has_id)
                
                with lock:
                    checked_count[0] += 1
                
                checking_queue.task_done()
                time.sleep(0.2)
                
            except queue.Empty:
                break
            except Exception as e:
                pass
    
    for number_id, phone_number in unchecked:
        checking_queue.put((number_id, phone_number))
    
    threads = []
    for _ in range(thread_count):
        t = threading.Thread(target=thread_worker, daemon=True)
        t.start()
        threads.append(t)
    
    update_interval = 0.1
    last_update = time.time()
    
    while checked_count[0] < total:
        if should_stop.get(user_id):
            time.sleep(1)
            continue
        
        current_time = time.time()
        
        if current_time - last_update >= 3:
            try:
                stats = get_stats(user_id)
                dashboard_text = create_live_dashboard(user_id, stats)
                bot.edit_message_text(
                    text="```\n" + dashboard_text + "\n```",
                    chat_id=user_id,
                    message_id=dashboard_msg_id,
                    parse_mode='Markdown'
                )
                last_update = current_time
            except:
                pass
        
        time.sleep(0.5)
    
    checking_queue.join()
    is_checking[user_id] = False
    should_stop[user_id] = False
    
    final_stats = get_stats(user_id)
    final_dashboard = create_live_dashboard(user_id, final_stats)
    
    bot.send_message(
        user_id,
        f"✅ চেকিং সম্পন্ন!\n\n"
        f"```\n{final_dashboard}\n```",
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: "stop_check_" in call.data)
def stop_checking(call):
    """চেকিং থামাবে"""
    user_id = int(call.data.split("_")[-1])
    should_stop[user_id] = True
    bot.answer_callback_query(call.id, "⏸️ চেকিং থেমে গেছে")

@bot.callback_query_handler(func=lambda call: "resume_check_" in call.data)
def resume_checking(call):
    """চেকিং চালু করবে"""
    user_id = int(call.data.split("_")[-1])
    should_stop[user_id] = False
    bot.answer_callback_query(call.id, "▶️ চেকিং শুরু হয়েছে")

@bot.message_handler(func=lambda message: message.text == "📥 Download")
def handle_download(message):
    """ডাউনলোড অপশন"""
    user_id = message.chat.id
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        telebot.types.KeyboardButton("🟢 Fresh Numbers"),
        telebot.types.KeyboardButton("🔴 Unfresh Numbers"),
        telebot.types.KeyboardButton("📋 All Numbers"),
        telebot.types.KeyboardButton("🔙 Back")
    )
    
    bot.send_message(
        user_id,
        "📥 কোনটি ডাউনলোড করবেন?",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "🟢 Fresh Numbers")
def download_fresh(message):
    """Fresh নম্বর ডাউনলোড করবে"""
    user_id = message.chat.id
    
    numbers = get_checked_numbers(user_id, 1)
    
    if not numbers:
        bot.send_message(user_id, "❌ কোনো Fresh নম্বর পাওয়া যায়নি।")
        return
    
    filename = f"{UPLOAD_FOLDER}/fresh_{user_id}_{int(time.time())}.txt"
    with open(filename, 'w') as f:
        for number in numbers:
            f.write(number + '\n')
    
    with open(filename, 'rb') as f:
        bot.send_document(
            user_id,
            f,
            caption=f"🟢 Fresh Numbers (ID আছে)\n\n"
                   f"মোট: {len(numbers)} টি"
        )
    
    Path(filename).unlink()
    send_welcome(message)

@bot.message_handler(func=lambda message: message.text == "🔴 Unfresh Numbers")
def download_unfresh(message):
    """Unfresh নম্বর ডাউনলোড করবে"""
    user_id = message.chat.id
    
    numbers = get_checked_numbers(user_id, 0)
    
    if not numbers:
        bot.send_message(user_id, "❌ কোনো Unfresh নম্বর পাওয়া যায়নি।")
        return
    
    filename = f"{UPLOAD_FOLDER}/unfresh_{user_id}_{int(time.time())}.txt"
    with open(filename, 'w') as f:
        for number in numbers:
            f.write(number + '\n')
    
    with open(filename, 'rb') as f:
        bot.send_document(
            user_id,
            f,
            caption=f"🔴 Unfresh Numbers (ID নেই)\n\n"
                   f"মোট: {len(numbers)} টি"
        )
    
    Path(filename).unlink()
    send_welcome(message)

@bot.message_handler(func=lambda message: message.text == "📋 All Numbers")
def download_all(message):
    """সব নম্বর ডাউনলোড করবে"""
    user_id = message.chat.id
    
    numbers = get_all_numbers(user_id)
    
    if not numbers:
        bot.send_message(user_id, "❌ কোনো নম্বর পাওয়া যায়নি।")
        return
    
    filename = f"{UPLOAD_FOLDER}/all_{user_id}_{int(time.time())}.txt"
    with open(filename, 'w') as f:
        for number in numbers:
            f.write(number + '\n')
    
    with open(filename, 'rb') as f:
        bot.send_document(
            user_id,
            f,
            caption=f"📋 সব Numbers\n\n"
                   f"মোট: {len(numbers)} টি"
        )
    
    Path(filename).unlink()
    send_welcome(message)

@bot.message_handler(func=lambda message: message.text == "🗑️ Manage Data")
def handle_manage_data(message):
    """ডাটা ম্যানেজমেন্ট অপশন"""
    user_id = message.chat.id
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        telebot.types.KeyboardButton("🔄 Replace All Numbers"),
        telebot.types.KeyboardButton("🗑️ Delete All Numbers"),
        telebot.types.KeyboardButton("❌ Delete Checked Only"),
        telebot.types.KeyboardButton("⚠️ Delete Unchecked Only"),
        telebot.types.KeyboardButton("🔙 Back")
    )
    
    stats = get_stats(user_id)
    
    bot.send_message(
        user_id,
        f"🗑️ *ডাটা ম্যানেজমেন্ট*\n\n"
        f"📊 বর্তমান স্ট্যাটাস:\n"
        f"• মোট নম্বর: {stats['total']}\n"
        f"• চেক করা: {stats['total_checked']}\n"
        f"• চেক না করা: {stats['remaining']}\n\n"
        f"নিচে থেকে একটি অপশন বেছে নিন:",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == "🔄 Replace All Numbers")
def handle_replace_numbers(message):
    """সব নম্বর রিপ্লেস করবে"""
    user_id = message.chat.id
    
    bot.send_message(
        user_id,
        "📄 নতুন নম্বর ফাইল পাঠান।\n\n"
        "⚠️ সব পুরোনো নম্বর ডিলিট হয়ে যাবে এবং নতুন নম্বর যুক্ত হবে।",
        parse_mode='Markdown'
    )
    bot.register_next_step_handler(message, process_replace_numbers)

def process_replace_numbers(message):
    """সব নম্বর রিপ্লেস করবে"""
    user_id = message.chat.id
    
    try:
        if message.document:
            delete_all_numbers(user_id)
            
            file_info = bot.get_file(message.document.file_id)
            file_path = file_info.file_path
            file_content = bot.download_file(file_path)
            
            local_file = f"{UPLOAD_FOLDER}/{user_id}_replaced_{message.document.file_name}"
            with open(local_file, 'wb') as f:
                f.write(file_content)
            
            with open(local_file, 'r', encoding='utf-8') as f:
                numbers = f.readlines()
            
            count = save_numbers_to_db(user_id, numbers)
            
            bot.send_message(
                user_id,
                f"✅ সফল!\n\n"
                f"🔄 সব নম্বর রিপ্লেস হয়েছে।\n"
                f"📊 নতুন নম্বর: {count} টি",
                parse_mode='Markdown'
            )
        else:
            bot.send_message(user_id, "❌ দয়া করে একটি ফাইল পাঠান।")
            
    except Exception as e:
        bot.send_message(user_id, f"❌ ত্রুটি: {str(e)}")

@bot.message_handler(func=lambda message: message.text == "🗑️ Delete All Numbers")
def delete_all_confirm(message):
    """সব নম্বর ডিলিট - কনফার্মেশন"""
    user_id = message.chat.id
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ হ্যাঁ, ডিলিট করুন", callback_data="delete_all_yes"),
        telebot.types.InlineKeyboardButton("❌ না, বাতিল করুন", callback_data="delete_all_no")
    )
    
    bot.send_message(
        user_id,
        "⚠️ *সব নম্বর ডিলিট করবেন?*\n\n"
        "এটি একটি স্থায়ী কার্যক্রম এবং পূর্ববর্তী করা যাবে না।",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == "delete_all_yes")
def delete_all_execute(call):
    """সব নম্বর ডিলিট করবে"""
    user_id = call.message.chat.id
    
    delete_all_numbers(user_id)
    bot.answer_callback_query(call.id)
    bot.send_message(user_id, "✅ সব নম্বর ডিলিট হয়েছে।")

@bot.callback_query_handler(func=lambda call: call.data == "delete_all_no")
def delete_all_cancel(call):
    """ডিলিট বাতিল করবে"""
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    bot.send_message(user_id, "❌ ডিলিট বাতিল করা হয়েছে।")

@bot.message_handler(func=lambda message: message.text == "❌ Delete Checked Only")
def delete_checked_confirm(message):
    """চেক করা নম্বর ডিলিট - কনফার্মেশন"""
    user_id = message.chat.id
    stats = get_stats(user_id)
    
    if stats['total_checked'] == 0:
        bot.send_message(user_id, "❌ চেক করা কোনো নম্বর নেই।")
        return
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ হ্যাঁ, ডিলিট করুন", callback_data="delete_checked_yes"),
        telebot.types.InlineKeyboardButton("❌ না, বাতিল করুন", callback_data="delete_checked_no")
    )
    
    bot.send_message(
        user_id,
        f"⚠️ *{stats['total_checked']} টি চেক করা নম্বর ডিলিট করবেন?*",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == "delete_checked_yes")
def delete_checked_execute(call):
    """চেক করা নম্বর ডিলিট করবে"""
    user_id = call.message.chat.id
    
    deleted = delete_checked_numbers(user_id)
    bot.answer_callback_query(call.id)
    bot.send_message(user_id, f"✅ {deleted} টি নম্বর ডিলিট হয়েছে।")

@bot.callback_query_handler(func=lambda call: call.data == "delete_checked_no")
def delete_checked_cancel(call):
    """চেক করা নম্বর ডিলিট বাতিল"""
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    bot.send_message(user_id, "❌ ডিলিট বাতিল করা হয়েছে।")

@bot.message_handler(func=lambda message: message.text == "⚠️ Delete Unchecked Only")
def delete_unchecked_confirm(message):
    """চেক না করা নম্বর ডিলিট - কনফার্মেশন"""
    user_id = message.chat.id
    stats = get_stats(user_id)
    
    if stats['remaining'] == 0:
        bot.send_message(user_id, "❌ চেক না করা কোনো নম্বর নেই।")
        return
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton("✅ হ্যাঁ, ডিলিট করুন", callback_data="delete_unchecked_yes"),
        telebot.types.InlineKeyboardButton("❌ না, বাতিল করুন", callback_data="delete_unchecked_no")
    )
    
    bot.send_message(
        user_id,
        f"⚠️ *{stats['remaining']} টি চেক না করা নম্বর ডিলিট করবেন?*",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == "delete_unchecked_yes")
def delete_unchecked_execute(call):
    """চেক না করা নম্বর ডিলিট করবে"""
    user_id = call.message.chat.id
    
    deleted = delete_unchecked_numbers(user_id)
    bot.answer_callback_query(call.id)
    bot.send_message(user_id, f"✅ {deleted} টি নম্বর ডিলিট হয়েছে।")

@bot.callback_query_handler(func=lambda call: call.data == "delete_unchecked_no")
def delete_unchecked_cancel(call):
    """চেক না করা নম্বর ডিলিট বাতিল"""
    user_id = call.message.chat.id
    bot.answer_callback_query(call.id)
    bot.send_message(user_id, "❌ ডিলিট বাতিল করা হয়েছে।")

@bot.message_handler(func=lambda message: message.text == "🔙 Back")
def go_back(message):
    """মেইন মেনুতে ফিরে যান"""
    send_welcome(message)

# Bot চালু করুন
if __name__ == "__main__":
    print("🤖 Facebook Checker Bot v3.3 চলছে...")
    print("✨ ডাটা ম্যানেজমেন্ট + Stop/Resume সহ!")
    print("🔕 সব SSL Warnings suppressed!")
    print("🛡️ Database Thread-Safe!")
    bot.infinity_polling()
