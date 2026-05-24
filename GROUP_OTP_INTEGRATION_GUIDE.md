# Group OTP Provider System - Integration Guide

এই গাইড আপনার SMART Bot-এ Group OTP Provider সিস্টেম যুক্ত করতে সাহায্য করবে।

## 📋 বৈশিষ্ট্য সমূহ

✅ **Telegram অ্যাকাউন্ট ম্যানেজমেন্ট**
- নতুন Telegram অ্যাকাউন্ট যুক্ত করুন
- অ্যাকাউন্ট লিস্ট দেখুন
- অ্যাকাউন্ট সরান

✅ **অটোমেটিক সেশন ম্যানেজমেন্ট**
- সেশন স্ট্রিং স্বয়ংক্রিয়ভাবে সংরক্ষিত হয়
- বট রিস্টার্ট পরেও লগিন অবস্থা বজায় থাকে
- কোন ম্যানুয়াল সেশন এন্ট্রি প্রয়োজন নেই

✅ **ডাটাবেস সংরক্ষণ**
- সব অ্যাকাউন্ট তথ্য ডাটাবেসে সংরক্ষিত
- সেশন স্ট্রিং এনক্রিপ্ট অবস্থায় রাখা যায়
- দ্রুত পুনরুদ্ধার

## 🚀 ইনস্টলেশন ধাপ

### ধাপ ১: প্রয়োজনীয় প্যাকেজ ইনস্টল করুন

```bash
pip install telethon
```

### ধাপ ২: `telethon_group_otp.py` যুক্ত করুন

ফাইলটি repository-তে রাখুন এবং bot.py থেকে import করুন:

```python
from telethon_group_otp import initialize_telethon_provider
```

### ধাপ ৩: Group OTP Provider হ্যান্ডলার যুক্ত করুন

`group_otp_handlers.py` থেকে সব ফাংশন bot.py-তে কপি করুন।

### ধাপ ৪: bot.py-তে initialize করুন

`async def main()` ফাংশনে এটি যুক্ত করুন:

```python
async def main():
    await init_db()
    
    # Initialize Telethon OTP Provider
    # আপনার নিজস্ব API ID এবং Hash ব্যবহার করুন
    # https://my.telegram.org থেকে পান
    await initialize_telethon_provider(
        api_id=YOUR_API_ID,        # আপনার API ID
        api_hash="YOUR_API_HASH"   # আপনার API Hash
    )
    
    # Start workers...
```

### ধাপ ৫: Handle buttons এ যুক্ত করুন

`handle_buttons()` ফাংশনে এটি যুক্ত করুন:

```python
# Check if admin is adding Telegram account
if user_id in admin_states:
    state_data = admin_states[user_id]
    
    elif state_data["state"] == "waiting_telegram_phone":
        if await handle_telegram_phone_input(message):
            return
    
    elif state_data["state"] == "waiting_telegram_code":
        if await handle_telegram_code_input(message):
            return
```

## 🔧 Telegram API ক্রেডেনশিয়াল পাওয়ার উপায়

১. https://my.telegram.org খুলুন
২. আপনার ফোন নম্বর দিয়ে লগইন করুন
৩. "API development tools" এ যান
৪. নতুন অ্যাপ্লিকেশন তৈরি করুন
৫. API ID এবং API Hash কপি করুন
৬. এগুলি bot.py-তে রাখুন

## 📊 ডাটাবেস টেবিল

### telegram_accounts
```
id              : অ্যাকাউন্ট ID
phone_number    : Telegram ফোন নম্বর
api_id          : API ID
api_hash        : API Hash
session_string  : সেশন স্ট্রিং (দীর্ঘমেয়াদী)
status          : Active/Inactive
created_at      : তৈরির সময়
updated_at      : আপডেটের সময়
```

### otp_provider_sessions
```
id              : সেশন ID
user_id         : ব্যবহারকারীর ID
phone_number    : অ্যাকাউন্ট ফোন নম্বর
verification_code: যাচাইকরণ কোড
status          : Pending/Verified
created_at      : তৈরির সময়
expires_at      : এক্সপায়ার সময়
```

### group_otp_logs
```
id              : লগ ID
account_phone   : অ্যাকাউন্ট ফোন
service         : সার্ভিস নাম
otp_code        : OTP কোড
received_from   : কোথা থেকে পাওয়া গেছে
received_at     : পাওয়ার সময়
```

