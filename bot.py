import os
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

if not BOT_TOKEN or not OWNER_ID:
    raise RuntimeError("❌ BOT_TOKEN або OWNER_ID не задані")

# ================== LOGGING ==================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ================== CATALOG ==================
CATALOG = {
    "liquids": {
        "title": "💧 Рідини",
        "items": {
            "elfliq": {"name": "ELFLIQ", "price": 18},
            "chaser": {"name": "CHASER", "price": 20},
            "hqd": {"name": "HQD PREMIUM", "price": 19},
        },
    },
    "devices": {
        "title": "📱 Девайси",
        "items": {
            "vape10k": {"name": "Багаторазова дудка 10 000 тяг", "price": 25},
            "vape20k": {"name": "Багаторазова дудка 20 000 тяг", "price": 35},
        },
    },
    "parts": {
        "title": "🔧 Комплектуючі",
        "items": {
            "vaporesso_pod": {
                "name": "Картриджі Vaporesso",
                "price": 7,
            },
        },
    },
}

# ================== HELPERS ==================
def get_username(user):
    if user.username:
        return f"@{user.username}"
    return "❌ username відсутній"

# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📦 Каталог", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Мій кошик", callback_data="cart")],
    ]
    await update.message.reply_text(
        "Вітаю! Оберіть дію:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton(cat["title"], callback_data=f"cat:{key}")]
        for key, cat in CATALOG.items()
    ]
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="start")])

    await query.message.reply_text(
        "Оберіть категорію:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cat_key = query.data.split(":")[1]
    category = CATALOG.get(cat_key)

    if not category:
        await query.message.reply_text("❌ Категорія не знайдена")
        return

    keyboard = [
        [
            InlineKeyboardButton(
                f"{item['name']} — {item['price']} €",
                callback_data=f"add:{cat_key}:{item_key}",
            )
        ]
        for item_key, item in category["items"].items()
    ]

    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="catalog")])

    await query.message.reply_text(
        category["title"],
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, cat_key, item_key = query.data.split(":")
    item = CATALOG[cat_key]["items"][item_key]

    cart = context.user_data.setdefault("cart", [])
    cart.append(item)

    await query.message.reply_text(
        f"✅ Додано: {item['name']} ({item['price']} €)",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🛒 Перейти до кошика", callback_data="cart")]]
        ),
    )


async def show_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cart = context.user_data.get("cart", [])

    if not cart:
        await query.message.reply_text("🛒 Кошик порожній")
        return

    total = sum(item["price"] for item in cart)

    text = "🛒 Ваше замовлення:\n\n"
    for item in cart:
        text += f"• {item['name']} — {item['price']} €\n"
    text += f"\n💰 Разом: {total} €"

    keyboard = [
        [InlineKeyboardButton("✅ Підтвердити", callback_data="confirm")],
        [InlineKeyboardButton("⬅ Каталог", callback_data="catalog")],
    ]

    await query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cart = context.user_data.get("cart")
    if not cart:
        await query.message.reply_text("🛒 Кошик порожній")
        return

    user = update.effective_user
    username = get_username(user)
    total = sum(item["price"] for item in cart)

    text = (
        "🆕 НОВЕ ЗАМОВЛЕННЯ\n\n"
        f"👤 Клієнт: {user.full_name}\n"
        f"🔗 Username: {username}\n\n"
    )

    for item in cart:
        text += f"• {item['name']} — {item['price']} €\n"

    text += f"\n💰 Сума: {total} €"

    await context.bot.send_message(chat_id=OWNER_ID, text=text)
    await query.message.reply_text("✅ Замовлення прийнято! Ми з вами звʼяжемось.")

    context.user_data.clear()

# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(show_categories, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(show_products, pattern="^cat:"))
    app.add_handler(CallbackQueryHandler(add_to_cart, pattern="^add:"))
    app.add_handler(CallbackQueryHandler(show_cart, pattern="^cart$"))
    app.add_handler(CallbackQueryHandler(confirm_order, pattern="^confirm$"))

    logger.info("🤖 Bot запущено успішно")
    app.run_polling()

if __name__ == "__main__":
    main()
