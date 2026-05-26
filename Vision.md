### **Project: "Hermes" - Local-First AI Knowledge Agent**

### 1. Concept & Vision

**Concept:** Hermes is a personal AI assistant that leverages the power of modern Large Language Models (LLMs) to interact with a user's private, local knowledge base. It operates on a "privacy-first" principle, ensuring that sensitive documents and data never leave the user's local machine.

**Vision:** To provide any user with a PC the ability to create a powerful, extensible AI agent that can reason, research, and perform tasks by securely combining their personal data with the capabilities of cloud-based LLMs. The system will be designed as a platform, allowing for the future addition of new "tools" and skills (e.g., web search, file system interaction, API calls).

This MVP will prove the core architecture by creating a web-based chat interface where a user can "talk" to a single document (e.g., a PDF book) stored on their computer.

### 2. Core Use Cases (MVP)

*   **Data Ingestion:** The user can "ingest" a single PDF document. The system will process and index this document into a local vector database.
*   **Question Answering:** The user can ask questions in natural language about the content of the ingested document through a web chat interface.
*   **Conversational Memory:** The system will remember the immediate context of the conversation, allowing for follow-up questions.
*   **Tool-Ready Architecture:** The backend will be built as an "agent" from the start, with the RAG search being its first "tool," making future extensions straightforward.

### 3. System Requirements

#### **Functional Requirements (FR)**

*   **FR1:** The system must provide a web-based user interface with a chat window and an input field.
*   **FR2:** The system must provide a mechanism to trigger the one-time ingestion of a specified local PDF file.
*   **FR3:** The backend must receive user messages from the frontend.
*   **FR4:** The backend agent must use its RAG tool to search the local vector database for information relevant to the user's message.
*   **FR5:** The backend agent must make an API call to a cloud-based LLM, sending the user's question and the retrieved context.
*   **FR6:** The frontend must display the AI's response in the chat window.

#### **Non-Functional Requirements (NFR)**

*   **NFR1 (Privacy):** The original source document and the generated vector database must never be transmitted outside the user's local machine.
*   **NFR2 (Performance):** The system should return a response to a user's query in a reasonable amount of time (target: < 10 seconds for the MVP).
*   **NFR3 (Usability):** The user interface should be clean, simple, and intuitive.
*   **NFR4 (Modularity):** The backend architecture must be modular, clearly separating the API layer, agent logic, and tool definitions.

#### **Technical Stack (MVP)**

*   **Frontend:** **Next.js** (TypeScript)
*   **Backend:** **Python**
*   **Backend Framework:** **FastAPI**
*   **AI/Agent Framework:** **LangChain**
*   **Vector Database:** **ChromaDB**
*   **Cloud LLM Provider:** **Google AI (Gemini Pro)** or **OpenAI (GPT-4)** via API

### 4. System Architecture

The system follows a classic decoupled frontend-backend architecture. All components will run on the user's local machine.

```
+-------------------------------------------------------------------------+
| User's Local Machine                                                    |
|                                                                         |
|  +-----------------+      (1) HTTP API Calls      +-------------------+  |
|  |   Frontend      | <--------------------------> |   Backend Server  |  |
|  |  (Next.js App)  |                              |  (FastAPI App)    |  |
|  |  (Browser)      |                              +---------+---------+  |
|  +-----------------+                                        |            |
|                                                               | (2) Python Calls
|                                                               v            |
|                                                     +-------------------+  |
|                                                     |  LangChain Agent  |  |
|                                                     |   (The "Brain")   |  |
|                                                     +---------+---------+  |
|                                                               |            |
|       +-------------------------------------------------------+--------+   |
|       | (3) Tool Execution                                             |   |
|       v                                                                v   |
|  +-----------------+      (4) DB Query      +--------------------+   +---------+---------+
|  | RAG Search Tool | ---------------------> |   Vector Database  |   | (Future Tool #2)  |
|  | (Python Func)   |                        | (ChromaDB)         |   +-------------------+
|  +-----------------+                        +--------------------+
|                                                                          |
+-------------------------------------------------------------------------+
       ^                                                                   | (5) External API Call
       |                                                                   v
+------+-------------------------------------------------------------------+------+
| Internet                                                                         |
|                                                                                  |
|                                                                       +----------+----------+
|                                                                       | Cloud LLM Service |
|                                                                       | (e.g., Google AI)   |
|                                                                       +-------------------+
```

