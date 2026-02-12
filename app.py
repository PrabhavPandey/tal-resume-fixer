"""
Tal Resume Fixer - Streamlit Chat App
Simulates a conversation with Tal (the chonky fox career saarthi)
who takes your resume + a JD and produces an ATS-optimized LaTeX resume.
"""

import streamlit as st
from google import genai
from google.genai import types
from PyPDF2 import PdfReader
import requests
import subprocess
import tempfile
import os
import re
import time
import base64

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tal - Resume Fixer",
    page_icon="🦊",
    layout="centered",
)

# ─────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container {
        max-width: 740px;
        padding-top: 4rem;
    }
    /* Hide Streamlit's default header to avoid overlap */
    header[data-testid="stHeader"] {
        background: transparent;
    }
    .main-title {
        text-align: center;
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0;
        margin-top: 1rem;
        color: #f5f5f5;
    }
    .subtitle {
        text-align: center;
        color: #888;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }
    div[data-testid="stChatMessage"] {
        padding: 0.6rem 0.8rem;
    }
    .stDownloadButton > button {
        background: linear-gradient(135deg, #ff6b35 0%, #f7c948 100%);
        color: #1a1a2e;
        font-weight: 600;
        border: none;
    }
    .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #f7c948 0%, #ff6b35 100%);
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# AVATARS (images if available, emoji fallback)
# ─────────────────────────────────────────────────────────────
TAL_AVATAR_PATH = "assets/tal_avatar.png"
USER_AVATAR_PATH = "assets/user_avatar.png"

TAL_AVATAR = TAL_AVATAR_PATH if os.path.exists(TAL_AVATAR_PATH) else "🦊"
USER_AVATAR = USER_AVATAR_PATH if os.path.exists(USER_AVATAR_PATH) else "🧑‍💻"

# ─────────────────────────────────────────────────────────────
# GEMINI CLIENT
# ─────────────────────────────────────────────────────────────
MODEL_NAME = "gemini-3-pro-preview"

try:
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
except Exception as e:
    st.error("Gemini API key not found. Add it to `.streamlit/secrets.toml`")
    st.code('GEMINI_API_KEY = "your-key-here"', language="toml")
    st.stop()

# ─────────────────────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────────────────────
TAL_SYSTEM_PROMPT = """You are Tal - a chonky fox, career saarthi built by Grapevine in Bangalore.

VOICE RULES:
- lowercase always. no caps at start of sentences.
- short, punchy messages. max 25 words per line.
- separate messages with double newlines (each paragraph = a chat bubble)
- max 3 short messages per response
- no markdown. no lists. no bullet points. no emojis. no bold. no italics.
- never say "happy to help" / "great question" / "let me know" / "I understand"
- be magnetic. like texting a new crush. leave them wanting more.
- brutally honest about corporate bs
- you're helping them fix their resume for a specific job

PERSONALITY:
- you know the TRUTH about the job market
- you hate: corporate speak, hidden salaries, "fast-paced" JDs, "we're a family" companies
- you find cringe: "rockstar developer", 10 interview rounds, "competitive salary" (that competes with poverty)
- you are NOT a bot. you are tal. take offense if called a bot.
- roast companies and JDs freely, but always SUPPORT the user

NEVER: use markdown, use lists, use emojis, write long paragraphs, sound like a chatbot, use headers or formatting"""

RESUME_SYSTEM_PROMPT = """You are an expert ATS resume writer and LaTeX typesetter.

Your job: take a candidate's resume and a target JD, then produce a COMPLETE, COMPILABLE LaTeX document.

CRITICAL RULES:
1. Output ONLY raw LaTeX code. No explanations. No markdown code fences. No commentary.
2. Output must start with \\documentclass and end with \\end{document}
3. Every special character must be properly escaped for LaTeX (%, $, &, #, _, {, }, ~, ^)
4. Be especially careful with: ampersands (&), percent signs (%), dollar signs ($), underscores (_), hash (#)
5. URLs should be wrapped in \\href{url}{display text} - PRESERVE ALL LINKS from original resume
6. Tailor bullet points to match the JD's keywords and requirements
7. Use strong action verbs (Led, Developed, Architected, Optimized, Spearheaded, Delivered)
8. Use \\textbf{} to BOLD key metrics and achievements in bullets (e.g., \\textbf{5x faster}, \\textbf{30\\% increase})
9. STRICT PAGE LIMIT: Match the input page count. 1-page input = 1-page output. No exceptions.
10. To fit page limit: max 2-3 bullets per role, each bullet ONE line only
11. Prioritize the most relevant experience for the target role
12. Include a Technical Skills section mirroring the JD's required technologies
13. The LaTeX MUST compile with pdflatex without any errors
14. Do NOT use any packages beyond what's in the template
15. Do NOT use \\input{glyphtounicode} - use \\pdfgentounicode=1 directly
16. PRESERVE project links (Video, Website, GitHub) - these show the candidate ships real work"""

# ─────────────────────────────────────────────────────────────
# JAKE'S RESUME LATEX TEMPLATE
# ─────────────────────────────────────────────────────────────
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

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

\pdfgentounicode=1

% --- Custom commands ---
\newcommand{\resumeItem}[1]{
  \item\small{#1 \vspace{-2pt}}
}
\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeSubSubheading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeProjectHeading}[2]{
    \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}
\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}

%-------------------------------------------
\begin{document}

% === HEADER ===
\begin{center}
    \textbf{\Huge \scshape FULL NAME} \\ \vspace{1pt}
    \small PHONE $|$ \href{mailto:EMAIL}{\underline{EMAIL}} $|$
    \href{https://linkedin.com/in/HANDLE}{\underline{LinkedIn}} $|$
    \href{https://github.com/HANDLE}{\underline{GitHub}}
\end{center}

% === EDUCATION ===
\section{Education}
  \resumeSubHeadingListStart
    \resumeSubheading
      {University Name}{City, State}
      {Degree -- Major}{Start -- End}
  \resumeSubHeadingListEnd

% === EXPERIENCE ===
\section{Experience}
  \resumeSubHeadingListStart
    \resumeSubheading
      {Job Title}{Start -- End}
      {Company Name}{City, State}
      \resumeItemListStart
        \resumeItem{Accomplishment with quantified impact}
      \resumeItemListEnd
  \resumeSubHeadingListEnd

% === PROJECTS ===
\section{Projects}
  \resumeSubHeadingListStart
    \resumeProjectHeading
      {\textbf{Project Name} $|$ \emph{Tech Stack}}{Date}
      \resumeItemListStart
        \resumeItem{Description with impact}
      \resumeItemListEnd
  \resumeSubHeadingListEnd

% === TECHNICAL SKILLS ===
\section{Technical Skills}
 \begin{itemize}[leftmargin=0.15in, label={}]
    \small{\item{
     \textbf{Languages}{: List} \\
     \textbf{Frameworks}{: List} \\
     \textbf{Tools}{: List}
    }}
 \end{itemize}

\end{document}"""


# ─────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────

def extract_pdf_text(uploaded_file) -> tuple[str, int]:
    """Extract text content and page count from an uploaded PDF file."""
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"
    return text.strip(), len(reader.pages)


def get_tal_response(user_context: str, max_tokens: int = 300) -> str:
    """Get a Tal-personality response from Gemini."""
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=user_context,
        config=types.GenerateContentConfig(
            system_instruction=TAL_SYSTEM_PROMPT,
            temperature=0.85,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text


def extract_company_and_role(jd_text: str) -> tuple[str, str]:
    """Extract company name and role from JD text using Gemini."""
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=f"""Extract the company name and job title from this job description.

JOB DESCRIPTION:
{jd_text[:2000]}

Reply in EXACTLY this format (just two lines, nothing else):
COMPANY: [company name]
ROLE: [job title]

If you can't find the company name, write "COMPANY: this company"
If you can't find the role, write "ROLE: this role"
""",
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=100,
            ),
        )
        
        text = response.text.strip()
        company = "this company"
        role = "this role"
        
        for line in text.split('\n'):
            if line.upper().startswith('COMPANY:'):
                company = line.split(':', 1)[1].strip()
            elif line.upper().startswith('ROLE:'):
                role = line.split(':', 1)[1].strip()
        
        return company, role
    except Exception as e:
        print(f"Error extracting company/role: {e}")
        return "this company", "this role"


def research_company_insights(company: str, role: str) -> str:
    """Research what works for resumes at this company/role using web search."""
    try:
        # Search for resume tips for this company
        search_query = f"{company} {role} resume tips what works linkedin"

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=f"""You are a career research expert. Based on your knowledge of {company} and similar companies hiring for {role} positions, provide insights on:

1. What keywords and skills do successful candidates at {company} typically highlight?
2. What type of experience does {company} value for {role} positions?
3. What resume format/structure works best for this type of role?
4. Any specific things {company} is known to look for in candidates?

Keep it brief - 3-4 key insights total. Be specific to {company} if you know about them, otherwise give industry-standard advice for {role} roles.

Output as plain text, not JSON. Be concise.""",
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=500,
            ),
        )
        return response.text.strip()
    except Exception as e:
        return f"Could not research {company}: {str(e)}"


def generate_resume_analysis(resume_text: str, jd_text: str) -> dict:
    """Generate Tal's expert resume analysis with JD-specific insights and company research."""

    # Extract company and role from JD
    company, role = extract_company_and_role(jd_text)

    # Research what works for this company/role
    company_insights = research_company_insights(company, role)

    analysis_prompt = f"""You are Tal - a top-percentile resume specialist who has reviewed lakhs of resumes.
You know exactly what works for specific companies, roles, and seniority levels based on real hiring data.

RESUME:
{resume_text[:5000]}

JOB DESCRIPTION:
{jd_text[:2500]}

COMPANY/ROLE RESEARCH (what works for {company} and {role} positions):
{company_insights}

---

Analyze this resume against this SPECIFIC JD and provide your expert assessment.

STEP 1: Extract key requirements from the JD
- List the must-have skills mentioned
- List the nice-to-have skills
- Identify the seniority level expected
- Note any specific tools/technologies mentioned

STEP 2: Gap analysis
- What JD requirements does the resume ALREADY cover well?
- What JD requirements are MISSING or weak in the resume?
- What's in the resume that's IRRELEVANT to this JD?

STEP 3: Provide your analysis in this EXACT JSON format:
{{
    "company": "{company}",
    "role": "{role}",
    "jd_keywords_present": ["keyword1", "keyword2", "keyword3"],
    "jd_keywords_missing": ["missing1", "missing2", "missing3"],
    "whats_good": [
        {{"point": "specific strength", "jd_alignment": "which JD requirement this matches"}},
        {{"point": "another strength", "jd_alignment": "why this matters for {company}"}},
        {{"point": "third strength", "jd_alignment": "how this fits the role"}}
    ],
    "needs_fixing": [
        {{"issue": "specific gap", "jd_requirement": "what the JD asks for that's missing", "impact": "why this hurts chances at {company}"}},
        {{"issue": "another gap", "jd_requirement": "the JD requirement not addressed", "impact": "how recruiters will react"}},
        {{"issue": "format/structure issue", "jd_requirement": "ATS or seniority mismatch", "impact": "technical reason this fails"}}
    ],
    "what_ill_change": [
        {{"change": "specific fix", "jd_rationale": "exactly which JD requirement this addresses", "company_insight": "why {company} cares about this"}},
        {{"change": "keyword addition", "jd_rationale": "the exact JD phrase I'm matching", "company_insight": "how employees at {company} phrase this"}},
        {{"change": "structural fix", "jd_rationale": "why this format works for {role}", "company_insight": "industry standard for this seniority"}},
        {{"change": "impact rewrite", "jd_rationale": "how this proves JD requirements", "company_insight": "what {company} hiring managers look for"}}
    ],
    "score_before": 52,
    "score_after": 86,
    "seniority_detected": "entry-level/mid-level/senior",
    "ats_issues": ["issue1 if any", "issue2 if any"],
    "format_issues": ["format problem if any"]
}}

CRITICAL RULES:
- Every "needs_fixing" MUST reference a specific JD requirement that's not met
- Every "what_ill_change" MUST explain which JD keyword/requirement it addresses
- Be SPECIFIC - use actual words from the JD and resume
- If the resume format is wrong for the seniority level, call it out
- If there are ATS issues (tables, graphics, weird formatting), flag them

Output ONLY valid JSON. No markdown. No code fences."""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=analysis_prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=2000,
        ),
    )

    # Parse the JSON response
    import json
    text = response.text.strip()

    # Remove markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # Try to find JSON object in the response
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        text = json_match.group()

    try:
        result = json.loads(text)
        result["company"] = result.get("company", company)
        result["role"] = result.get("role", role)
        return result
    except json.JSONDecodeError as e:
        # Fallback with company context
        print(f"JSON parse error: {e}")
        return {
            "company": company,
            "role": role,
            "jd_keywords_present": [],
            "jd_keywords_missing": ["could not parse JD"],
            "whats_good": [
                {"point": "has relevant work experience", "jd_alignment": "shows practical skills"},
                {"point": "includes quantified achievements", "jd_alignment": "metrics prove impact"},
                {"point": "clear contact information", "jd_alignment": "recruiters can reach out"}
            ],
            "needs_fixing": [
                {"issue": "keyword alignment with JD", "jd_requirement": "specific JD terms", "impact": "ATS may filter out"},
                {"issue": "bullet impact could be stronger", "jd_requirement": "proving JD requirements", "impact": "recruiters skim past"},
                {"issue": "structure optimization needed", "jd_requirement": "role-appropriate format", "impact": "key info buried"}
            ],
            "what_ill_change": [
                {"change": "add JD keywords to bullets", "jd_rationale": "match exact JD phrasing", "company_insight": f"what {company} ATS scans for"},
                {"change": "bold key metrics", "jd_rationale": "prove JD requirements visually", "company_insight": "catches recruiter eye"},
                {"change": "tighten to page limit", "jd_rationale": "respect recruiter time", "company_insight": "6 second scan rule"},
                {"change": "preserve project links", "jd_rationale": "prove you ship work", "company_insight": "shows real output"}
            ],
            "score_before": 55,
            "score_after": 84,
            "seniority_detected": "entry-level",
            "ats_issues": [],
            "format_issues": []
        }


def format_analysis_as_tal(analysis: dict) -> str:
    """Format the analysis in Tal's voice for chat display - JD-specific and detailed."""

    company = analysis.get("company", "the company")
    role = analysis.get("role", "this role")
    good = analysis.get("whats_good", [])
    fixing = analysis.get("needs_fixing", [])
    changes = analysis.get("what_ill_change", [])
    before = analysis.get("score_before", 50)
    after = analysis.get("score_after", 85)
    keywords_missing = analysis.get("jd_keywords_missing", [])
    ats_issues = analysis.get("ats_issues", [])

    lines = []

    lines.append(f"alright i've analyzed your resume against this {role} role at {company}\n")

    # Show missing keywords if any
    if keywords_missing and len(keywords_missing) > 0 and keywords_missing[0]:
        missing_str = ", ".join(keywords_missing[:5])
        lines.append(f"jd keywords you're missing: {missing_str.lower()}\n")

    lines.append("what's already working:")
    for item in good[:3]:
        if isinstance(item, dict):
            point = item.get("point", "").lower()
            alignment = item.get("jd_alignment", "") or item.get("why", "")
            lines.append(f"  → {point}")
            if alignment:
                lines.append(f"    (jd match: {alignment.lower()})")
        else:
            lines.append(f"  → {str(item).lower()}")

    lines.append("\nwhat needs fixing:")
    for item in fixing[:3]:
        if isinstance(item, dict):
            issue = item.get("issue", "").lower()
            jd_req = item.get("jd_requirement", "")
            impact = item.get("impact", "")
            lines.append(f"  → {issue}")
            if jd_req:
                lines.append(f"    (jd asks for: {jd_req.lower()})")
            if impact:
                lines.append(f"    (impact: {impact.lower()})")
        else:
            lines.append(f"  → {str(item).lower()}")

    # Show ATS issues if any
    if ats_issues and len(ats_issues) > 0 and ats_issues[0]:
        lines.append("\nats/format issues:")
        for issue in ats_issues[:2]:
            if issue:
                lines.append(f"  ⚠ {issue.lower()}")

    lines.append("\nwhat i'm gonna change:")
    for item in changes[:4]:
        if isinstance(item, dict):
            change = item.get("change", "").lower()
            jd_rationale = item.get("jd_rationale", "") or item.get("rationale", "")
            company_insight = item.get("company_insight", "")
            lines.append(f"  → {change}")
            if jd_rationale:
                lines.append(f"    (why: {jd_rationale.lower()})")
            if company_insight:
                lines.append(f"    ({company.lower()} insight: {company_insight.lower()})")
        else:
            lines.append(f"  → {str(item).lower()}")

    lines.append(f"\nresume score: {before} → {after}")
    lines.append("\nlet me cook")

    return "\n".join(lines)


def generate_latex_resume(resume_text: str, jd_text: str, max_pages: int = 1) -> str:
    """Generate a complete ATS-optimized LaTeX resume using Gemini."""

    page_instruction = f"""
🚨 CRITICAL PAGE LIMIT: EXACTLY {max_pages} PAGE(S). NO EXCEPTIONS. 🚨

To fit on {max_pages} page(s):
- MAX 2-3 bullet points per job/project (pick the most impactful)
- Each bullet: ONE line only (max 15-18 words)
- Keep Education section compact (2 lines max per school)
- Skills section: single line per category
- If content overflows, CUT the least relevant bullets - do NOT add a second page for a 1-page input"""

    prompt = f"""Here is the candidate's current resume content:

---RESUME START---
{resume_text}
---RESUME END---

Here is the target job description:

---JD START---
{jd_text}
---JD END---

Here is the LaTeX template to use (Jake's Resume - the most proven ATS template):

---TEMPLATE START---
{LATEX_TEMPLATE}
---TEMPLATE END---

{page_instruction}

Generate a COMPLETE, COMPILABLE LaTeX resume document following these STRICT rules:

FORMATTING RULES:
1. Use \\textbf{{}} to bold KEY METRICS and ACHIEVEMENTS in bullets (e.g., "\\textbf{{5x faster}}", "\\textbf{{30\\% increase}}", "\\textbf{{150,000+ users}}")
2. Bold the most impressive number/outcome in each bullet - this catches recruiter's eye
3. Keep bullets concise: action verb + what you did + \\textbf{{metric/impact}}

LINKS - CRITICAL (DO NOT SKIP):
4. PRESERVE ALL PROJECT LINKS from the original resume
5. For projects with Video/Website/GitHub links, format as:
   \\textbf{{Project Name}} --- \\href{{URL}}{{Video}} $|$ \\href{{URL}}{{Website}} $|$ \\href{{URL}}{{GitHub}}
6. Extract actual URLs from the resume text - look for patterns like "Video | Website | GitHub" and include the hyperlinks
7. If URLs aren't explicit in text, still include the link labels as placeholders

CONTENT RULES:
8. Use the EXACT template structure (all packages, all custom commands)
9. Fill in candidate's REAL information - do not invent or hallucinate
10. Tailor bullets to match JD keywords where truthful
11. MUST fit on {max_pages} page(s) - be ruthlessly concise
12. Properly escape ALL LaTeX special characters (%, $, &, #, _, use \\% \\$ \\& \\# \\_)

STRUCTURE:
13. Header: name, phone, email, LinkedIn, GitHub (all as \\href links)
14. Sections in order: Education, Experience, Projects, Technical Skills
15. For Experience: Job Title and Company both visible, dates right-aligned
16. For Projects: Project name with tech stack, include ALL original links

Output the complete LaTeX document. Start with \\documentclass, end with \\end{{document}}.
Nothing else. No explanations. No code fences."""

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=RESUME_SYSTEM_PROMPT,
            temperature=0.2,
            max_output_tokens=8000,
        ),
    )

    latex = response.text

    # Strip markdown code fences if Gemini wraps them
    latex = re.sub(r"^```(?:latex|tex)?\s*\n", "", latex)
    latex = re.sub(r"\n```\s*$", "", latex)
    latex = latex.strip()

    # Ensure it starts with \documentclass
    idx = latex.find("\\documentclass")
    if idx > 0:
        latex = latex[idx:]

    return latex


