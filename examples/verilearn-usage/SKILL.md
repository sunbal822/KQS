--- 
name: verilearn-usage
description: This skill teaches you how to use the VeriLearn project, an AI-powered viva examination platform. It covers installation, running the application, and key functions for both students and professors.
--- 
# Usage Example and Main Functions

## Overview
VeriLearn is an AI-powered viva examination platform designed to modernize oral assessments. It uses AI to generate questions, evaluate answers, and monitor for cheating. This skill guides you through its core functionalities.

## Installation & Running
1.  Clone the repository: `git clone [repository URL]`
2.  Navigate to the project directory: `cd verilearn`
3.  Install dependencies: `npm install`
4.  Run the development server: `npm run dev`

## Student Functions
*   `Onboarding({ onSubmit })`: Starts the viva session, allowing students to answer questions via voice or keyboard.  Example: `Onboarding({ onSubmit: (answer) => console.log(answer) })`
*   `Splash({ onDone })`: Displays the initial splash screen.
*   `AILoading()`:  Indicates that the AI is generating questions.
*   `ScoreReport({ studentData, result, answers, onRestart })`:  Displays the student's score and evaluation.
*   `VoiceInput({ onTranscript })`:  Captures student responses via voice.

## Professor Functions
*   `FaceEnroll({ username, onEnrolled, onSkip })`:  Enrolls the professor using face recognition.
*   `ProfessorDashboard({ professor, onLogout })`:  Provides a dashboard for managing students and viewing reports.

## Pitfalls
*   Ensure a stable internet connection for AI processing.
*   Verify correct microphone permissions for voice input.
*   Review generated questions for accuracy and relevance.
