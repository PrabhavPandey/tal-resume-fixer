"""
Tal Resume Fixer - The Rewrite
Clean architecture, robust parsing, and a chonky fox persona.
"""

import streamlit as st
from google import genai
from google.genai import types
import fitz  # PyMuPDF
import requests
import base64
import os
import json
import re

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
\usepackage[colorlinks=true, urlcolor=royalblue, linkcolor=royalblue]{hyperref}

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
    {\hypersetup{urlcolor=black} CONTACT_INFO}
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

    def extract_pdf_data(self, file) -> dict:
        """Extract text, page count, and hyperlinks from PDF using PyMuPDF (fitz)."""
        try:
            # Read file bytes
            file.seek(0)
            pdf_bytes = file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            text = ""
            links = []
            
            for page in doc:
                text += page.get_text() + "\n"
                
                # Extract Links (URI)
                page_links = page.get_links()
                for link in page_links:
                    if "uri" in link:
                        links.append(link["uri"])
            
            # Extract Text Links (Regex Fallback for non-hyperlinked text URLs)
            raw_links = re.findall(r'(https?://[^\s\)\}\],]+)', text)
            # Add https prefix to shorthand links if missing
            raw_links += [f"https://{l}" if not l.startswith("http") else l for l in re.findall(r'(?:github\.com/[^\s\)\}\],]+)', text)]
            raw_links += [f"https://{l}" if not l.startswith("http") else l for l in re.findall(r'(?:linkedin\.com/in/[^\s\)\}\],]+)', text)]
            
            all_links = sorted(list(set(links + raw_links)))
            
            return {
                "text": text.strip(),
                "pages": len(doc),
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
        you are tal, a brutal but helpful career mentor.
        
        task 1: research
        - use google search to find the specific "tech stack", "culture", and "stage" (startup vs corporate) of the company.
        - find what skills/outcomes they value most right now.
        
        task 2: strategy
        - define a "role translation strategy": how to frame the candidate's *actual* experience to fit this role?
        - explain this strategy directly to the user (e.g. "look, i need to rebrand your support role as customer success...").
        - identify "irrelevant skills" to cut.
        
        resume:
        {resume_text[:10000]}
        
        job description:
        {jd_text[:5000]}
        
        return a json object with this exact schema.
        keep text extremely short and punchy. max 10-15 words per string.
        
        {{
            "company_name": "extracted company name (or 'this company')",
            "role_title": "extracted job title (or 'this role')",
            "company_stage": "startup / scaleup / corporate",
            "role_translation_strategy": "direct explanation of the rebrand strategy to the user (max 20 words)",
            "missing_keywords": ["list", "of", "critical", "missing", "keywords"],
            "irrelevant_skills": ["list", "of", "skills", "to", "remove"],
            "good_points": [
                {{"point": "strength description", "why": "why it matters"}}
            ],
            "needs_fixing": [
                {{"issue": "biggest red flag or misalignment", "impact": "why this is a dealbreaker"}}
            ],
            "proposed_changes": [
                {{"change": "what you will change", "rationale": "why this helps"}}
            ],
            "score_before": 50,
            "score_after": 85
        }}
        
        important: in 'needs_fixing', put the single biggest red flag first. be direct.
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
                "company_stage": "corporate",
                "role_translation_strategy": "look, i'll frame your general skills for this generic role",
                "missing_keywords": ["key skills", "metrics"],
                "irrelevant_skills": [],
                "good_points": [{"point": "experience listed", "why": "shows history"}],
                "needs_fixing": [{"issue": "generic descriptions", "impact": "low engagement"}],
                "proposed_changes": [{"change": "quantify impact", "rationale": "prove value"}],
                "score_before": 50,
                "score_after": 80
            }

    def generate_cold_dm(self, resume_text: str, jd_text: str, company_name: str, analysis: dict = None) -> str:
        """Generate a single, deeply researched cold dm using google search."""
        
        # Extract best points from analysis if available
        highlights = ""
        strongest_point = "my background"
        if analysis:
            good_points = [p.get('point', '') for p in analysis.get('good_points', [])]
            if good_points:
                strongest_point = good_points[0].lower()
            highlights = f"\ncandidate strengths: {', '.join([p.lower() for p in good_points])}"
        
        prompt = f"""
        you are an elite career strategist.
        
        task: write one high-impact cold dm to a hiring manager or founder at {company_name}.
        
        research instructions (use google search):
        1. search for "{company_name} strategy 2026", "{company_name} recent news", "{company_name} blog".
        2. search for "{company_name} founders" or "hiring manager for [role]".
        3. find a specific insight: a recent product launch, a strategic pivot, a funding round, or a founder's quote.
        
        drafting instructions:
        - hook: start with the specific insight you found. show you did homework. (e.g. "just read your post on x...", "saw the series b announcement...").
        - bridge: connect that insight to the candidate's strongest point: "{strongest_point}".
        - ask: "open to a 10-min chat?"
        
        critical constraints:
        - max 50 words.
        - no fluff ("i hope you are well", "i'm a big fan").
        - no generic praise.
        - tone: witty and direct.
        
        resume summary:
        {resume_text[:2000]}
        
        job description summary:
        {jd_text[:2000]}
        {highlights}
        
        output:
        return only the message text.
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
            return f"hi [name], i've been following {company_name} and noticed your work on [specific project from jd]. my background matches this perfectly. let's chat? (search unavailable: {e})"

    def generate_latex_content(self, resume_text: str, jd_text: str, analysis: dict, links: list, max_pages: int = 1) -> str:
        """Generate the full LaTeX code for the resume."""
        
        company = analysis.get("company_name", "the company").lower()
        role = analysis.get("role_title", "the role").lower()
        strategy = analysis.get("role_translation_strategy", "focus on relevant impact.").lower()
        irrelevant_skills = [s.lower() for s in analysis.get("irrelevant_skills", [])]
        
        # Verify links are strings to be safe
        clean_links = [str(l) for l in links if isinstance(l, str)]
        links_str = "\n".join(clean_links)
        
        prompt = f"""
        you are an expert resume writer using latex.
        
        🚨 strategy & authenticity 🚨
        1. **execute this strategy**: "{strategy}"
        2. **be authentic**: do NOT invent titles or experience. highlight *transferable impact*.
        3. **punchy impact**: use strong action verbs. be concise but impressive.
        4. **bold metrics**: bold specific numbers, outcomes, and keywords (e.g. \\textbf{{30\% increase}}, \\textbf{{python}}).
        
        🚨 formatting rules (violation = failure) 🚨
        1. **hard 1-page limit**: the final pdf must be exactly 1 page.
           - **max**: 2 work experience entries total.
           - **max**: 2 bullet points per role.
           - **max**: 2 projects total, 2 bullets each.
           - if content still spills, cut the oldest work experience first, then the oldest project.
           - do NOT shrink fonts or margins to cheat. cut content.
           - **do NOT cut education**: keep all education entries (university and high school).
        2. **skill filtering**:
           - remove these irrelevant skills: {irrelevant_skills}
        3. **links**:
           - only use these verified links:
           {links_str}
           - format: \\href{{URL}}{{\\textbf{{display text}}}}
           - display text: use the original name found in the resume. do NOT rename.
           - **critical**: if a project in the input has multiple links (e.g. video | website | github), you must include all of them. do not drop any.
        
        task: rewrite this resume for the {role} role at {company}.
        
        resume content:
        {resume_text}
        
        target jd:
        {jd_text}
        
        latex template start:
        {LATEX_TEMPLATE}
        
        output:
        return only the raw latex code (starting with \\documentclass).
        - the hyperref package and link colors are already configured in the template above. do not add another \\usepackage{{hyperref}} or change link colors.
        - ensure all hyperlinks are functional.
        """
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                )
            )
            latex = response.text or ""
        except Exception as e:
            st.error(f"Resume generation failed: {e}")
            # Fallback: return a minimal LaTeX document with an error note
            latex = LATEX_TEMPLATE.replace("FULL_NAME", "Tal Resume (Generation Error)").replace(
                "EDUCATION_CONTENT", "Unfortunately, something went wrong while generating your resume."
            ).replace("EXPERIENCE_CONTENT", "").replace("PROJECTS_CONTENT", "").replace("SKILLS_CONTENT", "")
        
        # Clean up possible markdown fences
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
    
    # Good Points (Max 3)
    lines.append("**what's working:**")
    for item in analysis.get("good_points", [])[:3]:
        lines.append(f"- {item.get('point', '').lower()}")
    lines.append("") # Spacer
    
    # Fixes (Max 2)
    lines.append("**what needs fixing:**")
    for item in analysis.get("needs_fixing", [])[:2]:
        lines.append(f"- {item.get('issue', '').lower()}")
    lines.append("") # Spacer
    
    # Strategy (New)
    strategy = analysis.get("role_translation_strategy", "Focus on relevant impact.")
    lines.append(f"**tal's strategy:** \"{strategy.lower()}\"\n\n")
    
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
            🚀 score jump: {before} → {after}
        </p>
    </div>
    """
    
    lines.append(score_html)
    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────
