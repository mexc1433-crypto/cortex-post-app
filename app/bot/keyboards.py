"""Keyboards for Cortex Post Telegram Bot."""
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

# Main menu reply keyboard
def main_menu_keyboard() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="📢 القنوات"), KeyboardButton(text="⚡ القواعد")],
        [KeyboardButton(text="📝 القوالب"), KeyboardButton(text="🔌 المصادر")],
        [KeyboardButton(text="📊 الإحصائيات"), KeyboardButton(text="⚙️ الإعدادات")],
        [KeyboardButton(text="💎 الاشتراك المميز")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# Channel management
def channels_keyboard(channels: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(
                text=f"{'✅' if ch['is_active'] else '❌'} {ch['channel_title']}",
                callback_data=f"ch_{ch['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="➕ إضافة قناة", callback_data="ch_add")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def channel_detail_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🗑 حذف القناة", callback_data=f"ch_del_{channel_id}")],
        [InlineKeyboardButton(text="🔙 القنوات", callback_data="back_channels")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Rules management
def rules_keyboard(rules: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for rule in rules:
        status = "✅" if rule['is_active'] else "❌"
        buttons.append([
            InlineKeyboardButton(
                text=f"{status} {rule['name']}",
                callback_data=f"rule_{rule['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="➕ قاعدة جديدة", callback_data="rule_add")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def rule_detail_keyboard(rule_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "⏸ إيقاف" if is_active else "▶️ تفعيل"
    buttons = [
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"rule_toggle_{rule_id}"),
            InlineKeyboardButton(text="🔥 تشغيل الآن", callback_data=f"rule_run_{rule_id}"),
        ],
        [InlineKeyboardButton(text="🗑 حذف القاعدة", callback_data=f"rule_del_{rule_id}")],
        [InlineKeyboardButton(text="🔙 القواعد", callback_data="back_rules")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Templates management
def templates_keyboard(templates: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for tmpl in templates:
        buttons.append([
            InlineKeyboardButton(
                text=f"📝 {tmpl['name']}",
                callback_data=f"tmpl_{tmpl['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="➕ قالب جديد", callback_data="tmpl_add")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def template_detail_keyboard(template_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="✏️ تعديل", callback_data=f"tmpl_edit_{template_id}")],
        [InlineKeyboardButton(text="🗑 حذف", callback_data=f"tmpl_del_{template_id}")],
        [InlineKeyboardButton(text="🔙 القوالب", callback_data="back_templates")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Providers management
def providers_keyboard(providers: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for prov in providers:
        type_emoji = {
            "crypto": "🪙", "rss": "📰", "sports": "⚽",
            "weather": "🌤", "religious": "🕌", "webhook": "🔗"
        }
        emoji = type_emoji.get(prov['provider_type'], '🔌')
        buttons.append([
            InlineKeyboardButton(
                text=f"{emoji} {prov['name']}",
                callback_data=f"prov_{prov['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="➕ مصدر جديد", callback_data="prov_add")])
    buttons.append([InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def provider_type_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🪙 عملات رقمية", callback_data="prov_type_crypto"),
            InlineKeyboardButton(text="📰 RSS", callback_data="prov_type_rss"),
        ],
        [
            InlineKeyboardButton(text="⚽ رياضة", callback_data="prov_type_sports"),
            InlineKeyboardButton(text="🌤 طقس", callback_data="prov_type_weather"),
        ],
        [
            InlineKeyboardButton(text="🕌 أذكار وأوقات", callback_data="prov_type_religious"),
            InlineKeyboardButton(text="🔗 Webhook", callback_data="prov_type_webhook"),
        ],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_providers")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def provider_detail_keyboard(provider_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🗑 حذف", callback_data=f"prov_del_{provider_id}")],
        [InlineKeyboardButton(text="🔙 المصادر", callback_data="back_providers")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Subscription
def subscription_keyboard(is_premium: bool) -> InlineKeyboardMarkup:
    if is_premium:
        buttons = [
            [InlineKeyboardButton(text="✅ اشتراكك مميز فعلاً", callback_data="noop")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="💎 ترقية للمميز", callback_data="sub_upgrade")],
            [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_main")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Confirm keyboard
def confirm_keyboard(action: str, item_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ تأكيد", callback_data=f"confirm_{action}_{item_id}"),
            InlineKeyboardButton(text="❌ إلغاء", callback_data=f"cancel_{action}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Open Mini App
def open_mini_app_keyboard(webapp_url: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🖥 لوحة التحكم", web_app={"url": f"{webapp_url}/dashboard"})],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
