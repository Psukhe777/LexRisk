import streamlit as st

# 1. Page Config (Must match your main app)
st.set_page_config(
    page_title="Upgrade to Lexrisk Pro",
    page_icon="⚖️",
    layout="centered"
)

# 2. Hero Section
st.title("⚖️ Upgrade to Lexrisk Pro")
st.markdown("The free tier is limited to 2 pages to ensure fast processing for all users. Unlock the full power of our **High-Context AI Engine** to analyze massive legal documents.")
st.divider()

# 3. Pricing Cards
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🆓 Free Tier")
    st.markdown("""
    * 2-Page PDF Limit
    * Standard AI Engine (Groq Llama-3)
    * Basic Risk Scoring
    * Public Server Queue
    """)
    st.button("Your Current Plan", disabled=True, use_container_width=True)

with col2:
    st.markdown("### 👑 Pro Tier ($15/mo)")
    st.markdown("""
    * **Unlimited Pages** (50+ page contracts)
    * **Gemini 1.5 Pro Engine** (No truncation)
    * **Priority Server Access**
    * **Export Reports to PDF**
    """)
    # Replace the URL below with a free Stripe Payment Link
    st.link_button("Upgrade Now", "https://buy.stripe.com/test_your_link", type="primary", use_container_width=True)

st.divider()

# 4. Lead Capture (The "Hunter" Fallback)
st.markdown("### Need team access or custom API limits?")
st.write("Drop your email below and our founding team will reach out.")

with st.form("lead_capture_form"):
    email = st.text_input("Work Email Address", placeholder="nehemiahsturdivant@outlook.com")
    submitted = st.form_submit_button("Request Enterprise Access", use_container_width=True)
    
    if submitted:
        if "@" in email:
            # For now, it just shows success. Later we wire this to Supabase.
            st.success(f"✅ Received! We will be in touch with {email} shortly.")
            st.balloons()
        else:
            st.error("Please enter a valid email address.")

# 5. Clean Navigation Back
st.markdown("<br><br>", unsafe_allow_html=True)
st.page_link("app.py", label="← Back to Free Scanner", icon="🏠")
