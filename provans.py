import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, filters
)
from dotenv import load_dotenv

load_dotenv()

# Дані
waiters = ["Анастасія", "Юліана", "Анна", "Вероніка", "Віталіна"]

menu = {
    "🍕 Піца": ["Маргарита", "Пепероні", "Гавайська"],
    "🍣 Суші": ["Філадельфія", "Каліфорнія", "Дракон"],
    "🍷 Напої": ["Кола", "Фанта", "Вода"],
    "🧀 Делікатеси": ["Сирна тарілка", "Оливки", "Брускети"]
}

prices = {
    "Маргарита": 175, "Пепероні": 185, "Гавайська": 190,
    "Філадельфія": 150, "Каліфорнія": 135, "Дракон": 340,
    "Кола": 50, "Фанта": 50, "Вода": 30,
    "Сирна тарілка": 110, "Оливки": 60, "Брускети": 90
}

# Збереження / Завантаження історії
def save_to_file(waiter, history):
    with open(f"history_{waiter}.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_history(waiter):
    try:
        with open(f"history_{waiter}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

# Хендлери
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saved = context.user_data.get("history", {})
    checks = context.user_data.get("checks", {})
    context.user_data.clear()
    context.user_data["history"] = saved
    context.user_data["checks"] = checks
    keyboard = [[InlineKeyboardButton(name, callback_data=f"waiter|{name}")] for name in waiters]
    markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text("👤 Хто ви? Оберіть офіціанта:", reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.message.edit_text("👤 Хто ви? Оберіть офіціанта:", reply_markup=markup)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("new_check_waiting"):
        table = update.message.text.strip()
        waiter = context.user_data["waiter"]
        context.user_data["new_check_waiting"] = False
        context.user_data["current_check"] = table
        context.user_data["checks"].setdefault(waiter, {})[table] = {"items": []}
        await show_category_menu(update, context, table)

async def update_category_view(context, query, table, cat):
    waiter = context.user_data["waiter"]
    items = context.user_data["checks"][waiter][table]["items"]
    buttons = []
    for item in menu[cat]:
        count = items.count(item)
        row = []
        if count > 0:
            row.append(InlineKeyboardButton(f"➖ {count} {item}", callback_data=f"rm|{table}|{item}|{cat}"))
        row.append(InlineKeyboardButton(f"➕ {item}", callback_data=f"toggle|{table}|{item}|{cat}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅ Назад до категорій", callback_data=f"backcat|{table}")])
    try:
        await query.edit_message_text(f"🧾 {cat} — редагування позицій:", reply_markup=InlineKeyboardMarkup(buttons))
    except:
        await query.message.reply_text("⚠️ Не вдалося оновити. Спробуйте /start")

async def show_category_menu(update, context, table):
    waiter = context.user_data["waiter"]
    items = context.user_data["checks"][waiter][table]["items"]
    item_list = "\n".join([f"✅ {i+1}. {item}" for i, item in enumerate(items)]) or "(порожній)"
    text = f"🧾 Чек '{table}':\n{item_list}\n\n📂 Оберіть категорію:"
    keyboard = [[InlineKeyboardButton(cat, callback_data=f"category|{table}|{cat}")] for cat in menu]
    keyboard.append([InlineKeyboardButton("✏️ Редагувати чек", callback_data=f"edit|{table}")])
    keyboard.append([InlineKeyboardButton("✅ Завершити чек", callback_data=f"finish|{table}")])
    keyboard.append([InlineKeyboardButton("🔁 Повернутися до офіціантів", callback_data="restart")])
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    action = data[0]
    waiter = context.user_data.get("waiter")

    if action == "waiter":
        context.user_data["waiter"] = data[1]
        waiter = data[1]
        context.user_data["checks"].setdefault(waiter, {})
        context.user_data["history"].setdefault(waiter, load_history(waiter))
        keyboard = [[InlineKeyboardButton("➕ Створити новий чек", callback_data="new_check")]]
        for table in context.user_data["checks"][waiter]:
            keyboard.append([InlineKeyboardButton(f"📋 {table} (ред.)", callback_data=f"edit|{table}")])
        existing = set(context.user_data["checks"][waiter])
        for record in context.user_data["history"][waiter]:
            if record['table'] not in existing:
                keyboard.append([InlineKeyboardButton(f"📜 {record['table']} ({record['timestamp']})", callback_data=f"edit|{record['table']}")])
        await query.edit_message_text(f"✅ Офіціант: {waiter}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == "new_check":
        context.user_data["new_check_waiting"] = True
        await query.message.reply_text("✍️ Введіть назву столу:", reply_markup=ReplyKeyboardRemove())

    elif action == "category":
        table, cat = data[1], data[2]
        await update_category_view(context, query, table, cat)

    elif action == "toggle":
        table, item, cat = data[1], data[2], data[3]
        context.user_data["checks"][waiter][table]["items"].append(item)
        await update_category_view(context, query, table, cat)

    elif action == "rm":
        table, item, cat = data[1], data[2], data[3]
        items = context.user_data["checks"][waiter][table]["items"]
        if item in items:
            items.remove(item)
        await update_category_view(context, query, table, cat)

    elif action == "backcat":
        table = data[1]
        await show_category_menu(query.message, context, table)

    elif action == "edit":
        table = data[1]
        context.user_data["current_check"] = table
        if table not in context.user_data["checks"][waiter]:
            for record in context.user_data["history"][waiter]:
                if record["table"] == table:
                    context.user_data["checks"][waiter][table] = {"items": record["items"]}
        await show_category_menu(query.message, context, table)

    elif action == "finish":
        table = data[1]
        items = context.user_data["checks"][waiter][table]["items"]
        if not items:
            await query.edit_message_text("⚠️ Чек порожній.")
            return
        total = sum(prices[i] for i in items)
        counted = {i: items.count(i) for i in set(items)}
        text = f"🧾 Чек для {table} (офіціант: {waiter}):\n\n"
        for i, (item, count) in enumerate(counted.items(), 1):
            text += f"{i}. {item} x{count} — {count * prices[item]} грн\n"
        text += f"\n💰 Сума: {total} грн"
        record = {
            "table": table,
            "items": items.copy(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        context.user_data["history"][waiter].append(record)
        save_to_file(waiter, context.user_data["history"][waiter])
        await query.edit_message_text(text + "\n✅ Чек збережено.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔁 Назад", callback_data="restart")]]))

    elif action == "restart":
        await start(update, context)

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiter = context.user_data.get("waiter")
    if not waiter:
        await update.message.reply_text("⚠️ Спочатку оберіть офіціанта через /start")
        return
    context.user_data["history"][waiter] = []
    save_to_file(waiter, [])
    await update.message.reply_text("🗑 Історія очищена.")

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiter = context.user_data.get("waiter")
    if not waiter:
        await update.message.reply_text("⚠️ Ви ще не вибрали офіціанта (/start).")
        return
    history = context.user_data.get("history", {}).get(waiter, [])
    if not history:
        await update.message.reply_text("📭 Історія пуста.")
        return
    text = f"📜 Історія чеків ({waiter}):\n"
    for i, record in enumerate(history, 1):
        text += f"\n{i}. Стіл: {record['table']} — {record['timestamp']}\n"
        for j, item in enumerate(record["items"], 1):
            text += f"  {j}. {item}\n"
    await update.message.reply_text(text)

async def save_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiter = context.user_data.get("waiter")
    if not waiter:
        await update.message.reply_text("⚠️ Ви ще не вибрали офіціанта (/start).")
        return
    filename = f"history_{waiter}.json"
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            await update.message.reply_document(f, filename=filename)
    else:
        await update.message.reply_text("📭 Історія не знайдена.")

# Запуск
import asyncio

TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT"))
WEBHOOK_URL = f"https://web-production-ef63.up.railway.app/webhook"

async def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("history", show_history))
    app.add_handler(CommandHandler("save", save_file))
    app.add_handler(CommandHandler("clear", clear_history))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print(f"🚀 Встановлюємо Webhook: {WEBHOOK_URL}")
    await app.bot.set_webhook(WEBHOOK_URL)

    print(f"✅ Запуск на порту {PORT}")
    await app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=WEBHOOK_URL
    )

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()

    asyncio.get_event_loop().run_until_complete(main())

