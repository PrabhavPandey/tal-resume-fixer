# 🦊 Tal - Resume Fixer

A Streamlit chat app that simulates a conversation with **Tal**, a chonky fox career saarthi who transforms your resume into an ATS-optimized, job-tailored masterpiece.

## What it does

1. **Upload your resume** (PDF) - Tal reads and analyzes it
2. **Paste the job description** - Tal researches the company and role
3. **Get expert analysis** - Tal tells you what's good, what's missing from the JD, and what he'll fix
4. **Download your new resume** - ATS-compliant PDF with bold metrics, preserved links, tailored to the JD

## Features

- **JD-specific analysis** - identifies missing keywords and gaps against the job description
- **Company research** - understands what works for that specific company/role
- **ATS-optimized output** - uses Jake's Resume LaTeX template (proven to pass ATS)
- **Bold metrics** - key achievements highlighted to catch recruiter's eye
- **Preserves project links** - Video, Website, GitHub links stay intact
- **Page limit matching** - 1-page input → 1-page output

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/tal-resume-fixer.git
cd tal-resume-fixer
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your Gemini API key

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` and add your [Gemini API key](https://aistudio.google.com/app/apikey):

```toml
GEMINI_API_KEY = "your-actual-api-key"
```

### 4. Run the app

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Tech Stack

- **Streamlit** - Chat UI
- **Google Gemini 3 Pro** - Resume analysis and LaTeX generation
- **LaTeX** - Resume formatting (compiled via latex.ytotech.com API)
- **PyPDF2** - PDF text extraction

## Tal's Personality

Tal is a career saarthi built by Grapevine in Bangalore. He's:
- Brutally honest about corporate BS
- Short, punchy, lowercase
- An expert who's reviewed lakhs of resumes
- Your ally in getting that dream job

---

Built with 🦊 energy
