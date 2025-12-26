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
    ContextTypes
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
ADMIN_ID1 = int(os.getenv("ADMIN_ID1"))
COURIER_URL = "https://t.me/managervapeshopdd"

if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("❌ BOT_TOKEN або ADMIN_ID не задані")

# ================== LOGGING ==================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

# ================== LOAD CATALOG ==================
with open("catalog.json", "r", encoding="utf-8") as f:
    CATALOG = json.load(f)

# ================== HELPERS ==================
def get_cart(context):
    return context.user_data.setdefault("cart", [])

def get_username(user):
    return f"@{user.username}" if user.username else f"(id: {user.id})"

# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛍 Каталог продукції", callback_data="catalog")],
        [InlineKeyboardButton("ℹ️ Контакти адміністратора", url=COURIER_URL)]
    ]

    await update.message.reply_text(
        "Вітаю 👋\nЩо ви хочете замовити?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================== CATALOG ==================
async def catalog_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("💧 Рідини", callback_data="category:liquids")],
        [InlineKeyboardButton("🛒 Кошик", callback_data="cart")],
        [InlineKeyboardButton("⬅ На головну", callback_data="start")]
    ]

    await query.edit_message_text(
        "Оберіть категорію:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================== BRANDS ==================
async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category_key = query.data.split(":")[1]
    brands = CATALOG["categories"][category_key]["brands"]

    keyboard = [
        [InlineKeyboardButton(brand, callback_data=f"brand:{brand}")]
        for brand in brands
    ]
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="catalog")])

    await query.edit_message_text(
        "Оберіть бренд:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================== FLAVORS ==================
async def brand_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    brand = query.data.split(":")[1]
    brand_data = CATALOG["categories"]["liquids"]["brands"][brand]
    price = brand_data["price"]

    keyboard = [
        [InlineKeyboardButton(flavor, callback_data=f"add:{brand}:{flavor}")]
        for flavor in brand_data["items"]
    ]

    keyboard.append([InlineKeyboardButton("🛒 Кошик", callback_data="cart")])
    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="catalog")])

    await query.edit_message_text(
        f"🔥 {brand}\n💶 Ціна: {price} €\n\nОберіть смак:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================== ADD TO CART ==================
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, brand, flavor = query.data.split(":", 2)
    cart = get_cart(context)
    cart.append(f"{brand} – {flavor}")

    keyboard = [
        [InlineKeyboardButton("➕ Додати ще товар", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Перейти в кошик", callback_data="cart")]
    ]

    await query.edit_message_text(
        f"✅ Додано в кошик:\n{brand} – {flavor}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ================== CART ==================
async def cart_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cart = get_cart(context)

    if not cart:
        text = "🛒 Ваш кошик порожній"
    else:
        text = "🛒 Ваше замовлення:\n\n" + "\n".join(
            f"{i+1}. {item}" for i, item in enumerate(cart)
        )

    keyboard = [
        [InlineKeyboardButton("➕ Додати ще товар", callback_data="catalog")],
        [InlineKeyboardButton("✅ Оформити замовлення", callback_data="checkout")],
        [InlineKeyboardButton("❌ Очистити кошик", callback_data="clear_cart")]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

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

    order_text = (
        "📦 НОВЕ ЗАМОВЛЕННЯ\n\n"
        f"👤 Клієнт: {get_username(user)}\n"
        f"ID: {user.id}\n\n"
        "🛒 Товари:\n" +
        "\n".join(f"• {item}" for item in cart) +
        f"\n\n🕒 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    await context.bot.send_message(chat_id=ADMIN_ID, text=order_text)

    context.user_data.clear()

    await query.edit_message_text(
        "✅ Дякуємо за замовлення!\n\n"
        "З вами звʼяжеться наш курʼєр:\n"
        f"{COURIER_URL}"
    )

# ================== ERROR HANDLER ==================
async def error_handler(update, context):
    logging.error("Помилка:", exc_info=context.error)

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^start$"))
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
