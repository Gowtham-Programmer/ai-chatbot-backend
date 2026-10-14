
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import uuid
import os
import mysql.connector
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )


def save_conversation(conversation_id: str):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        query = """
            INSERT IGNORE INTO conversations (conversation_id)
            VALUES (%s)
        """
        cursor.execute(query, (conversation_id,))
        connection.commit()

    finally:
        cursor.close()
        connection.close()


# Store chat history separately for each conversation
chat_histories = {}



def save_message(conversation_id: str, role: str, content: str):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        query = """
            INSERT INTO messages (conversation_id, role, content)
            VALUES (%s, %s, %s)
        """
        cursor.execute(
            query,
            (conversation_id, role, content)
        )
        connection.commit()

    finally:
        cursor.close()
        connection.close()


def load_chat_history(conversation_id: str):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        query = """
            SELECT role, content
            FROM messages
            WHERE conversation_id = %s
            ORDER BY id DESC
            LIMIT 10
        """
        cursor.execute(query, (conversation_id,))
        rows = cursor.fetchall()

        # Restore messages in chronological order
        rows.reverse()

        return rows

    finally:
        cursor.close()
        connection.close()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


def generate_response(message: str, conversation_id: str) -> str:
    # Get the existing history for this conversation
    history = load_chat_history(conversation_id)

    # Ensure history starts with a user message
    if history and history[0]["role"] == "assistant":
        history = history[1:]

    # Add the new user message
    messages = history + [
        {"role": "user", "content": message}
    ]

    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "llama3.2:1b",
                "messages": messages,
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()

    except requests.RequestException:
        # Do not save an unsuccessful exchange
        raise

    answer = response.json()["message"]["content"]

    return answer


@app.post("/chat")
def chat(request: ChatRequest):
    message = request.message.strip()

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty"
        )

    # Reuse the supplied ID or create a new conversation
    conversation_id = (
        request.conversation_id or str(uuid.uuid4())
    )

    try:
        save_conversation(conversation_id)

         # Save the user's message in MySQL
        save_message(conversation_id, "user", message)

        answer = generate_response(message, conversation_id)

        # Save the AI's response in MySQL
        save_message(conversation_id, "assistant", answer)



        return {
            "conversation_id": conversation_id,
            "question": message,
            "answer": answer
        }

    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to the local AI model"
        )
