import streamlit as st
import pandas as pd
from pathlib import Path
import requests

# Azure OpenAI API details
api_endpoint = "https://infraprototype.openai.azure.com/openai/deployments/Ticketapi/chat/completions?api-version=2024-02-15-preview"
api_key = 'fa7200260a074193b9e1ddac77586e15'

# Columns to be analyzed
columns_to_analyze = [
    "Ticket Id", "Agent", "Requester Name", "Subject", "Type", "Description", "Note By Agents",
    "Created Time"
]

# Function to authenticate user
def authenticate(username, password):
    return username == "admin" and password == "admin@2075"

# Function to clean and structure CSV data
def clean_csv_data(file_path):
    df = pd.read_csv(file_path)
    for column in df.columns:
        df[column] = df[column].astype(str).str.replace('\n', ' ').str.strip()
    # Convert date columns to datetime
    date_columns = ["Created Time"]
    for date_column in date_columns:
        if date_column in df.columns:
            df[date_column] = pd.to_datetime(df[date_column], errors='coerce')
    return df[columns_to_analyze]

# Function to truncate conversation history to stay within token limits
def truncate_history(history, max_tokens=4096):
    truncated_history = history.copy()
    while len(truncated_history) > 0:
        total_tokens = sum([len(msg['content'].split()) for msg in truncated_history])
        if total_tokens <= max_tokens:
            break
        truncated_history.pop(0)
    return truncated_history

# Function to interact with Azure OpenAI using CSV data
def get_openai_response(history, agent_name, df, query):
    try:
        # Truncate conversation history to stay within token limits
        truncated_history = truncate_history(history)

        # Construct conversation history for prompt
        history_prompt = "\n".join([f"{msg['role']}: {msg['content']}" for msg in truncated_history])
        
        # Simplify the data summary to avoid too long prompts
        data_summary = df.head(200).to_string(index=False)  # Limit to the first 200 rows
        
        # Construct prompt with more context and structured data
        prompt = f"""
        You are an AI assistant that provides information based on the ticket database.
        Here are the details of some of the tickets handled by support agent {agent_name}:

        {data_summary}

        Conversation History:
        {history_prompt}

        User Query: {query}

        Please provide a detailed and accurate response based on the data above.
        """
        
        headers = {
            "Content-Type": "application/json",
            "api-key": api_key
        }
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,  # Adjust tokens to ensure the response fits within the limit
            "temperature": 0.7,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "top_p": 0.95,
            "stop": None
        }
        
        response = requests.post(api_endpoint, headers=headers, json=payload)
        
        response.raise_for_status()
        ai_response = response.json()['choices'][0]['message']['content'].strip()
        
        return ai_response

    except requests.exceptions.HTTPError as http_err:
        if response.status_code == 429:
            return "Error: You exceeded your current quota, please check your plan and billing details."
        elif response.status_code == 400:
            error_details = response.json().get('error', {}).get('message', 'Bad Request')
            return f"HTTP error occurred: {http_err}\nDetails: {error_details}"
        else:
            return f"HTTP error occurred: {http_err}"
    except Exception as e:
        return f"Error: {str(e)}"

# Path to your CSV file
csv_file_path = "data/tickets.csv"

# Load and clean CSV file
df = clean_csv_data(csv_file_path)

# Custom CSS for styling
st.markdown(
    """
    <style>
        body {
            background-image: url('https://www.sonata-software.com/sites/default/files/inline-images/home-pg/our-culture-desktop.jpg'); /* Replace with your image URL */
            background-size: cover;
        }
        .stApp {
            background-color: rgba(0, 0, 0, 0.5);
            color: white;
        }
        .login-box {
            background: rgba(255, 255, 255, 0.7);
            padding: 20px;
            border-radius: 10px;
        }
        @keyframes slow-blink {
            0% { opacity: 1; }
            50% { opacity: 0; }
            100% { opacity: 1; }
        }
        .warning-message {
            color: red;
            font-size: 14px;
            margin-top: 10px;
            font-weight: bold;
            text-shadow: 2px 2px 5px black
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Streamlit application
st.title("Altrua AI Assistant")

# Login page
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if not st.session_state['authenticated']:
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if authenticate(username, password):
            st.session_state['authenticated'] = True
            st.success("Logged in successfully")
        else:
            st.error("Invalid username or password")

    # Warning message
    st.markdown(
        """
        <div class="warning-message">
            Unauthorized login attempts will be tracked and are punishable under law. <br> Please go ahead only if you are an authorized user.
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.subheader("Ticket Analysis and AI Query")
    st.write("Interact with the AI Assistant to get details of the tickets handled by support agents.")

    # Initialize conversation history in session state
    if 'conversation_history' not in st.session_state:
        st.session_state['conversation_history'] = []
        st.session_state['first_query_submitted'] = False

    # User query input
    if not st.session_state['first_query_submitted']:
        query = st.text_input("Enter your query", key="user_query_input")

        if st.button("Submit"):
            if query:
                st.session_state['first_query_submitted'] = True
                st.session_state['conversation_history'].append({"role": "user", "content": query})
                response = get_openai_response(st.session_state['conversation_history'], "Agent", df, query)
                st.session_state['conversation_history'].append({"role": "assistant", "content": response})
    else:
        # Display conversation history
        for message in st.session_state['conversation_history']:
            if message['role'] == 'user':
                st.write(f"**You:** {message['content']}")
            else:
                st.write(f"**AI:** {message['content']}")

        # Continuous input for additional queries
        if 'new_query' not in st.session_state:
            st.session_state['new_query'] = ""

        def handle_new_query():
            new_query = st.session_state['new_query']
            if new_query:
                st.session_state['conversation_history'].append({"role": "user", "content": new_query})
                response = get_openai_response(st.session_state['conversation_history'], "Agent", df, new_query)
                st.session_state['conversation_history'].append({"role": "assistant", "content": response})
                st.session_state['new_query'] = ""  # Clear the input box for continuous query

        st.text_input("Your query:", key="new_query", on_change=handle_new_query)

        # Refresh button to clear session state and restart
        if st.button("Refresh"):
            for key in st.session_state.keys():
                del st.session_state[key]
            st.experimental_rerun()
