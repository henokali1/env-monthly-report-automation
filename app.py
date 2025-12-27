import os
import json
import datetime
import tkinter as tk
from tkinter import filedialog
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm
from PIL import Image, ImageFilter
import requests
import uuid
import webbrowser
import calendar
from threading import Timer

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'static', 'uploads')
app.config['CONFIG_FILE'] = os.path.join(os.getcwd(), 'config.json')

# API Configuration from User Sample
BASE_URL = "https://env-tls.henokcodes.com"

class APIClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.access_token = None
        self.refresh_token = None

    def login(self):
        """Obtain JWT tokens from the Django API."""
        if not self.username or not self.password:
            return False
            
        url = f"{self.base_url}/api/token/"
        try:
            response = requests.post(url, json={
                "username": self.username,
                "password": self.password
            }, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get('access')
            self.refresh_token = data.get('refresh')
            return True
        except requests.exceptions.RequestException as e:
            print(f"Login failed: {e}")
            return False

    def get_work_logs(self, start_date=None, end_date=None, tag=None):
        """Fetch WorkLog data from the secure endpoint."""
        if not self.access_token:
            if not self.login():
                return None

        url = f"{self.base_url}/work-logs/api/logs/"
        params = {}
        if start_date: params['start_date'] = start_date
        if end_date: params['end_date'] = end_date
        if tag: params['tag'] = tag

        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 401:
                if self.login():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    response = requests.get(url, params=params, headers=headers, timeout=10)
                else:
                    return None

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to fetch data: {e}")
            return None

def load_config():
    if os.path.exists(app.config['CONFIG_FILE']):
        with open(app.config['CONFIG_FILE'], 'r') as f:
            try:
                config = json.load(f)
            except:
                config = {}
    else:
        config = {}
        
    defaults = {
        "fm01_template": "",
        "fm02_template": "",
        "fm01_base_directory": "",
        "fm02_base_directory": ""
    }
    for key, val in defaults.items():
        if key not in config:
            config[key] = val
    return config

def save_config(config):
    with open(app.config['CONFIG_FILE'], 'w') as f:
        json.dump(config, f)

def process_image(input_path, output_path, target_width=328, target_height=278):
    """
    Resizes image to target size with blurred background.
    """
    img = Image.open(input_path)
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height

    # Create blurred background
    if img_ratio > target_ratio:
        # Image is wider than target
        bg_scale = target_width / img.width
        bg_width = target_width
        bg_height = int(img.height * (target_width / img.width))
    else:
        # Image is taller than target
        bg_scale = target_height / img.height
        bg_height = target_height
        bg_width = int(img.width * (target_height / img.height))

    # For blurred background, we want it to COVER the area
    if img_ratio > target_ratio:
        bg_cover_scale = target_height / img.height
    else:
        bg_cover_scale = target_width / img.width
    
    bg_img = img.resize((int(img.width * bg_cover_scale), int(img.height * bg_cover_scale)), Image.Resampling.LANCZOS)
    
    # Crop the background to exact target size
    left = (bg_img.width - target_width) / 2
    top = (bg_img.height - target_height) / 2
    right = (bg_img.width + target_width) / 2
    bottom = (bg_img.height + target_height) / 2
    bg_img = bg_img.crop((left, top, right, bottom))
    bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=15))

    # Resize original image to FIT within target size
    if img_ratio > target_ratio:
        fit_width = target_width
        fit_height = int(target_width / img_ratio)
    else:
        fit_height = target_height
        fit_width = int(target_height * img_ratio)
    
    fit_img = img.resize((fit_width, fit_height), Image.Resampling.LANCZOS)

    # Paste fit image onto blurred background
    paste_x = (target_width - fit_width) // 2
    paste_y = (target_height - fit_height) // 2
    bg_img.paste(fit_img, (paste_x, paste_y))
    
    bg_img.convert('RGB').save(output_path, "JPEG")

