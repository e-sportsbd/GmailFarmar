import telebot, time
from telebot.types import(
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
import firebase_admin
from firebase_admin import credentials, db

# ================= CONFIG =================
BOT_TOKEN = "8593373295:AAHU82sjTsbXo36eNZNr77PlbAmoAscYm-g"
BOT_USERNAME = "gmail_farmar_litebot"   # without @
CHANNEL_USERNAME = "gmail_farmar_lite"    # without @

# ================= BOT =================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ================= FIREBASE =================
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://post-c7e41-default-rtdb.firebaseio.com"
})

# ================= STATES =================
submit_state = {}
withdraw_state = {}   # user_id: current state
withdraw_method = {}  # user_id: selected method
withdraw_amount = {}

# ================= MENU =================
def main_menu(chat_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("✏️ Submit my own", "💰 Balance")
    kb.row("💸 Withdraw", "📄 My History")
    kb.row("📣 Share Referral Link", "🏆 Top Referrals")
    kb.row("📌Help")
    bot.send_message(chat_id, "📌 Main Menu", reply_markup=kb)

# ================= CHANNEL CHECK =================
def is_joined(user_id):
    try:
        status = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id).status
        return status in ["member", "administrator", "creator"]
    except:
        return False

# ================= /START + REFERRAL =================
@bot.message_handler(commands=["start"])
def start(message):
    user_id = str(message.from_user.id)
    args = message.text.split()
    ref_by = args[1] if len(args) > 1 else None

    user_ref = db.reference(f"users/{user_id}")
    if not user_ref.get():
        user_ref.set({
            "name": message.from_user.first_name,
            "balance": 0.0,
            "total_earned": 0.0,
            "referral_earned": 0.0,
            "referred_by": ref_by,
            "referrals": 0
        })

        if ref_by and ref_by != user_id:
            rref = db.reference(f"users/{ref_by}")
            if rref.get():
                rref.child("referrals").set(
                    (rref.child("referrals").get() or 0) + 1
                )

    if not is_joined(message.from_user.id):
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("📣 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME}"),
            InlineKeyboardButton("✅ Join & Verify", callback_data="verify")
        )
        bot.send_message(
            message.chat.id,
            "👋 Welcome!\n\nPlease join channel first.",
            reply_markup=kb
        )
    else:
        main_menu(message.chat.id)

@bot.callback_query_handler(func=lambda c: c.data == "verify")
def verify(c):
    if is_joined(c.from_user.id):
        bot.edit_message_text(
            "✅ Verified successfully!",
            c.message.chat.id,
            c.message.message_id
        )
        main_menu(c.message.chat.id)
    else:
        bot.answer_callback_query(c.id, "❌ Join channel first", show_alert=True)

# ================= SUBMIT MY OWN ===============

@bot.message_handler(func=lambda m: m.text == "✏️ Submit my own")
def submit_menu(m):
    rate = db.reference("settings/gmail_rate").get() or 0.15

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📩 Submit Gmail", "📋 View Requirements")
    kb.row("❌ Cancel")

    bot.send_message(
        m.chat.id,
        f"✏️ Submit Your Own Gmail\n\n"
        f"💰 Rate: {rate} USDT per Gmail\n"
        f"⏳ Approval: 24–48h",
        reply_markup=kb
    )


@bot.message_handler(func=lambda m: m.text == "📋 View Requirements")
def view_req(m):
    rate = db.reference("settings/gmail_rate").get() or 0.15

    bot.send_message(
        m.chat.id,
        "📋 Requirements\n\n"
        "✅ Gmail 30+ days old\n"
        "✅ Recovery email set\n"
        "✅ Password unchanged\n"
        f"💰 Rate: {rate} USDT"
    )


@bot.message_handler(func=lambda m: m.text == "📩 Submit Gmail")
def start_submit(m):
    submit_state[m.from_user.id] = True
     
    bot.send_message(
        m.chat.id,
        "📩 Submit Gmail\n\n"
        "Send in this format:\n"
        "gmail:Password:recovery_email\n\n"
        "Example:\n"
        "example@gmail.com: Password:recovery@gmail.com\n\n"
        "❌ Cancel to stop"
    )


@bot.message_handler(func=lambda m: submit_state.get(m.from_user.id))
def receive_submit(m):
    user_id = m.from_user.id

    if m.text in ["/cancel", "❌ Cancel"]:
        submit_state.pop(user_id, None)
        bot.send_message(
            m.chat.id,
            "❌ Submission cancelled",
            reply_markup=ReplyKeyboardRemove()
        )
        main_menu(m.chat.id)
        return

    parts = m.text.split(":")
    if len(parts) != 3:
        bot.send_message(
            m.chat.id,
            "❌ Wrong format\nUse: gmail:name:recovery_email"
        )
        return

    gmail, name, recovery = parts

    if "@gmail.com" not in gmail or "@gmail.com" not in recovery:
        bot.send_message(m.chat.id, "❌ Invalid Gmail address")
        return

    db.reference("submissions").push({
        "user_id": str(user_id),
        "gmail": gmail.strip(),
        "": name.strip(),
        "recovery": recovery.strip(),
        "status": "pending",
        "time": int(time.time())
    })

    submit_state.pop(user_id, None)

    bot.send_message(
        m.chat.id,
        "✅ Submitted successfully!\n⏳ Waiting for approval"
    )
    main_menu(m.chat.id)
