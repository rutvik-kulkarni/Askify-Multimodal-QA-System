"""
quiz_engine.py — Timed MCQ quiz generation and evaluation using LLM.
"""

import json
import re
import time
import streamlit as st

def generate_quiz(transcript: str, groq_client, model: str, num_questions: int = 5):
    """
    Generates multiple-choice questions from the transcript.
    Returns a list of dicts: {"question": "...", "options": ["A", "B", "C", "D"], "answer": "A"}
    """
    prompt = f"""
    You are an expert educator. Create {num_questions} multiple-choice questions based on the following text.
    Format your response STRICTLY as a JSON list of objects. Each object must have:
    - "question": The question text
    - "options": A list of exactly 4 strings for the choices
    - "answer": The exact string of the correct option

    Text excerpt: {transcript[:4000]}
    
    Output ONLY valid JSON.
    """
    
    try:
        response = groq_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            response_format={"type": "json_object"} if "llama-3" in model.lower() or "qwen" in model.lower() else None
        )
        content = response.choices[0].message.content.strip()
        
        # Try to parse json directly, or extract it if wrapped in markdown
        match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
        if match:
            content = match.group(0)
        else:
             match = re.search(r'\{\s*".*\}\s*', content, re.DOTALL)
             if match:
                 content = match.group(0)
                 
        data = json.loads(content)
        
        # Helper to check if a dict is a valid question
        def is_valid_q(item):
            return isinstance(item, dict) and "question" in item and "options" in item and "answer" in item
            
        # Handle cases where the LLM wraps the list in a dict, e.g., {"questions": [...]}
        if isinstance(data, dict):
            # If it returned a single question object
            if is_valid_q(data):
                return [data]
            # If it returned a dictionary containing the list of questions
            for val in data.values():
                if isinstance(val, list) and len(val) > 0 and is_valid_q(val[0]):
                    return val
            return []
        elif isinstance(data, list):
            # Filter out any invalid items just in case
            return [item for item in data if is_valid_q(item)]
        return []
    except Exception as e:
        print(f"Quiz generation error: {e}")
        return []

def render_quiz_ui(transcript: str, groq_client, model: str):
    """Renders the interactive timed quiz UI in Streamlit."""
    
    TIME_LIMIT_SEC = 300 # 5 minutes total
    
    if "quiz_data" not in st.session_state:
        st.session_state.quiz_data = None
    if "quiz_answers" not in st.session_state:
        st.session_state.quiz_answers = {}
    if "quiz_submitted" not in st.session_state:
        st.session_state.quiz_submitted = False
    if "quiz_start_time" not in st.session_state:
        st.session_state.quiz_start_time = None
    if "quiz_current_q" not in st.session_state:
        st.session_state.quiz_current_q = 0
        
    st.markdown("### 📝 Knowledge Check Quiz")
    st.write("Test your understanding of the material. You have 5 minutes!")
    
    if not st.session_state.quiz_data:
        if st.button("🚀 Start Quiz", use_container_width=True):
            with st.spinner("Generating questions based on the content..."):
                questions = generate_quiz(transcript, groq_client, model)
                if questions:
                    st.session_state.quiz_data = questions
                    st.session_state.quiz_answers = {}
                    st.session_state.quiz_submitted = False
                    st.session_state.quiz_start_time = time.time()
                    st.session_state.quiz_current_q = 0
                    st.rerun()
                else:
                    st.error("Failed to generate quiz. Please try again.")
    else:
        questions = st.session_state.quiz_data
        
        # Display Timer & Handle Timeout
        if not st.session_state.quiz_submitted:
            elapsed = int(time.time() - st.session_state.quiz_start_time)
            remaining = max(0, TIME_LIMIT_SEC - elapsed)
            
            # Progress bar for time
            st.progress(remaining / TIME_LIMIT_SEC)
            st.markdown(f"**⏱️ Time remaining:** {remaining // 60}m {remaining % 60}s")
            
            if remaining == 0:
                st.error("⏰ Time's up! Auto-submitting your quiz.")
                st.session_state.quiz_submitted = True
                st.rerun()
                
        if not st.session_state.quiz_submitted:
            curr = st.session_state.quiz_current_q
            q = questions[curr]
            
            st.markdown("---")
            st.markdown(f"#### Question {curr + 1} of {len(questions)}")
            st.markdown(f"**{q['question']}**")
            
            # Use unique key for the radio so it updates properly
            st.session_state.quiz_answers[curr] = st.radio(
                "Select answer:",
                q['options'],
                key=f"q_radio_{curr}",
                label_visibility="collapsed",
                index=q['options'].index(st.session_state.quiz_answers[curr]) if curr in st.session_state.quiz_answers and st.session_state.quiz_answers[curr] in q['options'] else None
            )
            
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if curr > 0:
                    if st.button("⬅️ Previous", use_container_width=True):
                        st.session_state.quiz_current_q -= 1
                        st.rerun()
            with col2:
                if curr < len(questions) - 1:
                    if st.button("Next ➡️", use_container_width=True):
                        st.session_state.quiz_current_q += 1
                        st.rerun()
                else:
                    if st.button("✅ Submit Quiz", type="primary", use_container_width=True):
                        st.session_state.quiz_submitted = True
                        st.rerun()
                        
        else:
            # Score and Results Review
            score = 0
            for i, q in enumerate(questions):
                if st.session_state.quiz_answers.get(i) == q['answer']:
                    score += 1
                    
            st.success(f"🎉 **Final Score: {score} / {len(questions)}**")
            
            st.markdown("### Review")
            for i, q in enumerate(questions):
                user_ans = st.session_state.quiz_answers.get(i, "No Answer")
                is_correct = (user_ans == q['answer'])
                
                with st.expander(f"Q{i+1}: {q['question']} {'✅' if is_correct else '❌'}"):
                    st.write(f"**Your Answer:** {user_ans}")
                    if not is_correct:
                        st.write(f"**Correct Answer:** {q['answer']}")
                        
            if st.button("🔄 Retake / Generate New Quiz", use_container_width=True):
                st.session_state.quiz_data = None
                st.rerun()
