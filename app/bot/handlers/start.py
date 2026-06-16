"""Start and basic command handlers."""
import logging
import time
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from app.database import crud
from app.database.models import UserCreate
from app.config import settings
from app.bot.keyboards import main_menu_keyboard, open_mini_app_keyboard

router = Router()
logger = logging.getLogger(__name__)

# Track bot start time for uptime calculation
_bot_start_time = time.time()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    await state.clear()

    logger.info(f"/start from user {message.from_user.id} (@{message.from_user.username or 'N/A'})")

    try:
        # Register or get user
        user = await crud.get_or_create_user(UserCreate(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code or "ar",
        ))

        is_premium = user["tier"] == "premium"
        tier_text = "مميز" if is_premium else "مجاني"
        tier_emoji = "💎" if is_premium else "🆓"

        # Get user stats
        limits = None
        try:
            from app.freemium import freemium
            limits = await freemium.get_user_limits(user["id"])
        except Exception:
            pass

        stats_text = ""
        if limits:
            stats_text = (
                f"\n📢 القنوات: {limits['channels']['used']}/{limits['channels']['max']}"
                f"\n⚡ القواعد: {limits['rules']['used']}/{limits['rules']['max']}"
                f"\n📝 القوالب: {limits['templates']['used']}/{limits['templates']['max']}"
            )

        text = (
            f"🧠 <b>أهلاً بيك في Cortex Post!</b>\n\n"
            f"منصتك الذكية لنشر المحتوى التلقائي على تليجرام وتويتر\n\n"
            f"حالتك: {tier_emoji} {tier_text}"
            f"{stats_text}\n\n"
            f"⚡ <b>المميزات:</b>\n"
            f"• نشر تلقائي حسب الشروط\n"
            f"• مصادر بيانات متعددة (عملات، RSS، طقس، رياضة)\n"
            f"• قوالب رسائل ديناميكية\n"
            f"• لوحة تحكم ويب\n\n"
            f"اختار من القائمة اللي تحت 👇"
        )

        await message.answer(text, reply_markup=main_menu_keyboard())
        logger.info(f"Start message sent to user {message.from_user.id}")

    except Exception as e:
        logger.error(f"Error in /start handler: {e}", exc_info=True)
        await message.answer("حصل خطأ، حاول تاني بكتابة /start")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    text = (
        "🧠 <b>Cortex Post - دليل الاستخدام</b>\n\n"
        "📢 <b>القنوات</b> - إدارة القنوات اللي البوت ناشر فيها\n"
        "⚡ <b>القواعد</b> - شروط النشر التلقائي (سعر العملة، النسبة، الوقت...)\n"
        "📝 <b>القوالب</b> - قوالب الرسائل بالمتغيرات الديناميكية\n"
        "🔌 <b>المصادر</b> - مصادر البيانات (عملات، RSS، رياضة، طقس...)\n"
        "📊 <b>الإحصائيات</b> - عدد المنشورات وقواعد النشر\n"
        "⚙️ <b>الإعدادات</b> - إعدادات الحساب\n"
        "💎 <b>الاشتراك المميز</b> - ترقية حسابك\n\n"
        "<b>أوامر:</b>\n"
        "/start - بدء البوت\n"
        "/help - المساعدة\n"
        "/panel - لوحة التحكم (ويب اب)\n"
        "/stats - إحصائيات سريعة\n"
        "/debug - حالة النظام والتشخيص\n"
        "/ping - فحص الاتصال"
    )
    await message.answer(text)


