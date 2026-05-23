import telebot
import yt_dlp
import os
import re

# 🔑 НАСТРОЙКИ
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = -1003620344255  # ID канала
CHANNEL_LINK = "https://t.me/wkami1"

bot = telebot.TeleBot(BOT_TOKEN)
user_links = {}
subscribed_users = set()  # Кэш (чтобы не спамить API при каждом сообщении)

def check_subscription(user_id):
    """Проверяет подписку через Telegram API"""
    if user_id in subscribed_users:
        return True
    try:
        # Бот обязан быть админом канала!
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            subscribed_users.add(user_id)
            return True
    except Exception as e:
        print(f"⚠️ Ошибка проверки подписки: {e}")
    return False

def send_sub_prompt(chat_id):
    """Отправляет блокирующий экран с кнопками"""
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_LINK),
        telebot.types.InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub")
    )
    bot.send_message(chat_id, 
        "**Доступ закрыт**\n\n"
        "Для использования бота необходимо подписаться на канал **@wkami1**.\n"
        "После подписки нажмите кнопку ниже 👇", 
        parse_mode="Markdown", reply_markup=markup)

def detect_platform(url):
    if 'tiktok.com' in url: return 'tiktok'
    elif 'instagram.com' in url: return 'instagram'
    elif 'soundcloud.com' in url: return 'soundcloud'
    elif 'youtube.com' in url or 'youtu.be' in url: return 'youtube'
    elif 'vk.com' in url: return 'vk'
    elif 'rutube.ru' in url: return 'rutube'
    return 'unknown'

@bot.message_handler(commands=['start'])
def cmd_start(message):
    if not check_subscription(message.from_user.id):
        send_sub_prompt(message.chat.id)
    else:
        bot.reply_to(message, "✅ Доступ открыт! Отправь ссылку на видео/аудио (YouTube, TikTok, Instagram, SoundCloud, VK, Rutube).")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check_sub(call):
    bot.answer_callback_query(call.id)
    if check_subscription(call.from_user.id):
        bot.edit_message_text("✅ Подписка подтверждена! Доступ открыт. Отправляй ссылки.", 
                              chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
    else:
        bot.answer_callback_query(call.id, "❌ Вы не подписаны! Подпишитесь и нажмите кнопку снова.", show_alert=True)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    # 1. Жёсткая проверка подписки перед любой обработкой
    if not check_subscription(message.from_user.id):
        send_sub_prompt(message.chat.id)
        return

    # 2. Поиск ссылки
    link_match = re.search(r'https?://\S+', message.text)
    if link_match:
        link = link_match.group()
        user_links[message.chat.id] = link
        platform = detect_platform(link)

        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        if platform == 'soundcloud':
            markup.add(telebot.types.InlineKeyboardButton("🎵 Скачать MP3", callback_data="mp3"))
            bot.reply_to(message, "🎵 SoundCloud обнаружен! Выбери формат:", reply_markup=markup)
        elif platform in ['tiktok', 'instagram']:
            markup.add(
                telebot.types.InlineKeyboardButton("📹 MP4 (без воды)", callback_data="mp4_nowatermark"),
                telebot.types.InlineKeyboardButton("📹 MP4 (со звуком)", callback_data="mp4_720"),
                telebot.types.InlineKeyboardButton("🎵 MP3 (только звук)", callback_data="mp3")
            )
            bot.reply_to(message, f"📱 {platform.title()} обнаружен! Выбери формат:", reply_markup=markup)
        else:
            markup.add(
                telebot.types.InlineKeyboardButton("📹 MP4 480p", callback_data="mp4_480"),
                telebot.types.InlineKeyboardButton("📹 MP4 720p", callback_data="mp4_720"),
                telebot.types.InlineKeyboardButton("📹 MP4 1080p", callback_data="mp4_1080"),
                telebot.types.InlineKeyboardButton("🎵 MP3", callback_data="mp3")
            )
            bot.reply_to(message, "🔗 Ссылка принята! Выбери формат и качество:", reply_markup=markup)
    else:
        bot.reply_to(message, "📎 Отправь мне ссылку на видео/аудио.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('mp4_', 'mp3')))
def handle_download(call):
    link = user_links.get(call.message.chat.id)
    if not link:
        bot.answer_callback_query(call.id, "❌ Сначала отправь ссылку!")
        return

    bot.answer_callback_query(call.id, "⏳ Загружаю...")
    bot.edit_message_text("⏳ Обрабатываю запрос...", chat_id=call.message.chat.id, message_id=call.message.message_id)

    choice = call.data
    ydl_opts = {
        'cookiefile': os.path.abspath('cookies.txt'),
        'quiet': True,
        'no_warnings': True,
        'outtmpl': '%(id)s.%(ext)s',
        'extract_flat': False,
        # Специальный обход защиты YouTube для серверов
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'web', 'android'],
                'player_skip': ['webpage'],
            }
        }
    }
    }

    if choice.startswith("mp4_"):
        if choice == "mp4_nowatermark":
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
        else:
            height = choice.split("_")[1]
            ydl_opts['format'] = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]'
        ydl_opts['merge_output_format'] = 'mp4'
    elif choice == "mp3":
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            filename = ydl.prepare_filename(info)
            if choice == "mp3" and not filename.endswith('.mp3'):
                filename = os.path.splitext(filename)[0] + '.mp3'
            
            if not os.path.exists(filename): 
                raise Exception("Файл не создан")
            if os.path.getsize(filename) > 48 * 1024 * 1024:
                bot.edit_message_text("❌ Файл >50 МБ. Telegram не позволяет отправить.", 
                                    chat_id=call.message.chat.id, message_id=call.message.message_id)
                os.remove(filename)
                return

            if choice.startswith("mp4"):
                with open(filename, 'rb') as f: 
                    bot.send_video(call.message.chat.id, f, caption=f"🎬 {info.get('title', 'Видео')[:100]}")
            else:
                with open(filename, 'rb') as f: 
                    bot.send_audio(call.message.chat.id, f, title=info.get('title', 'Аудио')[:100])
            
            os.remove(filename)
            bot.edit_message_text("✅ Готово! Файл отправлен выше.", 
                                chat_id=call.message.chat.id, message_id=call.message.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {str(e)}", 
                            chat_id=call.message.chat.id, message_id=call.message.message_id)

print("🤖 Бот запущен! Подписка на @wkami1 обязательна.")
bot.infinity_polling()