## 👥 Admin প্যানেল ইউজার ফ্লো

### নতুন অ্যাকাউন্ট যোগ করার প্রক্রিয়া:

```
Admin Panel
    ↓
OTP Providers
    ↓
Group OTP Provider
    ↓
Add New Account
    ↓
Enter Phone (+880XXXXXXXXXX)
    ↓
Telegram App-এ কোড আসে (২-৫ মিনিট)
    ↓
কোড প্রবেশ করুন
    ↓
✅ অ্যাকাউন্ট সফলভাবে সংযুক্ত
    ↓
API ID, API Hash এবং সেশন স্ট্রিং দেখুন
```

### অ্যাকাউন্ট তালিকা দেখা:

```
Admin Panel
    ↓
OTP Providers
    ↓
Group OTP Provider
    ↓
View Account List
    ↓
সব অ্যাকাউন্ট দেখুন
    ↓
যেকোনো অ্যাকাউন্ট সরান
```

## 🔐 নিরাপত্তা টিপস

1. **API ক্রেডেনশিয়াল গোপন রাখুন**
   - API ID এবং Hash শেয়ার করবেন না
   - .env ফাইলে রাখুন

2. **সেশন স্ট্রিং সুরক্ষিত রাখুন**
   - ডাটাবেস এনক্রিপ্ট করুন
   - ব্যাকআপ সুরক্ষিত স্থানে রাখুন

3. **অ্যাকাউন্ট ব্যবস্থাপনা**
   - অপ্রয়োজনীয় অ্যাকাউন্ট সরান
   - নিয়মিত অ্যাকাউন্ট স্ট্যাটাস চেক করুন

## ⚠️ সম্ভাব্য সমস্যা এবং সমাধান

### সমস্যা ১: "কোড পাওয়া যাচ্ছে না"
**সমাধান:**
- Telegram অ্যাপ খোলা রাখুন
- ২-৫ মিনিট অপেক্ষা করুন
- ইন্টারনেট সংযোগ চেক করুন
- SMS অ্যালার্ট চেক করুন

### সমস্যা ২: "ফোন নম্বর আগে ব্যবহৃত হয়েছে"
**সমাধান:**
- অন্য ডিভাইস বা অ্যাপে লগিন করুন
- 24 ঘণ্টা অপেক্ষা করুন
- Telegram সাপোর্ট যোগাযোগ করুন

### সমস্যা ৩: "সেশন এক্সপায়ার হয়েছে"
**সমাধান:**
- অ্যাকাউন্ট পুনরায় যুক্ত করুন
- ডাটাবেস রিসেট করুন
- বট রিস্টার্ট করুন

## 📝 কাস্টমাইজেশন

### OTP গ্রহণ করার জন্য গ্রুপ মনিটর করুন

```python
@telethon_client.on(events.NewMessage(chats=GROUP_ID))
async def handle_group_message(event):
    # Group থেকে OTP বার্তা ক্যাপচার করুন
    # সংরক্ষণ করুন এবং ব্যবহারকারীদের পাঠান
    pass
```

### স্বয়ংক্রিয় OTP ফরওয়ার্ডিং

```python
async def forward_otp_to_user(otp_code, phone_number):
    # ডাটাবেস থেকে অ্যাক্টিভ সেশন খুঁজুন
    # OTP পাঠান
    pass
```

## 📞 সাপোর্ট

সমস্যা হলে:
1. লগ চেক করুন
2. ডাটাবেস ভেরিফাই করুন
3. বট ডেভেলপারকে যোগাযোগ করুন

## ✅ চেকলিস্ট

- [ ] Telethon প্যাকেজ ইনস্টল করেছি
- [ ] telethon_group_otp.py যুক্ত করেছি
- [ ] group_otp_handlers.py সংহত করেছি
- [ ] API ID এবং Hash সেট করেছি
- [ ] handle_buttons এ ফাংশন যুক্ত করেছি
- [ ] বট টেস্ট করেছি
- [ ] লগ চেক করেছি

সব কিছু সম্পন্ন হলে আপনার Group OTP Provider সিস্টেম প্রস্তুত! 🎉
