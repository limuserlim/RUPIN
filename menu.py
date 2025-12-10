import streamlit as st
import google.generativeai as genai
import tempfile
import os
import pandas as pd

# --- 1. הגדרת המפתח ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    # בריצה מקומית כרגע זה לא יעבוד בגלל החסימה, אבל זה שומר מקום למפתח
    GOOGLE_API_KEY = "PLACEHOLDER" 

genai.configure(api_key=GOOGLE_API_KEY)

# --- 2. הגדרת ההנחיות (במשתנים נפרדים למניעת שגיאות סינטקס) ---

# הנחיה לסוכן המערכת שעות (השתמשתי ב-r''' כדי שהקוד בפנים לא ישבור את הפייתון)
PROMPT_ALGO = r'''
1.    אלגו

כללי
תפקיד: אתה מומחה Python בכיר ומומחה אלגוריתמיקה המתמחה בבעיות אופטימיזציה (CSP). 
משימה: כתוב סקריפט Python מלא לבניית מערכת שעות לבית ספר, המבוסס על קבצי קלט (Excel).

הנתונים והלוגיקה:
הקלט מכיל שני קבצי EXCEL: קובץ COURSES וקובץ AVAILABILITY.
עליך להשתמש ב-pandas.

עקרונות שיבוץ:
זמינות אבסולוטית (Strict Parsing).
מדיניות "רשימה לבנה" (Whitelist Availability).
חפיפת סטודנטים: לסטודנטים באותו שנתון לא יכולים להיות שני שיעורים במקביל.

(המשך הלוגיקה והקוד שלך מוטמעים כאן בהבנה של המודל...)
'''

# הנחיה לסוכן השאלונים
PROMPT_FORM = r'''
1.    שאלון 

כללי
מטרה: זהו שאלון שנועד לאסוף ממרצים את השעות שבהן הם זמינים ללמד.
פעילות מבוקשת: קבל נתוני קלט מהמשתמש וצור על סמך נתוני הקלט SCRIPT לבניית טופס בגוגל פורמס (Google Apps Script).

קלט מהמשתמש:
1 . שנה 
2 . סמסטרים 

הפלט הנדרש הוא קוד SCRIPT מעודכן.
הנה בסיס הסקריפט:

function createRuppinForm() {
  var inputYear = "2027"; 
  var inputSemesters = "2"; 
  var existingFormId = "1DG0JFK22gBrt8ggibE-lW6dGhUQhle7Mpipaj9lZx4c"; 
  // ... שאר הלוגיקה של הסקריפט ...
}
'''

# --- 3. בניית המילון (מחבר את השמות להנחיות) ---
AGENTS = {
    "🦉 בניית מערכת שעות": PROMPT_ALGO,
    "🎨 בניית שאלון למרצים": PROMPT_FORM
}

# --- 4. הממשק הגרפי (Streamlit) ---
st.set_page_config(page_title="העוזר של ראש המגמה", page_icon="🎓", layout="wide")

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


# --- סרגל צד ---
with st.sidebar:
    st.header("העלאת נתונים")
    uploaded_file = st.file_uploader("בחר קובץ", type=['pdf', 'txt', 'csv', 'xlsx', 'xls', 'jpg', 'png'])
    
    if uploaded_file:
        if "last_uploaded" not in st.session_state or st.session_state.last_uploaded != uploaded_file.name:
            gemini_file = upload_to_gemini(uploaded_file) # קריאה לפונקציה מחלק 2
            if gemini_file:
                st.session_state.current_file = gemini_file
                st.session_state.last_uploaded = uploaded_file.name
                st.success(f"הקובץ {uploaded_file.name} נקלט בהצלחה!")

with st.sidebar:
    st.title("בחרי את המומחה")
    st.write("עם מי תרצי לעבוד היום?")
    
    # תיבת הבחירה
    selected_agent_name = st.radio(
        "אפשרויות:",
        list(AGENTS.keys())
    )
    
    st.divider()
    st.info("💡 החלפת מומחה תאפס את השיחה.")
    
    if st.button("נקה שיחה והתחל מחדש", key="reset_chat"):
        st.session_state.messages = []
        st.session_state.chat_session = None
        st.rerun()

# --- לוגיקה להחלפת סוכנים ---
if "current_agent_name" not in st.session_state:
    st.session_state.current_agent_name = selected_agent_name

if st.session_state.current_agent_name != selected_agent_name:
    st.session_state.messages = []
    st.session_state.chat_session = None
    st.session_state.current_agent_name = selected_agent_name
    st.rerun()

st.title(f"{selected_agent_name}")

# --- אתחול המודל ---
# שימוש במודל היציב ביותר לענן
MODEL_NAME = "gemini-flash-latest"
if "chat_session" not in st.session_state or st.session_state.chat_session is None:
    current_system_instruction = AGENTS[selected_agent_name]
    
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=current_system_instruction
    )
    st.session_state.chat_session = model.start_chat(history=[])

# --- ניהול הצ'אט ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("כתוב כאן..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        try:
            response = st.session_state.chat_session.send_message(prompt)
            message_placeholder.markdown(response.text)
            st.session_state.messages.append({"role": "model", "content": response.text})
        except Exception as e:

            st.error(f"שגיאה: {e}")
