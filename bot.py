import os
import json
import logging
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
COURIER_URL = "https://t.me/managervapeshopdd"

def get_admin_ids():
    ids = []
    for key in ("ADMIN_ID", "ADMIN_ID1"):
        val = os.getenv(key)
        if val and val.isdigit():
            ids.append(int(val))
    if not ids:
        raise RuntimeError("❌ ADMIN_ID variables not set correctly")
    return ids

ADMIN_IDS = get_admin_ids()

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN not set")

# ================== LOGGING ==================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

# ================== LOAD CATALOG ==================
with open("catalog.json", "r", encoding="utf-8") as f:
    CATALOG = json.load(f)

CURRENCY = CATALOG.get("currency", "EUR")

# ================== HELPERS ==================
def get_cart(context):
    return context.user_data.setdefault("cart", [])

def cart_total(cart):
    return round(sum(item["price"] for item in cart), 2)

def get_username(user):
    return f"@{user.username}" if user.username else f"id:{user.id}"

# ================== CITY SELECTION ==================
async def ask_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📍 Берлін", callback_data="city:Berlin")],
        [InlineKeyboardButton("📍 Дрезден", callback_data="city:Dresden")],
        [InlineKeyboardButton("📍 Лейпциг", callback_data="city:Leipzig")],
        [InlineKeyboardButton("✍️ Інше місто", callback_data="city:OTHER")]
    ]

    await update.message.reply_text(
        "Звідки ви?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    city = query.data.split(":")[1]

    if city == "OTHER":
        context.user_data["awaiting_city"] = True
        await query.edit_message_text("✍️ Напишіть ваше місто:")
    else:
        context.user_data["city"] = city
        await show_main_menu(query, context)

async def city_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_city"):
        return

    context.user_data["city"] = update.message.text.strip()
    context.user_data.pop("awaiting_city", None)

    await show_main_menu(update, context)

# ================== MAIN MENU ==================
async def show_main_menu(update_or_query, context):
    keyboard = [
        [InlineKeyboardButton("🛍 Каталог", callback_data="catalog")],
        [InlineKeyboardButton("ℹ️ Контакт адміністратора", url=COURIER_URL)]
    ]

    text = "Вітаю 👋\nОберіть дію:"

    if hasattr(update_or_query, "edit_message_text"):
        await update_or_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update_or_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await ask_city(update, context)

# ================== CATALOG ==================
async def catalog_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    for key, data in CATALOG["categories"].items():
        keyboard.append([
            InlineKeyboardButton(data["title"], callback_data=f"category:{key}")
        ])

    keyboard.append([InlineKeyboardButton("🛒 Кошик", callback_data="cart")])
    keyboard.append([InlineKeyboardButton("⬅ На головну", callback_data="start")])

    await query.edit_message_text(
        "Оберіть категорію:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================== CATEGORY ==================
async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category = query.data.split(":")[1]
    context.user_data["category"] = category

    cat_data = CATALOG["categories"][category]
    keyboard = []

    if "brands" in cat_data:
        for brand in cat_data["brands"]:
            keyboard.append([
                InlineKeyboardButton(brand, callback_data=f"brand:{category}:{brand}")
            ])
    else:
        for item in cat_data["items"]:
            keyboard.append([
                InlineKeyboardButton(
                    f"{item['name']} — {item['price']} {CURRENCY}",
                    callback_data=f"add:{category}:{item['name']}"
                )
            ])

    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="catalog")])

    await query.edit_message_text(
        f"{cat_data['title']}\nОберіть товар:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================== BRAND ==================
async def brand_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, category, brand = query.data.split(":", 2)
    brand_data = CATALOG["categories"][category]["brands"][brand]

    keyboard = []
    for flavor in brand_data["items"]:
        keyboard.append([
            InlineKeyboardButton(
                flavor,
                callback_data=f"add:{category}:{brand}:{flavor}"
            )
        ])

    keyboard.append([InlineKeyboardButton("🛒 Кошик", callback_data="cart")])
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data=f"category:{category}")])

    info = f"{brand}\n💶 {brand_data['price']} {CURRENCY}"
    if "nicotine" in brand_data:
        info += f"\nНікотин: {brand_data['nicotine']}"
    if "volume" in brand_data:
        info += f"\nОбʼєм: {brand_data['volume']}"

    await query.edit_message_text(
        info + "\n\nОберіть смак:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================== ADD TO CART ==================
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    category = parts[1]
    cart = get_cart(context)

    if len(parts) == 4:
        _, _, brand, flavor = parts
        price = CATALOG["categories"][category]["brands"][brand]["price"]
        name = f"{brand} — {flavor}"
    else:
        _, _, name = parts
        items = CATALOG["categories"][category]["items"]
        price = next(i["price"] for i in items if i["name"] == name)

    cart.append({"name": name, "price": price})

    await query.edit_message_text(
        f"✅ Додано:\n{name}\n💶 {price} {CURRENCY}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Додати ще", callback_data="catalog")],
            [InlineKeyboardButton("🛒 Кошик", callback_data="cart")]
        ])
    )

# ================== CART ==================
async def cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cart = get_cart(context)

    if not cart:
        text = "🛒 Кошик порожній"
    else:
        lines = [
            f"{i+1}. {item['name']} — {item['price']} {CURRENCY}"
            for i, item in enumerate(cart)
        ]
        text = "🛒 Ваше замовлення:\n\n" + "\n".join(lines)
        text += f"\n\n💰 Разом: {cart_total(cart)} {CURRENCY}"

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Додати ще", callback_data="catalog")],
            [InlineKeyboardButton("✅ Оформити", callback_data="checkout")],
            [InlineKeyboardButton("❌ Очистити", callback_data="clear_cart")]
        ])
    )

# ================== CLEAR CART ==================
async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["cart"] = []
    await query.edit_message_text("🗑 Кошик очищено")

# ================== CHECKOUT ==================
async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    cart = get_cart(context)

    if not cart:
        await query.edit_message_text("🛒 Кошик порожній")
        return

    city = context.user_data.get("city", "Невідомо")
    total = cart_total(cart)

    order_text = (
        "📦 НОВЕ ЗАМОВЛЕННЯ\n\n"
        f"👤 Клієнт: {get_username(user)}\n"
        f"ID: {user.id}\n"
        f"📍 Місто: {city}\n\n"
        "🛒 Товари:\n" +
        "\n".join(f"• {i['name']} — {i['price']} {CURRENCY}" for i in cart) +
        f"\n\n💰 Разом: {total} {CURRENCY}"
        f"\n🕒 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(chat_id=admin_id, text=order_text)

    context.user_data.clear()

    await query.edit_message_text(
        "✅ Дякуємо за замовлення!\n\n"
        "Адміністратор звʼяжеться з вами:\n"
        f"{COURIER_URL}",
        reply_markup=None
    )

# ================== ERROR ==================
async def error_handler(update, context):
    logging.error("ERROR", exc_info=context.error)

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(city_handler, pattern="^city:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, city_text_handler))

    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^start$"))
    app.add_handler(CallbackQueryHandler(catalog_menu, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(category_handler, pattern="^category:"))
    app.add_handler(CallbackQueryHandler(brand_handler, pattern="^brand:"))
    app.add_handler(CallbackQueryHandler(add_to_cart, pattern="^add:"))
    app.add_handler(CallbackQueryHandler(cart_handler, pattern="^cart$"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    app.add_handler(CallbackQueryHandler(checkout, pattern="^checkout$"))

    app.add_error_handler(error_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
