"""Channel management handlers."""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, KICKED, MEMBER, ADMINISTRATOR
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.database import crud
from app.database.models import ChannelCreate
from app.bot.keyboards import channels_keyboard, channel_detail_keyboard, confirm_keyboard
from app.freemium import freemium

router = Router()
logger = logging.getLogger(__name__)


class ChannelStates(StatesGroup):
    waiting_for_channel = State()


@router.message(F.text == "📢 القنوات")
async def show_channels(message: Message):
    """Show user's channels."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("ابدأ البوت بـ /start الأول")
        return
    
    channels = await crud.get_channels_by_user(user["id"])
    
    if not channels:
        text = "📢 ماعندكش قنوات لسه\n\nاضيف القناة وادي البوت صلاحية الأدمن فيها"
    else:
        text = f"📢 **قنواتك** ({len(channels)})\n\nاضغط على قناة للتفاصيل:"
    
    kb = channels_keyboard(channels)
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "ch_add")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    """Start channel add process."""
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("ابدأ البوت بـ /start الأول", show_alert=True)
        return
    
    if not await freemium.can_add_channel(user["id"]):
        await callback.answer("❌ وصلت للحد الأقصى! رقّي حسابك للمميز", show_alert=True)
        return
    
    await state.set_state(ChannelStates.waiting_for_channel)
    await callback.message.edit_text(
        "➕ **إضافة قناة**\n\n"
        "1. ضيف البوت كأدمن في القناة\n"
        "2. ابعت معرف القناة (مثال: @my_channel)\n"
        "أو ابعته للأمام رسالة من القناة",
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(ChannelStates.waiting_for_channel)
async def process_channel_add(message: Message, state: FSMContext):
    """Process channel addition."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await state.clear()
        return
    
    # Extract channel username from message
    channel_username = message.text.strip()
    if channel_username.startswith("@"):
        channel_username = channel_username[1:]
    
    # Try to get chat info using the bot instance
    bot = message.bot
    
    try:
        chat = await bot.get_chat(f"@{channel_username}")
        
        # Check if bot is admin
        bot_member = await bot.get_chat_member(chat.id, bot.id)
        if bot_member.status not in ("administrator", "creator"):
            await message.answer("❌ البوت لازم يكون أدمن في القناة!")
            return
        
        # Save channel
        channel = await crud.create_channel(
            user["id"],
            ChannelCreate(
                channel_telegram_id=chat.id,
                channel_title=chat.title or channel_username,
                channel_username=chat.username or channel_username,
                channel_type="channel" if chat.type == "channel" else "group",
            ),
        )
        
        await message.answer(
            f"✅ تم إضافة القناة **{chat.title}** بنجاح!",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error adding channel: {e}")
        await message.answer(
            "❌ محدش قدر يضيف القناة.\n"
            "تأكد إن البوت أدمن فيها وإن المعرف صح"
        )
    
    await state.clear()


@router.callback_query(F.data.startswith("ch_") & (F.data != "ch_add"))
async def channel_detail(callback: CallbackQuery):
    """Show channel detail."""
    channel_id = int(callback.data.split("_")[1])
    channel = await crud.get_channel_by_id(channel_id)
    
    if not channel:
        await callback.answer("القناة مش موجودة", show_alert=True)
        return
    
    status = "✅ فعّالة" if channel["is_active"] else "❌ متوقفة"
    text = (
        f"📢 **{channel['channel_title']}**\n\n"
        f"المعرف: @{channel.get('channel_username', '—')}\n"
        f"النوع: {channel['channel_type']}\n"
        f"الحالة: {status}\n"
        f"التاريخ: {channel['created_at']}"
    )
    
    kb = channel_detail_keyboard(channel_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("ch_del_"))
async def delete_channel_confirm(callback: CallbackQuery):
    """Confirm channel deletion."""
    channel_id = int(callback.data.split("_")[2])
    channel = await crud.get_channel_by_id(channel_id)
    
    if not channel:
        await callback.answer("القناة مش موجودة", show_alert=True)
        return
    
    text = f"⚠️ متأكد إنك عايز تحذف القناة **{channel['channel_title']}**؟"
    kb = confirm_keyboard("ch_del", channel_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_ch_del_"))
async def delete_channel(callback: CallbackQuery):
    """Delete channel."""
    channel_id = int(callback.data.split("_")[3])
    await crud.delete_channel(channel_id)
    await callback.message.edit_text("✅ تم حذف القناة")
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_"))
async def cancel_action(callback: CallbackQuery):
    """Cancel any action."""
    await callback.message.edit_text("تم الإلغاء ❌")
    await callback.answer()


@router.callback_query(F.data == "back_channels")
async def back_to_channels(callback: CallbackQuery):
    """Go back to channels list."""
    user = await crud.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        return
    
    channels = await crud.get_channels_by_user(user["id"])
    text = f"📢 **قنواتك** ({len(channels)})"
    kb = channels_keyboard(channels)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()
