import os
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = "8997095280:AAEgfJXENJCoM06wVG5LRVljVs5Y1YntC7w"

DOWNLOAD_FOLDER = "downloads"
AUDIO_FOLDER = "audio"
COOKIES_FILE = "cookies.txt"

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

user_links = {}

def get_ydl_opts(platform=''):
    """Настройки с cookies если есть"""
    opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'quiet': True,
        'format': 'best',
        'merge_output_format': 'mp4',
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    # Добавляем cookies ТОЛЬКО для Instagram
    if platform == 'instagram' and os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
    
    return opts

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎥 *Бот для скачивания видео и аудио*\n\n"
        "Отправь ссылку на видео из Instagram или TikTok\n"
        "и выбери формат.\n\n"
        "⚠️ Для Instagram загрузи cookies.txt через /help",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔧 *Как скачивать из Instagram без ограничений:*\n\n"
        "1. Установи расширение 'Get cookies.txt LOCALLY' для Chrome\n"
        "2. Зайди на instagram.com и войди в аккаунт\n"
        "3. Экспортируй cookies через расширение\n"
        "4. Отправь файл cookies.txt сюда\n\n"
        "После этого Instagram заработает без ограничений!"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принимаем cookies файл"""
    file = await update.message.document.get_file()
    await file.download_to_drive(COOKIES_FILE)
    await update.message.reply_text("✅ Cookies сохранены! Instagram будет работать!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    urls = re.findall(r'https?://[^\s]+', text)
    
    if not urls:
        await update.message.reply_text("📎 Отправь ссылку на видео")
        return
    
    url = urls[0]
    is_instagram = 'instagram.com' in url.lower()
    is_tiktok = 'tiktok.com' in url.lower()
    
    if not (is_instagram or is_tiktok):
        await update.message.reply_text("❌ Только Instagram и TikTok")
        return
    
    platform = 'instagram' if is_instagram else 'tiktok'
    user_links[user_id] = {'url': url, 'platform': platform}
    
    keyboard = [
        [InlineKeyboardButton("🎬 Скачать видео", callback_data="video")],
        [InlineKeyboardButton("🎵 Скачать аудио MP3", callback_data="audio")]
    ]
    
    await update.message.reply_text(
        "Выбери формат:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in user_links:
        await query.edit_message_text("❌ Ссылка устарела. Отправь новую.")
        return
    
    data = user_links[user_id]
    url = data['url']
    platform = data['platform']
    choice = query.data
    
    for folder in [DOWNLOAD_FOLDER, AUDIO_FOLDER]:
        for f in os.listdir(folder):
            try:
                os.remove(os.path.join(folder, f))
            except:
                pass
    
    try:
        if choice == "video":
            await query.edit_message_text("⏳ Скачиваю видео...")
            
            ydl_opts = get_ydl_opts(platform)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
                
                files = os.listdir(DOWNLOAD_FOLDER)
                if not files:
                    raise Exception("Файл не найден")
                
                video_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                size = os.path.getsize(video_path)
                
                if size > 50 * 1024 * 1024:
                    os.remove(video_path)
                    await query.edit_message_text(f"❌ Слишком большой: {size/1024/1024:.1f} MB")
                    return
                
                await query.edit_message_text("📤 Отправляю...")
                
                with open(video_path, 'rb') as f:
                    await query.message.reply_video(video=f, caption="✅ Готово!")
                
                os.remove(video_path)
                
        elif choice == "audio":
            await query.edit_message_text("⏳ Извлекаю аудио...")
            
            ydl_opts = {
                'outtmpl': os.path.join(AUDIO_FOLDER, '%(title)s.%(ext)s'),
                'quiet': True,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
                
                audio_files = [f for f in os.listdir(AUDIO_FOLDER) if f.endswith('.mp3')]
                if not audio_files:
                    raise Exception("Аудио не найдено")
                
                audio_path = os.path.join(AUDIO_FOLDER, audio_files[0])
                size = os.path.getsize(audio_path)
                
                if size > 50 * 1024 * 1024:
                    os.remove(audio_path)
                    await query.edit_message_text(f"❌ Слишком большой: {size/1024/1024:.1f} MB")
                    return
                
                await query.edit_message_text("📤 Отправляю...")
                
                with open(audio_path, 'rb') as f:
                    await query.message.reply_audio(audio=f, title="Audio")
                
                os.remove(audio_path)
        
        del user_links[user_id]
        await query.edit_message_text("✅ Готово! Отправь новую ссылку.")
        
    except Exception as e:
        error_msg = str(e)
        if "login" in error_msg.lower() or "rate-limit" in error_msg.lower():
            await query.edit_message_text(
                "🔒 Instagram требует авторизацию!\n\n"
                "Отправь /help чтобы узнать как добавить cookies"
            )
        else:
            await query.edit_message_text(f"❌ Ошибка: {error_msg[:150]}")
        
        if user_id in user_links:
            del user_links[user_id]

if __name__ == '__main__':
    logger.info("Бот запускается...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Бот запущен!")
    app.run_polling()