import os
import re
import logging
import subprocess
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ВСТАВЬТЕ СЮДА СВОЙ ТОКЕН
TOKEN = "8997095280:AAEgfJXENJCoM06wVG5LRVljVs5Y1YntC7w"

# Папки для загрузок
DOWNLOAD_FOLDER = "downloads"
AUDIO_FOLDER = "audio"
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)
if not os.path.exists(AUDIO_FOLDER):
    os.makedirs(AUDIO_FOLDER)

# Файл cookie для Instagram
COOKIES_FILE = "cookies.txt"

# Словарь для хранения ссылок пользователей
user_links = {}

def create_cookies_file():
    """Создает файл cookie если его нет"""
    if not os.path.exists(COOKIES_FILE):
        print("\n" + "="*60)
        print("ВАЖНО! Для скачивания из Instagram нужны cookies!")
        print("="*60)
        print("\nКак получить cookies:")
        print("1. Установите расширение для браузера:")
        print("   Chrome: 'Get cookies.txt LOCALLY'")
        print("   Firefox: 'cookies.txt'")
        print("2. Зайдите на instagram.com и войдите в аккаунт")
        print("3. Нажмите на иконку расширения и экспортируйте cookies")
        print("4. Сохраните файл как 'cookies.txt' в папку с ботом")
        print("\nИЛИ нажмите Enter чтобы продолжить без cookies")
        print("="*60 + "\n")
        input("Нажмите Enter...")

