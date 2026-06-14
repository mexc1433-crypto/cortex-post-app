"""Provider management handlers."""
import json
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database import crud
from app.database.models import ProviderCreate
from app.bot.keyboards import (
    providers_keyboard, provider_type_keyboard, provider_detail_keyboard, confirm_keyboard
)
from app.providers import get_available_provider_types
from app.freemium import freemium

router = Router()
logger = logging.getLogger(__name__)


class ProviderStates(StatesGroup):
    waiting_for_type = State()
    waiting_for_config = State()


@router.message(F.text == "🔌 المصادر")
async def show_providers(message: Message):
    """Show user's providers."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("ابدأ البوت بـ /start الأول")
        return
    
    providers = await crud.get_providers_by_user(user["id"])
    
    if not providers:
        text = "🔌 ماعندكش مصادر لسه\n\nضيف مصدر عشان تجيب بيانات"
    else:
        text = f"🔌 **مصادرك** ({len(providers)})\n\nاضغط على مصدر للتفاصيل:"
    
    kb = providers_keyboard(providers)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "prov_add")
async def add_provider_start(callback: CallbackQuery, state: FSMContext):
    """Start provider creation."""
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("ابدأ البوت بـ /start", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🔌 اختار نوع المصدر:",
        reply_markup=provider_type_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prov_type_"))
async def provider_type_selected(callback: CallbackQuery, state: FSMContext):
    """Handle provider type selection."""
    provider_type = callback.data.split("prov_type_")[1]
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    
    # Check webhook access (premium only)
    if provider_type == "webhook" and not await freemium.can_use_webhook(user["id"]):
        await callback.answer("❌ Webhook للمشتركين المميزين بس!", show_alert=True)
        return
    
    config_hints = {
        "crypto": "اكتب معرف العملة والعملة\nمثال: `bitcoin usd`\nأو `ethereum egp`",
        "rss": "ابعت رابط الـ RSS feed\nمثال: `https://example.com/feed.xml`",
        "sports": "اكتب كود المسابقة\nمثال: `PL` (الدوري الإنجليزي)\nأو `CL` (دوري أبطال أوروبا)",
        "weather": "اكتب اسم المدينة\nمثال: `Cairo` أو `Riyadh`",
        "religious": "اكتب نوع المحتوى والمدينة\nمثال: `prayer_times Cairo`\nأو `quran_verse`\nأو `hijri_date`",
        "webhook": "الـ Webhook هيستقبل البيانات تلقائي\nالرابط هيتبعتلك بعد الإنشاء",
    }
    
    await state.update_data(provider_type=provider_type)
    await state.set_state(ProviderStates.waiting_for_config)
    
    await callback.message.edit_text(
        f"🔌 **إعداد مصدر {provider_type}**\n\n{config_hints.get(provider_type, 'اكتب الإعدادات:')}",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(ProviderStates.waiting_for_config)
async def provider_config(message: Message, state: FSMContext):
    """Process provider config."""
    data = await state.get_data()
    provider_type = data["provider_type"]
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    
    config = {}
    name = f"مصدر {provider_type}"
    
    if provider_type == "crypto":
        parts = message.text.strip().split()
        config = {
            "coin_id": parts[0] if parts else "bitcoin",
            "vs_currency": parts[1] if len(parts) > 1 else "usd",
        }
        name = f"🪙 {config['coin_id'].upper()}/{config['vs_currency'].upper()}"
    
    elif provider_type == "rss":
        config = {"feed_url": message.text.strip()}
        name = "📰 RSS Feed"
    
    elif provider_type == "sports":
        config = {
            "competition": message.text.strip().upper(),
            "endpoint": "matches",
        }
        name = f"⚽ {config['competition']}"
    
    elif provider_type == "weather":
        config = {
            "city": message.text.strip(),
            "units": "metric",
            "lang": "ar",
        }
        name = f"🌤 {config['city']}"
    
    elif provider_type == "religious":
        parts = message.text.strip().split()
        content_type = parts[0] if parts else "prayer_times"
        city = parts[1] if len(parts) > 1 else "Cairo"
        config = {
            "content_type": content_type,
            "city": city,
            "country": "Egypt",
        }
        name = f"🕌 {content_type}"
    
    elif provider_type == "webhook":
        config = {}
        name = "🔗 Webhook"
    
    provider = await crud.create_provider(
        user["id"],
        ProviderCreate(
            provider_type=provider_type,
            name=name,
            config=config,
        ),
    )
    
    webhook_url = ""
    if provider_type == "webhook":
        from app.config import settings
        webhook_url = f"\n\n🔗 رابط الـ Webhook:\n`{settings.WEBAPP_URL}/api/webhook/{provider['id']}`"
    
    await message.answer(
        f"✅ تم إنشاء المصدر **{name}** بنجاح!{webhook_url}",
        parse_mode="Markdown"
    )
    await state.clear()


@router.callback_query(F.data.startswith("prov_") & ~F.data.startswith("prov_add") & ~F.data.startswith("prov_type_"))
async def provider_detail(callback: CallbackQuery):
    """Show provider detail."""
    provider_id = int(callback.data.split("_")[1])
    provider = await crud.get_provider_by_id(provider_id)
    
    if not provider:
        await callback.answer("المصدر مش موجود", show_alert=True)
        return
    
    config = provider.get("config", {})
    if isinstance(config, str):
        config = json.loads(config)
    
    config_text = "\n".join(f"  • {k}: {v}" for k, v in config.items()) if config else "بدون إعدادات"
    
    text = (
        f"🔌 **{provider['name']}**\n\n"
        f"النوع: {provider['provider_type']}\n"
        f"الحالة: {'✅ فعّال' if provider['is_active'] else '❌ متوقف'}\n"
        f"آخر جلب: {provider.get('last_fetched_at', 'لم يتم بعد')}\n\n"
        f"الإعدادات:\n{config_text}"
    )
    
    kb = provider_detail_keyboard(provider_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("prov_del_"))
async def delete_provider_confirm(callback: CallbackQuery):
    """Confirm provider deletion."""
    provider_id = int(callback.data.split("_")[2])
    provider = await crud.get_provider_by_id(provider_id)
    if not provider:
        await callback.answer("المصدر مش موجود", show_alert=True)
        return
    
    text = f"⚠️ متأكد إنك عايز تحذف **{provider['name']}**؟\nالقواعد المرتبطة بيه هتتحذف كمان!"
    kb = confirm_keyboard("prov_del", provider_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_prov_del_"))
async def delete_provider(callback: CallbackQuery):
    """Delete provider."""
    provider_id = int(callback.data.split("_")[3])
    await crud.delete_provider(provider_id)
    await callback.message.edit_text("✅ تم حذف المصدر")
    await callback.answer()


@router.callback_query(F.data == "back_providers")
async def back_to_providers(callback: CallbackQuery):
    """Go back to providers list."""
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        return
    
    providers = await crud.get_providers_by_user(user["id"])
    text = f"🔌 **مصادرك** ({len(providers)})"
    kb = providers_keyboard(providers)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()
