from telegram.ext import CommandHandler, CallbackQueryHandler
from time import sleep
from threading import Thread

from bot import download_dict, dispatcher, download_dict_lock, OWNER_ID, user_data
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, auto_delete_message
from bot.helper.ext_utils.bot_utils import getDownloadByGid, getAllDownload, new_thread, MirrorStatus
from bot.helper.telegram_helper import button_build


def cancel_mirror(update, context):
    user_id = update.message.from_user.id
    if len(context.args) == 1:
        gid = context.args[0]
        dl = getDownloadByGid(gid)
        if not dl:
            return sendMessage(f"GID: <code>{gid}</code> Not Found.", context.bot, update.message)
    elif update.message.reply_to_message:
        mirror_message = update.message.reply_to_message
        with download_dict_lock:
            if mirror_message.message_id in download_dict:
                dl = download_dict[mirror_message.message_id]
            else:
                dl = None
        if not dl:
            return sendMessage("This is not an active task!", context.bot, update.message)
    elif len(context.args) == 0:
        msg = f"Reply to an active <code>/{BotCommands.MirrorCommand}</code> message which \
                was used to start the download or send <code>/{BotCommands.CancelMirror} GID</code> to cancel it!"
        return sendMessage(msg, context.bot, update.message)

    if OWNER_ID != user_id and dl.message.from_user.id != user_id and \
       (user_id not in user_data or not user_data[user_id].get('is_sudo')):
        return sendMessage("This task is not for you!", context.bot, update.message)

    if dl.status() == MirrorStatus.STATUS_CONVERTING:        
        return sendMessage("Converting... Can't cancel this task!", context.bot, update.message)
    
    dl.download().cancel_download()

cancel_listener = {}    
    
def cancel_all(status, info):
    user_id = info[0]
    msg = info[1]
    umsg = info[2]
    editMessage(f"Canceling tasks for {user_id or 'All'} in {status}", msg)
    if dls:= getAllDownload(status, user_id, False):
        canceled = 0
        cant_cancel = 0
        for dl in dls:
            try:
                if dl.status() == MirrorStatus.STATUS_CONVERTING:
                    cant_cancel += 1
                    continue
                dl.download().cancel_download()
                canceled += 1
                sleep(1)
            except:
                cant_cancel += 1
                continue
            editMessage(f"Canceling tasks for {user_id or 'All'} in {status} canceled {canceled}/{len(dls)}", msg)
        sleep(1)
        if umsg.from_user.username:
            tag = f"@{umsg.from_user.username}"
        else:
            tag = umsg.from_user.mention_html()
        _msg = "Canceling task Done\n"
        _msg += f"<b>Success</b>: {canceled}\n"
        _msg += f"<b>Faild</b>: {cant_cancel}\n"
        _msg += f"<b>Total</b>: {len(dls)}\n"
        _msg += f"<b>#cancel_all</b> : {tag}"
        editMessage(_msg, msg)
    else:
        editMessage(f"{user_id} Don't have any active task!", msg)

def cancell_all_buttons(update, context):
    with download_dict_lock:
        count = len(download_dict)
    if count == 0:
        return sendMessage("No active tasks!", context.bot, update.message)
    user_id = update.message.from_user.id
    if CustomFilters.owner_query(user_id):
        if reply_to:= update.message.reply_to_message:
            user_id = reply_to.from_user.id
        elif context.args and context.args[0].lower() == 'all':
            user_id = None
        elif  context.args and context.args[0].isdigit():
            try:
                user_id = int(context.args[0])
            except:
                return sendMessage("Invalid Argument! Send Userid or reply", context.bot, update.message)
    if user_id and not getAllDownload('all', user_id):
        return sendMessage(f"{user_id} Don't have any active task!", context.bot, update.message)
    msg_id = update.message.message_id
    buttons = button_build.ButtonMaker()
    buttons.sbutton("Downloading", f"canall {MirrorStatus.STATUS_DOWNLOADING} {msg_id}")
    buttons.sbutton("Uploading", f"canall {MirrorStatus.STATUS_UPLOADING} {msg_id}")
    buttons.sbutton("Seeding", f"canall {MirrorStatus.STATUS_SEEDING} {msg_id}")
    buttons.sbutton("Cloning", f"canall {MirrorStatus.STATUS_CLONING} {msg_id}")
    buttons.sbutton("Extracting", f"canall {MirrorStatus.STATUS_EXTRACTING} {msg_id}")
    buttons.sbutton("Archiving", f"canall {MirrorStatus.STATUS_ARCHIVING} {msg_id}")
    buttons.sbutton("Queued", f"canall {MirrorStatus.STATUS_WAITING} {msg_id}")
    buttons.sbutton("Paused", f"canall {MirrorStatus.STATUS_PAUSED} {msg_id}")
    buttons.sbutton("All", "canall all" {msg_id})
    buttons.sbutton("Close", "canall close" {msg_id})
    button = buttons.build_menu(2)
    can_msg = sendMarkup('Choose tasks to cancel. You have 30 Secounds only', context.bot, update.message, button)
    cancel_listener[msg_id] = [user_id, can_msg, update.message]
    Thread(target=auto_delete_message, args=(context.bot, update.message, can_msg)).start()
    Thread(target=_auto_cancel, args=(can_msg, msg_id)).start()

@new_thread
def cancel_all_update(update, context):
    with download_dict_lock:
        count = len(download_dict)
    if count == 0:
        sendMessage("No active tasks!", context.bot, update.message)
        return
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split()
    if CustomFilters.owner_query(user_id):
        query.answer()
        if data[1] == 'close':
            query.message.delete()
            query.message.reply_to_message.delete()
            return
        cancel_all(data[1])
    else:
        query.answer(text="You don't have permission to use these buttons!", show_alert=True)

def _auto_cancel(msg, msg_id):
    sleep(30)
    try:
        if cancel_listener.get(msg_id):
            del cancel_listener[msg_id]
            editMessage('Timed out!', msg)
    except:
        pass

cancel_mirror_handler = CommandHandler(BotCommands.CancelMirror, cancel_mirror,
                                   filters=(CustomFilters.authorized_chat | CustomFilters.authorized_user), run_async=True)
cancel_all_handler = CommandHandler(BotCommands.CancelAllCommand, cancell_all_buttons,
                                   filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)

cancel_all_buttons_handler = CallbackQueryHandler(cancel_all_update, pattern="canall", run_async=True)

dispatcher.add_handler(cancel_all_handler)
dispatcher.add_handler(cancel_mirror_handler)
dispatcher.add_handler(cancel_all_buttons_handler)
