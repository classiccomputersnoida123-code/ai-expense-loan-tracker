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

st.set_page_config(page_title="AI Finance Tracker", layout="wide")
st.title("📊 Smart AI Expense & Loan Tracker")

# --- DATA LOADING ---
data_trans = trans_ws.get_all_records()
df_trans = pd.DataFrame(data_trans) if data_trans else pd.DataFrame()
if not df_trans.empty:
    df_trans['Date'] = pd.to_datetime(df_trans['Date'])

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ex: food 40 / what is my expense?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Context for AI
    history_summary = df_trans.tail(20).to_string() if not df_trans.empty else "No data."
    
    system_prompt = f"""
    You are a financial assistant. 
    Current Date: {datetime.now().strftime("%Y-%m-%d")}
    Recent History: {history_summary}

    RULES:
    1. If user asks for a report or expense summary (e.g. 'tell me my expense'): 
       Respond by asking: 'Would you like the report for today, this week, or this month?'
       Set "action": "ask_period".
    
    2. If user specifies a period (today, week, month) or a specific item (food expense):
       Analyze the data. set "action": "report", "filter_period": "today/week/month/all", "filter_item": "category name or N/A".

    3. If user provides NEW DATA (food 40):
       set "action": "save", "tab": "Transactions", "type": "Expense/Income", "amount": number, "category": "Food/etc", "desc": "summary".

    4. If just chatting: set "action": "chat", "response": "Friendly reply".

    Respond ONLY in JSON.
    """

    try:
        completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        res = json.loads(completion.choices[0].message.content)

        if res['action'] == "save":
            date_str = datetime.now().strftime("%Y-%m-%d")
            trans_ws.append_row([date_str, res['type'], res['category'], res['amount'], res['desc']])
            bot_response = f"✅ Recorded: ₹{res['amount']} as {res['type']} ({res['desc']})"

        elif res['action'] == "ask_period":
            bot_response = "📊 I can check that for you. Would you like the report for **Today**, **This Week**, or **This Month**?"

        elif res['action'] == "report":
            if df_trans.empty:
                bot_response = "You don't have any data recorded yet."
            else:
                now = datetime.now()
                temp_df = df_trans.copy()
                
                # Filter by Period
                if res['filter_period'] == "today":
                    temp_df = temp_df[temp_df['Date'].dt.date == now.date()]
                elif res['filter_period'] == "week":
                    start_week = now - timedelta(days=now.weekday())
                    temp_df = temp_df[temp_df['Date'] >= start_week]
                elif res['filter_period'] == "month":
                    temp_df = temp_df[temp_df['Date'].dt.month == now.month]

                # Filter by Item/Category if mentioned
                item = res.get('filter_item', 'N/A')
                if item != "N/A":
                    temp_df = temp_df[temp_df['Category'].str.contains(item, case=False) | temp_df['Description'].str.contains(item, case=False)]

                total = temp_df['Amount'].sum()
                count = len(temp_df)
                bot_response = f"📋 **Report for {res['filter_period'].capitalize()}**:\n- Total Amount: ₹{total}\n- Transactions: {count}\n\n"
                if count > 0:
                    bot_response += "Recent items: " + ", ".join(temp_df['Description'].tail(3).tolist())

        else:
            bot_response = res.get('response', "I'm here to help!")

    except Exception as e:
        bot_response = f"❌ Error: {str(e)}"

    with st.chat_message("assistant"):
        st.markdown(bot_response)
    st.session_state.messages.append({"role": "assistant", "content": bot_response})
