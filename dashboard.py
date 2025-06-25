from dotenv import load_dotenv
import os
load_dotenv()
import streamlit as st
import time
import logging
from database import create_db_from_excel, query_db
from agent import get_agent_response
from conversation_store import ConversationStore
from shared_state import shared_state
import uuid

# Configure logging for dashboard to output to console/terminal
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This ensures output goes to console/terminal
    ]
)

# Constants
ASSISTANT_AVATAR = "https://app.optiwise.ai/assets/olivia-IF0pvoa5.png"
OPTIWISE_LOGO = "https://www.optiwise.ai/wp-content/uploads/2022/10/optiwise_logo_Color.png"

# if "GOOGLE_APPLICATION_CREDENTIALS_JSON" in st.secrets:
#     with open("gcp_creds.json", "w") as f:
#         f.write(st.secrets["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
#     os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp_creds.json"

# Initialize conversation store
conversation_store = ConversationStore()

def display_chat_message(message, is_assistant=False):
    """Helper function to display chat messages consistently"""
    if is_assistant:
        with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
            st.markdown(message["content"])
    else:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

def save_and_display_response(response, thread_id, db_path, response_time):
    """Helper function to save and display assistant response"""
    # Display assistant response
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        st.markdown(response)
    
    # Add to session state
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Save to conversation store
    conversation_store.save_message(
        thread_id,
        "assistant",
        response,
        db_path,
        metadata={"db_path": db_path, "response_time_seconds": response_time}
    )

# Improved logo and title alignment with public logo URL
st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 2.5rem; margin-bottom: 1.5rem;">
        <div style="background-color: white; padding: 0.75rem; border-radius: 12px; box-shadow: 0 2px 8px #0002;">
            <img src="{OPTIWISE_LOGO}" alt="Optiwise Logo" style="height: 90px; display: block;">
        </div>
        <div>
            <h1 style='margin-bottom:0; color:#FFFFFF; font-size:2.6rem; font-weight:800; letter-spacing:-1px;'>Optiwise Tacos AI Agent</h1>
            <p style='font-size:1.25rem; color:#FFFFFF; margin-top:0.5rem;'>Get deep insights and answers about your <b>Tacos report</b> with our smart AI agent.</p>
        </div>
    </div>
""", unsafe_allow_html=True)

# File uploader
st.markdown("""
    <div style='margin-top: 1.5rem; margin-bottom: 1.2rem;'>
        <b style='color:#FFFFFF;'>Upload your Tacos Excel report:</b>
    </div>
""", unsafe_allow_html=True)
uploaded_file = st.file_uploader("", type=["xlsx"], label_visibility="collapsed")

# Check if a file has been uploaded
if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False

if uploaded_file is not None:
    # Save the uploaded file temporarily
    with open("temp_excel.xlsx", "wb") as f:
        f.write(uploaded_file.getbuffer())

    db_path = "temp_db.sqlite"

    try:
        if st.session_state.file_uploaded == False:
            create_db_from_excel("temp_excel.xlsx", db_path)
            st.success(f"Database created successfully at {db_path}!")
            st.session_state.file_uploaded = True

        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Initialize a new thread_id for a new file upload/session
        if "thread_id" not in st.session_state:
            st.session_state.thread_id = str(uuid.uuid4())
            print(f"Initialized new thread_id for new DB: {st.session_state.thread_id}")
            
            # Save the new conversation
            conversation_store.save_message(
                st.session_state.thread_id,
                "system",
                "Conversation started.",
                db_path
            )

        # Display chat messages from history on app rerun
        for message in st.session_state.messages:
            display_chat_message(message, is_assistant=(message["role"] == "assistant"))

        # Add sidebar with popular questions
        with st.sidebar:
            st.header("Popular Questions")
            
            # Get questions from database using ConversationStore
            popular_questions = conversation_store.get_popular_questions()
            
            # Display questions as buttons
            selected_question = None
            for question in popular_questions:
                if st.button(question, key=question):
                    selected_question = question

        user_input = st.chat_input("Ask anything about your Tacos report:")
        prompt = selected_question or user_input
        
        # React to user input
        if prompt:
            # Display user message in chat message container
            st.chat_message("user").markdown(prompt)
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Save user message to conversation store
            conversation_store.save_message(
                st.session_state.thread_id,
                "user",
                prompt,
                db_path,
                metadata={"db_path": db_path}
            )

            # Get agent response
            try:
                dashboard_start_time = time.time()
                
                # Clear any previous response in shared state
                shared_state.clear_response()
                shared_state.set_capture(True)
                
                # Show animated spinner while Olivia is thinking
                with st.spinner("Olivia is thinking..."):
                    # Create an expander for the streaming response
                    with st.expander("Olivia is thinking... (Click to watch live response generation)", expanded=False):
                        response = st.write_stream(get_agent_response(db_path, prompt, st.session_state.thread_id))
                
                # Get the final captured response from shared state
                final_response = shared_state.get_response()
                
                dashboard_end_time = time.time()
                dashboard_total_time = dashboard_end_time - dashboard_start_time

                print("Final captured response:", final_response)
                
                # Save and display the final captured response
                save_and_display_response(final_response, st.session_state.thread_id, db_path, dashboard_total_time)
                
                # Display timing info in sidebar for debugging
                with st.sidebar:
                    st.write(f"⏱️ Response time: {dashboard_total_time:.2f}s")
                    
            except Exception as e:
                dashboard_end_time = time.time()
                dashboard_total_time = dashboard_end_time - dashboard_start_time
                logging.error(f"Dashboard error after {dashboard_total_time:.2f}s: {e}")
                st.error(f"Error getting response from agent: {e}")

    except Exception as e:
        st.error(f"Error processing Excel file: {e}")
    finally:
        # Clean up temporary files
        if os.path.exists("temp_excel.xlsx"):
            os.remove("temp_excel.xlsx")
            
else:
    st.markdown("""
        <div style='background: #dbeafe; color: #111; padding: 1.2rem 1.5rem; border-radius: 16px; font-size: 1.18rem; font-weight: 500; text-align: left; width: fit-content; min-width: 350px;'>
            Please upload a Tacos Excel report to begin.
        </div>
    """, unsafe_allow_html=True)
    st.session_state.file_uploaded = False