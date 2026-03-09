import streamlit as st
from groq import Groq
from supabase import create_client, Client
import json
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
# In Streamlit Cloud, add these to "Settings > Secrets"
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# Initialize Clients
@st.cache_resource
def init_connections():
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    groq_client = Groq(api_key=GROQ_API_KEY)
    return supabase_client, groq_client

supabase, groq_client = init_connections()

# --- APP UI ---
st.set_page_config(page_title="AI Finance Tracker", layout="wide")
st.title("🚀 Smart Hinglish AI Tracker (Supabase)")

# --- STATE MANAGEMENT ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_entry" not in st.session_state:
    st.session_state.pending_entry = None

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- CHAT INPUT ---
if prompt := st.chat_input("Ex: lunch 200 / mithun ko 500 diye"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 1. HANDLE CONFIRMATION (YES/NO)
    if st.session_state.pending_entry and prompt.lower() in ['yes', 'haan', 'ok', 'kar do', 'y', 'han']:
        e = st.session_state.pending_entry
        try:
            if e['table'] == "transactions":
                data = {
                    "type": e['type'], 
                    "category": e['category'], 
                    "amount": float(e['amount']), 
                    "description": e['desc']
                }
                supabase.table("transactions").insert(data).execute()
            else:
                data = {
                    "person": e['person'], 
                    "amount": float(e['amount']), 
                    "type": e['type']
                }
                supabase.table("loans").insert(data).execute()
            
            bot_response = f"✅ Done! ₹{e['amount']} ki entry Supabase mein save ho gayi hai."
        except Exception as err:
            bot_response = f"❌ Database Error: {err}"
        
        st.session_state.pending_entry = None

    elif st.session_state.pending_entry and prompt.lower() in ['no', 'nahi', 'cancel', 'n']:
        bot_response = "Theek hai, cancel kar diya. Kuch aur help chahiye?"
        st.session_state.pending_entry = None

    # 2. REGULAR AI LOGIC
    else:
        system_prompt = """
        You are a Hinglish financial assistant. 
        - If user wants to SAVE a transaction: Set "action": "confirm", "table": "transactions/loans", "type": "Income/Expense/Lent/Borrowed/Paid", "amount": number, "person": name/NA, "category": string, "desc": Hinglish summary.
        - If user asks for a REPORT: Set "action": "report", "table": "transactions/loans", "filter": "category/person/NA", "period": "today/week/month/all".
        - Respond ONLY in JSON.
        """

        try:
            completion = groq_client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"}
            )
            res = json.loads(completion.choices[0].message.content)

            if res['action'] == "confirm":
                st.session_state.pending_entry = res
                bot_response = f"Bhai, ₹{res['amount']} ka {res['type']} ({res['desc']}) save kar doon? (Yes/No)"
            
            elif res['action'] == "report":
                # Fetch data from Supabase
                query = supabase.table(res['table']).select("*").execute()
                df = pd.DataFrame(query.data)
                
                if df.empty:
                    bot_response = "Abhi tak koi data nahi mila."
                else:
                    total = df['amount'].sum()
                    bot_response = f"Aapka total {res['table']} ka hisab ₹{total} hai."
            else:
                bot_response = res.get('response', "Main samajh nahi paya, please firse boliye.")

        except Exception as e:
            bot_response = f"❌ Error: {str(e)}"

    with st.chat_message("assistant"):
        st.markdown(bot_response)
    st.session_state.messages.append({"role": "assistant", "content": bot_response})
