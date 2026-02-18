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

% Sections formatting
\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large\bfseries
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

\pdfgentounicode=1

% Custom Bullet Size Command - Re-definable by AI
\newcommand{\resumeBulletSize}{\small} 

\newcommand{\resumeItem}[1]{
  \item\resumeBulletSize{
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
    {\Huge \scshape FULL_NAME} \\ \vspace{2pt}
    {\hypersetup{urlcolor=black} \small CONTACT_INFO}
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
        Perform deep analysis using the new Dynamic Strategy Engine.
        Determines archetypes and creates a precise Execution Plan.
        """
        prompt = f"""
        You are Tal, a brutal but genius career strategist.
        
        TASK 1: ARCHETYPE DETECTION (Using Search)
        - Search Google for the company to determine its "Company Archetype":
          - "Early Stage": <50 employees, chaos, needs builders/generalists.
          - "Growth Stage": 50-500 employees, scaling, needs processes/specialists.
          - "Corporate": >500 employees, stable, needs compliance/politics/depth.
        - Determine the "Role Archetype" based on JD:
          - "Engineering": Focus on stack, scale, complexity.
          - "Product": Focus on user, metrics, strategy.
          - "Growth/Marketing": Focus on CAC, revenue, experiments.
          - "Research": Focus on patents, publications, novelty.
          - "Generalist": Ops, Chief of Staff, Founder's Office.
        
        TASK 2: STRATEGY & CONTENT PLAN
        - Define a "Role Translation Strategy": How to frame the candidate's past for *this* specific future.
        - Create a strictly defined CONTENT PLAN for the resume generator to follow:
          - **keep_sections**: Which sections MUST stay? (e.g. "Experience", "Projects").
          - **drop_sections**: Which sections MUST go to save space? (e.g. "Volunteering", "Patents" if irrelevant).
          - **top_projects**: Select exactly 2 strongest projects that match the JD best. Drop the rest.
          - **bullet_strategy**: "Dense" (for corp), "Punchy" (for startup), "Technical" (for eng).
        
        TASK 3: GAP ANALYSIS
        - **missing_hard_skills**: critical tech/tools missing (e.g. "Python", "Salesforce"). IGNORE soft skills.
        - **irrelevant_terms**: Buzzwords to kill (e.g. "synergy", "kpi tracking").
        
        RESUME:
        {resume_text[:10000]}
        
        JOB DESCRIPTION:
        {jd_text[:5000]}
        
        Return a JSON object with this exact schema (all keys lowercase):
        {{
            "company_name": "extracted name",
            "role_title": "extracted title",
            "company_archetype": "early stage / growth stage / corporate",
            "role_archetype": "engineering / product / growth / research / generalist",
            "role_translation_strategy": "Direct strategy explanation to user (max 15 words)",
            "content_plan": {{
                "keep_sections": ["list", "of", "sections"],
                "drop_sections": ["list", "of", "sections"],
                "top_projects": ["project 1", "project 2"],
                "bullet_guidelines": "specific instruction for bullet writing"
            }},
            "missing_keywords": ["list", "of", "hard", "skills"],
            "irrelevant_skills": ["list", "of", "terms", "to", "cut"],
            "good_points": [
                {{"point": "strength", "why": "reason"}}
            ],
            "needs_fixing": [
                {{"issue": "red flag", "impact": "consequence"}}
            ],
            "proposed_changes": [
                {{"change": "action", "rationale": "reason"}}
            ],
            "score_before": 50,
            "score_after": 90
        }}
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
            return {
                "company_name": "the company",
                "role_title": "the role",
                "company_archetype": "corporate",
                "role_archetype": "generalist",
                "role_translation_strategy": "Standard professional alignment",
                "content_plan": {
                    "keep_sections": ["Experience", "Education", "Projects"],
                    "drop_sections": ["Volunteering"],
                    "top_projects": ["Most recent project"],
                    "bullet_guidelines": "Standard STAR method"
                },
                "missing_keywords": ["relevant skills"],
                "irrelevant_skills": [],
                "good_points": [{"point": "Experience matches", "why": "Relevant history"}],
                "needs_fixing": [{"issue": "Generic descriptions", "impact": "Low impact"}],
                "proposed_changes": [{"change": "Add metrics", "rationale": "Show value"}],
                "score_before": 50,
                "score_after": 80
            }

    def generate_cold_dm(self, resume_text: str, jd_text: str, company_name: str, analysis: dict = None) -> str:
        """
        Generate a highly targeted cold DM based on the Company Archetype.
        """
        
        # Extract dynamic context
        company_archetype = "growth stage"
        role_archetype = "generalist"
        strongest_point = "my background"
        
        if analysis:
            company_archetype = analysis.get('company_archetype', 'growth stage').lower()
            role_archetype = analysis.get('role_archetype', 'generalist').lower()
            good_points = [p.get('point', '') for p in analysis.get('good_points', [])]
            if good_points:
                strongest_point = good_points[0].lower()

        prompt = f"""
        You are an elite career strategist.
        
        CONTEXT:
        - Target Company: {company_name} ({company_archetype})
        - Role: {role_archetype}
        - Candidate's "Ace Card": "{strongest_point}"
        
        TASK: Write ONE high-impact Cold DM (max 50 words) to a Hiring Manager or Founder.
        
        TONE STRATEGY (Based on Archetype):
        - If "Early Stage": "Builder Energy". Direct, slightly chaotic, "I ship fast", "I solve pain". Reference a specific problem they have.
        - If "Growth Stage": "Value Energy". Quantitative, "I scaled X to Y", "I built the system you need". Reference their recent win/round.
        - If "Corporate": "Professional Precision". Polished, "I specialize in [Domain]", "I led [Project] at [Top Firm]". Reference a strategic initiative.
        
        RESEARCH INSTRUCTIONS (Use Google Search):
        1. Search for "{company_name} recent news", "{company_name} funding", "{company_name} product launch".
        2. Find a SPECIFIC HOOK (e.g. "Series B raise", "New AI feature", "Expansion to US").
        
        STRUCTURE:
        1. **The Hook**: "Saw you just launched X..." or "Congratz on the Series A..." (Show you know them).
        2. **The Leverage**: "At [My Past Company], I built the exact system you need for Y..." (Connect YOUR ace card to THEIR problem).
        3. **The Ask**: "Open to a 10-min intro?"
        
        CONSTRAINTS:
        - NO fluff ("Hope you are well").
        - NO generic praise ("Love what you're doing").
        - STRICTLY under 50 words.
        - All text must be lowercase (style choice).
        
        RESUME SUMMARY:
        {resume_text[:2000]}
        
        JOB DESCRIPTION:
        {jd_text[:2000]}
        
        Output only the message text.
        """
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    temperature=0.7,
                )
            )
            return response.text.strip().lower()
        except Exception as e:
            return f"hi [name], saw {company_name} is scaling {role_archetype} - i built similar systems at my last role. open to a 10-min chat? (search unavailable)"

    def generate_latex_content(self, resume_text: str, jd_text: str, analysis: dict, links: list, max_pages: int = 1) -> str:
        """
        Generate LaTeX using the strict 'Brain & Hands' architecture.
        The 'Hands' (this function) must purely execute the 'Brain's' (analysis) Content Plan.
        """
        
        # Extract the Content Plan from the Brain
        content_plan = analysis.get("content_plan", {})
        keep_sections = content_plan.get("keep_sections", ["Experience", "Projects", "Education"])
        drop_sections = content_plan.get("drop_sections", [])
        top_projects = content_plan.get("top_projects", [])
        bullet_guidelines = content_plan.get("bullet_guidelines", "Standard professional bullets")
        
        # Other Strategy Elements
        company = analysis.get("company_name", "the company").lower()
        role = analysis.get("role_title", "the role").lower()
        strategy = analysis.get("role_translation_strategy", "Focus on impact").lower()
        irrelevant_terms = [s.lower() for s in analysis.get("irrelevant_skills", [])]
        
        # Link Handling
        clean_links = [str(l) for l in links if isinstance(l, str)]
        links_str = "\n".join(clean_links)
        
        prompt = f"""
        You are an obedient LaTeX generator. You have NO creative license. 
        You must STRICTLY execute the provided CONTENT PLAN to build a 1-page resume.
        
        CONTENT PLAN (The Law):
        1. **KEEP Sections**: {keep_sections} ONLY.
        2. **DROP Sections**: {drop_sections} (Do NOT include these headers or content).
        3. **PROJECTS**: Include ONLY these specific projects: {top_projects}. DELETE ALL OTHERS.
        4. **BULLET STRATEGY**: {bullet_guidelines}.
        5. **IRRELEVANT TERMS**: Remove mentions of: {irrelevant_terms}.
        
        STRATEGY ALIGNMENT:
        - "Role Strategy": {strategy}
        - "Anti-Hallucination": Do NOT invent skills. Only use what is in the input resume.
        
        LATEX RULES:
        1. **One Page Limit (DRACONIAN)**:
           - The resume MUST fit on exactly 1 page.
           - **Project Limit**: STRICTLY MAX 2 PROJECTS. If the plan lists more, ignore them.
           - **If content is DENSE**: Add `\\renewcommand{{\\resumeBulletSize}}{{\\footnotesize}}` immediately after `\\documentclass` to shrink bullet text.
           - **If content is SPARSE (<85%)**: Write longer, more detailed descriptions to fill the page. Do NOT leave it empty.
        2. **Header Formatting**:
           - **Dynamic Icons**: Use `fontawesome5` icons ONLY for links that exist in the input.
           - Format Example: `\\faEnvelope` email@domain.com $|$ `\\faLinkedin` LinkedIn $|$ `\\faGithub` GitHub
           - **Rule**: If a link (like Portfolio) is missing, do NOT include its icon or separator.
        3. **Formatting**:
           - **Bold** key metrics (e.g. \\textbf{{$2M revenue}}, \\textbf{{30% growth}}).
           - **Bold** hard skills (e.g. \\textbf{{Python}}, \\textbf{{React}}).
           - Links: \\href{{url}}{{\\textbf{{display_text}}}} (Blue & Bold).
        4. **Education Mandate**:
           - Keep ALL education entries (University AND High School/Grade 12). Do not cut them.
           - Keep ALL grades, CGPA, and percentages exactly as they appear in the input. Do NOT remove them.
        5. **Links**:
           - Use these links: {links_str}
           - Exact match project names to links.
        
        INPUT RESUME:
        {resume_text}
        
        TARGET JD:
        {jd_text}
        
        LATEX TEMPLATE START:
        {LATEX_TEMPLATE}
        
        OUTPUT:
        Return ONLY the raw LaTeX code starting with \\documentclass.
        """
        
        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2, # Low temperature for strict execution
                )
            )
            latex = response.text or ""
            
            # Post-processing cleanup
            latex = re.sub(r"^```(?:latex|tex)?\s*\n", "", latex, flags=re.MULTILINE)
            latex = re.sub(r"\n```\s*$", "", latex, flags=re.MULTILINE)
            return latex.strip()
            
        except Exception as e:
            st.error(f"Resume generation failed: {e}")
            return LATEX_TEMPLATE.replace("FULL_NAME", "Error Generating Resume")

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
    c_arch = analysis.get("company_archetype", "company")
    r_arch = analysis.get("role_archetype", "role")
    
    # Fix "role role" redundancy
    if role.lower().endswith(" role") or role.lower() == "this role":
        role_str = role
    else:
        role_str = f"{role} role"
        
    lines = []
    lines.append(f"alright i've analyzed your resume for the **{role_str}** at **{company}**\n\n")
    
    # Archetype & Strategy Block
    lines.append(f"**archetype detected:** {c_arch} + {r_arch}")
    
    strategy = analysis.get("role_translation_strategy", "Focus on relevant impact.")
    lines.append(f"**strategy:** \"{strategy.lower()}\"\n")

    # Content Plan (What we are doing)
    content_plan = analysis.get("content_plan", {})
    if content_plan:
        kept = len(content_plan.get("keep_sections", []))
        dropped = len(content_plan.get("drop_sections", []))
        top_proj = len(content_plan.get("top_projects", []))
        lines.append(f"**the plan:** keeping {kept} sections, dropping {dropped} fluff sections, highlighting top {top_proj} projects.")
        lines.append("")

    # Missing Keywords
    missing = analysis.get("missing_keywords", [])
    if missing:
        lines.append(f"**missing hard skills:** {', '.join(missing[:5]).lower()}\n")
    
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
