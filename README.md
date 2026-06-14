# 🧠 Cortex Post

منصة نشر المحتوى التلقائي على تليجرام وتويتر

## المميزات

- 🤖 بوت تليجرام ذكي لإدارة كل حاجة
- 🌐 ويب اب (Mini App) للتحكم من جوه تليجرام
- ⚡ محرك قواعد مرن (شروط النشر التلقائي)
- 📝 محرك قوالب ديناميكي
- 🔌 مصادر بيانات متعددة (عملات رقمية، RSS، رياضة، طقس، أذكار، Webhook)
- 📢 نشر على تليجرام وتويتر
- 💎 نظام اشتراكات (مجاني/مميز)
- ⏰ جدولة تلقائية مع APScheduler

## المصادر المدعومة

| المصدر | الوصف | يحتاج API Key |
|--------|-------|---------------|
| 🪙 عملات رقمية | أسعار العملات من CoinGecko | ❌ |
| 📰 RSS | متابعة أي RSS Feed | ❌ |
| ⚽ رياضة | ماتشات وترتيب من football-data.org | ✅ |
| 🌤 طقس | حالة الطقس من OpenWeatherMap | ✅ |
| 🕌 أذكار وأوقات | أوقات الصلاة والآيات من Aladhan | ❌ |
| 🔗 Webhook | استقبال بيانات خارجية | ❌ |

## التشغيل المحلي

### 1. إعداد البيئة

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

### 2. إعداد المتغيرات

```bash
cp .env.example .env
# عدل .env وحط الـ API keys بتاعتك
```

### 3. تشغيل

```bash
python -m app.main
```

## النشر على Railway

1. اعمل Fork/Upload المشروع على GitHub
2. روح Railway واعمل New Project
3. اختار Deploy from GitHub repo
4. اختار المشروع
5. ضيف المتغيرات البيئية في Settings > Variables
6. Railway هيبني وينشر تلقائي

### المتغيرات المطلوبة

| المتغير | الوصف | مطلوب |
|---------|-------|-------|
| `BOT_TOKEN` | توكن بوت تليجرام | ✅ |
| `WEBAPP_URL` | رابط التطبيق على Railway | ✅ |
| `ADMIN_IDS` | IDs الأدمن | ❌ |
| `TWITTER_API_KEY` | مفتاح تويتر | ❌ |
| `WEATHER_API_KEY` | مفتاح OpenWeatherMap | ❌ |
| `SPORTS_API_KEY` | مفتاح football-data.org | ❌ |

## الهيكل

```
app/
├── main.py              # نقطة التشغيل الرئيسية
├── config.py            # الإعدادات
├── database/            # قاعدة البيانات
│   ├── connection.py    # إدارة الاتصال
│   ├── models.py        # نماذج البيانات
│   ├── crud.py          # عمليات CRUD
│   └── schema.sql       # هيكل الجداول
├── bot/                 # بوت تليجرام
│   ├── handlers/        # معالجات الأوامر
│   └── keyboards.py     # لوحات المفاتيح
├── api/                 # REST API
│   ├── deps.py          # الاعتماديات
│   └── routes/          # مسارات API
├── engine/              # المحركات
│   ├── rules_engine.py  # محرك القواعد
│   ├── template_engine.py # محرك القوالب
│   └── scheduler.py     # الجدولة
├── providers/           # مصادر البيانات
│   ├── base.py          # الواجهة الأساسية
│   ├── crypto.py        # العملات الرقمية
│   ├── rss.py           # RSS
│   ├── sports.py        # الرياضة
│   ├── weather.py       # الطقس
│   ├── religious.py     # الأذكار
│   └── webhook.py       # Webhook
├── publishers/          # منصات النشر
│   ├── base.py          # الواجهة الأساسية
│   ├── telegram_publisher.py  # تليجرام
│   └── twitter_publisher.py   # تويتر
├── freemium/            # نظام الاشتراكات
│   └── limits.py        # حدود الاشتراك
└── static/              # الويب اب
    └── index.html       # لوحة التحكم
```

## الترخيص

MIT License
