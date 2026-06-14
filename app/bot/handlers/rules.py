"""Rules management handlers."""
import json
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database import crud
from app.database.models import ProviderCreate, TemplateCreate, RuleCreate, RuleUpdate, ConditionItem
from app.bot.keyboards import rules_keyboard, rule_detail_keyboard, provider_type_keyboard
from app.freemium import freemium

router = Router()
logger = logging.getLogger(__name__)


class RuleStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_provider = State()
    waiting_for_template = State()
    waiting_for_channel = State()
    waiting_for_conditions = State()
    waiting_for_condition_logic = State()
    waiting_for_cooldown = State()


@router.message(F.text == "⚡ القواعد")
async def show_rules(message: Message):
    """Show user's rules."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("ابدأ البوت بـ /start الأول")
        return
    
    rules = await crud.get_rules_by_user(user["id"])
    
    if not rules:
        text = "⚡ ماعندكش قواعد لسه\n\nاعمل قاعدة عشان ينزل محتوى تلقائي"
    else:
        text = f"⚡ **قواعدك** ({len(rules)})\n\nاضغط على قاعدة للتفاصيل:"
    
    kb = rules_keyboard(rules)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "rule_add")
async def add_rule_start(callback: CallbackQuery, state: FSMContext):
    """Start rule creation."""
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("ابدأ البوت بـ /start", show_alert=True)
        return
    
    if not await freemium.can_add_rule(user["id"]):
        await callback.answer("❌ وصلت للحد الأقصى! رقّي حسابك", show_alert=True)
        return
    
    await state.set_state(RuleStates.waiting_for_name)
    await callback.message.edit_text(
        "⚡ **قاعدة جديدة**\n\nاكتب اسم القاعدة:",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(RuleStates.waiting_for_name)
async def rule_name(message: Message, state: FSMContext):
    """Save rule name and ask for provider type."""
    await state.update_data(rule_name=message.text.strip())
    await state.set_state(RuleStates.waiting_for_provider)
    
    text = "🔌 اختار نوع المصدر اللي القاعدة هتتابعه:"
    kb = provider_type_keyboard()
    await message.answer(text, reply_markup=kb)


@router.callback_query(RuleStates.waiting_for_provider, F.data.startswith("prov_type_"))
async def rule_provider_type(callback: CallbackQuery, state: FSMContext):
    """Save provider type and show available providers or create one."""
    provider_type = callback.data.split("prov_type_")[1]
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    
    # Check if user has providers of this type
    providers = await crud.get_providers_by_user(user["id"])
    type_providers = [p for p in providers if p["provider_type"] == provider_type]
    
    if not type_providers:
        # Create a default provider for this type
        default_configs = {
            "crypto": {"coin_id": "bitcoin", "vs_currency": "usd"},
            "rss": {"feed_url": ""},
            "sports": {"competition": "PL", "endpoint": "matches"},
            "weather": {"city": "Cairo", "units": "metric"},
            "religious": {"content_type": "prayer_times", "city": "Cairo", "country": "Egypt"},
            "webhook": {},
        }
        
        provider = await crud.create_provider(
            user["id"],
            ProviderCreate(
                provider_type=provider_type,
                name=f"مصدر {provider_type} تلقائي",
                config=default_configs.get(provider_type, {}),
            ),
        )
        provider_id = provider["id"]
    else:
        provider_id = type_providers[0]["id"]
    
    await state.update_data(provider_id=provider_id, provider_type=provider_type)
    
    # Now show templates
    all_templates = await crud.get_templates_by_user(user["id"])
    templates = [t for t in all_templates if t["provider_type"] == provider_type]
    
    if not templates:
        # Create a default template
        default_templates = {
            "crypto": "🪙 {{coin}}\n💰 السعر: ${{price|comma}}\n📊 التغيير: {{price_change_24h|percent}}",
            "rss": "📰 {{title}}\n\n{{summary}}\n🔗 {{link}}",
            "sports": "⚽ {{competition_name}}\n{{home_team}} vs {{away_team}}",
            "weather": "🌤 {{city}}\n🌡 الحرارة: {{temp}}°\n💧 الرطوبة: {{humidity}}%\n{{description}}",
            "religious": "🕌 أوقات الصلاة - {{city}}\n🌅 الفجر: {{fajr}}\n☀️ الظهر: {{dhuhr}}\n🌤 العصر: {{asr}}\n🌅 المغرب: {{maghrib}}\n🌙 العشاء: {{isha}}",
            "webhook": "📡 {{data}}",
        }
        
        template = await crud.create_template(
            user["id"],
            TemplateCreate(
                name=f"قالب {provider_type} تلقائي",
                content=default_templates.get(provider_type, "{{data}}"),
                provider_type=provider_type,
            ),
        )
        template_id = template["id"]
    else:
        template_id = templates[0]["id"]
    
    await state.update_data(template_id=template_id)
    
    # Show channels
    channels = await crud.get_channels_by_user(user["id"])
    if not channels:
        await callback.message.edit_text(
            "❌ لازم تضيف قناة الأول!\n\nروح القنوات وضيف واحدة وبعدين ارجع اعمل القاعدة"
        )
        await state.clear()
        return
    
    from app.bot.keyboards import channels_keyboard
    await state.set_state(RuleStates.waiting_for_channel)
    await callback.message.edit_text(
        "📢 اختار القناة اللي عايز تنشر فيها:",
        reply_markup=channels_keyboard(channels)
    )
    await callback.answer()


@router.callback_query(RuleStates.waiting_for_channel, F.data.startswith("ch_") and ~F.data.endswith("add"))
async def rule_channel(callback: CallbackQuery, state: FSMContext):
    """Save channel selection and ask for conditions."""
    channel_id = int(callback.data.split("_")[1])
    await state.update_data(channel_id=channel_id)
    await state.set_state(RuleStates.waiting_for_conditions)
    
    await callback.message.edit_text(
        "📋 **الشروط**\n\n"
        "اكتب الشرط بالشكل ده:\n"
        "`field operator value`\n\n"
        "أمثلة:\n"
        "`price > 50000`\n"
        "`price_change_24h > 5`\n"
        "`temp < 10`\n\n"
        "لو عايز أكتر من شرط، اكتب كل واحد في سطر\n"
        "أو ابعت `done` عشان تنجز من غير شروط",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(RuleStates.waiting_for_conditions)
async def rule_conditions(message: Message, state: FSMContext):
    """Process rule conditions."""
    if message.text.strip().lower() == "done":
        conditions = []
    else:
        conditions = []
        for line in message.text.strip().split("\n"):
            parts = line.strip().split()
            if len(parts) >= 3:
                conditions.append({
                    "field": parts[0],
                    "operator": parts[1],
                    "value": parts[2] if len(parts) == 3 else parts[2:],
                })
    
    await state.update_data(conditions=conditions)
    await state.set_state(RuleStates.waiting_for_cooldown)
    
    await message.answer(
        "⏰ **فترة الانتظار**\n\n"
        "اكتب عدد الدقائق بين كل نشر (الافتراضي: 30)\n"
        "أو ابعت `done` للقيمة الافتراضية",
        parse_mode="Markdown"
    )


@router.message(RuleStates.waiting_for_cooldown)
async def rule_cooldown(message: Message, state: FSMContext):
    """Process cooldown and create rule."""
    try:
        cooldown = int(message.text.strip()) if message.text.strip().lower() != "done" else 30
    except ValueError:
        cooldown = 30
    
    data = await state.get_data()
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    
    condition_items = [ConditionItem(**c) for c in data.get("conditions", [])]

    rule = await crud.create_rule(
        user["id"],
        RuleCreate(
            name=data["rule_name"],
            provider_id=data["provider_id"],
            template_id=data["template_id"],
            channel_id=data["channel_id"],
            conditions=condition_items,
            condition_logic="AND",
            cooldown_minutes=cooldown,
        ),
    )
    
    await message.answer(
        f"✅ تم إنشاء القاعدة **{data['rule_name']}** بنجاح!\n\n"
        f"القاعدة هتشغل تلقائي لما الشروط تتحقق.",
        parse_mode="Markdown"
    )
    await state.clear()


@router.callback_query(F.data.startswith("rule_") and not F.data.startswith("rule_add"))
async def rule_detail(callback: CallbackQuery):
    """Show rule detail."""
    parts = callback.data.split("_")
    
    if parts[1] == "toggle":
        rule_id = int(parts[2])
        rule = await crud.get_rule_by_id(rule_id)
        if rule:
            new_status = not rule["is_active"]
            await crud.update_rule(rule_id, RuleUpdate(is_active=new_status))
            status_text = "فعّالة ✅" if new_status else "متوقفة ❌"
            await callback.answer(f"القاعدة {status_text}")
            # Refresh view
            rule = await crud.get_rule_by_id(rule_id)
        else:
            await callback.answer("القاعدة مش موجودة", show_alert=True)
            return
    elif parts[1] == "run":
        rule_id = int(parts[2])
        from app.engine.scheduler import cortex_scheduler
        await cortex_scheduler.trigger_rule_now(rule_id)
        await callback.answer("🔥 جاري التشغيل...")
        return
    elif parts[1] == "del":
        rule_id = int(parts[2])
        from app.bot.keyboards import confirm_keyboard
        text = "⚠️ متأكد إنك عايز تحذف القاعدة دي؟"
        kb = confirm_keyboard("rule_del", rule_id)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return
    else:
        rule_id = int(parts[1])
    
    rule = await crud.get_rule_by_id(rule_id)
    if not rule:
        await callback.answer("القاعدة مش موجودة", show_alert=True)
        return
    
    conditions = rule.get("conditions", [])
    if isinstance(conditions, str):
        conditions = json.loads(conditions)
    
    cond_text = "\n".join(
        f"  • {c['field']} {c['operator']} {c['value']}" 
        for c in conditions
    ) if conditions else "بدون شروط"
    
    status = "✅ فعّالة" if rule["is_active"] else "❌ متوقفة"
    
    text = (
        f"⚡ **{rule['name']}**\n\n"
        f"الحالة: {status}\n"
        f"المنطق: {rule['condition_logic']}\n"
        f"الانتظار: {rule['cooldown_minutes']} دقيقة\n\n"
        f"📋 الشروط:\n{cond_text}"
    )
    
    kb = rule_detail_keyboard(rule_id, rule["is_active"])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_rule_del_"))
async def delete_rule(callback: CallbackQuery):
    """Delete a rule."""
    rule_id = int(callback.data.split("_")[3])
    await crud.delete_rule(rule_id)
    await callback.message.edit_text("✅ تم حذف القاعدة")
    await callback.answer()


@router.callback_query(F.data == "back_rules")
async def back_to_rules(callback: CallbackQuery):
    """Go back to rules list."""
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        return
    
    rules = await crud.get_rules_by_user(user["id"])
    text = f"⚡ **قواعدك** ({len(rules)})"
    kb = rules_keyboard(rules)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()
