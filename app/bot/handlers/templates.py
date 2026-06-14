"""Template management handlers."""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database import crud
from app.database.models import TemplateCreate
from app.bot.keyboards import templates_keyboard, template_detail_keyboard
from app.freemium import freemium

router = Router()
logger = logging.getLogger(__name__)


class TemplateStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_type = State()
    waiting_for_content = State()


@router.message(F.text == "📝 القوالب")
async def show_templates(message: Message):
    """Show user's templates."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("ابدأ البوت بـ /start الأول")
        return
    
    templates = await crud.get_templates_by_user(user["id"])
    
    if not templates:
        text = "📝 ماعندكش قوالب لسه\n\nاعمل قالب عشان تنسق رسائلك"
    else:
        text = f"📝 **قوالبك** ({len(templates)})\n\nاضغط على قالب للتفاصيل:"
    
    kb = templates_keyboard(templates)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "tmpl_add")
async def add_template_start(callback: CallbackQuery, state: FSMContext):
    """Start template creation."""
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("ابدأ البوت بـ /start", show_alert=True)
        return
    
    if not await freemium.can_add_template(user["id"]):
        await callback.answer("❌ وصلت للحد الأقصى! رقّي حسابك", show_alert=True)
        return
    
    await state.set_state(TemplateStates.waiting_for_name)
    await callback.message.edit_text("📝 اكتب اسم القالب:", parse_mode="Markdown")
    await callback.answer()


@router.message(TemplateStates.waiting_for_name)
async def template_name(message: Message, state: FSMContext):
    """Save template name and ask for type."""
    await state.update_data(template_name=message.text.strip())
    await state.set_state(TemplateStates.waiting_for_type)
    
    from app.bot.keyboards import provider_type_keyboard
    await message.answer("🔌 اختار نوع المصدر اللي القالب بيتعامل معاه:", reply_markup=provider_type_keyboard())


@router.callback_query(TemplateStates.waiting_for_type, F.data.startswith("prov_type_"))
async def template_type(callback: CallbackQuery, state: FSMContext):
    """Save provider type and ask for content."""
    provider_type = callback.data.split("prov_type_")[1]
    await state.update_data(provider_type=provider_type)
    await state.set_state(TemplateStates.waiting_for_content)
    
    field_examples = {
        "crypto": "{{coin}}, {{price}}, {{price_change_24h|percent}}, {{volume_24h|comma}}",
        "rss": "{{title}}, {{link}}, {{summary}}, {{author}}, {{published}}",
        "sports": "{{home_team}}, {{away_team}}, {{score_home}}, {{score_away}}, {{competition_name}}",
        "weather": "{{city}}, {{temp}}, {{feels_like}}, {{humidity}}, {{description}}, {{wind_speed}}",
        "religious": "{{city}}, {{fajr}}, {{dhuhr}}, {{asr}}, {{maghrib}}, {{isha}}, {{hijri_month_ar}}",
        "webhook": "{{data}}, {{event_type}}, {{source}}",
    }
    
    examples = field_examples.get(provider_type, "{{data}}")
    
    await callback.message.edit_text(
        f"📝 **اكتب محتوى القالب**\n\n"
        f"استخدم المتغيرات دي: {examples}\n\n"
        f"فلاتر متاحة:\n"
        f"• `|comma` - أرقام بفواصل (50,000)\n"
        f"• `|percent` - نسبة مئوية (+5.50%)\n"
        f"• `|currency` - عملة ($50,000.00)\n"
        f"• `|emoji` - إيموجي حسب الاتجاه 🟢🔴\n"
        f"• `|upper` / `|lower` - أحرف\n\n"
        f"شرط:\n"
        f"{{{{#if price_change_24h}}}}...{{{{/if}}}}\n"
        f"{{{{#if price_change_24h}}}}صاعد{{{{else}}}}نازل{{{{/if}}}}",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(TemplateStates.waiting_for_content)
async def template_content(message: Message, state: FSMContext):
    """Save template content."""
    data = await state.get_data()
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    
    template = await crud.create_template(
        user["id"],
        TemplateCreate(
            name=data["template_name"],
            content=message.text,
            provider_type=data["provider_type"],
        ),
    )
    
    # Preview the template
    from app.engine.template_engine import template_engine
    variables = template_engine.get_variables(message.text)
    
    await message.answer(
        f"✅ تم إنشاء القالب **{data['template_name']}** بنجاح!\n\n"
        f"المتغيرات المستخدمة: {', '.join(variables) if variables else 'لا يوجد'}",
        parse_mode="Markdown"
    )
    await state.clear()


@router.callback_query(F.data.startswith("tmpl_") and not F.data.startswith("tmpl_add"))
async def template_detail(callback: CallbackQuery):
    """Show template detail."""
    parts = callback.data.split("_")
    
    if parts[1] == "del":
        template_id = int(parts[2])
        await crud.delete_template(template_id)
        await callback.message.edit_text("✅ تم حذف القالب")
        await callback.answer()
        return
    
    if parts[1] == "edit":
        template_id = int(parts[2])
        await callback.message.edit_text("✏️ ابعت المحتوى الجديد للقالب:")
        # For simplicity, we skip FSM here - user can delete and recreate
        await callback.answer("للتعديل، احذف واعمل قالب جديد", show_alert=True)
        return
    
    template_id = int(parts[1])
    template = await crud.get_template_by_id(template_id)
    
    if not template:
        await callback.answer("القالب مش موجود", show_alert=True)
        return
    
    from app.engine.template_engine import template_engine
    variables = template_engine.get_variables(template["content"])
    
    text = (
        f"📝 **{template['name']}**\n\n"
        f"النوع: {template['provider_type']}\n"
        f"الصيغة: {template['parse_mode']}\n"
        f"المتغيرات: {', '.join(variables) if variables else 'لا يوجد'}\n\n"
        f"المحتوى:\n```\n{template['content']}\n```"
    )
    
    kb = template_detail_keyboard(template_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data == "back_templates")
async def back_to_templates(callback: CallbackQuery):
    """Go back to templates list."""
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        return
    
    templates = await crud.get_templates_by_user(user["id"])
    text = f"📝 **قوالبك** ({len(templates)})"
    kb = templates_keyboard(templates)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()
