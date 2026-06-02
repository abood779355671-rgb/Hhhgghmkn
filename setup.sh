#!/bin/bash
# ═══════════════════════════════════════
# سكريبت تهيئة بوت رعد
# ═══════════════════════════════════════

set -e
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}════════════════════════════════${NC}"
echo -e "${GREEN}   بوت رعد — سكريبت التهيئة   ${NC}"
echo -e "${GREEN}════════════════════════════════${NC}"

# التحقق من Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 غير موجود${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${GREEN}✅ Python ${PYTHON_VERSION}${NC}"

# ─── ffmpeg (مطلوب للتحميل والتحويل) ───────────────────────────────
echo -e "\n${GREEN}🔍 التحقق من ffmpeg...${NC}"
if command -v ffmpeg &> /dev/null; then
    echo -e "${GREEN}✅ ffmpeg متوفر: $(ffmpeg -version 2>&1 | head -1)${NC}"
else
    echo -e "${YELLOW}⚠️  ffmpeg غير موجود — مطلوب لتحميل يوتيوب وتحويل الصوت${NC}"
    echo "   Ubuntu/Debian : sudo apt install ffmpeg"
    echo "   macOS         : brew install ffmpeg"
    echo "   Windows       : https://ffmpeg.org/download.html"
    echo ""
    echo -e "${YELLOW}   يمكنك متابعة التثبيت بدون ffmpeg لكن تحميل يوتيوب لن يعمل.${NC}"
fi

# إنشاء مجلدات العمل
mkdir -p data downloads

# نسخ ملف الإعدادات
if [ ! -f .env ]; then
    cp .env.example .env
    echo -e "${YELLOW}⚠️  تم إنشاء ملف .env — عدّله بإعداداتك أولاً${NC}"
fi

# ─── تثبيت متطلبات Python ───────────────────────────────────────
echo -e "\n${GREEN}📦 تثبيت متطلبات Python...${NC}"
pip install -r requirements.txt

# ─── التحقق من Redis ─────────────────────────────────────────────
echo -e "\n${GREEN}🔍 التحقق من Redis...${NC}"
if python3 -c "import redis; r = redis.Redis(); r.ping(); print('✅ Redis متصل')" 2>/dev/null; then
    :
else
    echo -e "${YELLOW}⚠️  Redis غير متصل — تأكد من تشغيله${NC}"
    echo "     Ubuntu/Debian: sudo apt install redis-server && sudo service redis start"
    echo "     macOS        : brew install redis && brew services start redis"
fi

echo -e "\n${GREEN}════════════════════════════════${NC}"
echo -e "${GREEN}        التهيئة اكتملت!        ${NC}"
echo -e "${GREEN}════════════════════════════════${NC}"
echo -e "${YELLOW}الخطوات التالية:${NC}"
echo "1. تأكد من تثبيت ffmpeg (راجع الأعلى)"
echo "2. عدّل ملف .env بـ BOT_TOKEN, API_ID, API_HASH, OWNER_ID"
echo "3. شغّل البوت: python3 main.py"
echo ""
