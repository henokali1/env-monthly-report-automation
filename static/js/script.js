let uploadedPhotos = new Array(8).fill(null);

async function pickPath(elementId, type) {
    const endpoint = type === 'file' ? '/api/pick_file' : '/api/pick_folder';
    try {
        const response = await fetch(endpoint, { method: 'POST' });
        const data = await response.json();
        if (data.path) {
            document.getElementById(elementId).value = data.path;
            // Save settings automatically
            saveSettings();
        }
    } catch (error) {
        logStatus(`❌ Error picking ${type}: ${error.message}`, 'error');
    }
}

async function saveSettings() {
    const settings = {
        fm01_template: document.getElementById('fm01_template').value,
        fm02_template: document.getElementById('fm02_template').value,
        fm01_base_directory: document.getElementById('fm01_base_directory').value,
        fm02_base_directory: document.getElementById('fm02_base_directory').value
    };
    await fetch('/api/save_settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
    });
}

function triggerUpload(index) {
    const input = document.getElementById('photo_input');
    // Store current slot index to track where single upload should go
    input.dataset.targetIndex = index;
    input.click();
}

document.getElementById('photo_input').addEventListener('change', async function (e) {
    const files = e.target.files;
    if (files.length === 0) return;

    const targetIndex = parseInt(this.dataset.targetIndex);

    if (files.length === 1 && !isNaN(targetIndex)) {
        // Single upload to specific slot
        await uploadPhoto(files[0], targetIndex);
    } else {
        // Bulk upload: fill starting from first empty slot or from start
        let currentSlot = 0;
        for (let i = 0; i < files.length && currentSlot < 8; i++) {
            // Find next empty slot
            while (currentSlot < 8 && uploadedPhotos[currentSlot]) {
                currentSlot++;
            }
            if (currentSlot < 8) {
                await uploadPhoto(files[i], currentSlot);
                currentSlot++;
            }
        }
    }
    this.value = ''; // Reset input
    this.dataset.targetIndex = '';
});

async function uploadPhoto(file, index) {
    logStatus(`📤 Uploading and processing photo ${index + 1}...`);
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload_image', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.error) throw new Error(data.error);

        uploadedPhotos[index] = data;
        updatePhotoGrid();
        logStatus(`✅ Photo ${index + 1} processed!`, 'success');
    } catch (error) {
        logStatus(`❌ Error uploading photo ${index + 1}: ${error.message}`, 'error');
    }
}

function updatePhotoGrid() {
    const grid = document.getElementById('photo_grid');
    const slots = grid.querySelectorAll('.photo-slot');

    uploadedPhotos.forEach((photo, i) => {
        const slot = slots[i];
        if (photo) {
            slot.classList.add('filled');
            slot.innerHTML = `
                <span class="order-num">${i + 1}</span>
                <img src="${photo.url}" alt="Photo ${i + 1}">
                <button class="remove-btn" onclick="removePhoto(${i}, event)">✕</button>
            `;
        } else {
            slot.classList.remove('filled');
            slot.innerHTML = `
                <span class="order-num">${i + 1}</span>
                <div class="upload-placeholder">
                    <span>➕</span>
                    <span>Upload</span>
                </div>
            `;
        }
    });
}

function removePhoto(index, event) {
    event.stopPropagation();
    uploadedPhotos[index] = null;
    updatePhotoGrid();
    logStatus(`🗑️ Removed photo ${index + 1}`);
}

// Drag and Drop Logic
let draggedIndex = null;

function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev) {
    draggedIndex = parseInt(ev.currentTarget.dataset.index);
    ev.dataTransfer.setData("text", draggedIndex);
}

function drop(ev) {
    ev.preventDefault();
    const targetIndex = parseInt(ev.currentTarget.dataset.index);

    if (draggedIndex !== null && draggedIndex !== targetIndex) {
        // Swap elements in the array
        const temp = uploadedPhotos[draggedIndex];
        uploadedPhotos[draggedIndex] = uploadedPhotos[targetIndex];
        uploadedPhotos[targetIndex] = temp;

        updatePhotoGrid();
        logStatus(`🔄 Swapped photo ${draggedIndex + 1} with ${targetIndex + 1}`);
    }
}

async function generateReport() {
    // Validation
    const filledCount = uploadedPhotos.filter(p => p !== null).length;
    if (filledCount < 8) {
        logStatus(`⚠️ Please upload all 8 photos before generating the report. (${filledCount}/8)`, 'error');
        alert("8 photos are required!");
        return;
    }

    const reportType = document.querySelector('input[name="report_type"]:checked').value;
    const month = document.getElementById('month').value;
    const year = document.getElementById('year').value;
    const workLog = document.getElementById('work_log').value;

    const data = {
        report_type: reportType,
        month: month,
        year: year,
        work_log: workLog,
        images: uploadedPhotos.map(p => p.processed)
    };

    updateProgress(10);
    logStatus(`🚀 Starting report generation for ${reportType} ${month} ${year}...`);

    try {
        updateProgress(30);
        logStatus(`📂 Preparing document and folders...`);

        const response = await fetch('/api/generate_report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.error) throw new Error(result.error);

        updateProgress(100);
        logStatus(`🎉 SUCCESS! Report generated at:`, 'success');
        logStatus(`📍 ${result.file_path}`, 'success');
        alert(`Report generated successfully!\n\nLocation: ${result.file_path}`);

    } catch (error) {
        updateProgress(0);
        logStatus(`❌ Failed to generate report: ${error.message}`, 'error');
        alert(`Error: ${error.message}`);
    }
}

function logStatus(message, type = '') {
    const log = document.getElementById('status_log');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = message;
    log.insertBefore(entry, log.firstChild);
}

function updateProgress(percent) {
    const bar = document.getElementById('progress-bar');
    bar.style.width = percent + '%';
}