# ================= BALANCE =================
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance(m):
    uref = db.reference(f"users/{m.from_user.id}")
    u = uref.get()

    if not u:
        bot.send_message(
            m.chat.id,
            "❌ Your account not found.\n\nPlease send /start first."
        )
        return

    # User balance
    balance_usdt = float(u.get("balance", 0.0))
    ref_earned_usdt = float(u.get("referral_earned", 0.0))
    total_usdt = float(u.get("total_earned", 0.0))

    # Conversion rate (USDT -> BDT)
    usdt_to_bdt = 115  # তুমি চাইলে db.reference("settings/usdt_to_bdt").get() দিয়ে dynamic করতে পারো

    # Convert to BDT
    balance_bdt = balance_usdt * usdt_to_bdt
    ref_earned_bdt = ref_earned_usdt * usdt_to_bdt
    total_bdt = total_usdt * usdt_to_bdt

    bot.send_message(
        m.chat.id,
        f"💰 Balance\n\n"
        f"Balance: {balance_usdt} USDT | {balance_bdt} BDT\n"
    )

# ================= REFERRAL =================
@bot.message_handler(func=lambda m: m.text == "📣 Share Referral Link")
def ref_link(m):
    bot.send_message(
        m.chat.id,
        f"📣 Your Referral Link\n\n"
        f"https://t.me/{BOT_USERNAME}?start={m.from_user.id}"
    )

@bot.message_handler(func=lambda m: m.text == "🏆 Top Referrals")
def top_refs(m):
    users = db.reference("users").get()

    if not users or not isinstance(users, dict):
        bot.send_message(m.chat.id, "❌ No referral data found")
        return

    clean_users = []

    for uid, u in users.items():
        if not isinstance(u, dict):
            continue

        referrals = u.get("referrals", 0)
        try:
            referrals = int(referrals)
        except:
            referrals = 0

        clean_users.append({
            "name": u.get("name", "Unknown"),
            "referrals": referrals
        })

    if not clean_users:
        bot.send_message(m.chat.id, "❌ No referral data found")
        return

    top = sorted(clean_users, key=lambda x: x["referrals"], reverse=True)[:10]

    txt = "🏆 Top Referrals\n\n"
    for i, u in enumerate(top, 1):
        txt += f"{i}. {u['name']} – {u['referrals']} referrals\n"

    bot.send_message(m.chat.id, txt)

# ================= WITHDRAW =================
@bot.message_handler(func=lambda m: m.text == "💸 Withdraw")
def withdraw(m):
    user_id = m.from_user.id
    uref = db.reference(f"users/{user_id}")
    u = uref.get()

    if not u:
        bot.send_message(m.chat.id, "❌ Account not found.\nSend /start first.")
        return

    # Minimum withdraw
    minw = db.reference("settings/min_withdraw").get()
    try:
        minw = float(minw)
    except:
        minw = 2.0

    balance = float(u.get("balance", 0))
    if balance < minw:
        bot.send_message(
            m.chat.id,
            f"❌ Minimum withdraw {minw} USDT\nYour balance: {balance} USDT"
        )
        return

    # Show withdraw method keyboard
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("📱 Bkash"),
        KeyboardButton("📱 Nagad"),
        KeyboardButton("💰 Binance")
    )
    kb.row("❌ Cancel")

    bot.send_message(
        m.chat.id,
        "💸 Select Withdraw Method:",
        reply_markup=kb
    )

    # Mark user as choosing method
    withdraw_state[user_id] = "choose_method"

# ================= Withdraw Method Selection =================
@bot.message_handler(func=lambda m: withdraw_state.get(m.from_user.id) == "choose_method")
def select_withdraw_method(m):
    user_id = m.from_user.id

    if m.text in ["❌ Cancel", "/cancel"]:
        withdraw_state.pop(user_id, None)
        bot.send_message(m.chat.id, "❌ Withdraw cancelled", reply_markup=ReplyKeyboardRemove())
        main_menu(m.chat.id)
        return

    if m.text not in ["📱 Bkash", "📱 Nagad", "💰 Binance"]:
        bot.send_message(m.chat.id, "❌ Please select a valid method")
        return

    withdraw_method[user_id] = m.text
    withdraw_state[user_id] = "enter_amount"

    bot.send_message(
        m.chat.id,
        f"✅ Method selected: {m.text}\n\n"
        f"Send the amount you want to withdraw:",
        reply_markup=ReplyKeyboardRemove()
    )

