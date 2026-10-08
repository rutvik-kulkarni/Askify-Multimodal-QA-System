import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
import groq
import tempfile
import os
import re
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from better_profanity import profanity
import speech_recognition as sr
import chat_history
import ui_styles
import quiz_engine
try:
    import advanced_features
    _ADVANCED_FEATURES = True
except ImportError:
    _ADVANCED_FEATURES = False

load_dotenv()

# os.environ["PATH"] = r"C:\ffmpeg\bin" + os.pathsep + os.environ["PATH"]

st.set_page_config(
    page_title="Askify - AI Multimodal Q&A",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

ui_styles.load_css()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
API_NINJA_KEY = os.getenv("API_NINJA_KEY", "")

if not GROQ_API_KEY or GROQ_API_KEY == "gsk_...":
    st.error("⚠️ Please hardcode your Groq API Key in the code where it says 'GROQ_API_KEY'")
    st.stop()

groq_client = groq.Groq(api_key=GROQ_API_KEY)

# --- Session State ---
if 'vectorstore' not in st.session_state:
    st.session_state.vectorstore = None
if 'video_data' not in st.session_state:
    st.session_state.video_data = None
if 'transcript' not in st.session_state:
    st.session_state.transcript = None
if 'user_question' not in st.session_state:
    st.session_state.user_question = ""
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []

# --- Functions ---

def extract_video_id(url):
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)
    if match: return match.group(1)
    return None

@st.cache_data
def get_youtube_transcript(video_id, url):
    title = "YouTube Video"
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and 'title' in info:
                title = info['title']
    except Exception:
        pass

    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([t['text'] for t in transcript]), "📝 YouTube Captions", title
    except Exception:
        st.info("⏳ No captions found. Downloading audio for Whisper AI...")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_base = os.path.join(tmpdir, 'audio')
            audio_mp3 = os.path.join(tmpdir, 'audio.mp3')
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': temp_base + '.%(ext)s',
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
                if os.path.exists(audio_mp3): audio_path = audio_mp3
                else:
                    for f in os.listdir(tmpdir):
                        if f.startswith('audio'): 
                            audio_path = os.path.join(tmpdir, f)
                            break
            except Exception: raise Exception("YouTube Audio Download Failed.")
            
            try:
                with open(audio_path, 'rb') as audio_file:
                    transcription = groq_client.audio.transcriptions.create(
                        file=audio_file, model="whisper-large-v3", response_format="text"
                    )
                return str(transcription), "🎤 YouTube (Whisper)", title
            except Exception as e: raise Exception(f"Whisper Failed: {e}")

def setup_rag(transcript_text):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_text(transcript_text)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = FAISS.from_texts(chunks, embeddings)
    return vectorstore, len(chunks)

def analyze_sentiment(text):
    try:
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{"role": "user", "content": f"Analyze sentiment. Return ONLY: Positive, Negative, or Neutral.\n\nText: {text[:1500]}"}],
            max_tokens=10
        )
        sentiment = response.choices[0].message.content.strip().lower()
        if "positive" in sentiment: return "😊 Positive"
        elif "negative" in sentiment: return "😞 Negative"
        else: return "😐 Neutral"
    except: return "😐 Neutral"

def check_profanity(text):
    try:
        profanity.load_censor_words()
        words = text.split()
        if not words: return False, 0.0
        profane_count = sum(1 for word in words if profanity.contains_profanity(word))
        return profane_count > 0, (profane_count / len(words)) * 100
    except: return False, 0.0

def ask_question_rag(question, vectorstore):
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    relevant_docs = retriever.invoke(question)
    context = "\n\n".join([doc.page_content for doc in relevant_docs])
    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": "You are an expert AI assistant. Answer the question based STRICTLY on the provided context."},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"}
        ],
        max_tokens=500
    )
    return response.choices[0].message.content.strip()

