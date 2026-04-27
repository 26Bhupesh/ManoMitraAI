# 🧠 ManoMitra AI - Intelligent Mental Health Support System

<div align="center">

![ManoMitra AI Logo](https://img.shields.io/badge/ManoMitra-AI-blue?style=for-the-badge&logo=robot)
![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python)
![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)
![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=flat-square&logo=typescript)

**A comprehensive AI-powered mental health support platform combining advanced emotion detection, crisis intervention, and personalized psychological screening.**

[🚀 Live Demo](#) • [📖 Documentation](#) • [🛠️ Setup Guide](#setup)

</div>

---

## 📋 Table of Contents

- [🌟 Overview](#-overview)
- [✨ Key Features](#-key-features)
- [🏗️ Architecture](#️-architecture)
- [🛠️ Quick Start](#️-quick-start)
- [📖 User Manual](#-user-manual)
- [🔧 API Documentation](#-api-documentation)
- [🧪 Testing](#-testing)

---

## 🌟 Overview

ManoMitra AI is an intelligent mental health chatbot that provides accessible, evidence-based mental health support through advanced AI technologies. The system combines multiple modalities of emotion detection with comprehensive crisis intervention protocols and personalized mental health screening.

### 🎯 Mission

To provide accessible, stigma-free mental health support through AI, helping users navigate emotional challenges with evidence-based resources, crisis intervention, and professional guidance pathways.

### 🌍 Impact

- **Multilingual Support**: English, Hindi, and Marathi
- **24/7 Availability**: Always accessible support
- **Crisis Detection**: Real-time intervention for acute situations
- **Evidence-Based**: Grounded in psychological research and best practices

---

## ✨ Key Features

### 🧠 Advanced Emotion Detection
- **Text Analysis**: Natural language processing for emotional content
- **Voice Recognition**: Audio emotion detection using machine learning
- **Facial Analysis**: Video-based emotion recognition
- **Multi-modal Fusion**: Combined emotion assessment for accuracy

### 🚨 Crisis Intervention
- **Real-time Detection**: Immediate identification of crisis situations
- **Emergency Protocols**: Automated emergency contact activation
- **Resource Routing**: Connection to professional help services
- **Safety First**: Prioritized user safety and well-being

### 📊 Mental Health Screening
- **Comprehensive Assessments**: Standardized psychological questionnaires
- **Personalized Results**: Tailored recommendations based on responses
- **Progress Tracking**: Historical screening data and trends
- **Professional Referrals**: Guidance for appropriate professional care

### 🌐 Multilingual Support
- **English (EN)**: Complete feature support
- **Hindi (HI)**: Full localization
- **Marathi (MR)**: Complete regional support
- **Cultural Adaptation**: Region-specific mental health resources

### 📚 Knowledge Base
- **Anxiety Management**: Evidence-based coping strategies
- **Depression Support**: Recovery-focused resources
- **Anger Management**: Emotional regulation techniques
- **Stress Reduction**: Mindfulness and relaxation methods
- **Sleep Health**: Sleep hygiene and insomnia support
- **Relationship Issues**: Communication and conflict resolution
- **Academic Stress**: Study-related mental health support
- **Grounding Techniques**: Crisis stabilization methods

---

## 🏗️ Architecture

```
ManoMitraAI/
├── 🖥️ backend/                    # FastAPI Backend Service
│   ├── 🚀 app/
│   │   ├── main.py               # Application Entry Point
│   │   ├── chat_orchestrator.py  # Main Chat Pipeline
│   │   ├── emotion_service.py    # Text Emotion Analysis
│   │   ├── emotion_voice_service.py # Voice Emotion Detection
│   │   ├── emotion_fusion_service.py # Multi-modal Fusion
│   │   ├── crisis_service.py     # Crisis Detection & Response
│   │   ├── screening_service.py  # Mental Health Assessments
│   │   ├── support_service.py    # Knowledge-Based Responses
│   │   ├── routing_service.py    # User Flow Management
│   │   ├── preprocess_service.py # Input Processing
│   │   ├── video_service.py      # Video Analysis
│   │   ├── session_state.py      # Session Management
│   │   └── knowledge/            # Multilingual Knowledge Base
│   │       ├── anxiety_*.txt     # Anxiety Resources
│   │       ├── depression_*.txt  # Depression Support
│   │       ├── stress_*.txt      # Stress Management
│   │       └── ...               # Additional Topics
│   ├── 🤖 models/                # ML Model Storage
│   └── 📦 requirements.txt       # Python Dependencies
│
├── 🎨 frontend/                  # React TypeScript Frontend
│   ├── 📱 src/
│   │   ├── components/           # Reusable UI Components
│   │   ├── pages/                # Application Pages
│   │   ├── hooks/                # Custom React Hooks
│   │   ├── i18n/                 # Internationalization
│   │   ├── lib/                  # Utilities & API Client
│   │   └── App.tsx               # Main Application
│   ├── 🎨 tailwind.config.ts     # Styling Configuration
│   ├── ⚡ vite.config.ts          # Build Configuration
│   └── 📦 package.json           # Node Dependencies
│
└── 📚 documentation/             # Project Documentation
    ├── SETUP.md                  # Detailed Setup Guide
    ├── API.md                    # API Reference
    └── TESTING.md                # Testing Guidelines
```

### 🏛️ System Architecture

```
┌─────────────────┐     ┌─────────────────┐    ┌─────────────────┐
│   User Input    │───▶│  Preprocessing  │───▶│ Emotion Analysis│
│ (Text/Voice/    │     │   Service       │    │   Services      │
│  Video)         │     │                 │    │                 │
└─────────────────┘     └─────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐     ┌─────────────────┐             │
│ Crisis Detection│◀───│  Emotion Fusion │◀────────────┘
│   & Response    │     │   Service       │
└─────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐    ┌─────────────────┐
│ Support Service │───▶│ Chat            │───▶│   User          │
│ (Knowledge Base)│     │ Orchestrator    │    │   Response      │
└─────────────────┘     └─────────────────┘    └─────────────────┘
```

---

## 🛠️ Quick Start

### 📋 Prerequisites

- **Python**: 3.8 or higher (3.10+ recommended)
- **Node.js**: 16+ or **Bun**: Latest version
- **Git**: 2.25 or higher
- **Disk Space**: Minimum 5GB free space

### 🚀 Installation

#### 1. Clone Repository
```bash
git clone https://github.com/26Bhupesh/ManoMitraAI.git
cd ManoMitraAI
```

#### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r app/requirements.txt
```

#### 3. Frontend Setup
```bash
# Navigate to frontend directory
cd ../frontend

# Install dependencies (choose one)
npm install
# or
yarn install
# or
bun install
```

#### 4. Environment Configuration

**Backend Environment Variables:**
```bash
# Copy example file
cp .env.example .env

# Edit .env with your configuration
# Required: API keys, database URLs, etc.
```

**Frontend Environment Variables:**
```bash
# Copy example file
cp .env.example .env.local

# Configure API endpoints and settings
```

#### 5. Start Services

**Terminal 1 - Backend:**
```bash
cd backend
python app/main.py
# API available at: http://localhost:8000
# Documentation at: http://localhost:8000/docs
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
# Application available at: http://localhost:5173
```

### ✅ Verification

1. Open **http://localhost:5173** in your browser
2. Verify backend connection at **http://localhost:8000/docs**
3. Test basic chat functionality

---

## 📖 User Manual

### 👤 Getting Started

1. **Language Selection**: Choose your preferred language (EN/HI/MR)
2. **Initial Assessment**: Complete the mental health screening questionnaire
3. **Profile Setup**: Configure your support preferences

### 💬 Using the Chat System

#### Text Chat
- Type your message in the chat input
- The system analyzes your emotional state
- Receives personalized support responses
- Access knowledge base resources

#### Voice Chat
- Click the microphone button
- Speak your message clearly
- System analyzes voice emotion
- Receives audio-guided responses

#### Video Chat (Optional)
- Enable camera permissions
- System analyzes facial expressions
- Enhanced emotion detection
- Visual support interface

### 🚨 Crisis Situations

If the system detects a crisis:
- **Immediate Response**: System provides crisis stabilization
- **Emergency Contacts**: Automatic display of emergency numbers
- **Professional Help**: Guidance to seek immediate professional care
- **Safety Resources**: Access to crisis hotlines and support services

### 📊 Mental Health Screening

#### Available Assessments
- **General Mental Health**: Comprehensive psychological evaluation
- **Anxiety Screening**: GAD-7 assessment
- **Depression Screening**: PHQ-9 assessment
- **Stress Assessment**: PSS-10 evaluation

#### Taking a Screening
1. Navigate to "Screening" section
2. Select appropriate assessment
3. Answer questions honestly
4. Review personalized results
5. Access recommended resources

### 🌍 Language Support

#### English (EN)
- Full feature support
- Complete knowledge base
- All assessments available

#### Hindi (HI)
- Complete localization
- Hindi knowledge resources
- Culturally adapted content

#### Marathi (MR)
- Regional language support
- Marathi mental health resources
- Local cultural context

### ⚙️ Settings & Preferences

- **Language Settings**: Change interface language
- **Notification Preferences**: Configure alert settings
- **Privacy Settings**: Manage data sharing preferences
- **Session Management**: View chat history and sessions

### 📞 Emergency Resources

#### India Emergency Contacts
- **Emergency**: 112
- **Police**: 100
- **Medical Emergency**: 108
- **Mental Health Helpline**: 1800-121-4567

#### International Resources
- **Befrienders Worldwide**: Local suicide prevention
- **Mental Health America**: 1-800-950-NAMI
- **Crisis Text Line**: Text HOME to 741741 (US)

---

## 🔧 API Documentation

### 📡 Core Endpoints

#### Chat System
```
POST /chat/message          # Main chat endpoint
POST /chat/voice           # Voice message processing
POST /chat/video           # Video analysis
```

#### Emotion Analysis
```
POST /emotion/text         # Text emotion detection
POST /emotion/voice        # Voice emotion analysis
POST /emotion/fusion       # Multi-modal emotion fusion
```

#### Mental Health Services
```
POST /screening/assess     # Mental health screening
GET  /support/resources    # Knowledge base access
POST /crisis/detect        # Crisis detection
```

#### Session Management
```
POST /session/create       # Create new session
GET  /session/{id}         # Get session data
POST /session/update       # Update session state
```

### 📚 API Documentation Access

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 🔐 Authentication

Session-based authentication with secure token management.

---

## 🧪 Testing

### Backend Testing
```bash
cd backend
python -m pytest tests/
```

### Frontend Testing
```bash
cd frontend
npm run test
```

### End-to-End Testing
```bash
# Integration tests
npm run test:e2e
```

### API Testing
See `backend/Endpoint Testing.txt` for comprehensive API test examples.

---

<div align="center">

[⬆️ Back to Top](#-manoMitra-ai---intelligent-mental-health-support-system)

</div>
