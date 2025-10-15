document.addEventListener('DOMContentLoaded', () => {
    // --- DOM ELEMENTS ---
    const uploadForm = document.getElementById('upload-form');
    const fileInput = document.getElementById('file-input');
    const processButton = document.getElementById('process-button');
    const editorContainer = document.getElementById('editor-container');
    const previewContainer = document.getElementById('preview-container');
    const canvas = document.getElementById('editor-canvas');
    const ctx = canvas.getContext('2d');
    const pdfPagesList = document.getElementById('pdf-pages-list');
    const generatePdfButton = document.getElementById('generate-pdf-button');

    // --- STATE ---
    const backendUrl = 'http://127.0.0.1:5000';
    let state = {
        originalImage: null,
        file_id: null,
        corners: [],
        is_book: false,
        divider: [],
        imageScale: 1,
        dragging: false,
        dragTarget: null,
        dragIndex: -1,
        pdfPages: [],
        lastProcessedUrls: [],
    };

    // 1. UPLOAD LOGIC
    uploadForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        previewContainer.innerHTML = '<p>Uploading and analyzing...</p>';
        editorContainer.style.display = 'none';
        processButton.style.display = 'none';

        try {
            const response = await fetch(`${backendUrl}/upload`, { method: 'POST', body: formData });
            if (!response.ok) throw new Error('Upload failed');

            const data = await response.json();
            state.file_id = data.file_id;
            state.is_book = data.is_book;

            state.originalImage = new Image();
            state.originalImage.crossOrigin = "Anonymous";
            state.originalImage.onload = () => setupCanvas(data.corners, data.divider);
            state.originalImage.src = `${backendUrl}${data.original_url}`;

        } catch (error) {
            previewContainer.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
        }
    });

    // 2. CANVAS SETUP
    function setupCanvas(initialCorners, initialDivider) {
        const maxCanvasWidth = 800;
        state.imageScale = maxCanvasWidth / state.originalImage.width;

        canvas.width = state.originalImage.width * state.imageScale;
        canvas.height = state.originalImage.height * state.imageScale;

        state.corners = initialCorners.map(p => ({ x: p[0] * state.imageScale, y: p[1] * state.imageScale }));
        if (state.is_book && initialDivider) {
            state.divider = initialDivider.map(p => ({ x: p[0] * state.imageScale, y: p[1] * state.imageScale }));
        }

        canvas.addEventListener('mousedown', onMouseDown);
        canvas.addEventListener('mousemove', onMouseMove);
        canvas.addEventListener('mouseup', onMouseUp);
        canvas.addEventListener('mouseout', onMouseUp);

        editorContainer.style.display = 'block';
        processButton.style.display = 'block';
        previewContainer.innerHTML = '';

        draw();
    }

    // 3. DRAWING LOGIC (unchanged from before)
    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(state.originalImage, 0, 0, canvas.width, canvas.height);
        ctx.beginPath();
        ctx.moveTo(state.corners[0].x, state.corners[0].y);
        for (let i = 1; i < 4; i++) { ctx.lineTo(state.corners[i].x, state.corners[i].y); }
        ctx.closePath();
        ctx.fillStyle = 'rgba(255, 255, 0, 0.3)';
        ctx.fill();
        ctx.strokeStyle = 'yellow';
        ctx.lineWidth = 2;
        ctx.stroke();
        drawGrid(7, 10);
        state.corners.forEach(corner => {
            ctx.beginPath();
            ctx.arc(corner.x, corner.y, 10, 0, 2 * Math.PI);
            ctx.fillStyle = 'red';
            ctx.fill();
        });
        if (state.is_book) { drawDivider(); }
    }
    function drawGrid(h_div, v_div) {
        ctx.strokeStyle = 'rgba(0, 0, 255, 0.5)';
        ctx.lineWidth = 1;
        const [tl, tr, br, bl] = state.corners;
        for (let i = 1; i < v_div; i++) {
            const t = i / (v_div - 1);
            const p1 = { x: tl.x * (1 - t) + bl.x * t, y: tl.y * (1 - t) + bl.y * t };
            const p2 = { x: tr.x * (1 - t) + br.x * t, y: tr.y * (1 - t) + br.y * t };
            ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
        }
        for (let i = 1; i < h_div; i++) {
            const t = i / (h_div - 1);
            const p1 = { x: tl.x * (1 - t) + tr.x * t, y: tl.y * (1 - t) + tr.y * t };
            const p2 = { x: bl.x * (1 - t) + br.x * t, y: bl.y * (1 - t) + br.y * t };
            ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
        }
    }
    function drawDivider() {
        const [top, bottom] = state.divider;
        ctx.beginPath();
        ctx.moveTo(top.x, top.y);
        ctx.lineTo(bottom.x, bottom.y);
        ctx.strokeStyle = 'cyan';
        ctx.lineWidth = 3;
        ctx.stroke();
        [top, bottom].forEach(handle => {
            ctx.beginPath();
            ctx.arc(handle.x, handle.y, 10, 0, 2 * Math.PI);
            ctx.fillStyle = 'cyan';
            ctx.fill();
        });
    }

    // 4. INTERACTION LOGIC (unchanged from before)
    function onMouseDown(e) {
        const { x, y } = getMousePos(e);
        if (state.is_book) {
            for (let i = 0; i < 2; i++) {
                if (Math.sqrt((x - state.divider[i].x) ** 2 + (y - state.divider[i].y) ** 2) < 12) {
                    state.dragging = true; state.dragTarget = 'divider'; state.dragIndex = i; return;
                }
            }
        }
        for (let i = 0; i < 4; i++) {
            if (Math.sqrt((x - state.corners[i].x) ** 2 + (y - state.corners[i].y) ** 2) < 12) {
                state.dragging = true; state.dragTarget = 'corner'; state.dragIndex = i; return;
            }
        }
    }
    function onMouseMove(e) {
        if (!state.dragging) return;
        const { x, y } = getMousePos(e);
        if (state.dragTarget === 'corner') { state.corners[state.dragIndex] = { x, y }; }
        else if (state.dragTarget === 'divider') { state.divider[state.dragIndex] = { x, y }; }
        draw();
    }
    function onMouseUp() {
        state.dragging = false; state.dragIndex = -1; state.dragTarget = null;
    }
    function getMousePos(e) {
        const rect = canvas.getBoundingClientRect();
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }

    // 5. PROCESSING & PDF BIN LOGIC
    processButton.addEventListener('click', async () => {
        if (!state.file_id) return;
        previewContainer.innerHTML = '<p>Processing...</p>';

        const payload = {
            file_id: state.file_id,
            corners: state.corners.map(p => [p.x / state.imageScale, p.y / state.imageScale]),
            divider: state.is_book ? state.divider.map(p => [p.x / state.imageScale, p.y / state.imageScale]) : null,
        };

        try {
            const response = await fetch(`${backendUrl}/process`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) throw new Error('Processing failed');

            const data = await response.json();
            state.lastProcessedUrls = data.processed_urls;

            // Show preview and "Add to PDF" button
            previewContainer.innerHTML = '<h3>Preview</h3>';
            state.lastProcessedUrls.forEach(url => {
                const img = document.createElement('img');
                img.src = `${backendUrl}${url}?t=${new Date().getTime()}`;
                previewContainer.appendChild(img);
            });
            const addToPdfButton = document.createElement('button');
            addToPdfButton.textContent = 'Add to PDF Bin';
            addToPdfButton.onclick = addToPdfBin;
            previewContainer.appendChild(addToPdfButton);

            editorContainer.style.display = 'none';
            processButton.style.display = 'none';
        } catch (error) {
            previewContainer.innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
        }
    });

    function addToPdfBin() {
        state.pdfPages.push(...state.lastProcessedUrls);
        state.lastProcessedUrls = [];

        updatePdfBinUI();

        previewContainer.innerHTML = '<p>Added to PDF bin. Upload another image or generate the PDF.</p>';
    }

    function updatePdfBinUI() {
        pdfPagesList.innerHTML = '';
        state.pdfPages.forEach(url => {
            const thumb = document.createElement('img');
            thumb.src = `${backendUrl}${url}`;
            thumb.className = 'pdf-page-thumbnail';
            pdfPagesList.appendChild(thumb);
        });

        if (state.pdfPages.length > 0) {
            generatePdfButton.style.display = 'block';
        } else {
            generatePdfButton.style.display = 'none';
        }
    }

    // 6. PDF GENERATION
    generatePdfButton.addEventListener('click', async () => {
        if (state.pdfPages.length === 0) return;

        try {
            const response = await fetch(`${backendUrl}/generate-pdf`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_urls: state.pdfPages })
            });

            if (!response.ok) throw new Error('PDF generation failed.');

            const pdfBlob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(pdfBlob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = downloadUrl;
            a.download = 'scanned_document.pdf';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            a.remove();

        } catch (error) {
            alert(`Error generating PDF: ${error.message}`);
        }
    });
});
