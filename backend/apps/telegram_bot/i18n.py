"""
apps/telegram_bot/i18n.py — Minimal message dictionary for the Telegram bot.
Every user-facing string lives here, keyed by a short name, with 'hi' and
'en' variants. Use t(lang, key, **kwargs) to look one up with .format()
substitution.
"""

MESSAGES = {
    'choose_language': {
        'hi': "Namaste! 🙏 MedAdhere Telegram bot mein aapka swagat hai.\nApni bhasha chuniye:",
        'en': "Welcome to the MedAdhere Telegram bot! 🙏\nPlease choose your language:",
    },
    'ask_email': {
        'hi': "Verify karne ke liye apna registered email address type karein:",
        'en': "To verify your account, please type your registered email address:",
    },
    'email_not_found': {
        'hi': "Yeh email MedAdhere ke kisi patient/caregiver account se match nahi hua.\n"
              "Kripya sahi email try karein, ya support@medadhere.app se contact karein.",
        'en': "This email doesn't match any MedAdhere patient/caregiver account.\n"
              "Please try again, or contact support@medadhere.app.",
    },
    'invalid_email_format': {
        'hi': "Yeh valid email nahi lag raha. Dobara try karein.",
        'en': "That doesn't look like a valid email. Please try again.",
    },
    'otp_sent': {
        'hi': "📧 Aapke email *{email}* par ek 6-digit code bheja gaya hai.\n"
              "Apna inbox check karke wahi code yahan type karein.\n"
              "Yeh {minutes} minute mein expire ho jayega.",
        'en': "📧 A 6-digit code has been sent to *{email}*.\n"
              "Please check your inbox and type that code here.\n"
              "It expires in {minutes} minutes.",
    },
    'otp_send_failed': {
        'hi': "❗ Email bhejne mein problem hui. Kripya thodi der baad apna email dobara type karein.\n"
              "Agar problem bani rahe toh support@medadhere.app se contact karein.",
        'en': "❗ We couldn't send the verification email right now. Please type your email again in a "
              "few minutes.\nIf this keeps happening, contact support@medadhere.app.",
    },
    'otp_invalid': {
        'hi': "Code galat hai. Dobara try karein.",
        'en': "Incorrect code. Please try again.",
    },
    'otp_expired': {
        'hi': "Code expire ho gaya. Apna email phir se type karein.",
        'en': "That code expired. Please type your email again to get a new one.",
    },
    'otp_locked': {
        'hi': "Bohot zyada galat attempts ho gaye. Apna email phir se type karein.",
        'en': "Too many incorrect attempts. Please type your email again to get a new one.",
    },
    'welcome_verified': {
        'hi': "✅ Verified! Namaste, *{name}*! 👋\nAb aap neeche diye options use kar sakte hain.",
        'en': "✅ Verified! Welcome, *{name}*! 👋\nYou can now use the options below.",
    },
    'no_schedule_today': {
        'hi': "Aaj ke liye koi dava schedule nahi hai. 😊",
        'en': "No medication scheduled for today. 😊",
    },
    'status_header': {
        'hi': "📋 Aaj ki Medications:",
        'en': "📋 Today's Medications:",
    },
    'report_header': {
        'hi': "📈 Pichhle {days} din ka Adherence Report:",
        'en': "📈 Adherence Report — last {days} days:",
    },
    'report_body': {
        'hi': "✅ Li gayi: {taken}\n❌ Chhooti: {missed}\n⏭️ Skip ki: {skipped}\n📊 Adherence: *{pct}%*",
        'en': "✅ Taken: {taken}\n❌ Missed: {missed}\n⏭️ Skipped: {skipped}\n📊 Adherence: *{pct}%*",
    },
    'report_no_data': {
        'hi': "Is period ke liye koi data nahi mila.",
        'en': "No data found for this period.",
    },
    'help_text': {
        'hi': "MedAdhere Help:\n"
              "• Status — aaj ki dava dekhein\n"
              "• Report — adherence report dekhein\n"
              "• Reminder aane par Y/N/Skip button dabayein\n"
              "Support: support@medadhere.app",
        'en': "MedAdhere Help:\n"
              "• Status — view today's medications\n"
              "• Report — view your adherence report\n"
              "• When a reminder arrives, tap Y/N/Skip\n"
              "Support: support@medadhere.app",
    },
    'menu_prompt': {
        'hi': "Kya karna chahenge?",
        'en': "What would you like to do?",
    },
    'dose_reminder_prompt': {
        'hi': "\nKya aapne dawai le li?",
        'en': "\nHave you taken your medicine?",
    },
    'dose_recorded_taken': {
        'hi': "✅ Dawai lene ke liye shukriya! Record kar liya gaya.",
        'en': "✅ Thanks for taking your dose! Recorded.",
    },
    'dose_recorded_missed': {
        'hi': "Theek hai, is dose ko MISSED mark kar diya gaya hai.",
        'en': "Okay, this dose has been marked as MISSED.",
    },
    'dose_recorded_skipped': {
        'hi': "Theek hai, is dose ko SKIP kar diya gaya hai.",
        'en': "Okay, this dose has been marked as SKIPPED.",
    },
    'no_reminder_context': {
        'hi': "Koi active reminder nahi mila.",
        'en': "No active reminder found.",
    },
    'reminder_not_found': {
        'hi': "Reminder record nahi mila.",
        'en': "Reminder record not found.",
    },
    'unknown_input': {
        'hi': "Samajh nahi aaya. Neeche diye options use karein:",
        'en': "Sorry, I didn't understand. Please use the options below:",
    },
}

BUTTON_LABELS = {
    'lang_hi':   {'hi': "हिंदी", 'en': "हिंदी"},
    'lang_en':   {'hi': "English", 'en': "English"},
    'status':    {'hi': "📋 Aaj ka Status", 'en': "📋 Today's Status"},
    'report':    {'hi': "📈 Adherence Report", 'en': "📈 Adherence Report"},
    'help':      {'hi': "❓ Help", 'en': "❓ Help"},
    'change_lang': {'hi': "🌐 Bhasha Badlein", 'en': "🌐 Change Language"},
    'dose_yes':  {'hi': "✅ Haan, li li", 'en': "✅ Yes, taken"},
    'dose_no':   {'hi': "❌ Nahi li", 'en': "❌ Not taken"},
    'dose_skip': {'hi': "⏭️ Baad mein", 'en': "⏭️ Later"},
}


def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in ('hi', 'en') else 'hi'
    text = MESSAGES.get(key, {}).get(lang) or MESSAGES.get(key, {}).get('hi') or key
    return text.format(**kwargs) if kwargs else text


def btn(lang: str, key: str) -> str:
    lang = lang if lang in ('hi', 'en') else 'hi'
    return BUTTON_LABELS.get(key, {}).get(lang) or key
