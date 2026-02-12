"""
Tal Resume Fixer - The Rewrite
Clean architecture, robust parsing, and a chonky fox persona.
"""

import streamlit as st
from google import genai
from google.genai import types
from PyPDF2 import PdfReader
import requests
import base64
import os
import json
import re
import time
from typing import Optional, List, Dict, Tuple
from pydantic import BaseModel

try:
    from streamlit_pdf_viewer import pdf_viewer
except ImportError:
    pdf_viewer = None

# ─────────────────────────────────────────────────────────────
# CONFIGURATION & CSS
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Tal - Resume Fixer",
    page_icon="🦊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* Main container spacing */
    .block-container {
        padding-top: 3rem;
        max-width: 800px;
    }
    
    /* Header fix - hide default, style custom */
    header[data-testid="stHeader"] {
        background: transparent;
    }
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        text-align: center;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        background: -webkit-linear-gradient(45deg, #ff6b35, #f7c948);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .subtitle {
        text-align: center;
        color: #888;
        font-size: 1rem;
        margin-bottom: 2rem;
    }

    /* Chat message styling */
    div[data-testid="stChatMessage"] {
        background-color: transparent;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.5rem;
    }
    div[data-testid="stChatMessage"] p {
        font-size: 1.05rem;
        line-height: 1.6;
    }

    /* Buttons */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
    }
    
    /* Analysis bullets */
    .analysis-point {
        margin-bottom: 0.8rem;
        display: block;
    }
    
    /* Hide branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# CONSTANTS & TEMPLATES
# ─────────────────────────────────────────────────────────────

MODEL_NAME = "gemini-3-pro-preview"
TAL_AVATAR = "assets/tal_avatar.png" if os.path.exists("assets/tal_avatar.png") else "🦊"
USER_AVATAR = "assets/user_avatar.png" if os.path.exists("assets/user_avatar.png") else "👤"

TAL_SYSTEM_PROMPT = """You are Tal, a "chonky fox" and career saarthi (guide).
Voice:
- Lowercase, casual, direct, punchy.
- Brutally honest but supportive.
- Like a smart friend texting you.
- NO marketing fluff. NO "happy to help". NO generic bot responses.
- Use line breaks for pacing.
- Hate corporate jargon ("synergy", "rockstar").
- Love clear, quantified achievements.
"""

LATEX_TEMPLATE = r"""% Jake's Resume Template - ATS Optimized
\documentclass[letterpaper,11pt]{article}
\usepackage{latexsym}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage{marvosym}
\usepackage[usenames,dvipsnames]{color}
\usepackage{verbatim}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage{fontawesome5}
\usepackage{multicol}
\setlength{\multicolsep}{-3.0pt}
\setlength{\columnsep}{-1pt}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.6in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1.19in}
\addtolength{\topmargin}{-.7in}
\addtolength{\textheight}{1.4in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large\bfseries
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

\pdfgentounicode=1

\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{1.0\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & \textbf{\small #2} \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{1.0\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & \textbf{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.0in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

\begin{document}

% HEADER
\begin{center}
    {\Huge \scshape FULL_NAME} \\ \vspace{1pt}
    CONTACT_INFO
\end{center}

% EDUCATION
\section{Education}
  \resumeSubHeadingListStart
    EDUCATION_CONTENT
  \resumeSubHeadingListEnd

% EXPERIENCE
\section{Experience}
  \resumeSubHeadingListStart
    EXPERIENCE_CONTENT
  \resumeSubHeadingListEnd

% PROJECTS
\section{Projects}
    \resumeSubHeadingListStart
      PROJECTS_CONTENT
    \resumeSubHeadingListEnd

% SKILLS
\section{Technical Skills}
 \begin{itemize}[leftmargin=0.15in, label={}]
    \small{\item{
     SKILLS_CONTENT
    }}
 \end{itemize}

\end{document}
"""

# ─────────────────────────────────────────────────────────────
# CORE LOGIC
# ─────────────────────────────────────────────────────────────

class TalAgent:
    def __init__(self):
        try:
            self.client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
        except Exception:
            st.error("Missing GEMINI_API_KEY in secrets.toml")
            st.stop()

    def chat(self, user_msg: str, context: str = "") -> str:
        """Get a simple chat response from Tal."""
        prompt = f"{TAL_SYSTEM_PROMPT}\n\nContext: {context}\nUser: {user_msg}\nTal:"
        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                max_output_tokens=300,
            )
        )
        return response.text.lower() # Tal speaks lowercase

    def extract_pdf_text(self, file) -> tuple[str, int]:
        """Extract text and page count from PDF."""
        try:
            reader = PdfReader(file)
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
            return text.strip(), len(reader.pages)
        except Exception as e:
            return f"Error reading PDF: {e}", 0

    def analyze_resume(self, resume_text: str, jd_text: str) -> dict:
        """
        Perform deep analysis of resume vs JD.
        Returns structured JSON.
        """
        prompt = f"""
        You are an expert ATS resume analyst.
        
        Analyze this resume against the job description.
        
        RESUME:
        {resume_text[:10000]}
        
        JOB DESCRIPTION:
        {jd_text[:5000]}
        
        Return a JSON object with this EXACT schema:
        {{
            "company_name": "extracted company name (or 'this company')",
            "role_title": "extracted job title (or 'this role')",
            "missing_keywords": ["list", "of", "critical", "missing", "keywords"],
            "good_points": [
                {{"point": "strength description", "why": "why it matters"}}
            ],
            "needs_fixing": [
                {{"issue": "weakness description", "impact": "negative consequence"}}
            ],
            "proposed_changes": [
                {{"change": "what you will change", "rationale": "why this helps"}}
            ],
            "score_before": 50,
            "score_after": 85
        }}
        """
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                )
            )
            return json.loads(response.text)
        except Exception as e:
            st.error(f"Analysis failed: {e}")
            # Robust Fallback
            return {
                "company_name": "the company",
                "role_title": "the role",
                "missing_keywords": ["key skills", "quantifiable metrics"],
                "good_points": [{"point": "Experience listed", "why": "shows history"}],
                "needs_fixing": [{"issue": "Generic descriptions", "impact": "low engagement"}],
                "proposed_changes": [{"change": "Quantify impact", "rationale": "prove value"}],
                "score_before": 50,
                "score_after": 80
            }

    def generate_latex_content(self, resume_text: str, jd_text: str, analysis: dict, max_pages: int = 1) -> str:
        """Generate the full LaTeX code for the resume."""
        
        company = analysis.get("company_name", "the company")
        role = analysis.get("role_title", "the role")
        
        prompt = f"""
        You are an expert Resume Writer using LaTeX.
        
        TASK: Rewrite this resume for the {role} role at {company}.
        
        CONSTRAINTS:
        1. Output ONLY valid LaTeX code starting with \\documentclass.
        2. STRICTLY fit content to {max_pages} page(s). Be concise.
        3. Use Jake's Resume Template structure (provided below).
        4. Use \\textbf{{}} to bold KEY METRICS (e.g., \\textbf{{20% growth}}).
        5. PRESERVE ALL LINKS (GitHub, LinkedIn, Projects) using \\href{{url}}{{text}}.
        6. Use action verbs and include JD keywords naturally.
        7. Escape LaTeX special chars (%, $, &, #, _) properly (\\%, \\$, etc).
        
        TEMPLATE TO USE:
        {LATEX_TEMPLATE}
        
        RESUME CONTENT:
        {resume_text}
        
        TARGET JD:
        {jd_text}
        
        Generate the complete LaTeX document now.
        """
        
        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                # Not using JSON mode here, we want raw text (LaTeX)
            )
        )
        
        # Clean up code fences
        latex = response.text
        latex = re.sub(r"^```(?:latex|tex)?\s*\n", "", latex, flags=re.MULTILINE)
        latex = re.sub(r"\n```\s*$", "", latex, flags=re.MULTILINE)
        return latex.strip()

    def compile_pdf(self, latex_content: str) -> tuple[bytes, str]:
        """Try to compile LaTeX to PDF using external services."""
        
        # 1. Try latex.ytotech.com (Most robust for standard templates)
        try:
            resp = requests.post(
                "https://latex.ytotech.com/builds/sync",
                json={"compiler": "pdflatex", "resources": [{"main": True, "content": latex_content}]},
                timeout=30
            )
            if resp.status_code in (200, 201):
                return resp.content, None
        except:
            pass
            
        # 2. Try latexonline.cc
        try:
            import urllib.parse
            encoded = urllib.parse.quote(latex_content)
            # Check length to avoid 414
            if len(encoded) < 8000:
                url = f"https://latexonline.cc/compile?text={encoded}"
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200:
                    return resp.content, None
        except:
            pass
            
        return None, "Compilation failed. Please download the .tex file and use Overleaf."

# ─────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────

def render_chat_message(role, content, avatar=None):
    with st.chat_message(role, avatar=avatar):
        if role == "assistant":
            # Tal's specific formatting
            st.markdown(content) # Use markdown for the analysis structure
        else:
            st.write(content)

def format_analysis_display(analysis: dict) -> str:
    """Format analysis with bullets and new lines as requested."""
    
    company = analysis.get("company_name", "the company")
    role = analysis.get("role_title", "this role")
    
    # Fix "role role" redundancy
    if role.lower().endswith(" role") or role.lower() == "this role":
        role_str = role
    else:
        role_str = f"{role} role"
        
    lines = []
    lines.append(f"alright i've analyzed your resume for the **{role_str}** at **{company}**\n\n")
    
    # Missing Keywords
    missing = analysis.get("missing_keywords", [])
    if missing:
        lines.append(f"**missing keywords:** {', '.join(missing).lower()}\n\n")
    
    # Good Points
    lines.append("**what's working:**")
    for item in analysis.get("good_points", [])[:3]:
        lines.append(f"- {item.get('point', '').lower()}")
        if item.get('why'):
            lines.append(f"  *({item.get('why', '').lower()})*")
    lines.append("") # Spacer
    
    # Fixes
    lines.append("**what needs fixing:**")
    for item in analysis.get("needs_fixing", [])[:3]:
        lines.append(f"- {item.get('issue', '').lower()}")
        if item.get('impact'):
            lines.append(f"  *(impact: {item.get('impact', '').lower()})*")
    lines.append("") # Spacer
    
    # Changes
    lines.append("**what i'm gonna change:**")
    for item in analysis.get("proposed_changes", [])[:4]:
        lines.append(f"- {item.get('change', '').lower()}")
        if item.get('rationale'):
            lines.append(f"  *(why: {item.get('rationale', '').lower()})*")
    lines.append("") # Spacer
    
    lines.append(f"**score jump:** {analysis.get('score_before')} → {analysis.get('score_after')}")
    lines.append("\nlet me cook")
    
    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────
# MAIN APP LOOP
# ─────────────────────────────────────────────────────────────

def main():
    # Session State Init
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.step = "upload" # upload -> jd -> processing -> done
        st.session_state.resume_text = ""
        st.session_state.resume_pages = 1
        st.session_state.jd_text = ""
        
        # Opening Line
        st.session_state.messages.append({
            "role": "assistant",
            "content": "yo. i'm tal.\n\ndrop your resume pdf below. let's fix it."
        })

    # Header
    st.markdown('<div class="main-title">🦊 tal - resume fixer</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">ats-optimized. recruiter-approved. no fluff.</div>', unsafe_allow_html=True)

    # Agent Init
    agent = TalAgent()

    # Chat History
    for msg in st.session_state.messages:
        avatar = TAL_AVATAR if msg["role"] == "assistant" else USER_AVATAR
        render_chat_message(msg["role"], msg["content"], avatar)

    # ─── STEP 1: UPLOAD ───
    if st.session_state.step == "upload":
        uploaded = st.file_uploader("upload resume (pdf)", type="pdf", label_visibility="collapsed")
        if uploaded:
            with st.spinner("reading..."):
                text, pages = agent.extract_pdf_text(uploaded)
                if len(text) > 50:
                    st.session_state.resume_text = text
                    st.session_state.resume_pages = pages
                    
                    # User msg
                    st.session_state.messages.append({"role": "user", "content": f"Uploaded {uploaded.name} ({pages} pages)"})
                    
                    # Tal response
                    ack = agent.chat("I just uploaded my resume.", context=f"Resume length: {len(text)} chars. Pages: {pages}")
                    st.session_state.messages.append({"role": "assistant", "content": f"{ack}\n\npaste the jd now."})
                    
                    st.session_state.step = "jd"
                    st.rerun()
                else:
                    st.error("Could not read text from PDF. Is it an image scan?")

    # ─── STEP 2: JD INPUT ───
    elif st.session_state.step == "jd":
        with st.form("jd_form"):
            jd = st.text_area("paste job description", height=200, placeholder="paste the full JD here...")
            submitted = st.form_submit_button("fix my resume →")
            
            if submitted and len(jd) > 50:
                st.session_state.jd_text = jd
                st.session_state.messages.append({"role": "user", "content": "Here is the JD."})
                st.session_state.messages.append({"role": "assistant", "content": "bet. analyzing now..."})
                st.session_state.step = "processing"
                st.rerun()

    # ─── STEP 3: PROCESSING ───
    elif st.session_state.step == "processing":
        with st.status("🦊 tal is working...", expanded=True) as status:
            
            # 1. Analyze
            st.write("analyzing match...")
            analysis = agent.analyze_resume(st.session_state.resume_text, st.session_state.jd_text)
            
            # Show analysis
            analysis_msg = format_analysis_display(analysis)
            st.session_state.messages.append({"role": "assistant", "content": analysis_msg})
            
            # 2. Generate LaTeX
            st.write("rewriting content...")
            latex = agent.generate_latex_content(
                st.session_state.resume_text, 
                st.session_state.jd_text, 
                analysis,
                max_pages=st.session_state.resume_pages
            )
            st.session_state.latex_content = latex
            
            # 3. Compile
            st.write("compiling pdf...")
            pdf_bytes, error = agent.compile_pdf(latex)
            st.session_state.pdf_bytes = pdf_bytes
            st.session_state.compile_error = error
            
            status.update(label="done!", state="complete")
            st.session_state.step = "done"
            st.rerun()

    # ─── STEP 4: RESULT ───
    elif st.session_state.step == "done":
        st.divider()
        
        # Display PDF
        if st.session_state.pdf_bytes:
            if pdf_viewer:
                pdf_viewer(input=st.session_state.pdf_bytes, width=700)
            else:
                st.info("Preview unavailable (library missing). Download below.")
                
            # Buttons
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📥 Download PDF",
                    data=st.session_state.pdf_bytes,
                    file_name="Tal_Resume.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary"
                )
            with col2:
                st.download_button(
                    "📄 Download .tex",
                    data=st.session_state.latex_content,
                    file_name="Tal_Resume.tex",
                    mime="text/plain",
                    use_container_width=True
                )
        else:
            st.error("PDF Compilation Failed. But I generated the code!")
            if st.session_state.compile_error:
                with st.expander("Error Details"):
                    st.write(st.session_state.compile_error)
            
            st.download_button(
                "📄 Download .tex source (Use Overleaf)",
                data=st.session_state.latex_content,
                file_name="Tal_Resume.tex",
                mime="text/plain",
                use_container_width=True
            )
            
        if st.button("🔄 Start Over"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