@router.message(Command("panel"))
async def cmd_panel(message: Message):
    """Open Mini App web panel."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("أول حاجة ابدأ البوت بـ /start")
        return

    text = "🖥 افتح لوحة التحكم من الزرار اللي تحت 👇"
    kb = open_mini_app_keyboard(settings.WEBAPP_URL)
    await message.answer(text, reply_markup=kb)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Quick stats command."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("أول حاجة ابدأ البوت بـ /start")
        return

    from app.freemium import freemium
    limits = await freemium.get_user_limits(user["id"])

    ch = limits.get("channels", {})
    ru = limits.get("rules", {})
    te = limits.get("templates", {})

    tier = "💎 مميز" if user["tier"] == "premium" else "🆓 مجاني"

    # Get recent posts count
    recent_posts = await crud.get_post_logs_by_user(user["id"], limit=100)
    sent_count = sum(1 for p in recent_posts if p["status"] == "sent")
    failed_count = sum(1 for p in recent_posts if p["status"] == "failed")

    text = (
        f"📊 <b>إحصائيات حسابك</b>\n\n"
        f"الحالة: {tier}\n"
        f"📢 القنوات: {ch.get('used', 0)}/{ch.get('max', 0)}\n"
        f"⚡ القواعد: {ru.get('used', 0)}/{ru.get('max', 0)}\n"
        f"📝 القوالب: {te.get('used', 0)}/{te.get('max', 0)}\n\n"
        f"📤 المنشورات:\n"
        f"  ✅ ناجح: {sent_count}\n"
        f"  ❌ فاشل: {failed_count}\n"
    )
    await message.answer(text)


@router.message(Command("debug"))
async def cmd_debug(message: Message):
    """Debug command - show system status."""
    from app.main import (
        bot as app_bot, dp as app_dp,
        _webhook_updates_received, _webhook_updates_processed,
        _webhook_updates_errors, _startup_complete, _startup_error,
        _last_webhook_update_time, ALLOWED_UPDATE_TYPES
    )

    lines = ["🔧 <b>تشخيص Cortex Post v2.0</b>\n"]

    # Bot status
    if app_bot:
        try:
            me = await app_bot.get_me()
            lines.append(f"✅ البوت: @{me.username}")
        except Exception as e:
            lines.append(f"❌ البوت: خطأ - {e}")
    else:
        lines.append("❌ البوت: غير معد")

    # Webhook status
    if settings.use_webhook and app_bot:
        try:
            info = await app_bot.get_webhook_info()
            lines.append(f"📡 Webhook: {info.url}")
            lines.append(f"📋 تحديثات معلقة: {info.pending_update_count}")
            if info.allowed_updates:
                lines.append(f"📋 Allowed: {', '.join(info.allowed_updates)}")
            else:
                lines.append("📋 Allowed: all (default)")
            if info.last_error_message:
                lines.append(f"⚠️ آخر خطأ: {info.last_error_message}")
            else:
                lines.append("✅ لا أخطاء في الـ webhook")
        except Exception as e:
            lines.append(f"❌ Webhook info error: {e}")
    else:
        lines.append("📡 الوضع: Polling")

    lines.append(f"📨 تحديثات مستلمة: {_webhook_updates_received}")
    lines.append(f"📨 تحديثات معالجة: {_webhook_updates_processed}")
    lines.append(f"📨 أخطاء معالجة: {_webhook_updates_errors}")
    lines.append(f"📨 آخر تحديث: {_last_webhook_update_time or 'لم يأتِ بعد'}")
    lines.append(f"🚀 بدء التشغيل: {'مكتمل' if _startup_complete else 'جاري...'}")

    if _startup_error:
        lines.append(f"❌ خطأ: {_startup_error}")

    lines.append(f"🔗 الرابط: {settings.WEBAPP_URL}")
    lines.append(f"🔧 Allowed Updates: {', '.join(ALLOWED_UPDATE_TYPES)}")

    # Uptime
    uptime = time.time() - _bot_start_time
    hours = int(uptime // 3600)
    minutes = int((uptime % 3600) // 60)
    lines.append(f"⏱ مدة التشغيل: {hours}س {minutes}د")

    text = "\n".join(lines)
    await message.answer(text)


@router.message(Command("ping"))
async def cmd_ping(message: Message):
    """Simple ping command to test bot responsiveness."""
    import time as _time
    start = _time.time()
    reply = await message.answer("🏓 بونج!")
    elapsed = (_time.time() - start) * 1000
    await reply.edit_text(f"🏓 بونج! ({elapsed:.0f}ms)")


@router.message(F.text == "🔙 رجوع")
async def back_to_main(message: Message, state: FSMContext):
    """Return to main menu."""
    await state.clear()
    await message.answer("القائمة الرئيسية 👇", reply_markup=main_menu_keyboard())


# Catch-all for unrecognized text messages
@router.message(F.text)
async def handle_unknown_text(message: Message):
    """Handle unrecognized text messages with a helpful response."""
    # Don't respond to messages that look like commands (starting with /)
    if message.text.startswith("/"):
        await message.answer("❓ أمر مش معروف. جرب /help عشان تشوف الأوامر المتاحة")
        return

    # For other text, suggest using the menu
    await message.answer(
        "🤖 اختار من القائمة اللي تحت 👇\n\n"
        "لو محتاج مساعدة اكتب /help"
    )
