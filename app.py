import os
import json
import pdfplumber
from docx import Document
from PIL import Image
import pytesseract
from flask import Flask, request, render_template
import openai
from dotenv import load_dotenv

# Load API Key from .env
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ─── Configuration ─────────────────────────────────────────────────────────────
UPLOAD_FOLDER = 'uploads'
DATABASE_FILE = 'resumes.json'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MODEL = "gpt-4o"

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ─── Helpers ────────────────────────────────────────────────────────────────────
def extract_text(file_path, ext):
    if ext == 'pdf':
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    if ext == 'docx':
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    if ext in ('png','jpg','jpeg'):
        return pytesseract.image_to_string(Image.open(file_path))
    return ""

def parse_with_openai(text):
    prompt = f"""
You are a resume parser. Extract into JSON with these fields:
- name
- email
- phone
- education: list of {{institution, degree, start, end}}
- experience: list of {{company, position, start, end, summary}}
- skills: list of strings
Return only valid JSON.
"""
    resp = openai.ChatCompletion.create(
        model=MODEL,
        messages=[{"role":"user","content": prompt + "\n\nRESUME:\n" + text}]
    )
    return json.loads(resp.choices[0].message.content)

def save_to_db(record):
    db = []
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE,'r') as f:
            db = json.load(f)
    db.append(record)
    with open(DATABASE_FILE,'w') as f:
        json.dump(db, f, indent=2)

def load_db():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE,'r') as f:
            return json.load(f)
    return []

def search_by_keyword(keyword):
    results = []
    kw = keyword.lower()
    for c in load_db():
        text_blob = json.dumps(c).lower()
        if kw in text_blob:
            results.append(c)
    return results

# ─── Routes ─────────────────────────────────────────────────────────────────────
@app.route('/', methods=['GET','POST'])
def index():
    message = ""
    results = []
    if request.method == 'POST':
        if 'resume' in request.files:
            f = request.files['resume']
            fn = f.filename
            path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
            f.save(path)

            ext = fn.rsplit('.',1)[-1].lower()
            raw = extract_text(path, ext)
            parsed = parse_with_openai(raw)
            parsed['filename'] = fn

            save_to_db(parsed)
            message = f"Parsed and saved: {parsed.get('name','<unknown>')}"

        elif 'keyword' in request.form:
            kw = request.form['keyword']
            results = search_by_keyword(kw)

    return render_template('index.html',
                           message=message,
                           results=results)

if __name__ == '__main__':
    app.run(debug=True)
