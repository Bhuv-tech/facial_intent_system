# 😊 AI-Powered Facial Intent Recognition & Behavioral Analysis Platform

🔗 **Live Demo:** *(Add deployment URL if available)*

🛠 **Built by:** @Bhuv-tech

---

# 📖 What It Does

AI-Powered Facial Intent Recognition & Behavioral Analysis Platform is a full-stack intelligent web application that combines Computer Vision, Deep Learning, and Behavioral Analytics to recognize facial emotions, infer user intent, and generate context-aware risk assessments in real time.

The system integrates a React-based frontend with a FastAPI backend and AI inference engine to provide an interactive and scalable platform for emotion analysis across multiple domains, including education, healthcare, recruitment, and workplace assessment.

The application enables users to:

* Detect facial expressions from images or webcam input
* Recognize emotions using AI models
* Perform context-aware behavioral analysis
* Generate intelligent risk assessments
* Produce downloadable reports
* Support multiple user roles through dedicated dashboards
* Run locally or using Docker containers

---

# 📌 Key Features

* 😊 Real-Time Facial Emotion Detection
* 🧠 AI-Based Intent Recognition
* 📊 Context-Aware Behavioral Analysis
* ⚠️ Intelligent Risk Assessment Engine
* 🌐 Interactive React Frontend
* ⚡ FastAPI REST APIs
* 🔄 Real-Time WebSocket Communication
* 📄 Automated DOCX Report Generation
* 🔐 Authentication & Session Management
* 🐳 Dockerized Deployment
* 🎭 Multi-Role Dashboard Support (HR, Teacher, Doctor, Student & Candidate)

---

# 🛠 Technologies Used

### Programming Languages

* Python
* JavaScript

### Frontend

* React
* Vite
* HTML
* CSS

### Backend

* FastAPI
* WebSockets

### Artificial Intelligence

* TensorFlow
* OpenCV
* MediaPipe
* NumPy
* Pandas

### Deployment

* Docker
* Docker Compose

### Utilities

* python-docx
* Git
* GitHub

---

# 🏗 System Architecture

```text
                 React + Vite Frontend
                          │
                          ▼
                 FastAPI Backend Server
                          │
        ┌─────────────────┼──────────────────┐
        │                 │                  │
        ▼                 ▼                  ▼
 Authentication    WebSocket Server    REST APIs
        │
        ▼
Behavior Analysis Engine
        │
        ├── Emotion Detection
        ├── Intent Recognition
        ├── Context Analysis
        ├── Risk Assessment
        ├── Session Logging
        └── Report Generation
                │
                ▼
TensorFlow + OpenCV + MediaPipe
```

---

# ⚙️ Workflow

```text
User Uploads Image / Webcam
            │
            ▼
      Face Detection
            │
            ▼
 Emotion Recognition Model
            │
            ▼
 Intent & Context Analysis
            │
            ▼
 Behavioral Risk Assessment
            │
            ▼
 Prediction & Visualization
            │
            ▼
 Report Generation
```

---

# 📸 Screenshots

*(Add screenshots here)*

* Home Page
* Login Page
* Dashboard
* Image Upload Interface
* Real-Time Emotion Detection
* Prediction Results
* Risk Analysis
* Generated Report

---

# 📂 Project Structure

```text
Facial-Intent-Recognition-System/
├── backend/                    # FastAPI backend, AI inference & business logic
├── frontend/                   # React + Vite frontend
├── legacy/                     # Legacy implementation files
├── scratch/                    # Experimental development files
├── .env                        # Environment variables
├── .gitignore                  # Git ignored files
├── Dockerfile                  # Docker image configuration
├── docker-compose.yml          # Multi-container deployment
├── generate_docx.py            # DOCX report generation
├── models.json                 # Model configuration
├── requirements.txt            # Python dependencies
├── run.bat                     # Run locally
├── run_docker.bat              # Run using Docker
├── run_instructions.txt        # Setup instructions
└── README.md                   # Project documentation
```

---

# 🚀 Installation

## Clone the Repository

```bash
git clone https://github.com/Bhuv-tech/facial_intent_system.git
cd facial_intent_system
```

## Install Backend Dependencies

```bash
pip install -r requirements.txt
```

## Install Frontend Dependencies

```bash
cd frontend
npm install
```

---

# ▶️ Running the Application

## Backend

```bash
uvicorn backend.api:app --reload
```

## Frontend

```bash
cd frontend
npm run dev
```

---

# 🐳 Docker Deployment

```bash
docker-compose up --build
```

---

# 🚀 Future Enhancements

* Live Multi-Face Detection
* Voice Emotion Recognition
* Cloud Deployment
* Advanced AI Explainability
* User Activity Analytics
* Mobile Application Support
* Model Performance Dashboard
* Continuous Learning Pipeline

---

# 👨‍💻 Author

**Bhuvaneshwari M**

GitHub: https://github.com/Bhuv-tech

LinkedIn: https://linkedin.com/in/bhuvaneshwari-mohan-5b780034a

Portfolio: https://bhuvanaportfolio-one.vercel.app/
