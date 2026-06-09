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

# Bot Configuration
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # আপনার টেলিগ্রাম বট টোকেন দিন
bot = telebot.TeleBot(BOT_TOKEN)

# Database Setup
DB_PATH = "facebook_checker.db"
UPLOAD_FOLDER = "uploads"
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)

# Global Variables
user_threads = {}
checking_queue = queue.Queue()
is_checking = {}

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
    conn = sqlite3.connect(DB_PATH)
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

init_db()

# ==================== DATABASE FUNCTIONS ====================

def save_numbers_to_db(user_id, phone_numbers):
    """টেক্সট ফাইল থেকে নম্বর ডাটাবেসে সেভ করবে"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    count = 0
    for number in phone_numbers:
        number = number.strip()
        if number:  # সব ধরনের নম্বর accept করব
            cursor.execute('''
                INSERT INTO numbers (user_id, phone_number, status)
                VALUES (?, ?, 'unchecked')
            ''', (user_id, number))
            count += 1
    
    conn.commit()
    conn.close()
    return count

def get_unchecked_numbers(user_id):
    """সমস্ত unchecked নম্বর fetch করবে"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, phone_number FROM numbers 
        WHERE user_id = ? AND status = 'unchecked'
        ORDER BY id
    ''', (user_id,))
    results = cursor.fetchall()
    conn.close()
    return results

def update_number_status(number_id, has_id):
    """নম্বরের স্ট্যাটাস আপডেট করবে"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE numbers 
        SET status = 'checked', has_id = ?, checked_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (has_id, number_id))
    conn.commit()
    conn.close()

def get_checked_numbers(user_id, has_id=None):
    """Checked নম্বর গুলো fetch করবে (Fresh/Unfresh)"""
    conn = sqlite3.connect(DB_PATH)
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

def get_user_thread_count(user_id):
    """ইউজারের থ্রেড কাউন্ট পান"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT thread_count FROM user_settings WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return result[0]
    return 20  # Default

def set_user_thread_count(user_id, thread_count):
    """ইউজারের থ্রেড কাউন্ট সেট করুন"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_settings (user_id, thread_count, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, thread_count))
    conn.commit()
    conn.close()

# ==================== USER AGENT FUNCTION ====================

def get_random_user_agent():
    """প্রতিবার নতুন User-Agent generate করবে"""
    return random.choice(USER_AGENTS)

# ==================== FACEBOOK CHECK FUNCTION ====================

def check_facebook_number(phone_number):
    """Advanced Facebook নম্বর চেক - প্রতিবার নতুন User-Agent দিয়ে"""
    try:
        # প্রতিবার নতুন User-Agent generate করবে
        user_agent = get_random_user_agent()
        
        # Facebook Forget API
        url = "https://www.facebook.com/login/identify"
        
        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.facebook.com/',
            'Origin': 'https://www.facebook.com'
        }
        
        params = {
            'ctx': 'recover',
            'q': phone_number
        }
        
        session = requests.Session()
        response = session.get(url, params=params, headers=headers, timeout=15)
        
        # Check if account exists - এর জন্য response analyze করব
        response_text = response.text.lower()
        
        # যদি নিচের কোনটা পাওয়া যায় তাহলে ID আছে
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
            'phone_number_warning' # এটা মানে নম্বর টি Facebook account এ linked
        ]
        
        found_id = False
        for indicator in has_id_indicators:
            if indicator in response_text:
                found_id = True
                break
        
        return found_id
        
    except requests.exceptions.Timeout:
        print(f"Timeout: {phone_number}")
        return False
    except Exception as e:
        print(f"Error checking {phone_number}: {str(e)}")
        return False

# ==================== TELEGRAM BOT COMMANDS ====================

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """শুরু করার কমান্ড"""
    user_id = message.chat.id
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        telebot.types.KeyboardButton("📤 Upload"),
        telebot.types.KeyboardButton("✅ Check Numbers"),
        telebot.types.KeyboardButton("⚙️ Thread Setup"),
        telebot.types.KeyboardButton("📥 Download")
    )
    
    bot.send_message(
        user_id,
        "🎉 *Facebook Checker Bot v2*\n\n"
        "আমি আপনার Facebook নম্বরগুলি চেক করতে পারি।\n"
        "প্রতিটি চেক এ নতুন User-Agent ব্যবহার করব।\n\n"
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
            
            # ফাইল ডাউনলোড করুন
            file_content = bot.download_file(file_path)
            
            # ফাইল সংরক্ষণ করুন
            local_file = f"{UPLOAD_FOLDER}/{user_id}_{message.document.file_name}"
            with open(local_file, 'wb') as f:
                f.write(file_content)
            
            # নম্বর পড়ুন এবং সেভ করুন
            with open(local_file, 'r', encoding='utf-8') as f:
                numbers = f.readlines()
            
            count = save_numbers_to_db(user_id, numbers)
            
            bot.send_message(
                user_id,
                f"✅ সফল!\n\n"
                f"📊 {count} টি নম্বর আপলোড হয়েছে।",
                parse_mode='Markdown'
            )
        else:
            bot.send_message(user_id, "❌ দয়া করে একটি ফাইল পাঠান।")
            
    except Exception as e:
        bot.send_message(user_id, f"❌ ত্রুটি: {str(e)}")

@bot.message_handler(func=lambda message: message.text == "⚙️ Thread Setup")
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
                f"নতুন থ্রেড সংখ্যা: *{thread_count}*\n\n"
                f"🔄 প্রতিটি থ্রেডে নতুন User-Agent ব্যবহার হবে।",
                parse_mode='Markdown'
            )
        else:
            bot.send_message(user_id, "❌ দয়া করে 10-200 এর মধ্যে একটি সংখ্যা দিন।")
            
    except ValueError:
        bot.send_message(user_id, "❌ দয়া করে একটি সংখ্যা দিন।")

@bot.message_handler(func=lambda message: message.text == "✅ Check Numbers")
def handle_check_numbers(message):
    """নম্বর চেক করা শুরু করবে"""
    user_id = message.chat.id
    
    # অবশেষ unchecked নম্বর পান
    unchecked = get_unchecked_numbers(user_id)
    
    if not unchecked:
        bot.send_message(user_id, "❌ কোনো নম্বর চেক করার নেই।")
        return
    
    if is_checking.get(user_id):
        bot.send_message(user_id, "⏳ চেকিং ইতিমধ্যে চলছে।")
        return
    
    is_checking[user_id] = True
    thread_count = get_user_thread_count(user_id)
    
    # শুরুর বার্তা পাঠান
    total = len(unchecked)
    bot.send_message(
        user_id,
        f"🚀 চেকিং শুরু হয়েছে!\n\n"
        f"📊 মোট নম্বর: {total}\n"
        f"🔄 থ্রেড সংখ্যা: {thread_count}\n"
        f"🔀 প্রতিটি চেক এ নতুন User-Agent\n\n"
        f"⏳ এটি কিছু সময় নিতে পারে...",
        parse_mode='Markdown'
    )
    
    # Multi-threading চেকিং শুরু করুন
    checked_count = [0]
    lock = threading.Lock()
    
    def thread_worker():
        while True:
            try:
                number_id, phone_number = checking_queue.get(timeout=1)
                
                # প্রতিবার নতুন User-Agent দিয়ে চেক করবে
                has_id = 1 if check_facebook_number(phone_number) else 0
                update_number_status(number_id, has_id)
                
                with lock:
                    checked_count[0] += 1
                
                # প্রতিটি 25টি নম্বর চেক করার পর আপডেট পাঠান
                if checked_count[0] % 25 == 0:
                    bot.send_message(
                        user_id,
                        f"⏳ অগ্রগতি: {checked_count[0]}/{total} নম্বর চেক হয়েছে।",
                        parse_mode='Markdown'
                    )
                
                checking_queue.task_done()
                time.sleep(0.2)  # Little delay between checks
                
            except queue.Empty:
                break
    
    # Queue পূরণ করুন
    for number_id, phone_number in unchecked:
        checking_queue.put((number_id, phone_number))
    
    # থ্রেড শুরু করুন
    threads = []
    for _ in range(thread_count):
        t = threading.Thread(target=thread_worker, daemon=True)
        t.start()
        threads.append(t)
    
    # সব থ্রেড শেষ হওয়ার জন্য অপেক্ষা করুন
    checking_queue.join()
    
    is_checking[user_id] = False
    
    # চূড়ান্ত রিপোর্ট পাঠান
    fresh = len(get_checked_numbers(user_id, 1))
    unfresh = len(get_checked_numbers(user_id, 0))
    
    bot.send_message(
        user_id,
        f"✅ চেকিং সম্পন্ন!\n\n"
        f"📊 ফলাফল:\n"
        f"• 🟢 Fresh (ID আছে): *{fresh}*\n"
        f"• 🔴 Unfresh (ID নেই): *{unfresh}*\n"
        f"• 📈 মোট চেক করা: *{checked_count[0]}*\n\n"
        f"🔀 প্রতিটি চেক এ নতুন User-Agent ব্যবহার করা হয়েছে।",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda message: message.text == "📥 Download")
def handle_download(message):
    """ডাউনলোড অপশন"""
    user_id = message.chat.id
    
    markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    markup.add(
        telebot.types.KeyboardButton("🟢 Fresh Numbers"),
        telebot.types.KeyboardButton("🔴 Unfresh Numbers"),
        telebot.types.KeyboardButton("🔙 Back")
    )
    
    bot.send_message(
        user_id,
        "📥 কোনটি ডাউনলোড করবেন?",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == "🟢 Fresh Numbers")
def download_fresh(message):
    """Fresh নম্বর ডাউনলোড করবে (ID আছে)"""
    user_id = message.chat.id
    
    numbers = get_checked_numbers(user_id, 1)
    
    if not numbers:
        bot.send_message(user_id, "❌ কোনো Fresh নম্বর পাওয়া যায়নি।")
        return
    
    # ফাইল তৈরি করুন
    filename = f"{UPLOAD_FOLDER}/fresh_{user_id}_{int(time.time())}.txt"
    with open(filename, 'w') as f:
        for number in numbers:
            f.write(number + '\n')
    
    # ফাইল পাঠান
    with open(filename, 'rb') as f:
        bot.send_document(
            user_id,
            f,
            caption=f"🟢 Fresh Numbers\n\n"
                   f"মোট: {len(numbers)} টি"
        )
    
    # ফাইল মুছে ফেলুন
    Path(filename).unlink()
    send_welcome(message)

@bot.message_handler(func=lambda message: message.text == "🔴 Unfresh Numbers")
def download_unfresh(message):
    """Unfresh নম্বর ডাউনলোড করবে (ID নেই)"""
    user_id = message.chat.id
    
    numbers = get_checked_numbers(user_id, 0)
    
    if not numbers:
        bot.send_message(user_id, "❌ কোনো Unfresh নম্বর পাওয়া যায়নি।")
        return
    
    # ফাইল তৈরি করুন
    filename = f"{UPLOAD_FOLDER}/unfresh_{user_id}_{int(time.time())}.txt"
    with open(filename, 'w') as f:
        for number in numbers:
            f.write(number + '\n')
    
    # ফাইল পাঠান
    with open(filename, 'rb') as f:
        bot.send_document(
            user_id,
            f,
            caption=f"🔴 Unfresh Numbers\n\n"
                   f"মোট: {len(numbers)} টি"
        )
    
    # ফাইল মুছে ফেলুন
    Path(filename).unlink()
    send_welcome(message)

@bot.message_handler(func=lambda message: message.text == "🔙 Back")
def go_back(message):
    """মেইন মেনুতে ফিরে যান"""
    send_welcome(message)

# Bot চালু করুন
if __name__ == "__main__":
    print("🤖 Facebook Checker Bot v2 চলছে...")
    print("✨ প্রতিটি থ্রেডে নতুন User-Agent ব্যবহার হবে।")
    print("⚠️ BOT_TOKEN সেট করুন আগে!")
    bot.infinity_polling()
