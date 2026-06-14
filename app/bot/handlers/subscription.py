"""Subscription and settings handlers."""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from app.database import crud
from app.bot.keyboards import subscription_keyboard, main_menu_keyboard
from app.freemium import freemium

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "💎 الاشتراك المميز")
async def show_subscription(message: Message):
    """Show subscription info."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("ابدأ البوت بـ /start الأول")
        return
    
    limits = await freemium.get_user_limits(user["id"])
    is_premium = user["tier"] == "premium"
    
    if is_premium:
        text = (
            "💎 **اشتراكك مميز!**\n\n"
            "✅ قنوات غير محدودة\n"
            "✅ قواعد غير محدودة\n"
            "✅ قوالب غير محدودة\n"
            "✅ نشر على تويتر\n"
            "✅ Webhook\n\n"
            f"بينتهي: {user.get('premium_expires_at', 'غير محدد')}"
        )
    else:
        text = (
            "🆓 **حسابك مجاني**\n\n"
            f"📢 القنوات: {limits['channels']['used']}/{limits['channels']['max']}\n"
            f"⚡ القواعد: {limits['rules']['used']}/{limits['rules']['max']}\n"
            f"📝 القوالب: {limits['templates']['used']}/{limits['templates']['max']}\n"
            f"🐦 تويتر: ❌\n"
            f"🔗 Webhook: ❌\n\n"
            "💎 **المميز يديك:**\n"
            "• قنوات غير محدودة\n"
            "• قواعد غير محدودة\n"
            "• قوالب غير محدودة\n"
            "• نشر على تويتر\n"
            "• Webhook\n\n"
            "تواصل مع الإدارة للترقية 📩"
        )
    
    kb = subscription_keyboard(is_premium)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.message(F.text == "📊 الإحصائيات")
async def show_stats(message: Message):
    """Show statistics."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("ابدأ البوت بـ /start الأول")
        return
    
    limits = await freemium.get_user_limits(user["id"])
    recent_posts = await crud.get_post_logs_by_user(user["id"], limit=5)
    
    posts_text = ""
    for post in recent_posts:
        status = "✅" if post["status"] == "sent" else "❌"
        platform = "📱" if post["platform"] == "telegram" else "🐦"
        posts_text += f"\n{status} {platform} {post['created_at'][:16]}"
    
    text = (
        f"📊 **إحصائيات حسابك**\n\n"
        f"📢 القنوات: {limits['channels']['used']}/{limits['channels']['max']}\n"
        f"⚡ القواعد: {limits['rules']['used']}/{limits['rules']['max']}\n"
        f"📝 القوالب: {limits['templates']['used']}/{limits['templates']['max']}\n\n"
        f"📝 آخر المنشورات:{posts_text if posts_text else '\nلا يوجد منشورات بعد'}"
    )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "⚙️ الإعدادات")
async def show_settings(message: Message):
    """Show settings."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("ابدأ البوت بـ /start الأول")
        return
    
    text = (
        f"⚙️ **الإعدادات**\n\n"
        f"👤 الاسم: {user.get('first_name', '—')}\n"
        f"🆔 المعرف: @{user.get('username', '—')}\n"
        f"💼 الحساب: {'💎 مميز' if user['tier'] == 'premium' else '🆓 مجاني'}\n"
        f"🌐 اللغة: {user.get('language_code', 'ar')}\n\n"
        f"لتحديث إعداداتك، تواصل مع الإدارة 📩"
    )
    
    await message.answer(text, parse_mode="Markdown")


@router.callback_query(F.data == "sub_upgrade")
async def upgrade_request(callback: CallbackQuery):
    """Handle upgrade request."""
    await callback.message.edit_text(
        "💎 **ترقية الحساب**\n\n"
        "تواصل مع إدارة البوت للترقية:\n"
        "أو استخدم كود التفعيل لو عندك واحد"
    )
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    """Go back to main menu."""
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        return
    
    tier_emoji = "💎" if user["tier"] == "premium" else "🆓"
    text = f"🧠 **Cortex Post** | {tier_emoji}\n\nاختار من القائمة 👇"
    await callback.message.edit_text(text, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    """Do nothing."""
    await callback.answer()