def get_ydl_opts():
    """Базовые настройки для yt-dlp"""
    opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title).50s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }
    
    # Добавляем cookies если файл существует и не пустой
    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        opts['cookiefile'] = COOKIES_FILE
    
    return opts

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
        "🔹 *Аудио* - только звук в MP3\n\n"
        "⚠️ Для Instagram может потребоваться авторизация.\n"
        "Отправьте /help для инструкции"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь"""
    help_text = (
        "🔧 *Как добавить cookies для Instagram:*\n\n"
        "1️⃣ Установите расширение для браузера:\n"
        "• Chrome: 'Get cookies.txt LOCALLY'\n"
        "• Firefox: 'cookies.txt'\n\n"
        "2️⃣ Зайдите на instagram.com и войдите\n\n"
        "3️⃣ Нажмите на иконку расширения\n\n"
        "4️⃣ Экспортируйте cookies.txt\n\n"
        "5️⃣ Отправьте файл cookies.txt боту\n\n"
        "✅ После этого Instagram заработает!\n\n"
        "*Форматы скачивания:*\n"
        "• 🎬 Видео со звуком\n"
        "• 🎵 Только звук (MP3)"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принимаем файл cookies"""
    if update.message.document.file_name == 'cookies.txt':
        file = await update.message.document.get_file()
        await file.download_to_drive(COOKIES_FILE)
        await update.message.reply_text("✅ Cookies сохранены! Теперь Instagram будет работать!")
    else:
        await update.message.reply_text("Отправьте файл с именем cookies.txt")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящих ссылок"""
    text = update.message.text
    user_id = update.effective_user.id
    
    # Извлекаем URL
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    
    if not urls:
        await update.message.reply_text(
            "📎 *Отправьте мне ссылку на видео*\n\n"
            "Поддерживаемые платформы:\n"
            "• Instagram (reels, видео)\n"
            "• TikTok\n\n"
            "Примеры:\n"
            "`https://www.instagram.com/reel/...`\n"
            "`https://www.tiktok.com/@user/video/...`",
            parse_mode='Markdown'
        )
        return
    
    url = urls[0]
    
    # Определяем тип ссылки
    is_instagram = 'instagram.com' in url.lower()
    is_tiktok = 'tiktok.com' in url.lower()
    
    if not (is_instagram or is_tiktok):
        await update.message.reply_text("❌ Я работаю только с Instagram и TikTok")
        return
    
    # Сохраняем ссылку пользователя
    user_links[user_id] = {
        'url': url,
        'platform': 'instagram' if is_instagram else 'tiktok'
    }
    
    # Создаем клавиатуру с выбором формата
    keyboard = [
        [
            InlineKeyboardButton("🎬 Скачать видео (со звуком)", callback_data="format_video"),
        ],
        [
            InlineKeyboardButton("🎵 Скачать только звук (MP3)", callback_data="format_audio"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем сообщение с кнопками
    platform_name = "Instagram" if is_instagram else "TikTok"
    await update.message.reply_text(
        f"🔗 Ссылка получена ({platform_name})\n\n"
        f"*Выберите формат для скачивания:*\n"
        f"🎬 Видео - видео со звуком\n"
        f"🎵 Аудио - только звук в MP3",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    choice = query.data
    
    # Проверяем, есть ли ссылка у пользователя
    if user_id not in user_links:
        await query.edit_message_text("❌ Ссылка устарела. Отправьте новую ссылку.")
        return
    
    url_data = user_links[user_id]
    url = url_data['url']
    platform = url_data['platform']
    
    # Очищаем старые файлы
    clean_folders()
    
    # Отправляем статус
    await query.edit_message_text("⏳ Начинаю загрузку...")
    
    try:
        if choice == "format_video":
            await download_video(query, url, platform)
        elif choice == "format_audio":
            await download_audio(query, url, platform)
        
        # Удаляем ссылку после использования
        del user_links[user_id]
        
    except Exception as e:
        logger.error(f"Ошибка при скачивании: {e}")
        await query.edit_message_text(
            f"❌ Ошибка при скачивании\n\n"
            f"Причина: {str(e)[:200]}\n\n"
            f"Попробуйте:\n"
            f"• Другое видео\n"
            f"• Проверить ссылку\n"
            f"• Отправить /help"
        )

async def download_video(query, url, platform):
    """Скачивание видео со звуком"""
    await query.edit_message_text("📥 Скачиваю видео...")
    
    # Настройки для скачивания видео
    ydl_opts = get_ydl_opts()
    ydl_opts.update({
        'format': 'best[height<=720]/best',  # HD качество
        'merge_output_format': 'mp4',
    })
    
    # Для Instagram добавляем специальные настройки
    if platform == 'instagram':
        ydl_opts.update({
            'extractor_args': {
                'instagram': {
                    'no_watermark': True,
                }
            },
            'format_sort': ['vcodec:h264'],
        })
    
    # Скачиваем
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        
        # Ищем скачанный файл
        downloaded_files = [f for f in os.listdir(DOWNLOAD_FOLDER) 
                          if os.path.isfile(os.path.join(DOWNLOAD_FOLDER, f))]
        
        if not downloaded_files:
            raise Exception("Видео не найдено после скачивания")
        
        video_path = os.path.join(DOWNLOAD_FOLDER, downloaded_files[0])
        file_size = os.path.getsize(video_path)
        
        # Проверка размера
        if file_size > 50 * 1024 * 1024:
            os.remove(video_path)
            await query.edit_message_text(
                f"❌ Видео слишком большое ({(file_size/1024/1024):.1f}MB > 50MB)\n"
                "Попробуйте скачать только звук"
            )
            return
        
        await query.edit_message_text("📤 Отправляю видео...")
        
        # Отправляем видео
        caption = f"🎬 {info.get('title', 'Видео')[:200]}"
        if platform == 'instagram':
            caption += "\n📸 Скачано из Instagram"
        else:
            caption += "\n🎵 Скачано из TikTok"
        
        with open(video_path, 'rb') as video_file:
            await query.message.reply_video(
                video=video_file,
                caption=caption,
                supports_streaming=True
            )
        
        os.remove(video_path)
        await query.edit_message_text("✅ Видео успешно скачано!")

async def download_audio(query, url, platform):
    """Скачивание только аудио в MP3"""
    await query.edit_message_text("📥 Скачиваю и конвертирую в MP3...")
    
    # Сначала скачиваем видео в лучшем качестве для аудио
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
    
    # Скачиваем и конвертируем
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        
        # Ищем MP3 файл
        audio_files = [f for f in os.listdir(AUDIO_FOLDER) 
                      if f.endswith('.mp3') and os.path.isfile(os.path.join(AUDIO_FOLDER, f))]
        
        if not audio_files:
            raise Exception("Аудио не найдено после конвертации")
        
        audio_path = os.path.join(AUDIO_FOLDER, audio_files[0])
        file_size = os.path.getsize(audio_path)
        
        # Проверка размера
        if file_size > 50 * 1024 * 1024:
            os.remove(audio_path)
            await query.edit_message_text(
                f"❌ Аудио слишком большое ({(file_size/1024/1024):.1f}MB > 50MB)"
            )
            return
        
        await query.edit_message_text("📤 Отправляю аудио...")
        
        # Отправляем аудио
        title = info.get('title', 'Аудио')[:200]
        performer = info.get('uploader', 'Unknown')
        
        with open(audio_path, 'rb') as audio_file:
            await query.message.reply_audio(
                audio=audio_file,
                title=title,
                performer=performer,
                caption=f"🎵 {title}\nСкачано из {platform.title()}"
            )
        
        os.remove(audio_path)
        await query.edit_message_text("✅ Аудио успешно скачано в MP3!")

def clean_folders():
    """Очистка папок от старых файлов"""
    for folder in [DOWNLOAD_FOLDER, AUDIO_FOLDER]:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                try:
                    os.remove(os.path.join(folder, file))
                except:
                    pass

def check_ffmpeg():
    """Проверка наличия ffmpeg"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

def main():
    """Запуск бота"""
    print("\n" + "="*60)
    print("🎥 ТЕЛЕГРАМ БОТ ДЛЯ СКАЧИВАНИЯ ВИДЕО И АУДИО")
    print("="*60)
    
    # Проверяем ffmpeg (нужен для конвертации в MP3)
    if check_ffmpeg():
        print("✅ ffmpeg найден")
    else:
        print("⚠️  ffmpeg НЕ НАЙДЕН!")
        print("   Для скачивания аудио в MP3 установите ffmpeg:")
        print("   • Windows: скачайте с https://ffmpeg.org/download.html")
        print("   • Mac: brew install ffmpeg")
        print("   • Linux: sudo apt install ffmpeg")
        print("   Бот будет работать, но без конвертации в MP3\n")
    
    # Создаем файл cookies если нужно
    create_cookies_file()
    
    # Обновляем yt-dlp
    print("Обновляю библиотеки...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], 
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ yt-dlp обновлен")
    except:
        pass
    
    # Запускаем бота
    print("\nЗапускаю бота...")
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот запущен!")
    print("📱 Отправьте ссылку и выберите формат:")
    print("   🎬 Видео - скачивает видео со звуком")
    print("   🎵 Аудио - извлекает звук в MP3")
    print("="*60 + "\n")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()