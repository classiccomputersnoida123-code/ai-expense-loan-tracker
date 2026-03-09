import streamlit as st
from groq import Groq
import gspread
from google.oauth2.service_account import Credentials
import json
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
SHEET_NAME = "My_AI_Tracker"  # <-- DOUBLE CHECK THIS MATCHES YOUR SHEET NAME
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
GOOGLE_JSON = st.secrets["GOOGLE_SERVICE_ACCOUNT"]

# Initialize Groq
client = Groq(api_key=GROQ_API_KEY)

# Initialize Google Sheets (Cached for performance)
@st.cache_resource
def get_gs_client():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    service_account_info = json.loads(GOOGLE_JSON)
    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    return gspread.authorize(creds)

try:
    gs_client = get_gs_client()
    sheet = gs_client.open(SHEET_NAME)
    trans_ws = sheet.worksheet("Transactions")
    loans_ws = sheet.worksheet("Loans")
except Exception as e:
    st.error(f"⚠️ Connection Error: {e}")
    st.stop()

# --- APP UI ---
st.set_page_config(page_title="AI Finance Tracker", layout="wide")
st.title("💰 AI Expense & Loan Tracker")

# --- DASHBOARD SECTION ---
try:
    # Refresh data for the dashboard
    data = trans_ws.get_all_records()
    if data:
        df_trans = pd.DataFrame(data)
        income = df_trans[df_trans['Type'] == 'Income']['Amount'].sum()
        expense = df_trans[df_trans['Type'] == 'Expense']['Amount'].sum()
        balance = income - expense
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Current Balance", f"₹{balance}")
        col2.metric("Total Expenses", f"₹{expense}")
        col3.metric("Total Income", f"₹{income}")
except:
    st.info("Start chatting to see your financial summary here!")

st.divider()

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("Ex: Spent 500 on dinner / Gave 1000 to Amit"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- SMART AI BRAIN (GROQ) ---
    system_prompt = """
    You are a financial assistant. Analyze the user's message.
    
    1. If the message is just a greeting (hi, hello) or general chat (how are you, you know hindi?):
       set "save_data": false and "response": "A friendly reply to the user".
       
    2. If the message describes a financial transaction (spent, lent, earned, received, paid):
       set "save_data": true and fill these fields:
       - "tab": "Transactions" (for personal) or "Loans" (for friends)
       - "type": "Income", "Expense", "Lent", "Borrowed", or "Paid"
       - "amount": number
       - "person": Name of friend or "N/A"
       - "category": Food, Travel, Salary, Rent, Loan, etc.
       - "desc": A very short 3-word summary.
       
    Respond ONLY in a valid JSON format.
    """
    
    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        
        res = json.loads(completion.choices[0].message.content)

        # --- SMART SAVE LOGIC ---
        if res.get('save_data') == True:
            date_str = datetime.now().strftime("%Y-%m-%d")
            
            if res['tab'] == "Transactions":
                trans_ws.append_row([date_str, res['type'], res['category'], res['amount'], res['desc']])
            else:
                loans_ws.append_row([date_str, res['person'], res['amount'], res['type']])
            
            bot_response = f"✅ **Recorded:** ₹{res['amount']} as {res['type']} ({res['desc']})"
        else:
            # Just talk back, do not write to Google Sheets
            bot_response = res.get('response', "I'm listening! Tell me about an expense or a loan.")
            
    except Exception as e:
        bot_response = f"❌ Error: {str(e)}"

    with st.chat_message("assistant"):
        st.markdown(bot_response)
    st.session_state.messages.append({"role": "assistant", "content": bot_response})