import streamlit as st
from groq import Groq
import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime

# --- SETUP ---
SHEET_NAME = "My_AI_Tracker" 
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
GOOGLE_JSON = st.secrets["GOOGLE_SERVICE_ACCOUNT"]

# Initialize Groq
client = Groq(api_key=GROQ_API_KEY)

# Initialize Google Sheets with modern google-auth
@st.cache_resource
def get_gspread_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    service_account_info = json.loads(GOOGLE_JSON)
    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    return gspread.authorize(creds)

try:
    gs_client = get_gspread_client()
    sheet = gs_client.open(SHEET_NAME)
except Exception as e:
    st.error(f"Failed to connect to Google Sheets: {e}")
    st.stop()

st.title("💰 AI Expense & Loan Tracker")

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ex: Gave 500 to Rahul for lunch"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- AI LOGIC (GROQ) ---
    system_prompt = """
    You are a financial assistant. Convert user text into a JSON object.
    Fields: "tab" (either 'Transactions' or 'Loans'), "type" (Income/Expense/Lent/Borrowed), "amount" (number), "person" (name or 'N/A'), "category" (Food/Travel/Salary/etc), "desc" (summary).
    Example: "Gave 500 to Rahul" -> {"tab": "Loans", "type": "Lent", "amount": 500, "person": "Rahul", "category": "Loan", "desc": "Lent to Rahul"}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            response_format={"type": "json_object"}
        )
        data = json.loads(chat_completion.choices[0].message.content)
        
        # --- SAVE TO GOOGLE SHEETS ---
        worksheet = sheet.worksheet(data['tab'])
        date_today = datetime.now().strftime("%Y-%m-%d")
        
        if data['tab'] == "Transactions":
            worksheet.append_row([date_today, data['type'], data['category'], data['amount'], data['desc']])
        else:
            worksheet.append_row([date_today, data['person'], data['amount'], data['type']])
            
        response = f"✅ Logged {data['amount']} as {data['type']}."
    except Exception as e:
        response = f"❌ Error: {e}"

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})