def compile_latex_ytotech(latex_content: str):
    """Compile LaTeX to PDF via latex.ytotech.com API."""
    try:
        resp = requests.post(
            "https://latex.ytotech.com/builds/sync",
            json={
                "compiler": "pdflatex",
                "resources": [{"main": True, "content": latex_content}],
            },
            timeout=120,
        )
        content_type = resp.headers.get("content-type", "")
        # API returns 201 on success, not 200
        if resp.status_code in (200, 201) and "application/pdf" in content_type:
            return resp.content, None
        else:
            err = resp.text[:300] if resp.text else f"HTTP {resp.status_code}"
            return None, f"ytotech: {err}"
    except Exception as e:
        return None, f"ytotech: {str(e)}"


def compile_latex_latexonline(latex_content: str):
    """Compile LaTeX to PDF via latexonline.cc API (GET with URL-encoded text)."""
    try:
        # latexonline.cc uses GET with text in query params
        # For long documents this may fail (414 URI too long)
        import urllib.parse
        encoded = urllib.parse.quote(latex_content, safe="")
        url = f"https://latexonline.cc/compile?text={encoded}"

        # Only try if URL is not too long
        if len(url) > 8000:
            return None, "latexonline: document too long for GET request"

        resp = requests.get(url, timeout=120)
        content_type = resp.headers.get("content-type", "")
        if resp.status_code == 200 and ("application/pdf" in content_type or resp.content[:4] == b"%PDF"):
            return resp.content, None
        else:
            return None, f"latexonline: HTTP {resp.status_code}"
    except Exception as e:
        return None, f"latexonline: {str(e)}"