# --- Sidebar ---
with st.sidebar:
    st.markdown("## 🎬 Askify")
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.vectorstore = None
        st.session_state.video_data = None
        st.session_state.transcript = None
        st.session_state.user_question = ""
        st.session_state.session_id = None
        st.session_state.chat_messages = []
        if "_af_suggestions" in st.session_state: del st.session_state["_af_suggestions"]
        if "_af_key_points" in st.session_state: del st.session_state["_af_key_points"]
        st.rerun()

    st.markdown("---")
    st.markdown("### 📚 Past Chats")
    sessions = chat_history.get_sessions_sorted()
    if not sessions:
        st.write("No past chats yet.")
    for s in sessions:
        label = s['label'] or "Untitled"
        if len(label) > 35:
            label = label[:32] + "..."
        if st.button(f"📄 {label}", key=f"session_{s['session_id']}", use_container_width=True):
            st.session_state.session_id = s['session_id']
            st.session_state.chat_messages = s['messages']
            st.session_state.vectorstore = None
            st.session_state.video_data = None
            st.session_state.transcript = None
            st.session_state.user_question = ""

    if _ADVANCED_FEATURES:
        advanced_features.render_progress_sidebar()
    
    st.markdown("---")
    st.markdown("### 🚀 Powered By")
    st.text("• Llama 3.3 (Groq)\n• Whisper V3\n• FAISS Vector DB")

# --- Main UI ---
st.title("🎬 Askify")
st.write("Transform videos and audio into an interactive AI-powered Q&A knowledge base")

st.markdown("### 1️⃣ Select Content Source")
input_type = st.radio(
    "Choose Input Type",
    ["YouTube Link", "Upload Audio", "Upload Text"],
    horizontal=True,
    label_visibility="collapsed"
)

# --- Dynamic Input Section (Fixed Alignment) ---
url = ""
uploaded_file = None
manual_text = ""

if input_type == "YouTube Link":
    col1, col2 = st.columns([5, 1])
    with col1:
        url = st.text_input("YouTube URL", placeholder="https://youtube.com/watch?v=...", label_visibility="collapsed", key="yt_url")
    with col2:
        process_btn = st.button("🔍 Analyze", use_container_width=True, key="process_yt")

elif input_type == "Upload Audio":
    uploaded_file = st.file_uploader("📂 Upload Audio File (MP3, WAV, M4A)", type=["mp3", "wav", "m4a"])
    process_btn = st.button("🔍 Analyze Audio", use_container_width=False, key="process_audio")

elif input_type == "Upload Text":
    manual_text = st.text_area("📝 Paste Text / Transcript", height=150, placeholder="Paste your content here...")
    process_btn = st.button("🔍 Analyze Text", use_container_width=False, key="process_text")

# --- Processing Logic ---
if process_btn:
    try:
        with st.spinner("🧠 Analyzing content..."):
            transcript, method, title_label = "", "", ""
            
            if input_type == "YouTube Link" and url:
                vid_id = extract_video_id(url)
                if vid_id: transcript, method, title_label = get_youtube_transcript(vid_id, url)
                else: st.error("Invalid YouTube URL")

            elif input_type == "Upload Audio" and uploaded_file:
                with tempfile.NamedTemporaryFile(delete=False, suffix="."+uploaded_file.name.split('.')[-1]) as tmp:
                    tmp.write(uploaded_file.read())
                    tmp_path = tmp.name
                try:
                    with open(tmp_path, "rb") as f:
                        transcript = str(groq_client.audio.transcriptions.create(
                            file=f, model="whisper-large-v3", response_format="text"))
                    method = "📂 Audio File"
                    title_label = f"Audio: {uploaded_file.name}"
                finally: os.remove(tmp_path)

            elif input_type == "Upload Text" and manual_text:
                transcript, method = manual_text, "📝 Text Input"
                title_label = f"Text snippet ({len(transcript)} chars)"

            if transcript:
                st.session_state.transcript = transcript
                st.session_state.vectorstore, chunks = setup_rag(transcript)
                sent = analyze_sentiment(transcript)
                has_prof, prof_pct = check_profanity(transcript)
                
                st.session_state.video_data = {
                    'method': method, 'chunks': chunks, 'sentiment': sent,
                    'profanity': has_prof, 'profanity_percentage': prof_pct,
                    'length': len(transcript)
                }
                
                session_id = chat_history.make_session_id(transcript, title_label)
                chat_history.create_session(session_id, title_label, method, transcript)
                st.session_state.session_id = session_id
                st.session_state.chat_messages = []
                
                if _ADVANCED_FEATURES:
                    advanced_features.record_activity(advanced_features.extract_topics(transcript))
                    
                st.success("✅ Content analyzed successfully!")
                st.rerun()
            else:
                st.warning("⚠️ No valid input detected")

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

