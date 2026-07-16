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

# ВАШ ТОКЕН (замените на реальный!)
TOKEN = "8997095280:AAEgfJXENJCoM06wVG5LRVljVs5Y1YntC7w"

# Временные папки
DOWNLOAD_FOLDER = "/tmp/downloads"
AUDIO_FOLDER = "/tmp/audio"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

# Хранилище ссылок
user_links = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "🎥 *Бот для скачивания видео и аудио*\n\n"
        "Отправьте ссылку на видео из Instagram или TikTok\n"
        "и выберите формат скачивания.",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылок"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Ищем URL
    urls = re.findall(r'https?://[^\s]+', text)
    
    if not urls:
        await update.message.reply_text("📎 Отправьте ссылку на видео")
        return
    
    url = urls[0]
    
    # Проверяем платформу
    is_instagram = 'instagram.com' in url.lower()
    is_tiktok = 'tiktok.com' in url.lower()
    
    if not (is_instagram or is_tiktok):
        await update.message.reply_text("❌ Поддерживаются только Instagram и TikTok")
        return
    
    # Сохраняем ссылку
    user_links[user_id] = {
        'url': url,
        'platform': 'Instagram' if is_instagram else 'TikTok'
    }
    
    # Кнопки выбора
    keyboard = [
        [InlineKeyboardButton("🎬 Скачать видео", callback_data="video")],
        [InlineKeyboardButton("🎵 Скачать аудио MP3", callback_data="audio")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Выберите формат скачивания:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_links:
        await query.edit_message_text("❌ Ссылка устарела. Отправьте новую.")
        return
    
    data = user_links[user_id]
    url = data['url']
    platform = data['platform']
    choice = query.data
    
    # Очищаем временные папки
    for folder in [DOWNLOAD_FOLDER, AUDIO_FOLDER]:
        for file in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, file))
            except:
                pass
    
    try:
        if choice == "video":
            await query.edit_message_text("⏳ Скачиваю видео в лучшем качестве...")
            
            ydl_opts = {
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'format': 'best',  # ЛУЧШЕЕ КАЧЕСТВО
                'merge_output_format': 'mp4',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Получаем название видео
                title = info.get('title', 'Видео')
                
                files = os.listdir(DOWNLOAD_FOLDER)
                if not files:
                    raise Exception("Файл не найден")
                
                video_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                file_size = os.path.getsize(video_path)
                
                # Проверяем размер файла
                if file_size > 50 * 1024 * 1024:  # Больше 50 MB
                    await query.edit_message_text(
                        f"⚠️ Видео слишком большое для Telegram ({(file_size/1024/1024):.1f} MB)\n"
                        f"Максимальный размер: 50 MB\n\n"
                        f"Попробуйте скачать аудио или выберите другое видео."
                    )
                    os.remove(video_path)
                    return
                
                await query.edit_message_text("📤 Отправляю видео...")
                
                with open(video_path, 'rb') as f:
                    await query.message.reply_video(
                        video=f,
                        caption=f"🎬 {title}\nСкачано из {platform} в лучшем качестве",
                        supports_streaming=True
                    )
                
                os.remove(video_path)
                
        elif choice == "audio":
            await query.edit_message_text("⏳ Извлекаю аудио в MP3...")
            
            ydl_opts = {
                'outtmpl': os.path.join(AUDIO_FOLDER, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',  # Максимальное качество MP3
                }],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'Аудио')
                
                audio_files = [f for f in os.listdir(AUDIO_FOLDER) if f.endswith('.mp3')]
                if not audio_files:
                    raise Exception("Аудио не найдено")
                
                audio_path = os.path.join(AUDIO_FOLDER, audio_files[0])
                file_size = os.path.getsize(audio_path)
                
                if file_size > 50 * 1024 * 1024:
                    await query.edit_message_text(
                        f"⚠️ Аудио слишком большое ({(file_size/1024/1024):.1f} MB)"
                    )
                    os.remove(audio_path)
                    return
                
                await query.edit_message_text("📤 Отправляю аудио...")
                
                with open(audio_path, 'rb') as f:
                    await query.message.reply_audio(
                        audio=f,
                        title=title,
                        performer=info.get('uploader', platform),
                        caption=f"🎵 {title}\nКачество: 320 kbps MP3"
                    )
                
                os.remove(audio_path)
        
        del user_links[user_id]
        await query.edit_message_text("✅ Готово! Отправьте новую ссылку.")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(f"❌ Ошибка: {str(e)[:150]}")
        if user_id in user_links:
            del user_links[user_id]

def main():
    """Запуск бота"""
    logger.info("Starting bot...")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()