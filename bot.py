import os
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен из переменных окружения Render или напрямую
TOKEN = "8997095280:AAEgfJXENJCoM06wVG5LRVljVs5Y1YntC7w"

# Папки для загрузок
DOWNLOAD_FOLDER = "/tmp/downloads"
AUDIO_FOLDER = "/tmp/audio"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# Словарь для хранения ссылок пользователей
user_links = {}

def get_ydl_opts():
    """Базовые настройки для yt-dlp"""
    return {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title).50s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'format': 'best[height<=720]/best',
        'merge_output_format': 'mp4',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    welcome_text = (
        "🎥 *Бот для скачивания видео и аудио*\n\n"
        "Я скачиваю контент из:\n"
        "• 📸 Instagram (Reels, видео)\n"
        "• 🎵 TikTok\n\n"
        "📝 *Как использовать:*\n"
        "1. Отправьте мне ссылку\n"
        "2. Выберите формат: видео или аудио\n"
        "3. Получите файл!\n\n"
        "🔹 *Видео* - скачивается со звуком\n"
        "🔹 *Аудио* - только звук в MP3"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    help_text = (
        "🔧 *Как использовать бота:*\n\n"
        "1. Отправьте ссылку на видео из Instagram или TikTok\n"
        "2. Выберите формат:\n"
        "   🎬 Видео - скачает видео со звуком\n"
        "   🎵 Аудио - извлечет звук в MP3\n\n"
        "⚠️ Некоторые видео Instagram могут требовать авторизацию"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящих ссылок"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Извлекаем URL
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    
    if not urls:
        await update.message.reply_text(
            "📎 Отправьте мне ссылку на видео из Instagram или TikTok"
        )
        return
    
    url = urls[0]
    is_instagram = 'instagram.com' in url.lower()
    is_tiktok = 'tiktok.com' in url.lower()
    
    if not (is_instagram or is_tiktok):
        await update.message.reply_text("❌ Я работаю только с Instagram и TikTok")
        return
    
    # Сохраняем ссылку
    user_links[user_id] = {
        'url': url,
        'platform': 'instagram' if is_instagram else 'tiktok'
    }
    
    # Создаем кнопки
    keyboard = [
        [
            InlineKeyboardButton("🎬 Скачать видео (со звуком)", callback_data="format_video"),
        ],
        [
            InlineKeyboardButton("🎵 Скачать только звук (MP3)", callback_data="format_audio"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    platform_name = "Instagram" if is_instagram else "TikTok"
    await update.message.reply_text(
        f"🔗 Ссылка получена ({platform_name})\n\n"
        f"*Выберите формат для скачивания:*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    choice = query.data
    
    if user_id not in user_links:
        await query.edit_message_text("❌ Ссылка устарела. Отправьте новую.")
        return
    
    url_data = user_links[user_id]
    url = url_data['url']
    platform = url_data['platform']
    
    # Очищаем папки
    for folder in [DOWNLOAD_FOLDER, AUDIO_FOLDER]:
        for file in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, file))
            except:
                pass
    
    await query.edit_message_text("⏳ Начинаю загрузку...")
    
    try:
        if choice == "format_video":
            await query.edit_message_text("📥 Скачиваю видео...")
            
            ydl_opts = get_ydl_opts()
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                files = [f for f in os.listdir(DOWNLOAD_FOLDER) 
                        if os.path.isfile(os.path.join(DOWNLOAD_FOLDER, f))]
                
                if not files:
                    raise Exception("Видео не найдено")
                
                video_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                file_size = os.path.getsize(video_path)
                
                if file_size > 50 * 1024 * 1024:
                    await query.edit_message_text("❌ Видео слишком большое (>50MB)")
                    os.remove(video_path)
                    return
                
                await query.edit_message_text("📤 Отправляю видео...")
                
                caption = f"🎬 {info.get('title', 'Видео')[:200]}"
                
                with open(video_path, 'rb') as video_file:
                    await query.message.reply_video(
                        video=video_file,
                        caption=caption,
                        supports_streaming=True
                    )
                
                os.remove(video_path)
                
        elif choice == "format_audio":
            await query.edit_message_text("📥 Скачиваю аудио...")
            
            ydl_opts = get_ydl_opts()
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(AUDIO_FOLDER, '%(title).50s.%(ext)s'),
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                audio_files = [f for f in os.listdir(AUDIO_FOLDER) 
                             if f.endswith('.mp3')]
                
                if not audio_files:
                    raise Exception("Аудио не найдено")
                
                audio_path = os.path.join(AUDIO_FOLDER, audio_files[0])
                file_size = os.path.getsize(audio_path)
                
                if file_size > 50 * 1024 * 1024:
                    await query.edit_message_text("❌ Аудио слишком большое (>50MB)")
                    os.remove(audio_path)
                    return
                
                await query.edit_message_text("📤 Отправляю аудио...")
                
                title = info.get('title', 'Аудио')[:200]
                
                with open(audio_path, 'rb') as audio_file:
                    await query.message.reply_audio(
                        audio=audio_file,
                        title=title,
                        caption=f"🎵 {title}"
                    )
                
                os.remove(audio_path)
        
        # Удаляем ссылку после использования
        del user_links[user_id]
        await query.edit_message_text("✅ Готово! Отправьте новую ссылку.")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(
            f"❌ Ошибка: {str(e)[:200]}\n\nПопробуйте другую ссылку"
        )

def main():
    """Запуск бота"""
    logger.info("Starting bot...")
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot started!")
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()