# --- Tabs UI ---
if st.session_state.vectorstore:
    tab_chat, tab_quiz, tab_insights = st.tabs(["💬 Q&A Chat", "📝 Timed Quiz", "📊 Content Insights"])
    
    with tab_insights:
        st.markdown("### 📊 Content Insights")
        d = st.session_state.video_data
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.metric("📌 Source", d['method'])
        with c2: st.metric("📏 Length", f"{d['length']:,} chars")
        with c3: st.metric("🧩 RAG Chunks", d['chunks'])
        with c4: st.metric("😊 Sentiment", d['sentiment'])
        
        if d['profanity_percentage'] > 0:
            st.warning(f"⚠️ Profanity Detected: {d['profanity_percentage']:.2f}%")
            
        if _ADVANCED_FEATURES:
            advanced_features.render_topic_tags(st.session_state.transcript)
            advanced_features.render_key_points(st.session_state.transcript, groq_client, "openai/gpt-oss-20b")
            
    with tab_quiz:
        quiz_engine.render_quiz_ui(st.session_state.transcript, groq_client, "openai/gpt-oss-20b")
        
    with tab_chat:
        st.markdown("### 💬 Chat with Content")
        
        # --- Display History ---
        if st.session_state.chat_messages:
            for msg in st.session_state.chat_messages:
                with st.chat_message("user"):
                    st.write(msg.get('question',''))
                with st.chat_message("assistant"):
                    st.write(msg.get('answer',''))
                    
        st.markdown("<br>", unsafe_allow_html=True)
        
        # --- Chat Input Box ---
        col1, col2 = st.columns([8.5, 1.5])
        
        with col1:
            question = st.text_input(
                "Your Question", 
                value=st.session_state.user_question,
                placeholder="Type your question here...",
                label_visibility="collapsed",
                key="question_input"
            )
        
        with col2:
            ask_btn = st.button("💡 Ask", use_container_width=True, key="ask_btn")
            
        if st.button("🎙️ Speak Question", help="Click to speak your question", key="mic_btn", use_container_width=True):
            r = sr.Recognizer()
            with sr.Microphone() as source:
                with st.spinner("🎧 Listening..."):
                    try:
                        r.adjust_for_ambient_noise(source)
                        audio = r.listen(source, timeout=5)
                        text = r.recognize_google(audio)
                        st.session_state.user_question = text
                        st.rerun()
                    except:
                        st.error("❌ No audio detected")

        # Answer Display
        if ask_btn and question:
            with st.chat_message("user"):
                st.write(question)
                
            with st.spinner("🤖 Thinking..."):
                try:
                    st.session_state.user_question = question
                    answer = ask_question_rag(question, st.session_state.vectorstore)
                    
                    with st.chat_message("assistant"):
                        st.write(answer)
                        
                    if st.session_state.session_id:
                        chat_history.add_message(st.session_state.session_id, question, answer)
                        st.session_state.chat_messages.append({"question": question, "answer": answer})
                        st.session_state.user_question = ""
                        # Don't rerun immediately so the user can read the streamed answer. Rerunning forces a reload.
                        
                except Exception as e:
                    st.error(f"❌ Error: {e}")

        if _ADVANCED_FEATURES:
            asked = [m.get("question", "") for m in st.session_state.chat_messages]
            advanced_features.render_followup_suggestions(st.session_state.transcript, asked, groq_client, "openai/gpt-oss-20b")

# --- Footer ---
st.markdown("---")
st.markdown("<center style='color:#64748b; font-size:0.9rem;'>© 2025 Askify | Built with Streamlit, Groq & LangChain</center>", unsafe_allow_html=True)