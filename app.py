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
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}
\usepackage{fontawesome5}
\usepackage{multicol}
\setlength{\multicolsep}{-3.0pt}
\setlength{\columnsep}{-1pt}
\usepackage[hidelinks]{hyperref}

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

    def chat(self, user_msg: str) -> str:
        """Get a simple chat response from Tal."""
        prompt = f"{TAL_SYSTEM_PROMPT}\nUser: {user_msg}\nTal:"
        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                max_output_tokens=300,
            )
        )
        return response.text.lower() # Tal speaks lowercase

    def extract_pdf_data(self, file) -> dict:
        """Extract text, page count, and hyperlinks from PDF."""
        try:
            file.seek(0) # Reset pointer
            reader = PdfReader(file)
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
            pages = len(reader.pages)
            
            # Extract Metadata Links (Annotations)
            links = []
            for page in reader.pages:
                if "/Annots" in page:
                    for annot in page["/Annots"]:
                        try:
                            obj = annot.get_object()
                            if "/A" in obj and "/URI" in obj["/A"]:
                                uri = obj["/A"]["/URI"]
                                links.append(uri)
                        except:
                            continue
            
            # Extract Text Links (Regex Fallback)
            # Remove parentheses/trailing punctuation often caught by regex
            raw_links = re.findall(r'(https?://[^\s\)\}\],]+)', text)
            # Add https prefix to shorthand links if missing
            raw_links += [f"https://{l}" if not l.startswith("http") else l for l in re.findall(r'(?:github\.com/[^\s\)\}\],]+)', text)]
            raw_links += [f"https://{l}" if not l.startswith("http") else l for l in re.findall(r'(?:linkedin\.com/in/[^\s\)\}\],]+)', text)]
            
            all_links = sorted(list(set(links + raw_links)))
            
            return {
                "text": text.strip(),
                "pages": pages,
                "links": all_links
            }
        except Exception as e:
            st.error(f"Error reading PDF: {e}")
            return {"text": "", "pages": 0, "links": []}

    def analyze_resume(self, resume_text: str, jd_text: str) -> dict:
        """
        Perform deep analysis of resume vs JD using Search Grounding.
        Returns structured JSON.
        """
        prompt = f"""
        You are Tal, a brutal but helpful career mentor.
        
        TASK 1: RESEARCH
        - Use Google Search to find the specific "Tech Stack", "Culture", and "Stage" (Startup vs Corporate) of the company.
        - Find what skills/outcomes they value MOST right now.
        
        TASK 2: STRATEGY
        - Define a "Role Translation Strategy": How to frame the candidate's *actual* experience to fit this role? (e.g. "Highlight the *business impact* of RAG agents, not just the code").
        - Identify "Irrelevant Skills" to cut.
        
        RESUME:
        {resume_text[:10000]}
        
        JOB DESCRIPTION:
        {jd_text[:5000]}
        
        Return a JSON object with this EXACT schema.
        KEEP TEXT EXTREMELY SHORT AND PUNCHY. Max 10-15 words per string.
        
        {{
            "company_name": "extracted company name (or 'this company')",
            "role_title": "extracted job title (or 'this role')",
            "company_stage": "Startup / Scaleup / Corporate",
            "role_translation_strategy": "One specific instruction on how to frame their experience",
            "missing_keywords": ["list", "of", "critical", "missing", "keywords"],
            "irrelevant_skills": ["list", "of", "skills", "to", "remove"],
            "good_points": [
                {{"point": "strength description", "why": "why it matters"}}
            ],
            "needs_fixing": [
                {{"issue": "BIGGEST RED FLAG OR MISALIGNMENT", "impact": "Why this is a dealbreaker"}}
            ],
            "proposed_changes": [
                {{"change": "what you will change", "rationale": "why this helps"}}
            ],
            "score_before": 50,
            "score_after": 85
        }}
        
        IMPORTANT: In 'needs_fixing', PUT THE SINGLE BIGGEST RED FLAG FIRST. Be direct.
        """
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    tools=[types.Tool(google_search=types.GoogleSearch())],
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
                "missing_keywords": ["key skills", "metrics"],
                "irrelevant_skills": [],
                "good_points": [{"point": "Experience listed", "why": "shows history"}],
                "needs_fixing": [{"issue": "Generic descriptions", "impact": "low engagement"}],
                "proposed_changes": [{"change": "Quantify impact", "rationale": "prove value"}],
                "score_before": 50,
                "score_after": 80
            }

    def generate_cold_dm(self, resume_text: str, jd_text: str, company_name: str, tone: str = "professional but bold", analysis: dict = None) -> str:
        """Generate a single, deeply researched Cold DM using Google Search."""
        
        # Extract best points from analysis if available
        highlights = ""
        strongest_point = "my background"
        if analysis:
            good_points = [p.get('point', '') for p in analysis.get('good_points', [])]
            if good_points:
                strongest_point = good_points[0]
            highlights = f"\nCANDIDATE STRENGTHS: {', '.join(good_points)}"
        
        prompt = f"""
        You are an elite career strategist.
        
        TASK: Write ONE high-impact Cold DM to a Hiring Manager or Founder at {company_name}.
        
        RESEARCH INSTRUCTIONS (USE GOOGLE SEARCH):
        1. Search for "{company_name} strategy 2026", "{company_name} recent news", "{company_name} blog".
        2. Search for "{company_name} founders" or "Hiring Manager for [Role]".
        3. Find a SPECIFIC insight: A recent product launch, a strategic pivot, a funding round, or a founder's quote.
        
        DRAFTING INSTRUCTIONS:
        - **HOOK**: Start with the specific insight you found. Show you did homework. (e.g. "Just read your post on X...", "Saw the Series B announcement...").
        - **BRIDGE**: Connect that insight to the candidate's STRONGEST point: "{strongest_point}".
        - **ASK**: "Open to a 10-min chat?"
        
        CRITICAL CONSTRAINTS:
        - MAX 50 WORDS.
        - NO fluff ("I hope you are well", "I'm a big fan").
        - NO generic praise.
        - TONE: {tone}.
        
        RESUME SUMMARY:
        {resume_text[:2000]}
        
        JOB DESCRIPTION SUMMARY:
        {jd_text[:2000]}
        {highlights}
        
        OUTPUT:
        Return ONLY the message text.
        """
        
        try:
            # Enable Google Search Grounding
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.8,
                )
            )
            return response.text.strip()
        except Exception as e:
            # Fallback if search unavailable
            return f"Hi [Name], I've been following {company_name} and noticed your work on [Specific Project from JD]. My background matches this perfectly. Let's chat? (Search unavailable: {e})"

    def generate_latex_content(self, resume_text: str, jd_text: str, analysis: dict, links: list, max_pages: int = 1) -> str:
        """Generate the full LaTeX code for the resume."""
        
        company = analysis.get("company_name", "the company")
        role = analysis.get("role_title", "the role")
        strategy = analysis.get("role_translation_strategy", "Focus on relevant impact.")
        irrelevant_skills = analysis.get("irrelevant_skills", [])
        
        # Verify links are strings to be safe
        clean_links = [str(l) for l in links if isinstance(l, str)]
        links_str = "\n".join(clean_links)
        
        prompt = f"""
        You are an expert Resume Writer using LaTeX.
        
        🚨 STRATEGY & AUTHENTICITY 🚨
        1. **EXECUTE THIS STRATEGY**: "{strategy}"
        2. **BE AUTHENTIC**: Do NOT invent titles or experience. Do NOT rename "Technical Support" to "Engineer" if false. Instead, highlight the *transferable impact* (e.g. "Automated tickets" vs "Resolved tickets").
        3. **NO FLUFF**: Do not use "marketing speak" or buzzwords that don't match the actual work.
        
        🚨 FORMATTING RULES (VIOLATION = FAILURE) 🚨
        1. **STRICT PAGE LIMIT**: {max_pages} PAGE(S).
           - CUT older/irrelevant work experience (keep only Title + Company + 1 bullet).
           - MERGE projects.
           - REDUCE bullet points (Max 3 per recent role, 1-2 for older).
        2. **SKILL FILTERING**:
           - REMOVE these irrelevant skills: {irrelevant_skills}
        3. **LINKS**:
           - ONLY use these VERIFIED LINKS:
           {links_str}
           - Format: \\href{{URL}}{{Display Text}}
           - DISPLAY TEXT MUST BE SHORT (e.g. "Project", "Code").
        
        TASK: Rewrite this resume for the {role} role at {company}.
        
        RESUME CONTENT:
        {resume_text}
        
        TARGET JD:
        {jd_text}
        
        LATEX TEMPLATE START:
        {LATEX_TEMPLATE}
        
        OUTPUT:
        Return ONLY the raw LaTeX code (starting with \\documentclass).
        - Use \\usepackage[hidelinks]{{hyperref}} as the LAST package.
        - Ensure all hyperlinks are functional.
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

def img_to_base64(image_path):
    """Convert image to base64 for embedding in HTML."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None

