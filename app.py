

import streamlit as st
import google.generativeai as genai
import tempfile
import os
import pandas as pd

# --- הגדרות ---
# 1. הדבק את המפתח שלך כאן בתוך המרכאות
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
# 2. הגדרת המודל
MODEL_NAME = "gemini-flash-latest"

# 3. הוראות מערכת (כדי שהמודל יבין שהוא יודע לקרוא קבצים)
SYSTEM_PROMPT = """
אתה אנליסט נתונים מומחה ועוזר מחקר אקדמי.
יש לך יכולת מלאה לקרוא, לנתח ולהבין קבצים שמצורפים לשיחה (כולל CSV, PDF, TXT).
כאשר משתמש מעלה קובץ Excel, המערכת ממירה אותו עבורך ל-CSV באופן אוטומטי. התייחס לזה כאל קובץ הנתונים המקורי.
אל תגיד "אני מודל שפה ולא יכול לקרוא קבצים". התפקיד שלך הוא לנתח את הנתונים שבקובץ ולענות על שאלות לגביהם.
ענה בעברית מקצועית וברורה.
"""

st.set_page_config(page_title="החוקר הדיגיטלי", page_icon="📊", layout="centered")
st.title("📊 לראש המגמה שלי")

# --- חיבור לגוגל ---
try:
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error(f"שגיאה בהגדרת המפתח: {e}")

# --- פונקציה להעלאת קובץ ---
def upload_to_gemini(uploaded_file):
    try:
        suffix = f".{uploaded_file.name.split('.')[-1].lower()}"
        mime_type = uploaded_file.type
        
        # יצירת קובץ זמני
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            # המרת אקסל ל-CSV
            if suffix in ['.xlsx', '.xls']:
                with st.spinner("ממיר אקסל לקריאה..."):
                    df = pd.read_excel(uploaded_file)
                    new_path = tmp_file.name.replace(suffix, ".csv")
                    df.to_csv(new_path, index=False, encoding='utf-8')
                    tmp_path = new_path
                    mime_type = "text/csv"
            else:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

        # העלאה לגוגל
        with st.spinner("שולח לג'מיני..."):
            gemini_file = genai.upload_file(tmp_path, mime_type=mime_type)
        
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
        return gemini_file
        
    except Exception as e:
        st.error(f"שגיאה בעיבוד הקובץ: {e}")
        return None

# --- ניהול זיכרון השיחה ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# אתחול המודל עם ההוראות החדשות
if "chat_session" not in st.session_state:
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_PROMPT
    )
    st.session_state.chat_session = model.start_chat(history=[])

# --- סרגל צד ---
with st.sidebar:
    st.header("העלאת נתונים")
    uploaded_file = st.file_uploader("בחר קובץ", type=['pdf', 'txt', 'csv', 'xlsx', 'xls', 'jpg', 'png'])
    
    if uploaded_file:
        if "last_uploaded" not in st.session_state or st.session_state.last_uploaded != uploaded_file.name:
            gemini_file = upload_to_gemini(uploaded_file)
            if gemini_file:
                st.session_state.current_file = gemini_file
                st.session_state.last_uploaded = uploaded_file.name
                st.success(f"הקובץ {uploaded_file.name} נקלט בהצלחה!")

    # הוספנו כאן key="reset_btn" כדי למנוע את השגיאה
    if st.button("נקה שיחה", key="reset_btn"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- הצגת השיחה ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- אזור הקלט ---
if prompt := st.chat_input("שאל על הנתונים..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    content_to_send = [prompt]
    
    # צירוף הקובץ להודעה אם קיים
    if "current_file" in st.session_state and st.session_state.current_file:
        content_to_send.append("מצורף קובץ הנתונים שהמשתמש העלה. נתח אותו:")
        content_to_send.append(st.session_state.current_file)
        del st.session_state.current_file 

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        try:
            response = st.session_state.chat_session.send_message(content_to_send)
            full_response = response.text
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "model", "content": full_response})
        except Exception as e:
            st.error(f"שגיאה: {e}")