#### **Component Breakdown:**

1.  **Frontend (Next.js):**
    *   **Responsibility:** Render the chat UI, manage UI state, and communicate with the backend server.
    *   **Implementation:** A standard Next.js application. It will have a main page for the chat and will use `fetch` or a library like `axios` to make API calls to the Python backend.

2.  **Backend Server (FastAPI):**
    *   **Responsibility:** Expose API endpoints for the frontend (e.g., `/api/chat`), receive requests, pass them to the LangChain agent, and return the agent's final response.
    *   **Implementation:** A lightweight FastAPI server. It will handle the web communication and act as the host for the agent.

3.  **LangChain Agent (Python):**
    *   **Responsibility:** The core logic. It orchestrates the entire process of answering a query.
    *   **Implementation:** Built using LangChain's Agent Executor. For the MVP, it will be configured with one primary tool: `local_knowledge_search`.

4.  **Tools (Python Functions):**
    *   **Responsibility:** A collection of functions decorated as LangChain "Tools."
    *   **`local_knowledge_search` (MVP):** This function will take a query string, use it to search the ChromaDB vector store, and return the most relevant document chunks.

5.  **Services:**
    *   **Vector Database (ChromaDB):** Runs as a persistent local service (or in-memory for simplicity). It stores the embeddings of the user's document.
    *   **Cloud LLM (API):** An external service that the agent calls for reasoning and final text generation.

### 5. Data & Logic Flow (User Asks a Question)

1.  **UI Interaction:** The user types "How do I prepare tomatoes for canning?" into the Next.js chat input and hits Enter.
2.  **Frontend Request:** The Next.js app makes a `POST` request to `http://localhost:8000/api/chat` with the JSON body: `{"question": "How do I prepare tomatoes for canning?"}`.
3.  **Backend Receives:** The FastAPI server receives the request and passes the question to the LangChain Agent Executor.
4.  **Agent Reasoning:** The agent (via the LLM) receives the prompt and the list of available tools. It determines that the `local_knowledge_search` tool is appropriate.
5.  **Tool Execution:** The agent calls the `local_knowledge_search` function with the query.
6.  **Vector Search:** The tool function connects to ChromaDB, searches for the most relevant chunks related to "tomatoes canning preparation," and gets back raw text snippets from the original book.
7.  **Observation:** The tool returns these text snippets to the agent as an "observation."
8.  **Final Generation:** The agent makes a final call to the LLM. The prompt now includes the original question *and* the context retrieved from the book.
9.  **LLM Responds:** The LLM generates a coherent answer based on the provided context and sends it back.
10. **Backend Responds:** The FastAPI server sends a `200 OK` response to the frontend with the JSON body: `{"answer": "To prepare tomatoes for canning, you should first wash them thoroughly, then blanch them in boiling water for 30-60 seconds..."}`.
11. **UI Update:** The Next.js app receives the response and displays the answer in the chat window.

### 6. MVP Implementation Plan (High-Level)

1.  **Phase 0: Setup**
    *   Initialize a Python project with `pip` and a `virtualenv`.
    *   Initialize a Next.js project with `npx create-next-app`.
    *   Acquire API keys for the chosen cloud LLM provider.

2.  **Phase 1: Backend - The Core Logic**
    *   Build the data ingestion script to process a PDF, create embeddings, and save them to ChromaDB.
    *   Create the `local_knowledge_search` tool function.
    *   Build the LangChain agent and configure it to use the tool and the cloud LLM.
    *   Wrap the agent in a FastAPI server with a single `/api/chat` endpoint. Test using API tools like Postman or `curl`.

3.  **Phase 2: Frontend - The User Interface**
    *   Build a simple chat component in React (Next.js).
    *   Implement the state management for the conversation history.
    *   Write the function to call the backend API and display the streaming or complete response.

4.  **Phase 3: Integration & Testing**
    *   Run both the backend and frontend servers simultaneously.
    *   Perform end-to-end testing by asking questions through the UI.
    *   Package the application with clear instructions on how to run it.
