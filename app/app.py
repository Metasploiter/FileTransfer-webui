import os
import time
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
from datetime import datetime
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
MAX_CONTENT_LENGTH = 10 * 1024 * 1024 * 1024  # 10 GB

app.config.update({
    'UPLOAD_FOLDER': UPLOAD_FOLDER,
    'MAX_CONTENT_LENGTH': MAX_CONTENT_LENGTH,
    'SECRET_KEY': 'your-secret-key-here'
})

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Track upload progress globally
upload_progress = {}

# Allow all file types
def allowed_file(filename):
    return '.' in filename  # Only check if it has an extension

# Custom template filters
@app.template_filter('datetime')
def format_datetime(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

@app.template_filter('filesize')
def format_filesize(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

@app.route('/')
def index():
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.isfile(path):
            files.append({
                'name': filename,
                'size': os.path.getsize(path),
                'date': os.path.getmtime(path),
                'type': filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            })

    files.sort(key=lambda x: x['date'], reverse=True)
    return render_template('index.html', files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    upload_progress.clear()
    
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        upload_progress[filename] = {
            'total': request.content_length,
            'uploaded': 0,
            'start_time': time.time(),
            'filename': filename
        }

        try:
            chunk_size = 4096
            with open(file_path, 'wb') as f:
                while True:
                    chunk = file.stream.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    upload_progress[filename]['uploaded'] += len(chunk)

            upload_time = time.time() - upload_progress[filename]['start_time']
            return jsonify({
                'status': 'success',
                'message': f'{filename} uploaded successfully!',
                'filename': filename,
                'size': os.path.getsize(file_path),
                'upload_time': f'{upload_time:.1f} seconds'
            })
        except Exception as e:
            if filename in upload_progress:
                del upload_progress[filename]
            return jsonify({'status': 'error', 'message': f'Error uploading file: {str(e)}'}), 500
    else:
        return jsonify({'status': 'error', 'message': 'File type not allowed'}), 400

@app.route('/progress/<filename>')
def upload_progress_api(filename):
    if filename in upload_progress:
        progress = upload_progress[filename]
        percentage = (progress['uploaded'] / progress['total']) * 100 if progress['total'] else 0
        elapsed = time.time() - progress['start_time']
        speed = progress['uploaded'] / elapsed if elapsed > 0 else 0
        remaining = (progress['total'] - progress['uploaded']) / speed if speed > 0 else 0

        return jsonify({
            'filename': filename,
            'total': progress['total'],
            'uploaded': progress['uploaded'],
            'percentage': percentage,
            'speed': speed,
            'remaining': remaining,
            'elapsed': elapsed
        })
    return jsonify({'error': 'No upload in progress'}), 404

@app.route('/download/<filename>')
def download_file(filename):
    if '..' in filename or filename.startswith('/'):
        return "Invalid filename", 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        return "File not found", 404

    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        as_attachment=True
    )

@app.route('/delete/<filename>')
def delete_file(filename):
    if '..' in filename or filename.startswith('/'):
        return "Invalid filename", 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            flash(f'{filename} deleted successfully!', 'success')
        except Exception as e:
            flash(f'Error deleting file: {str(e)}', 'error')
    else:
        flash('File not found', 'error')

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