# ================= Enter Amount =================
@bot.message_handler(func=lambda m: withdraw_state.get(m.from_user.id) == "enter_amount")
def enter_withdraw_amount(m):
    user_id = m.from_user.id

    if m.text in ["❌ Cancel", "/cancel"]:
        withdraw_state.pop(user_id, None)
        withdraw_method.pop(user_id, None)
        bot.send_message(m.chat.id, "❌ Withdraw cancelled")
        main_menu(m.chat.id)
        return

    try:
        amount = float(m.text)
    except:
        bot.send_message(m.chat.id, "❌ Invalid amount")
        return

    if amount <= 0:
        bot.send_message(m.chat.id, "❌ Amount must be greater than 0")
        return

    # Check min withdraw & balance
    uref = db.reference(f"users/{user_id}")
    u = uref.get()
    balance = float(u.get("balance", 0))
    minw = db.reference("settings/min_withdraw").get()
    try:
        minw = float(minw)
    except:
        minw = 2.0

    if amount < minw:
        bot.send_message(m.chat.id, f"❌ Minimum withdraw is {minw} USDT")
        return

    if amount > balance:
        bot.send_message(m.chat.id, f"❌ Insufficient balance\nYour balance: {balance} USDT")
        return

    # Save amount & move to next step
    withdraw_amount[user_id] = amount
    withdraw_state[user_id] = "enter_address"

    method = withdraw_method[user_id]
    if method in ["📱 Bkash", "📱 Nagad"]:
        input_type = "phone number"
    else:
        input_type = "wallet address"

    bot.send_message(
        m.chat.id,
        f"✅ Amount received: {amount} USDT\n\n"
        f"Now send your {input_type}:",
        reply_markup=ReplyKeyboardRemove()
    )

# ================= Enter Address / Phone Number =================
@bot.message_handler(func=lambda m: withdraw_state.get(m.from_user.id) == "enter_address")
def enter_withdraw_address(m):
    user_id = m.from_user.id

    if m.text in ["/cancel", "❌ Cancel"]:
        withdraw_state.pop(user_id, None)
        withdraw_method.pop(user_id, None)
        withdraw_amount.pop(user_id, None)
        bot.send_message(m.chat.id, "❌ Withdraw cancelled")
        main_menu(m.chat.id)
        return

    address = m.text.strip()
    method = withdraw_method[user_id]

    # Validate input
    if method in ["📱 Bkash", "📱 Nagad"]:
        if not address.isdigit() or len(address) < 10:
            bot.send_message(m.chat.id, "❌ Invalid phone number")
            return
    else:
        if len(address) < 10:
            bot.send_message(m.chat.id, "❌ Invalid wallet address")
            return

    amount = withdraw_amount.get(user_id)

    # Deduct balance
    uref = db.reference(f"users/{user_id}")
    u = uref.get()
    balance = float(u.get("balance", 0))
    uref.update({"balance": balance - amount})

    # Save withdraw request
    db.reference("withdraw_requests").push({
        "user_id": str(user_id),
        "amount": amount,
        "address": address,
        "method": method,
        "status": "pending",
        "time": int(time.time())
    })

    # Clear states
    withdraw_state.pop(user_id, None)
    withdraw_method.pop(user_id, None)
    withdraw_amount.pop(user_id, None)

    bot.send_message(
        m.chat.id,
        "✅ Withdraw request submitted!\n"
        "⏳ Processing time: 24–48 hours"
    )

    main_menu(m.chat.id)
# ================= HISTORY =================
@bot.message_handler(func=lambda m: m.text == "📄 My History")
def history(m):
    user_id = str(m.from_user.id)

    try:
        reqs = (
            db.reference("withdraw_requests")
            .order_by_child("user_id")
            .equal_to(user_id)
            .get()
        )
    except Exception as e:
        bot.send_message(m.chat.id, "❌ Failed to load history")
        return

    if not reqs or not isinstance(reqs, dict):
        bot.send_message(m.chat.id, "📄 No withdraw history found")
        return

    txt = "📄 Withdraw History\n\n"

    count = 0
    for r in reqs.values():
        if not isinstance(r, dict):
            continue

        amount = r.get("amount", 0)
        status = r.get("status", "pending")

        txt += f"• {amount} USDT – {status}\n"
        count += 1

    if count == 0:
        bot.send_message(m.chat.id, "📄 No withdraw history found")
        return

    bot.send_message(m.chat.id, txt)




# ================= RUN =================
print("Bot running...")
bot.infinity_polling()