@app.route('/')
def index():
    config = load_config()
    
    # Default date: previous month
    now = datetime.datetime.now()
    first_of_this_month = now.replace(day=1)
    last_month = first_of_this_month - datetime.timedelta(days=1)
    
    default_month = last_month.strftime('%B')
    default_year = last_month.strftime('%Y')
    
    return render_template('index.html', config=config, default_month=default_month, default_year=default_year)

@app.route('/api/pick_file', methods=['POST'])
def pick_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    file_path = filedialog.askopenfilename(filetypes=[("Word Documents", "*.docx")])
    root.destroy()
    return jsonify({"path": file_path})

@app.route('/api/pick_folder', methods=['POST'])
def pick_folder():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder_path = filedialog.askdirectory()
    root.destroy()
    return jsonify({"path": folder_path})

@app.route('/api/fetch_logs', methods=['POST'])
def fetch_logs():
    data = request.json
    month_name = data.get('month')
    year = data.get('year')
    report_type = data.get('report_type')
    
    # Credentials from environment variables
    username = os.environ.get("API_USERNAME")
    password = os.environ.get("API_PASSWORD")
    
    # Hardcoded Tag IDs: FM01 is 1, FM02 is 2
    tag = "1" if report_type == 'FM01' else "2"
    
    if not username or not password:
        return jsonify({"error": "API_USERNAME or API_PASSWORD environment variables are not set."}), 400
        
    try:
        month_num = datetime.datetime.strptime(month_name, "%B").month
        last_day = calendar.monthrange(int(year), month_num)[1]
        start_date = f"{year}-{month_num:02d}-01"
        end_date = f"{year}-{month_num:02d}-{last_day:02d}"
    except Exception as e:
        return jsonify({"error": f"Invalid date: {str(e)}"}), 400

    client = APIClient(BASE_URL, username, password)
    logs = client.get_work_logs(start_date=start_date, end_date=end_date, tag=tag)
    
    if logs is not None:
        # Extract task descriptions
        # Assuming logs matches the structure from the sample snippet
        # Sample snippet shows 'data' key in response if success
        # Wait, the sample Flask app returns jsonify({"data": logs}), so let's check what get_work_logs returns.
        # get_work_logs returns response.json(), which is the actual list or object from Django.
        
        # Format logs as one task per line for the textarea
        log_lines = []
        for entry in logs:
            desc = entry.get('task_description', '').strip()
            if desc:
                log_lines.append(desc)
        
        return jsonify({
            "status": "success",
            "logs": "\n".join(log_lines)
        })
    else:
        return jsonify({"error": "Could not retrieve data from API. Check environment variables and connection."}), 500

@app.route('/api/rephrase_logs', methods=['POST'])
def rephrase_logs():
    data = request.json
    logs = data.get('logs', '')
    report_type = data.get('report_type')
    
    if not logs.strip():
        return jsonify({"error": "No logs to rephrase"}), 400
        
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY environment variable not set."}), 400

    # Load prompt from file
    prompt_file = "fm01-prompt.md" if report_type == "FM01" else "fm02-prompt.md"
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except Exception as e:
        return jsonify({"error": f"Failed to read prompt file {prompt_file}: {str(e)}"}), 500

    # Combine prompt with logs
    full_prompt = f"{prompt_template}\n\n{logs}"

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-4o-mini", # Using 4o-mini for speed and cost-efficiency
                "messages": [
                    {"role": "system", "content": "You are a professional technical writer for engineering reports."},
                    {"role": "user", "content": full_prompt}
                ],
                "temperature": 0.3
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        rephrased_text = result['choices'][0]['message']['content'].strip()
        
        return jsonify({
            "status": "success",
            "logs": rephrased_text
        })
    except Exception as e:
        return jsonify({"error": f"AI Rephrasing failed: {str(e)}"}), 500

@app.route('/api/save_settings', methods=['POST'])
def save_settings():
    data = request.json
    config = load_config()
    config.update(data)
    save_config(config)
    return jsonify({"status": "success"})

