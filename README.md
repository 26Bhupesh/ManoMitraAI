# ManoMitra AI - Mental Health Support Chatbot

> A comprehensive mental health support system combining advanced emotion detection, crisis intervention, and personalized mental health screening.

## 📋 Project Overview

ManoMitra AI is an intelligent mental health chatbot that leverages:
- **Advanced Emotion Detection**: Multi-modal emotion recognition (text, voice, video)
- **Crisis Intervention**: Real-time crisis detection and emergency support routing
- **Mental Health Screening**: Comprehensive psychological screening assessments
- **Multilingual Support**: Support for English, Hindi, and Marathi
- **Knowledge-Based Support**: Evidence-based resources for anxiety, depression, anger management, and grounding techniques

## 🏗️ Repository Structure

```
ManoMitraAI/
├── backend/                    # FastAPI backend service
│   ├── app/
│   │   ├── main.py            # FastAPI application entry point
│   │   ├── chat_orchestrator.py
│   │   ├── emotion_service.py
│   │   ├── emotion_fusion_service.py
│   │   ├── emotion_voice_service.py
│   │   ├── crisis_service.py
│   │   ├── screening_service.py
│   │   ├── support_service.py
│   │   ├── routing_service.py
│   │   ├── preprocess_service.py
│   │   ├── video_service.py
│   │   ├── session_state.py
│   │   ├── knowledge/          # Knowledge base for mental health topics
│   │   └── requirements.txt
│   ├── models/                 # ML Model weights (ignored in git)
│   ├── .gitignore
│   └── README.md
│
├── frontend/                   # React TypeScript frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/             # Page components
│   │   ├── hooks/             # Custom React hooks
│   │   ├── i18n/              # Internationalization (EN, HI, MR)
│   │   ├── lib/               # Utilities and API client
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/                # Static assets
│   ├── vite.config.ts         # Vite configuration
│   ├── tailwind.config.ts     # Tailwind CSS configuration
│   ├── tsconfig.json
│   ├── package.json
│   ├── .gitignore
│   └── README.md
│
├── .gitignore                 # Unified gitignore for entire repo
└── README.md                  # This file

```

## 🚀 Quick Start

### Prerequisites
- **Backend**: Python 3.8+, pip
- **Frontend**: Node.js 16+, npm/yarn/bun

### Backend Setup

See [backend/README.md](backend/README.md) for detailed setup instructions.

```bash
cd backend
pip install -r app/requirements.txt
python app/main.py
```

Backend will run on `http://localhost:8000`

### Frontend Setup

See [frontend/README.md](frontend/README.md) for detailed setup instructions.

```bash
cd frontend
npm install  # or yarn install / bun install
npm run dev
```

Frontend will run on `http://localhost:5173`

## 🔧 Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Authentication**: Session-based
- **Language Processing**: FastText, IndicTransToolkit, Langdetect
- **Audio Processing**: Librosa, PyDub, Faster-Whisper
- **ML/DL**: PyTorch, Transformers, DeepFace, TensorFlow
- **Web Server**: Uvicorn

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **UI Components**: Radix UI
- **State Management**: TanStack React Query
- **Form Handling**: React Hook Form + Zod
- **Internationalization**: i18next
- **HTTP Client**: Axios

## 📚 Key Features

### Emotion Detection
- Text-based emotion analysis
- Voice emotion recognition
- Facial emotion detection
- Fused multi-modal emotion assessment

### Crisis Management
- Real-time crisis detection
- Immediate intervention protocols
- Emergency contact support
- Crisis resources and hotline information

### Mental Health Screening
- Standardized psychological assessments
- Personalized screening questionnaires
- Result tracking and history
- Professional recommendations

### Multilingual Support
- English (EN)
- Hindi (HI)
- Marathi (MR)
- Knowledge base available in all languages

## 📝 Development

### Code Structure
- **Backend**: Service-oriented architecture with dependency injection
- **Frontend**: Component-based architecture with custom hooks

### Testing
- Backend: Unit tests and integration tests (see backend/README.md)
- Frontend: Component tests and E2E tests (see frontend/README.md)

### Contributing
1. Create a feature branch from `main`
2. Follow the existing code style and patterns
3. Add tests for new functionality
4. Submit a pull request with clear descriptions

## 🔐 Security & Privacy

- Large ML models are not committed to git (see `.gitignore`)
- Environment variables for sensitive data must be configured locally
- Session data is not persisted in git
- User data handling complies with mental health privacy standards

## 🎯 Project Goals

- Provide accessible mental health support through AI
- Detect and respond to mental health crises
- Offer evidence-based psychological resources
- Support users in their preferred language
- Maintain user privacy and data security

## 📖 Documentation

- **Backend API**: See `backend/README.md` for API documentation and setup
- **Frontend**: See `frontend/README.md` for component documentation and setup
- **Endpoint Testing**: See `Endpoint Testing.txt` for API endpoint examples

## 🤝 Support

For questions or issues related to:
- **Backend**: Check backend/README.md or create an issue with the `backend` label
- **Frontend**: Check frontend/README.md or create an issue with the `frontend` label
- **General**: Create an issue with detailed information about your problem

## 📄 License

[Add your license here - e.g., MIT, Apache 2.0, etc.]

## 👥 Authors

ManoMitra AI Team

---

**Note**: This is a unified repository combining both the backend and frontend of the ManoMitra AI project. Large ML model files and Python virtual environments are intentionally excluded from git (see `.gitignore`).
