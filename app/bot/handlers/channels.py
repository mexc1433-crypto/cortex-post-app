"""Channel management handlers."""
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter, KICKED, MEMBER, ADMINISTRATOR, OWNER
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


# ============================================================================
# My Chat Member Handler - Auto-detect when bot is added/removed from channels
# ============================================================================

@router.my_chat_member()
async def on_bot_chat_member_updated(event: ChatMemberUpdated):
    """
    Automatically detect when the bot is added to or removed from a channel/group.
    This handler fires when the bot's own chat member status changes.
    """
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    chat = event.chat
    user_id = event.from_user.id

    logger.info(
        f"Bot chat member update: chat={chat.id} ({chat.type}) "
        f"title={chat.title} old={old_status} new={new_status} "
        f"by user={user_id}"
    )

    # Bot was added to a channel/group as admin
    if new_status in ("administrator", "member") and old_status in ("left", "kicked"):
        if chat.type in ("channel", "supergroup", "group"):
            # Try to find the user who added the bot
            db_user = await crud.get_user_by_telegram_id(user_id)

            if db_user:
                # Check if channel already exists
                existing_channels = await crud.get_channels_by_user(db_user["id"])
                already_exists = any(
                    ch["channel_telegram_id"] == chat.id for ch in existing_channels
                )

                if not already_exists:
                    # Auto-add the channel
                    try:
                        from app.freemium import freemium
                        if await freemium.can_add_channel(db_user["id"]):
                            channel = await crud.create_channel(
                                db_user["id"],
                                ChannelCreate(
                                    channel_telegram_id=chat.id,
                                    channel_title=chat.title or str(chat.id),
                                    channel_username=chat.username,
                                    channel_type="channel" if chat.type == "channel" else "group",
                                ),
                            )
                            logger.info(f"Auto-added channel {chat.title} for user {user_id}")

                            # Notify the user
                            try:
                                await event.bot.send_message(
                                    chat_id=user_id,
                                    text=f"✅ تم إضافة القناة <b>{chat.title}</b> تلقائياً!\n\nالقناة جاهزة للاستخدام مع القواعد.",
                                )
                            except Exception as e:
                                logger.warning(f"Could not notify user {user_id}: {e}")
                        else:
                            try:
                                await event.bot.send_message(
                                    chat_id=user_id,
                                    text=f"⚠️ تم إضافة البوت لقناة <b>{chat.title}</b> لكن وصلت للحد الأقصى!\n\nرقّي حسابك للمميز عشان تضيف قنوات أكتر.",
                                )
                            except Exception:
                                pass
                    except Exception as e:
                        logger.error(f"Error auto-adding channel: {e}")
                else:
                    logger.info(f"Channel {chat.id} already exists for user {user_id}")
            else:
                logger.info(f"User {user_id} not registered, skipping auto-add")

    # Bot was removed from a channel/group
    elif new_status in ("left", "kicked") and old_status in ("administrator", "member"):
        logger.info(f"Bot removed from {chat.type} {chat.title} ({chat.id})")
        # We don't auto-delete - just log it. The channel will fail on publish anyway.


# ============================================================================
# Manual channel management
# ============================================================================

@router.message(F.text == "📢 القنوات")
async def show_channels(message: Message):
    """Show user's channels."""
    user = await crud.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("ابدأ البوت بـ /start الأول")
        return
    
    channels = await crud.get_channels_by_user(user["id"])
    
    if not channels:
        text = (
            "📢 ماعندكش قنوات لسه\n\n"
            "💡 <b>طريقة سهلة:</b> ضيف البوت كأدمن في القناة وهو هيضيفها تلقائي!\n\n"
            "أو استخدم الزرار اللي تحت عشان تضيفها يدوي"
        )
    else:
        text = f"📢 <b>قنواتك</b> ({len(channels)})\n\nاضغط على قناة للتفاصيل:"
    
    kb = channels_keyboard(channels)
    await message.answer(text, reply_markup=kb)


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
        "➕ <b>إضافة قناة</b>\n\n"
        "💡 <b>أسهل طريقة:</b> ضيف البوت كأدمن في القناة وهيتضاف تلقائي!\n\n"
        "أو اكتب معرف القناة:\n"
        "1. ضيف البوت كأدمن في القناة\n"
        "2. ابعت معرف القناة (مثال: @my_channel)"
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
            f"✅ تم إضافة القناة <b>{chat.title}</b> بنجاح!"
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
        f"📢 <b>{channel['channel_title']}</b>\n\n"
        f"المعرف: @{channel.get('channel_username', '—')}\n"
        f"النوع: {channel['channel_type']}\n"
        f"الحالة: {status}\n"
        f"التاريخ: {channel['created_at']}"
    )
    
    kb = channel_detail_keyboard(channel_id)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("ch_del_"))
async def delete_channel_confirm(callback: CallbackQuery):
    """Confirm channel deletion."""
    channel_id = int(callback.data.split("_")[2])
    channel = await crud.get_channel_by_id(channel_id)
    
    if not channel:
        await callback.answer("القناة مش موجودة", show_alert=True)
        return
    
    text = f"⚠️ متأكد إنك عايز تحذف القناة <b>{channel['channel_title']}</b>؟"
    kb = confirm_keyboard("ch_del", channel_id)
    await callback.message.edit_text(text, reply_markup=kb)
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
    text = f"📢 <b>قنواتك</b> ({len(channels)})"
    kb = channels_keyboard(channels)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()
