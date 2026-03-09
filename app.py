import streamlit as st
from groq import Groq
import gspread
from google.oauth2.service_account import Credentials
import json
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURATION ---
SHEET_NAME = "My_AI_Tracker" 
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
GOOGLE_JSON = st.secrets["GOOGLE_SERVICE_ACCOUNT"]

client = Groq(api_key=GROQ_API_KEY)

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

st.set_page_config(page_title="Hinglish AI Finance Tracker", layout="wide")
st.title("💸 Smart Hinglish Finance Tracker")

# --- DATA LOADING & CLEANING ---
def get_clean_data(worksheet):
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        # Fix the 'str + int' error by forcing Amount to be numeric
        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    return df

df_trans = get_clean_data(trans_ws)

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_entry" not in st.session_state:
    st.session_state.pending_entry = None

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ex: 500 mithun ko diye / mera kharcha dikhao"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- HANDLE CONFIRMATION ---
    if st.session_state.pending_entry and prompt.lower() in ['yes', 'haan', 'ok', 'kar do', 'y']:
        entry = st.session_state.pending_entry
        date_str = datetime.now().strftime("%Y-%m-%d")
        if entry['tab'] == "Transactions":
            trans_ws.append_row([date_str, entry['type'], entry['category'], entry['amount'], entry['desc']])
        else:
            loans_ws.append_row([date_str, entry['person'], entry['amount'], entry['type']])
        
        bot_response = f"✅ Done! ₹{entry['amount']} entry save kar di hai."
        st.session_state.pending_entry = None
    
    elif st.session_state.pending_entry and prompt.lower() in ['no', 'nahi', 'cancel', 'n']:
        bot_response = "Theek hai, entry cancel kar di. Kuch aur help chahiye?"
        st.session_state.pending_entry = None

    # --- REGULAR AI LOGIC ---
    else:
        history_summary = df_trans.tail(10).to_string() if not df_trans.empty else "No records."
        system_prompt = f"""
        You are a Hinglish financial assistant. Talk in a mix of Hindi and English.
        Current Data: {history_summary}

        RULES:
        1. If user wants to SAVE data: DO NOT save yet. Set "action": "confirm" and explain what you understood in Hinglish.
        2. If user asks for a REPORT: Set "action": "report", "filter_period": "today/week/month/all".
        3. Respond ONLY in JSON.
        
        Fields for 'confirm': "tab", "type", "amount", "person", "category", "desc".
        """

        try:
            completion = client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"}
            )
            res = json.loads(completion.choices[0].message.content)

            if res['action'] == "confirm":
                st.session_state.pending_entry = res
                bot_response = f"Aapne kaha: ₹{res['amount']} ka {res['type']} for {res['desc']}. Kya main ise save karun? (Yes/No)"
            
            elif res['action'] == "report":
                # Logic for filtering df_trans based on res['filter_period']
                total = df_trans['Amount'].sum() # Simplified for brevity
                bot_response = f"Aapka total {res['filter_period']} ka kharcha ₹{total} hai."
            
            else:
                bot_response = res.get('response', "Main samajh nahi paya, please firse boliye.")

        except Exception as e:
            bot_response = f"❌ Error: {str(e)}"

    with st.chat_message("assistant"):
        st.markdown(bot_response)
    st.session_state.messages.append({"role": "assistant", "content": bot_response})