# MAIN APP LOOP
# ─────────────────────────────────────────────────────────────

def main():
    # Session State Init
    if "messages" not in st.session_state:
        st.session_state.messages = []
        # Flow: upload -> analysis -> generating -> done
        st.session_state.step = "upload"
        st.session_state.resume_text = ""
        st.session_state.resume_pages = 1
        st.session_state.resume_links = []
        st.session_state.jd_text = ""
        st.session_state.cold_dm = ""
        st.session_state.company_name = ""
        
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

    # ─── STEP 1: UPLOAD & JD ───
    if st.session_state.step == "upload":
        st.markdown("### 1. the inputs")
        col1, col2 = st.columns([1, 1])
        with col1:
            uploaded = st.file_uploader("upload resume (pdf)", type="pdf")
        with col2:
            jd = st.text_area("paste job description", height=200, placeholder="paste full jd here...", label_visibility="visible")
            
        submitted = st.button("analyze match →", type="primary", use_container_width=True)
        
        if submitted:
            if uploaded and jd and len(jd) > 50:
                with st.spinner("reading pdf..."):
                    data = agent.extract_pdf_data(uploaded)
                    if len(data["text"]) > 50:
                        st.session_state.resume_text = data["text"]
                        st.session_state.resume_pages = data["pages"]
                        st.session_state.resume_links = data["links"]
                        st.session_state.jd_text = jd
                        
                        st.session_state.messages.append({"role": "user", "content": f"uploaded {uploaded.name} and jd."})
                        st.session_state.step = "analysis"
                        st.rerun()
                    else:
                        st.error("could not read pdf. is it an image scan?")
            else:
                st.warning("please upload a resume and paste the jd.")

    # ─── STEP 3: ANALYSIS & STRATEGY ───
    elif st.session_state.step == "analysis":
        # Run Analysis once, then immediately generate the resume
        if "analysis_results" not in st.session_state:
            with st.status("🦊 tal is analyzing...", expanded=True) as status:
                st.write("checking the vibe...")
                analysis = agent.analyze_resume(st.session_state.resume_text, st.session_state.jd_text)
                st.session_state.analysis_results = analysis
                st.session_state.company_name = analysis.get("company_name", "the company")
                status.update(label="analysis done!", state="complete")
            
            # Show Strategy Message in chat
            analysis_msg = format_analysis_display(analysis)
            st.session_state.messages.append({"role": "assistant", "content": analysis_msg})
            st.session_state.messages.append({"role": "assistant", "content": "cool, let me cook this into a resume."})
            
            # Move straight to resume generation
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
                st.info("preview unavailable (library missing). download below.")
                
            # Buttons
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📥 download pdf",
                    data=st.session_state.pdf_bytes,
                    file_name="Tal_Resume.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary"
                )
            with col2:
                st.download_button(
                    "📄 download .tex",
                    data=st.session_state.latex_content,
                    file_name="Tal_Resume.tex",
                    mime="text/plain",
                    use_container_width=True
                )
        else:
            st.error("pdf compilation failed. but i generated the code!")
            if st.session_state.compile_error:
                with st.expander("error details"):
                    st.write(st.session_state.compile_error)
            
            st.download_button(
                "📄 download .tex source (use overleaf)",
                data=st.session_state.latex_content,
                file_name="Tal_Resume.tex",
                mime="text/plain",
                use_container_width=True
            )
            
        # Cold DM Section (Add-on)
        st.divider()
        
        if not st.session_state.cold_dm:
            st.markdown("### 📨 want to get hired faster?")
            st.write("tal can research the company and draft a high-impact cold dm to the founder.")
            if st.button("✨ draft cold dm (deep research)"):
                with st.spinner("researching company strategy & drafting..."):
                    dm = agent.generate_cold_dm(
                        st.session_state.resume_text, 
                        st.session_state.jd_text, 
                        st.session_state.company_name,
                        analysis=st.session_state.get('analysis_results')
                    )
                    st.session_state.cold_dm = dm
                    st.rerun()
        
        else:
            st.markdown(f"### 📨 the cold dm")
            st.info("💡 pro tip: tal researched the company to write this. send it to the founder/hm directly.")
            st.code(st.session_state.cold_dm, language="text")
            
        if st.button("🔄 start over"):
            st.session_state.clear()
            st.rerun()

if __name__ == "__main__":
    main()