def render_chat_message(role, content, avatar=None):
    with st.chat_message(role, avatar=avatar):
        if role == "assistant":
            # Tal's specific formatting
            st.markdown(content, unsafe_allow_html=True) # Use markdown for the analysis structure
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
        lines.append(f"**missing keywords:** {', '.join(missing[:5]).lower()}\n\n")
    
    # Good Points (Max 1)
    lines.append("**what's working:**")
    for item in analysis.get("good_points", [])[:1]:
        lines.append(f"- {item.get('point', '').lower()}")
    lines.append("") # Spacer
    
    # Fixes (Max 1)
    lines.append("**what needs fixing:**")
    for item in analysis.get("needs_fixing", [])[:1]:
        lines.append(f"- {item.get('issue', '').lower()}")
    lines.append("") # Spacer
    
    # Strategy (New)
    strategy = analysis.get("role_translation_strategy", "Focus on relevant impact.")
    lines.append(f"**the strategy:** {strategy.lower()}\n\n")
    
    # Execution (Changes)
    lines.append("**execution:**")
    for item in analysis.get("proposed_changes", [])[:2]:
        lines.append(f"- {item.get('change', '').lower()}")
    lines.append("") # Spacer
    
    # Score Jump - Green Block
    before = analysis.get('score_before', 50)
    after = analysis.get('score_after', 85)
    
    score_html = f"""
    <div style="background-color: rgba(74, 222, 128, 0.1); border: 1px solid #4ade80; border-radius: 8px; padding: 16px; margin-top: 10px; margin-bottom: 10px;">
        <p style="margin: 0; color: #4ade80; font-weight: bold; font-size: 1.1em; text-align: center;">
            🚀 Score Jump: {before} → {after}
        </p>
    </div>
    """
    
    lines.append(score_html)
    # lines.append("\nlet me cook") # Removed, button handles this
    
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
        st.session_state.resume_links = []
        st.session_state.jd_text = ""
        st.session_state.cold_dm = ""
        st.session_state.company_name = ""
        st.session_state.dm_tone = "Professional & Insightful"
        
        # Opening Line
        st.session_state.messages.append({
            "role": "assistant",
            "content": "yo. i'm tal.\n\ndrop your resume pdf below. let's fix it."
        })
    
    # Hot-reload safety: Ensure new keys exist even if session is old
    if "cold_dm" not in st.session_state:
        st.session_state.cold_dm = ""
    if "company_name" not in st.session_state:
        st.session_state.company_name = ""
    if "dm_tone" not in st.session_state:
        st.session_state.dm_tone = "Professional & Insightful"

    # Header
    tal_img = img_to_base64(TAL_AVATAR)
    if tal_img:
        icon_html = f'<img src="data:image/png;base64,{tal_img}" style="width: 60px; height: 60px; vertical-align: bottom; margin-right: 10px;">'
    else:
        icon_html = "🦊 "
        
    st.markdown(f'<div class="main-title">{icon_html}tal - resume fixer</div>', unsafe_allow_html=True)
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
                data = agent.extract_pdf_data(uploaded)
                text = data["text"]
                pages = data["pages"]
                
                if len(text) > 50:
                    st.session_state.resume_text = text
                    st.session_state.resume_pages = pages
                    st.session_state.resume_links = data["links"]
                    
                    # User msg
                    st.session_state.messages.append({"role": "user", "content": f"Uploaded {uploaded.name} ({pages} pages)"})
                    
                    # Tal response
                    ack = agent.chat("I just uploaded my resume.")
                    st.session_state.messages.append({"role": "assistant", "content": f"{ack}\n\npaste the jd now."})
                    
                    st.session_state.step = "jd"
                    st.rerun()
                else:
                    st.error("Could not read text from PDF. Is it an image scan?")

    # ─── STEP 2: JD INPUT ───
    elif st.session_state.step == "jd":
        with st.form("jd_form"):
            jd = st.text_area("paste job description", height=200, placeholder="paste the full JD here...")
            submitted = st.form_submit_button("analyze match →")
            
            if submitted and len(jd) > 50:
                st.session_state.jd_text = jd
                st.session_state.messages.append({"role": "user", "content": "Here is the JD."})
                st.session_state.step = "analysis"
                st.rerun()

    # ─── STEP 3: ANALYSIS & STRATEGY ───
    elif st.session_state.step == "analysis":
        # Run Analysis (Once)
        if "analysis_results" not in st.session_state:
            with st.status("🦊 tal is analyzing...", expanded=True) as status:
                st.write("checking the vibe...")
                analysis = agent.analyze_resume(st.session_state.resume_text, st.session_state.jd_text)
                st.session_state.analysis_results = analysis
                st.session_state.company_name = analysis.get("company_name", "the company")
                status.update(label="analysis done!", state="complete")
            
            # Show Strategy Message
            analysis_msg = format_analysis_display(analysis)
            st.session_state.messages.append({"role": "assistant", "content": analysis_msg})
            st.session_state.messages.append({"role": "assistant", "content": "you cool with this plan?"})
            st.rerun()

        # Approval Button
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("🔥 Yes, Cook", type="primary"):
                st.session_state.messages.append({"role": "user", "content": "Yes, cook."})
                st.session_state.messages.append({"role": "assistant", "content": "bet. rewriting now..."})
                st.session_state.step = "generating"
                st.rerun()

    # ─── STEP 4: GENERATING RESUME ───
    elif st.session_state.step == "generating":
        with st.status("🦊 cooking...", expanded=True) as status:
            
            # 1. Generate LaTeX
            st.write("applying strategy...")
            latex = agent.generate_latex_content(
                st.session_state.resume_text, 
                st.session_state.jd_text, 
                st.session_state.analysis_results,
                links=st.session_state.resume_links,
                max_pages=st.session_state.resume_pages
            )
            st.session_state.latex_content = latex
            
            # 2. Compile
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
            
        # Cold DM Section (Add-on)
        st.divider()
        
        if not st.session_state.cold_dm:
            st.markdown("### 📨 Want to get hired faster?")
            st.write("Tal can research the company and draft a high-impact Cold DM to the founder.")
            if st.button("✨ Draft Cold DM (Deep Research)"):
                with st.spinner("researching company strategy & drafting..."):
                    dm = agent.generate_cold_dm(
                        st.session_state.resume_text, 
                        st.session_state.jd_text, 
                        st.session_state.company_name,
                        tone=st.session_state.dm_tone,
                        analysis=st.session_state.get('analysis_results')
                    )
                    st.session_state.cold_dm = dm
                    st.rerun()
        
        else:
            st.markdown(f"### 📨 The Cold DM ({st.session_state.dm_tone})")
            st.info("💡 Pro Tip: Tal researched the company to write this. Send it to the Founder/HM directly.")
            st.code(st.session_state.cold_dm, language="text")
            
            if st.button("🔄 Regenerate with New Tone"):
                # Cycle tone
                tones = ["Direct & Bold", "Casual & Witty", "Professional & Insightful"]
                current_tone = st.session_state.dm_tone
                # Find next tone
                try:
                    next_idx = (tones.index(current_tone) + 1) % len(tones)
                except ValueError:
                    next_idx = 0
                new_tone = tones[next_idx]
                st.session_state.dm_tone = new_tone
                
                with st.spinner(f"Re-researching & drafting ({new_tone})..."):
                    new_dm = agent.generate_cold_dm(
                        st.session_state.resume_text, 
                        st.session_state.jd_text, 
                        st.session_state.company_name,
                        tone=new_tone,
                        analysis=st.session_state.get('analysis_results')
                    )
                    st.session_state.cold_dm = new_dm
                    st.rerun()
            
        if st.button("🔄 Start Over"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
