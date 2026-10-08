import streamlit as st

def load_css():
    st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* Base App Styling */
        .stApp {
            background-color: #f4f6f8;
            font-family: 'Outfit', sans-serif;
            color: #1e293b;
        }
        
        /* Main Container */
        .block-container {
            background-color: #ffffff;
            border-radius: 24px;
            padding: 3rem 4rem;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.04);
            max-width: 1200px;
            margin: 2rem auto;
            border: 1px solid #f1f5f9;
        }
        
        /* Headers */
        h1 {
            background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800 !important;
            font-size: 3.5rem !important;
            letter-spacing: -0.04em !important;
            margin-bottom: 0.5rem !important;
        }
        h2, h3 {
            color: #0f172a !important;
            font-weight: 700 !important;
            letter-spacing: -0.03em !important;
        }
        
        /* Inputs & TextAreas */
        .stTextInput > div > div > input, 
        .stTextArea textarea {
            border-radius: 12px;
            border: 2px solid #e2e8f0;
            padding: 16px 20px;
            font-size: 16px;
            background-color: #f8fafc;
            transition: all 0.3s ease;
            font-weight: 500;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
        }
        .stTextInput > div > div > input:focus, 
        .stTextArea textarea:focus {
            border-color: #3b82f6;
            background-color: #ffffff;
            box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.15);
            outline: none;
        }

        /* Buttons */
        .stButton > button {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white !important;
            border: none;
            border-radius: 12px;
            padding: 0.8rem 2rem;
            font-weight: 600;
            font-size: 16px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
            letter-spacing: 0.02em;
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.35);
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        }
        
        /* Sidebar styling */
        section[data-testid="stSidebar"] {
            background-color : #ffffff;
            border-right: 1px solid #e2e8f0;
            box-shadow: 4px 0 24px rgba(0,0,0,0.02);
        }
        
        /* Custom Past Chat Buttons (Make them look like menu items) */
        section[data-testid="stSidebar"] .stButton > button {
            background: transparent;
            color: #475569 !important;
            box-shadow: none;
            border: 1px solid transparent;
            text-align: left;
            justify-content: flex-start;
            padding: 12px 16px;
            border-radius: 8px;
            font-weight: 500;
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            background: #f1f5f9;
            color: #0f172a !important;
            transform: none;
        }
        
        /* Tabs styling */
        button[data-baseweb="tab"] {
            background-color: transparent;
            padding: 16px 24px;
            margin-right: 8px;
            transition: all 0.2s;
            border: none;
            border-bottom: 3px solid transparent;
            font-weight: 600;
            color: #64748b;
            font-size: 1.05rem;
        }
        button[data-baseweb="tab"]:hover {
            color: #2563eb;
            background: transparent;
        }
        button[aria-selected="true"] {
            color: #2563eb !important;
            border-bottom: 3px solid #2563eb !important;
            background: transparent !important;
        }
        
        hr {
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 2.5rem 0;
        }
    </style>
    """, unsafe_allow_html=True)
