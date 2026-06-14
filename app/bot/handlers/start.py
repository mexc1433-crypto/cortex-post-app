"""Start and basic command handlers."""
import logging
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


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Handle /start command."""
    await state.clear()
    
    # Register or get user
    user = await crud.get_or_create_user(UserCreate(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code or "ar",
    ))
    
    is_premium = user["tier"] == "premium"
    tier_emoji = "💎" if is_premium else "🆓"
    
    text = (
        f"🧠 أهلاً بيك في **Cortex Post**!\n\n"
        f"منصتك الذكية لنشر المحتوى التلقائي على تليجرام وتويتر\n\n"
        f"حالتك: {tier_emoji} {'مميز' if is_premium else 'مجاني'}\n\n"
        f"اختار من القائمة اللي تحت 👇"
    )
    
    await message.answer(text, reply_markup=main_menu_keyboard(), parse_mode="Markdown")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    text = (
        "🧠 **Cortex Post - دليل الاستخدام**\n\n"
        "📢 **القنوات** - إدارة القنوات اللي البوت ناشر فيها\n"
        "⚡ **القواعد** - شروط النشر التلقائي (سعر العملة، النسبة، الوقت...)\n"
        "📝 **القوالب** - قوالب الرسائل بالمتغيرات الديناميكية\n"
        "🔌 **المصادر** - مصادر البيانات (عملات، RSS، رياضة، طقس...)\n"
        "📊 **الإحصائيات** - عدد المنشورات وقواعد النشر\n"
        "⚙️ **الإعدادات** - إعدادات الحساب\n"
        "💎 **الاشتراك المميز** - ترقية حسابك\n\n"
        "🖥 /panel - لوحة التحكم (ويب اب)\n"
        "📊 /stats - إحصائيات سريعة"
    )
    await message.answer(text, parse_mode="Markdown")


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
    
    text = (
        f"📊 **إحصائيات حسابك**\n\n"
        f"الحالة: {tier}\n"
        f"📢 القنوات: {ch.get('used', 0)}/{ch.get('max', 0)}\n"
        f"⚡ القواعد: {ru.get('used', 0)}/{ru.get('max', 0)}\n"
        f"📝 القوالب: {te.get('used', 0)}/{te.get('max', 0)}\n"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "🔙 رجوع")
async def back_to_main(message: Message, state: FSMContext):
    """Return to main menu."""
    await state.clear()
    await message.answer("القائمة الرئيسية 👇", reply_markup=main_menu_keyboard())
