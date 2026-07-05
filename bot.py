import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart

# ----------------- الإعدادات الأساسية -----------------
import os
BOT_TOKEN = os.environ.get('8504051379:AAFOuehQW8aLFWalGIdGMcj0eJmJKyjdt5M') # سيقرأ التوكن من السحابة لاحقاً
ADMIN_ID = 8333172705

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CATEGORIES = ["كيمياء عضوية","تحليلة 1 ",  "نحليلية 2", "تحليل آلي", "تقارير مختبرات", "كيمياء فيزيائية"]
pending_files = {}

# ----------------- إعداد قاعدة البيانات -----------------
def init_db():
    conn = sqlite3.connect('applied_chemistry.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chemistry_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            category TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ----------------- 1. الكيبورد التفاعلي واستدعاء الملفات (للطلاب) -----------------
# وضعنا هذا الأمر في الأعلى لكي يستجيب فوراً

@dp.message(CommandStart())
async def show_main_menu(message: types.Message):
    keyboard = []
    for i in range(0, len(CATEGORIES), 2):
        row = [types.InlineKeyboardButton(text=cat, callback_data=f"view_{cat}") for cat in CATEGORIES[i:i+2]]
        keyboard.append(row)
        
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.answer("🧪 مرحبًا بك في بوت أرشفة الكيمياء التطبيقية.\nاختر القسم الذي تريد تصفح ملفاته:", reply_markup=markup)

# ----------------- 2. أرشفة الملفات (خاص بالمشرف) -----------------

# هذا الكود يستقبل أي نوع من الملفات (صور، فيديو، ملفات، إلخ)
@dp.message(F.content_type.in_({'document', 'photo', 'video', 'audio', 'voice'}))
async def handle_admin_all_files(message: types.Message):
    # التحقق من أن المرسل هو المشرف
    if message.from_user.id != ADMIN_ID:
        await message.reply("عذراً، هذا البوت مخصص للأرشفة من قبل الإدارة فقط.")
        return

    # استخراج معلومات الملف
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    elif message.photo:
        file_id = message.photo[-1].file_id  
        file_name = "صورة_أرشفة.jpg"
    elif message.video:
        file_id = message.video.file_id
        file_name = message.video.file_name or "فيديو_أرشفة.mp4"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "صوت_أرشفة.mp3"
    elif message.voice:
        file_id = message.voice.file_id
        file_name = "رسالة_صوتية.ogg"
    else:
        return

    # حفظ المعلومات مؤقتاً
    pending_files[ADMIN_ID] = {"file_id": file_id, "file_name": file_name}
    
    # إظهار الأقسام
    keyboard = []
    for i in range(0, len(CATEGORIES), 2):
        row = [types.InlineKeyboardButton(text=cat, callback_data=f"save_{cat}") for cat in CATEGORIES[i:i+2]]
        keyboard.append(row)
        
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await message.reply(f"📁 تم استلام الملف: `{file_name}`\n\nالرجاء اختيار القسم لأرشفته:", reply_markup=markup, parse_mode="Markdown")
async def save_file_callback(callback: types.CallbackQuery):
    category = callback.data.replace("save_", "")
    file_data = pending_files.get(ADMIN_ID)
    
    if file_data:
        conn = sqlite3.connect('applied_chemistry.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chemistry_files (file_id, file_name, category) VALUES (?, ?, ?)",
                       (file_data['file_id'], file_data['file_name'], category))
        conn.commit()
        conn.close()
        
        await callback.message.edit_text(f"✅ تم حفظ الملف `{file_data['file_name']}` بنجاح في قسم *{category}*.", parse_mode="Markdown")
        pending_files.pop(ADMIN_ID, None)
    else:
        await callback.answer("عذراً، انتهت صلاحية الجلسة أو لم يتم العثور على ملف.", show_alert=True)

# دالة استعراض الملفات (محدثة لتشمل زر الحذف للمشرف)
@dp.callback_query(F.data.startswith("view_"))
async def view_category_callback(callback: types.CallbackQuery):
    category = callback.data.replace("view_", "")
    
    conn = sqlite3.connect('applied_chemistry.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_name FROM chemistry_files WHERE category = ?", (category,))
    files = cursor.fetchall()
    conn.close()
    
    if not files:
        await callback.answer(f"لا توجد ملفات مؤرشفة في قسم {category} حالياً.", show_alert=True)
        return
        
    keyboard = []
    for file_info in files:
        file_db_id = file_info[0]
        file_name = file_info[1]
        
        # إذا كنت أنت المشرف، أظهر زر الحذف 🗑️
        if callback.from_user.id == ADMIN_ID:
            keyboard.append([
                types.InlineKeyboardButton(text=f"📄 {file_name}", callback_data=f"getfile_{file_db_id}"),
                types.InlineKeyboardButton(text="🗑️", callback_data=f"delete_{file_db_id}")
            ])
        else:
            # إذا كان طالباً، أظهر زر التحميل فقط
            keyboard.append([types.InlineKeyboardButton(text=f"📄 {file_name}", callback_data=f"getfile_{file_db_id}")])
            
    keyboard.append([types.InlineKeyboardButton(text="⬅️ عودة للقائمة الرئيسية", callback_data="back_to_main")])
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(f"📚 ملفات قسم *{category}*:", reply_markup=markup, parse_mode="Markdown")

# دالة الحذف (أضفها تحت دالة الاستعراض مباشرة)
@dp.callback_query(F.data.startswith("delete_"))
async def delete_file_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ليس لديك صلاحية الحذف!")
        return
        
    file_db_id = callback.data.replace("delete_", "")
    
    conn = sqlite3.connect('applied_chemistry.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chemistry_files WHERE id = ?", (file_db_id,))
    conn.commit()
    conn.close()
    
    await callback.answer("تم حذف الملف من الأرشيف بنجاح!", show_alert=True)
    # نقوم بحذف الرسالة القديمة ونعيد عرض القائمة لكي يختفي الملف
    await callback.message.delete()
    await show_main_menu(callback.message)
@dp.callback_query(F.data.startswith("getfile_"))
async def get_file_callback(callback: types.CallbackQuery):
    file_db_id = callback.data.replace("getfile_", "")
    
    conn = sqlite3.connect('applied_chemistry.db')
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, file_name FROM chemistry_files WHERE id = ?", (file_db_id,))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        file_id = res[0]
        file_name = res[1]
        await callback.answer(f"جاري إرسال: {file_name}")
        await callback.message.answer_document(document=file_id)
    else:
        await callback.answer("الملف غير موجود أو تم حذفه.", show_alert=True)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: types.CallbackQuery):
    await callback.message.delete()
    keyboard = []
    for i in range(0, len(CATEGORIES), 2):
        row = [types.InlineKeyboardButton(text=cat, callback_data=f"view_{cat}") for cat in CATEGORIES[i:i+2]]
        keyboard.append(row)
    markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.answer("🧪 مرحبًا بك في بوت أرشفة الكيمياء التطبيقية.\nاختر القسم الذي تريد تصفح ملفاته:", reply_markup=markup)


# ----------------- 4. إدارة المجموعة (الترحيب والفلترة) -----------------

@dp.message(F.new_chat_members)
async def welcome_new_members(message: types.Message):
    for member in message.new_chat_members:
        welcome_text = f"أهلاً بك يا {member.first_name} في مجموعة مناقشة الكيمياء التطبيقية! 🧪\n\nيرجى الالتزام بالقوانين."
        await message.answer(welcome_text)

# خصصنا الفلتر ليعمل في المجموعات فقط، ولن يتدخل في المحادثة الخاصة
@dp.message(F.text & F.chat.type.in_({'group', 'supergroup'}))
async def spam_filter(message: types.Message):
    blacklisted_words = ["ربح", "دولار", "اشترك", "شات", "موقع لربح"]
    contains_link = "http://" in message.text or "https://" in message.text or "t.me/" in message.text
    contains_spam_word = any(word in message.text for word in blacklisted_words)
    
    if (contains_link or contains_spam_word):
        if message.from_user.id != ADMIN_ID:
            try:
                await message.delete()
                warning = await message.answer(f"تم حذف رسالة {message.from_user.first_name} تلقائياً لمنع الروابط أو الإعلانات.")
                await asyncio.sleep(5)
                await warning.delete()
            except Exception as e:
                print(f"خطأ في حذف الرسالة: {e}")
            return

# ----------------- التشغيل -----------------
async def main():
    print("البوت يعمل الآن بنجاح ومستعد لاستقبال الأوامر (باستخدام aiogram)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())