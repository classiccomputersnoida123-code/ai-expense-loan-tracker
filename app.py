import streamlit as st
from groq import Groq
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from datetime import datetime

# --- SETUP ---
SHEET_NAME = "My_AI_Tracker"  # <-- CHANGE THIS to your Google Sheet name
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
GOOGLE_JSON = st.secrets["GOOGLE_SERVICE_ACCOUNT"]

# Initialize Groq
client = Groq(api_key=GROQ_API_KEY)

# Initialize Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(GOOGLE_JSON), scope)
gs_client = gspread.authorize(creds)
sheet = gs_client.open(SHEET_NAME)

st.title("💰 AI Expense & Loan Tracker")
st.markdown("Chat with me to log expenses, income, or loans!")

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
    
    chat_completion = client.chat.completions.create(
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        model="llama3-8b-8192",
        response_format={"type": "json_object"}
    )
    
    data = json.loads(chat_completion.choices[0].message.content)
    
    # --- SAVE TO GOOGLE SHEETS ---
    try:
        worksheet = sheet.worksheet(data['tab'])
        date_today = datetime.now().strftime("%Y-%m-%d")
        
        if data['tab'] == "Transactions":
            worksheet.append_row([date_today, data['type'], data['category'], data['amount'], data['desc']])
        else:
            worksheet.append_row([date_today, data['person'], data['amount'], data['type']])
            
        response = f"✅ Logged {data['amount']} as {data['type']} for {data.get('person', data.get('category'))}."
    except Exception as e:
        response = f"❌ Error saving to sheet: {e}"

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})