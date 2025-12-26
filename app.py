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
import uuid
import webbrowser
from threading import Timer

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'static', 'uploads')
app.config['CONFIG_FILE'] = os.path.join(os.getcwd(), 'config.json')

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def load_config():
    if os.path.exists(app.config['CONFIG_FILE']):
        with open(app.config['CONFIG_FILE'], 'r') as f:
            return json.load(f)
    return {
        "fm01_template": "",
        "fm02_template": "",
        "fm01_base_directory": "",
        "fm02_base_directory": ""
    }

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