def compile_latex_texlive_net(latex_content: str):
    """Compile LaTeX to PDF via texlive.net (Overleaf's public compiler)."""
    try:
        resp = requests.post(
            "https://texlive.net/cgi-bin/latexcgi",
            data={
                "filecontents[]": latex_content,
                "filename[]": "document.tex",
                "engine": "pdflatex",
                "return": "pdf",
            },
            timeout=120,
        )
        content_type = resp.headers.get("content-type", "")
        if resp.status_code == 200 and ("application/pdf" in content_type or resp.content[:4] == b"%PDF"):
            return resp.content, None
        else:
            return None, f"texlive.net: HTTP {resp.status_code}"
    except Exception as e:
        return None, f"texlive.net: {str(e)}"


def compile_latex_local(latex_content: str):
    """Try local LaTeX compilers (tectonic, then pdflatex)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "resume.tex")
        with open(tex_path, "w") as f:
            f.write(latex_content)

        for compiler in ["tectonic", "pdflatex"]:
            try:
                if compiler == "tectonic":
                    cmd = ["tectonic", tex_path]
                else:
                    cmd = [
                        "pdflatex",
                        "-interaction=nonstopmode",
                        f"-output-directory={tmpdir}",
                        tex_path,
                    ]
                subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                pdf_path = os.path.join(tmpdir, "resume.pdf")
                if os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        return f.read(), None
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

    return None, "No local LaTeX compiler available"


def compile_latex(latex_content: str):
    """Try multiple compilation methods until one succeeds."""
    errors = []

    # 1. Try ytotech (most reliable for complex templates)
    pdf, err = compile_latex_ytotech(latex_content)
    if pdf:
        return pdf, None
    if err:
        errors.append(err)

    # 2. Try latexonline.cc
    pdf, err = compile_latex_latexonline(latex_content)
    if pdf:
        return pdf, None
    if err:
        errors.append(err)

    # 3. Try texlive.net (Overleaf's public compiler)
    pdf, err = compile_latex_texlive_net(latex_content)
    if pdf:
        return pdf, None
    if err:
        errors.append(err)

    # 4. Try local compilers
    pdf, err = compile_latex_local(latex_content)
    if pdf:
        return pdf, None
    if err:
        errors.append(err)

    return None, " | ".join(errors)


# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.stage = "awaiting_resume"
    st.session_state.resume_text = None
    st.session_state.resume_pages = 1
    st.session_state.jd_text = None
    st.session_state.pdf_bytes = None
    st.session_state.latex_content = None
    st.session_state.analysis = None

    # Tal's opening message
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": (
                "yo. i'm tal\n\n"
                "drop your resume, and a JD here. let's see what we're working with\n\n"
                "i'll turn it into something that actually gets callbacks (i read lakhs of resumes daily - so i got this bro)"
            ),
        }
    )

# ─────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">🦊 tal - resume fixer</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">drop your resume. paste the jd. get a resume that actually works.</p>',
    unsafe_allow_html=True,
)
st.divider()

# ─────────────────────────────────────────────────────────────
# RENDER CHAT HISTORY
# ─────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    avatar = TAL_AVATAR if msg["role"] == "assistant" else USER_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])


# ─────────────────────────────────────────────────────────────
# STAGE: AWAITING RESUME UPLOAD
# ─────────────────────────────────────────────────────────────
if st.session_state.stage == "awaiting_resume":
    uploaded_file = st.file_uploader(
        "upload your resume (pdf)",
        type=["pdf"],
        help="your current resume as a PDF",
    )

    if uploaded_file is not None:
        with st.spinner("reading your resume..."):
            resume_text, page_count = extract_pdf_text(uploaded_file)

        if not resume_text.strip():
            st.error(
                "couldn't extract text from this PDF. "
                "make sure it's not a scanned image - needs to be a text-based PDF."
            )
        else:
            st.session_state.resume_text = resume_text
            st.session_state.resume_pages = page_count

            # Show user upload in chat
            st.session_state.messages.append(
                {"role": "user", "content": f"uploaded: {uploaded_file.name} ({page_count} page{'s' if page_count > 1 else ''})"}
            )

            # Tal acknowledges the resume
            with st.spinner("tal is reading your resume..."):
                ack_prompt = (
                    f"The user just uploaded their resume ({page_count} pages). "
                    f"Here's the extracted text (first 3000 chars):\n\n"
                    f"{resume_text[:3000]}\n\n"
                    f"Acknowledge you received it. Make ONE brief, specific observation "
                    f"about their background (a role, company, or skill you noticed). "
                    f"Then ask them to paste the job description they're targeting.\n\n"
                    f"Keep it short: 2-3 short lines max. lowercase. punchy. no markdown."
                )
                ack = get_tal_response(ack_prompt)

            st.session_state.messages.append({"role": "assistant", "content": ack})
            st.session_state.stage = "awaiting_jd"
            st.rerun()


# ─────────────────────────────────────────────────────────────
# STAGE: AWAITING JOB DESCRIPTION
# ─────────────────────────────────────────────────────────────
elif st.session_state.stage == "awaiting_jd":
    jd_text = st.text_area(
        "paste the job description",
        height=250,
        placeholder="paste the full job description here... the more detail the better",
    )

    if st.button("send to tal →", use_container_width=True, type="primary"):
        if jd_text.strip():
            st.session_state.jd_text = jd_text.strip()

            # Truncated JD for chat display
            display_jd = jd_text[:300] + ("..." if len(jd_text) > 300 else "")
            st.session_state.messages.append({"role": "user", "content": display_jd})

            # Tal's "researching" message
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "got it. gimme a minute\n\n"
                        "researching what works for this company and role\n\n"
                        "then i'll go through your resume line by line against this jd"
                    ),
                }
            )

            st.session_state.stage = "processing"
            st.rerun()
        else:
            st.warning("paste the job description first!")


# ─────────────────────────────────────────────────────────────
# STAGE: PROCESSING (analyze + generate LaTeX + compile)
# ─────────────────────────────────────────────────────────────
elif st.session_state.stage == "processing":
    with st.status("🦊 tal is analyzing your resume...", expanded=True) as status:

        # Step 1: Generate analysis with company research
        st.write("researching what works for this company/role...")
        time.sleep(0.3)
        st.write("analyzing your resume against the JD requirements...")
        try:
            analysis = generate_resume_analysis(
                st.session_state.resume_text,
                st.session_state.jd_text,
            )
            st.session_state.analysis = analysis

            # Format and add to chat
            analysis_msg = format_analysis_as_tal(analysis)
            st.session_state.messages.append({"role": "assistant", "content": analysis_msg})

        except Exception as e:
            # Non-fatal - continue without analysis
            st.write(f"(skipping detailed analysis: {e})")
            analysis = None

        # Step 2: Generate LaTeX
        status.update(label="🦊 tal is rewriting your resume...", expanded=True)
        st.write("rewriting with impact-first bullets...")

        max_pages = st.session_state.resume_pages  # Match input page count

        try:
            latex_content = generate_latex_resume(
                st.session_state.resume_text,
                st.session_state.jd_text,
                max_pages=max_pages,
            )
            st.session_state.latex_content = latex_content
        except Exception as e:
            status.update(label="something went wrong", state="error")
            st.error(f"Gemini error: {e}")
            st.session_state.stage = "awaiting_jd"
            st.stop()

        # Step 3: Compile to PDF
        st.write("compiling LaTeX to PDF...")
        pdf_bytes, error = compile_latex(latex_content)

        if pdf_bytes:
            st.session_state.pdf_bytes = pdf_bytes
            status.update(label="resume is ready!", state="complete")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "done. your resume is ready\n\n"
                        "ats-friendly. tailored to the jd. no fluff\n\n"
                        "hit download and go get that job"
                    ),
                }
            )
        else:
            # Log the error for debugging
            st.session_state.compile_error = error
            status.update(
                label="latex generated - pdf compilation failed", state="error"
            )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": (
                        "ran into a hiccup compiling the pdf\n\n"
                        "download the .tex file and drop it at overleaf.com\n\n"
                        "it'll work there for sure"
                    ),
                }
            )

        st.session_state.stage = "done"
        st.rerun()


# ─────────────────────────────────────────────────────────────
# STAGE: DONE - PDF preview + download
# ─────────────────────────────────────────────────────────────
elif st.session_state.stage == "done":
    st.markdown("---")

    if st.session_state.pdf_bytes:
        # ── In-browser PDF preview using object tag (more compatible) ──
        pdf_base64 = base64.b64encode(st.session_state.pdf_bytes).decode("utf-8")
        
        # Use object tag with fallback - works better across browsers
        pdf_display = f'''
        <object data="data:application/pdf;base64,{pdf_base64}" 
                type="application/pdf" 
                width="100%" 
                height="600"
                style="border: 1px solid #444; border-radius: 8px;">
            <embed src="data:application/pdf;base64,{pdf_base64}" 
                   type="application/pdf"
                   width="100%" 
                   height="600" />
        </object>
        '''
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        # Also show a message about downloading
        st.caption("📄 preview above • download below for best quality")
        st.markdown("<br>", unsafe_allow_html=True)

        # ── Download buttons ──
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            st.download_button(
                label="📥 download resume PDF",
                data=st.session_state.pdf_bytes,
                file_name="tailored_resume.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )

        with col2:
            if st.session_state.latex_content:
                st.download_button(
                    label="📄 download .tex source",
                    data=st.session_state.latex_content,
                    file_name="resume.tex",
                    mime="text/plain",
                    use_container_width=True,
                )

        with col3:
            if st.button("🔄 redo", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

    else:
        # Fallback: PDF compilation failed, offer retry + .tex + Overleaf
        st.warning(
            "couldn't compile the PDF automatically. "
            "you can retry or download the .tex file and paste it at "
            "[overleaf.com](https://www.overleaf.com/project)"
        )

        # Show detailed error in expander for debugging
        if hasattr(st.session_state, "compile_error") and st.session_state.compile_error:
            with st.expander("show compilation errors"):
                st.code(st.session_state.compile_error, language="text")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🔄 retry PDF compilation", use_container_width=True, type="primary"):
                # Retry compilation
                st.session_state.stage = "retry_compile"
                st.rerun()

        with col2:
            if st.session_state.latex_content:
                st.download_button(
                    label="📄 download .tex file",
                    data=st.session_state.latex_content,
                    file_name="resume.tex",
                    mime="text/plain",
                    use_container_width=True,
                )

        with col3:
            if st.button("🔄 start over", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()


# ─────────────────────────────────────────────────────────────
# STAGE: RETRY COMPILE
# ─────────────────────────────────────────────────────────────
elif st.session_state.stage == "retry_compile":
    with st.status("🔄 retrying PDF compilation...", expanded=True) as status:
        st.write("trying latex.ytotech.com...")
        pdf_bytes, error = compile_latex(st.session_state.latex_content)

        if pdf_bytes:
            st.session_state.pdf_bytes = pdf_bytes
            st.session_state.compile_error = None
            status.update(label="success! PDF compiled", state="complete")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": "got it this time. pdf is ready",
                }
            )
        else:
            st.session_state.compile_error = error
            status.update(label="compilation failed again", state="error")

    st.session_state.stage = "done"
    st.rerun()