@app.route('/api/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    processed_filename = "proc_" + filename
    processed_path = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
    
    try:
        process_image(filepath, processed_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
    return jsonify({
        "original": filename,
        "processed": processed_filename,
        "url": f"/static/uploads/{processed_filename}"
    })

@app.route('/api/rotate_image', methods=['POST'])
def rotate_image():
    data = request.json
    original_filename = data.get('original')
    processed_filename = data.get('processed')
    
    if not original_filename or not processed_filename:
        return jsonify({"error": "Missing filenames"}), 400
        
    original_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
    processed_path = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
    
    if not os.path.exists(original_path):
        return jsonify({"error": "Original image not found"}), 404
        
    try:
        img = Image.open(original_path)
        # Rotate 90 degrees clockwise
        rotated_img = img.transpose(Image.ROTATE_270)
        
        # Save back to original path (maintaining original format if possible, or just JPEG)
        if img.format:
            rotated_img.save(original_path, format=img.format)
        else:
            rotated_img.save(original_path)
            
        # Re-process the image to update the preview and the version used in docx
        process_image(original_path, processed_path)
        
        # return new URL with cache buster
        return jsonify({
            "status": "success",
            "url": f"/static/uploads/{processed_filename}?t={uuid.uuid4().hex[:8]}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate_report', methods=['POST'])
def generate_report():
    data = request.json
    report_type = data.get('report_type') # 'FM01' or 'FM02'
    month = data.get('month')
    year = data.get('year')
    images = data.get('images', []) # List of processed filenames in order
    work_log = data.get('work_log', "")
    
    config = load_config()
    template_path = config.get('fm01_template') if report_type == 'FM01' else config.get('fm02_template')
    base_dir = config.get('fm01_base_directory') if report_type == 'FM01' else config.get('fm02_base_directory')

    if not template_path or not os.path.exists(template_path):
        return jsonify({"error": f"Template for {report_type} not found. Please set it in settings."}), 400
    if not base_dir:
        return jsonify({"error": f"Base directory for {report_type} not set. Please set it in settings."}), 400

    # Ensure month and year are valid
    try:
        month_num = datetime.datetime.strptime(month, "%B").month
        month_str = f"{month_num:02d}"
    except ValueError:
        return jsonify({"error": f"Invalid month: {month}"}), 400

    # Create directory structure: base_directory\YYYY\MM\
    output_dir = os.path.join(base_dir, str(year), month_str)
    os.makedirs(output_dir, exist_ok=True)

    # Filename
    display_type = "FM01 MET" if report_type == "FM01" else "FM02 IT"
    filename = f"{display_type} Monthly Operational Report {month} {year}.docx"
    output_path = os.path.join(output_dir, filename)

    try:
        doc = DocxTemplate(template_path)
        
        # Process work logs to continue numbering from 7
        # We assume the template already has "7. " before the {{work_logs}} placeholder
        lines = [line.strip() for line in work_log.split('\n') if line.strip()]
        formatted_work_logs = ""
        for i, line in enumerate(lines):
            if i == 0:
                formatted_work_logs += line
            else:
                num = 7 + i
                formatted_work_logs += f"{num}. {line}"
            
            if i < len(lines) - 1:
                formatted_work_logs += "\n"

        context = {
            'Month': month,
            'YYYY': year,
            'work_logs': formatted_work_logs
        }
        
        # Add images
        for i, img_name in enumerate(images):
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], img_name)
            if os.path.exists(img_path):
                # docxtpl uses InlineImage to inject images
                context[f'img{i+1}'] = InlineImage(doc, img_path, width=Mm(86.8), height=Mm(73.6)) # ~328x278px at 96dpi is roughly 86.8x73.6mm
            else:
                context[f'img{i+1}'] = ""

        # Fill remaining images if less than 8 provided (though UI requires 8)
        for i in range(len(images), 8):
            context[f'img{i+1}'] = ""

        doc.render(context)
        doc.save(output_path)
        
        return jsonify({"status": "success", "file_path": output_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000")

if __name__ == '__main__':
    Timer(1.5, open_browser).start()
    app.run(debug=True, port=5000)
