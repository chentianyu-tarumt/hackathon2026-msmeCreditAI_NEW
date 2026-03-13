from dotenv import load_dotenv
load_dotenv("apiKey.env")

import streamlit as st
import anthropic
import json
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import hashlib

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hackathon 2026: MSME CreditAI Analysis",
    page_icon="💼",
    layout="centered",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Space Grotesk', sans-serif; }
.main { background-color: #0d0f14; }

.hero {
    background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%);
    border: 1px solid #2a3142;
    border-radius: 16px;
    padding: 2rem 2.5rem;
    margin-bottom: 2rem;
    text-align: center;
}
.hero h1 { font-size: 2.2rem; font-weight: 700; color: #e8eaf0; margin: 0 0 0.4rem 0; }
.hero h1 span { color: #4ade80; }
.hero p { color: #7a8499; font-size: 0.95rem; margin: 0; }

.section-label {
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem; font-weight: 500; color: #4ade80;
    letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.5rem;
}

.score-card { border-radius: 14px; padding: 1.8rem 2rem; margin: 1.5rem 0; border: 1px solid; text-align: center; }
.score-high  { background: linear-gradient(135deg, #052e16 0%, #0d1f0d 100%); border-color: #4ade80; }
.score-medium{ background: linear-gradient(135deg, #1c1a05 0%, #1a1505 100%); border-color: #facc15; }
.score-low   { background: linear-gradient(135deg, #1f0d0d 0%, #200808 100%); border-color: #f87171; }
.score-label { font-family: 'DM Mono', monospace; font-size: 0.75rem; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 0.4rem; }
.score-value { font-size: 3rem; font-weight: 700; line-height: 1; margin-bottom: 0.3rem; }
.score-tier  { font-size: 1rem; font-weight: 600; opacity: 0.85; }

.info-box {
    background: #131720; border: 1px solid #2a3142; border-radius: 10px;
    padding: 1.2rem 1.5rem; margin: 1rem 0; font-size: 0.9rem; color: #c8ccd8; line-height: 1.7;
}
.tip-item {
    display: flex; gap: 0.75rem; align-items: flex-start;
    padding: 0.7rem 0; border-bottom: 1px solid #1e2330;
    color: #c8ccd8; font-size: 0.88rem; line-height: 1.6;
}
.tip-num {
    font-family: 'DM Mono', monospace; font-size: 0.72rem;
    background: #1e2d1e; color: #4ade80;
    padding: 2px 7px; border-radius: 4px; flex-shrink: 0; margin-top: 2px;
}
hr { border-color: #1e2330; }

div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] select {
    background-color: #131720 !important; color: #e8eaf0 !important;
    border: 1px solid #2a3142 !important; border-radius: 8px !important;
}
.stButton > button {
    background: linear-gradient(135deg, #16a34a, #15803d) !important;
    color: white !important; border: none !important; border-radius: 10px !important;
    font-family: 'Space Grotesk', sans-serif !important; font-weight: 600 !important;
    font-size: 1rem !important; padding: 0.7rem 2rem !important;
    width: 100% !important; transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.88 !important; }

div[data-testid="stMetricValue"] {
    font-size: 1.1rem !important;
    overflow: visible !important;
    white-space: normal !important;
    word-break: break-word !important;
}

</style>
""", unsafe_allow_html=True)

# ── Firebase Setup ─────────────────────────────────────────────────────────────
@st.cache_resource
def init_firebase():
    if not firebase_admin._apps:
        if "firebase" in st.secrets:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
        else:
            cred = credentials.Certificate("service_account.json")
        firebase_admin.initialize_app(cred)
    return firestore.client()

try:
    db = init_firebase()
except Exception as e:
    st.error(f"Firebase connection failed: {str(e)}")
    st.stop()

# ── Auth Helpers ───────────────────────────────────────────────────────────────
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    users_ref = db.collection("users")
    existing = users_ref.where("username", "==", username).get()
    if len(list(existing)) > 0:
        return False, "Username already exists."
    users_ref.add({
        "username": username,
        "password": hash_password(password),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    return True, "Account created successfully!"

def login_user(username, password):
    users_ref = db.collection("users")
    results = users_ref.where("username", "==", username).get()
    for doc in results:
        user = doc.to_dict()
        if user["password"] == hash_password(password):
            return True, "Login successful!"
    return False, "Invalid username or password."

# ── Firestore Helpers ──────────────────────────────────────────────────────────
def save_to_firestore(db, data, result, username):
    doc = {
        "username": username,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "business_name": data["business_name"],
        "industry": data["industry"],
        "years_operating": data["years_operating"],
        "num_employees": data["num_employees"],
        "monthly_revenue": data["monthly_revenue_RM"],
        "monthly_expenses": data["monthly_expenses_RM"],
        "has_bank_account": data["has_bank_account"],
        "loan_requested": data["loan_amount_requested_RM"],
        "digital_presence": data["digital_presence"],
        "digital_payments": data["digital_payments"],
        "supplier_relations": data["supplier_relationships"],
        "customer_base": data["customer_base"],
        "credit_score": result["credit_score"],
        "tier": result["tier"],
        "summary": result["summary"],
        "recommended_loan": result["recommended_loan_range_RM"],
    }
    db.collection("credit_assessments").add(doc)

def load_history(db, username):
    docs = db.collection("credit_assessments")\
        .where("username", "==", username)\
        .order_by("timestamp", direction=firestore.Query.DESCENDING)\
        .stream()
    records = []
    for doc in docs:
        row = doc.to_dict()
        row["doc_id"] = doc.id
        records.append(row)
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)

def delete_record(db, doc_id):
    db.collection("credit_assessments").document(doc_id).delete()

# ── Session State ──────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>MSME <span>CreditAI</span></h1>
    <p>An Alternative Credit Scoring for ASEAN Micro, Small and Medium Enterprise · Developed for Hackathon 2026</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# NOT LOGGED IN
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        st.markdown('<div class="section-label">Login to your account</div>', unsafe_allow_html=True)
        login_user_input = st.text_input("Username", key="login_username")
        login_pass_input = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            if login_user_input and login_pass_input:
                success, msg = login_user(login_user_input, login_pass_input)
                if success:
                    st.session_state.logged_in = True
                    st.session_state.username = login_user_input
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("Please enter username and password.")

    with tab2:
        st.markdown('<div class="section-label">Create a new account</div>', unsafe_allow_html=True)
        reg_username = st.text_input("Choose a Username", key="reg_username")
        reg_password = st.text_input("Choose a Password", type="password", key="reg_password")
        reg_password2 = st.text_input("Confirm Password", type="password", key="reg_password2")
        if st.button("Register"):
            if reg_username and reg_password and reg_password2:
                if reg_password != reg_password2:
                    st.error("Passwords do not match.")
                elif len(reg_password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    success, msg = register_user(reg_username, reg_password)
                    if success:
                        st.success(msg + " Please login now.")
                    else:
                        st.error(msg)
            else:
                st.warning("Please fill in all fields.")

# ══════════════════════════════════════════════════════════════════════════════
# LOGGED IN
# ══════════════════════════════════════════════════════════════════════════════
else:
    col_user, col_logout = st.columns([4, 1])
    with col_user:
        st.markdown(f'<div class="section-label">You are now Logged in as: {st.session_state.username}</div>', unsafe_allow_html=True)
    with col_logout:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

    page = st.radio("", ["New Assessment", "My History & Analytics"], horizontal=True, label_visibility="collapsed")
    st.markdown("<br>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1 — NEW ASSESSMENT
    # ══════════════════════════════════════════════════════════════════════════
    if page == "New Assessment":

        st.markdown('<div class="section-label">Business Profile</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            business_name = st.text_input("Business Name", placeholder="e.g. ABC Enterprise")
            industry = st.selectbox("Industry", [
                "Retail & Grocery", "Food & Beverage", "Agriculture",
                "Manufacturing", "Services", "E-commerce", "Handicraft & Artisan", "Others"
            ])
            years_operating = st.number_input("Years in Operation", min_value=0, max_value=99, value=0)
            num_employees = st.number_input("Number of Employees", min_value=1, max_value=500, value=1)

        with col2:
            monthly_revenue = st.number_input("Avg Monthly Revenue (RM)", min_value=0, value=0, step=1000)
            monthly_expenses = st.number_input("Avg Monthly Expenses (RM)", min_value=0, value=0, step=1000)
            has_bank_account = st.selectbox("Has Business Bank Account?", ["Yes", "No"])
            loan_amount_requested = st.number_input("Loan Amount Requested (RM)", min_value=0, value=0, step=1000)

        st.markdown('<div class="section-label" style="margin-top:1rem">Additional Signals</div>', unsafe_allow_html=True)

        col3, col4 = st.columns(2)
        with col3:
            has_digital_presence = st.selectbox("Online/Digital Presence?", ["Yes — active social media/e-commerce", "Partial — basic online presence", "No"])
            payment_method = st.selectbox("Accepts Digital Payments?", ["Yes — multiple platforms", "Yes — one platform", "Cash only"])
        with col4:
            supplier_relationships = st.selectbox("Supplier Relationships", ["Long-term (3+ years)", "Medium (1–3 years)", "Short-term / New"])
            customer_retention = st.selectbox("Customer Base", ["Mostly repeat customers", "Mixed", "Mostly new customers"])

        additional_notes = st.text_area("Any additional context (optional)", placeholder="e.g. Recently expanded to online sales, seasonal business, etc.", height=80)

        st.markdown("<br>", unsafe_allow_html=True)
        submit = st.button("Analyse Creditworthiness Now!")

        if submit:
            if monthly_revenue == 0:
                st.warning("Please enter a monthly revenue figure.")
            else:
                with st.spinner("AI is analysing your business profile..."):

                    business_data = {
                        "business_name": business_name or "Unnamed Business",
                        "industry": industry,
                        "years_operating": years_operating,
                        "num_employees": num_employees,
                        "monthly_revenue_RM": monthly_revenue,
                        "monthly_expenses_RM": monthly_expenses,
                        "monthly_net_profit_RM": monthly_revenue - monthly_expenses,
                        "profit_margin_pct": round((monthly_revenue - monthly_expenses) / monthly_revenue * 100, 1) if monthly_revenue else 0,
                        "has_bank_account": has_bank_account,
                        "loan_amount_requested_RM": loan_amount_requested,
                        "loan_to_monthly_revenue_ratio": round(loan_amount_requested / monthly_revenue, 1) if monthly_revenue else 0,
                        "digital_presence": has_digital_presence,
                        "digital_payments": payment_method,
                        "supplier_relationships": supplier_relationships,
                        "customer_base": customer_retention,
                        "additional_notes": additional_notes or "None"
                    }

                    prompt = f"""
You are an inclusive MSME credit analyst for ASEAN markets. Assess this small business's creditworthiness using ALTERNATIVE data signals (not just bank history), because many MSMEs are unbanked or informal.

Business Data:
{json.dumps(business_data, indent=2)}

Respond ONLY with a valid JSON object in this exact format (no markdown, no extra text):
{{
  "credit_score": <integer 300-850>,
  "tier": "<one of: High / Medium / Low>",
  "summary": "<2-3 sentence plain-language summary of their creditworthiness>",
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "risks": ["<risk 1>", "<risk 2>"],
  "improvement_tips": ["<tip 1>", "<tip 2>", "<tip 3>"],
  "recommended_loan_range_RM": "<e.g. RM 10,000 – RM 25,000>"
}}

Be fair, practical, and encouraging. Consider that informal businesses in ASEAN often lack credit history but are viable. Weight digital presence, profit margins, years operating, and supplier relationships heavily.
"""

                    try:
                        client = anthropic.Anthropic()
                        response = client.messages.create(
                            model="claude-haiku-4-5-20251001",
                            max_tokens=1000,
                            messages=[{"role": "user", "content": prompt}]
                        )

                        raw = response.content[0].text.strip()
                        if raw.startswith("```"):
                            raw = raw.split("```")[1]
                            if raw.startswith("json"):
                                raw = raw[4:]
                        result = json.loads(raw.strip())

                        save_to_firestore(db, business_data, result, st.session_state.username)

                        score = result["credit_score"]
                        tier = result["tier"]

                        if tier == "High":
                            card_class, score_color = "score-high", "#4ade80"
                        elif tier == "Medium":
                            card_class, score_color = "score-medium", "#facc15"
                        else:
                            card_class, score_color = "score-low", "#f87171"

                        st.markdown(f"""
<div class="score-card {card_class}">
    <div class="score-label" style="color:{score_color}">Credit Score</div>
    <div class="score-value" style="color:{score_color}">{score}</div>
    <div class="score-tier" style="color:{score_color}">{tier} Creditworthiness</div>
</div>
""", unsafe_allow_html=True)

                        st.success("Result saved to your account!")

                        st.markdown('<div class="section-label">AI Summary</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="info-box">{result["summary"]}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="info-box"><strong>Recommended Loan Range:</strong> {result["recommended_loan_range_RM"]}</div>', unsafe_allow_html=True)

                        col5, col6 = st.columns(2)
                        with col5:
                            st.markdown('<div class="section-label">Strengths</div>', unsafe_allow_html=True)
                            strengths_html = "".join([f'<div class="tip-item"><span class="tip-num">+</span>{s}</div>' for s in result["strengths"]])
                            st.markdown(f'<div class="info-box" style="padding:0.8rem 1rem">{strengths_html}</div>', unsafe_allow_html=True)
                        with col6:
                            st.markdown('<div class="section-label">Risk Factors</div>', unsafe_allow_html=True)
                            risks_html = "".join([f'<div class="tip-item"><span class="tip-num" style="background:#2d1515;color:#f87171">!</span>{r}</div>' for r in result["risks"]])
                            st.markdown(f'<div class="info-box" style="padding:0.8rem 1rem">{risks_html}</div>', unsafe_allow_html=True)

                        st.markdown('<div class="section-label">How to Improve Your Score</div>', unsafe_allow_html=True)
                        tips_html = "".join([
                            f'<div class="tip-item"><span class="tip-num">0{i+1}</span>{tip}</div>'
                            for i, tip in enumerate(result["improvement_tips"])
                        ])
                        st.markdown(f'<div class="info-box" style="padding:0.8rem 1rem">{tips_html}</div>', unsafe_allow_html=True)

                    except json.JSONDecodeError:
                        st.error("Could not parse AI response. Please try again.")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — MY HISTORY & ANALYTICS
    # ══════════════════════════════════════════════════════════════════════════
    else:
        st.markdown(f'<div class="section-label"> {st.session_state.username}\'s Assessment History</div>', unsafe_allow_html=True)

        df = load_history(db, st.session_state.username)

        if df.empty:
            st.info("No assessments yet. Run a New Assessment first!")
        else:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Assessments", len(df))
            col2.metric("Average Credit Score", f"{int(pd.to_numeric(df['credit_score'], errors='coerce').mean())}")
            col3.metric("High Tier", len(df[df['tier'] == 'High']))
            col4.metric("Average Loan Requested", f"RM {int(pd.to_numeric(df['loan_requested'], errors='coerce').mean()):,}")

            st.markdown("<br>", unsafe_allow_html=True)

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown('<div class="section-label">Assessments by Tier</div>', unsafe_allow_html=True)
                tier_counts = df['tier'].value_counts().reset_index()
                tier_counts.columns = ['Tier', 'Count']
                st.bar_chart(tier_counts.set_index('Tier'))
            with col_b:
                st.markdown('<div class="section-label">Assessments by Industry</div>', unsafe_allow_html=True)
                industry_counts = df['industry'].value_counts().reset_index()
                industry_counts.columns = ['Industry', 'Count']
                st.bar_chart(industry_counts.set_index('Industry'))

            st.markdown('<div class="section-label">My Records</div>', unsafe_allow_html=True)
            display_cols = ['timestamp', 'business_name', 'industry',
                            'monthly_revenue', 'credit_score', 'tier', 'recommended_loan']
            available_cols = [c for c in display_cols if c in df.columns]
            st.dataframe(df[available_cols], use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)
            csv = df.drop(columns=['doc_id'], errors='ignore').to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export My Records as CSV File (.csv)",
                data=csv,
                file_name=f"my_assessments_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

            st.markdown('<div class="section-label" style="margin-top:1.5rem">Delete a Record</div>', unsafe_allow_html=True)
            if 'doc_id' in df.columns:
                options = {f"{row['business_name']} — {row['timestamp']}": row['doc_id'] for _, row in df.iterrows()}
                selected_label = st.selectbox("Select record to delete", list(options.keys()))
                if st.button("Delete Selected Record"):
                    delete_record(db, options[selected_label])
                    st.success("Record deleted.")
                    st.rerun()