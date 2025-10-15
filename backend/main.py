import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS, cross_origin
from flask import send_file
from fpdf import FPDF
from PIL import Image
import io
# Deferring heavy imports
# from processing import process_image
# import cv2
import numpy as np

# Create the uploads directory if it doesn't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')

app = Flask(__name__)
CORS(app) # Keep a basic global CORS, but we'll decorate the route

# In-memory mapping of a unique ID to filenames.
# In a real app, you'd use a database.
file_storage = {}

@app.route('/upload', methods=['POST'])
@cross_origin()
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        original_filename = file.filename
        filepath = os.path.join('uploads', original_filename)
        file.save(filepath)

        # LAZY IMPORT
        from processing import process_image
        import cv2

        # The initial processed image is just a temporary preview
        # It will be overwritten by the /process call
        processed_filename = "processed_" + original_filename
        processed_filepath = os.path.join('uploads', processed_filename)

        processing_result = process_image(filepath)
        cv2.imwrite(processed_filepath, processing_result["image"])

        file_id = os.path.splitext(original_filename)[0]
        file_storage[file_id] = {
            "original": original_filename,
            "processed_parts": [] # Will be populated by /process
        }

        return jsonify({
            "message": "File uploaded, ready for editing",
            "file_id": file_id,
            "original_url": f"/uploads/{original_filename}",
            "corners": processing_result["corners"],
            "is_book": processing_result["is_book"],
            "divider": processing_result["divider"]
        })

@app.route('/uploads/<filename>', methods=['GET'])
def get_original_image(filename):
    """ Serves an original or processed image file. """
    return send_from_directory('uploads', filename)

@app.route('/process', methods=['POST'])
def process_with_new_points():
    data = request.get_json()
    file_id = data.get('file_id')
    corners = np.array(data.get('corners'), dtype="float32")
    divider = data.get('divider') # This will be None if not a book

    if not file_id or corners is None:
        return jsonify({"error": "Missing file_id or corners"}), 400

    if file_id not in file_storage:
        return jsonify({"error": "File not found"}), 404

    original_filename = file_storage[file_id]["original"]
    filepath = os.path.join('uploads', original_filename)

    # LAZY IMPORT
    import cv2
    original_image = cv2.imread(filepath)

    # 1. Warp the entire area based on the 4 corners
    rect = np.zeros((4, 2), dtype="float32")
    s = corners.sum(axis=1)
    rect[0] = corners[np.argmin(s)]
    rect[2] = corners[np.argmax(s)]
    diff = np.diff(corners, axis=1)
    rect[1] = corners[np.argmin(diff)]
    rect[3] = corners[np.argmax(diff)]

    widthA = np.sqrt(((rect[2][0] - rect[3][0]) ** 2) + ((rect[2][1] - rect[3][1]) ** 2))
    widthB = np.sqrt(((rect[1][0] - rect[0][0]) ** 2) + ((rect[1][1] - rect[0][1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((rect[1][0] - rect[2][0]) ** 2) + ((rect[1][1] - rect[2][1]) ** 2))
    heightB = np.sqrt(((rect[0][0] - rect[3][0]) ** 2) + ((rect[0][1] - rect[3][1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
    M = cv2.getPerspectiveTransform(rect, dst)
    warped_spread = cv2.warpPerspective(original_image, M, (maxWidth, maxHeight))

    processed_parts = []
    processed_urls = []

    if divider:
        # 2. If it's a book, split the warped image
        divider = np.array(divider, dtype="float32").reshape(-1, 1, 2)
        # Transform the divider points to the warped image's coordinate space
        warped_divider = cv2.perspectiveTransform(divider, M)[0]

        split_x = int((warped_divider[0][0] + warped_divider[1][0]) / 2)

        left_page = warped_spread[:, :split_x]
        right_page = warped_spread[:, split_x:]

        # Save both pages
        left_filename = f"processed_{file_id}_L.jpg"
        right_filename = f"processed_{file_id}_R.jpg"
        cv2.imwrite(os.path.join('uploads', left_filename), left_page)
        cv2.imwrite(os.path.join('uploads', right_filename), right_page)

        processed_parts.extend([left_filename, right_filename])
        processed_urls.extend([f"/uploads/{left_filename}", f"/uploads/{right_filename}"])
    else:
        # It's a single page
        single_filename = f"processed_{file_id}.jpg"
        cv2.imwrite(os.path.join('uploads', single_filename), warped_spread)
        processed_parts.append(single_filename)
        processed_urls.append(f"/uploads/{single_filename}")

    file_storage[file_id]["processed_parts"] = processed_parts

    return jsonify({
        "message": "Image processed successfully",
        "processed_urls": processed_urls
    })

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    data = request.get_json()
    image_urls = data.get('image_urls')

    if not image_urls:
        return jsonify({"error": "No image URLs provided"}), 400

    from fpdf import FPDF
    from PIL import Image
    import io

    pdf = FPDF()
    # A4 size in mm: 210 x 297
    A4_WIDTH = 210
    A4_HEIGHT = 297

    for img_url in image_urls:
        # Assumes URL is like '/uploads/filename.jpg'
        filename = os.path.basename(img_url)
        filepath = os.path.join('uploads', filename)

        if not os.path.exists(filepath):
            # Log an error and skip this image
            print(f"Warning: File not found at {filepath}, skipping.")
            continue

        try:
            with Image.open(filepath) as img:
                width_px, height_px = img.size

            # Convert pixels to mm (assuming 96 DPI, 1 inch = 25.4 mm)
            # This is a bit arbitrary, what matters is the ratio
            width_mm = width_px / 96 * 25.4
            height_mm = height_px / 96 * 25.4

            # Calculate aspect ratio
            aspect_ratio = width_mm / height_mm

            # Fit image to A4 page, preserving aspect ratio
            if width_mm > A4_WIDTH or height_mm > A4_HEIGHT:
                if (A4_WIDTH / aspect_ratio) <= A4_HEIGHT:
                    # Width is the limiting factor
                    display_width = A4_WIDTH
                    display_height = display_width / aspect_ratio
                else:
                    # Height is the limiting factor
                    display_height = A4_HEIGHT
                    display_width = display_height * aspect_ratio
            else:
                display_width = width_mm
                display_height = height_mm

            # Center the image on the page
            x_pos = (A4_WIDTH - display_width) / 2
            y_pos = (A4_HEIGHT - display_height) / 2

            pdf.add_page()
            pdf.image(filepath, x=x_pos, y=y_pos, w=display_width, h=display_height)

        except Exception as e:
            print(f"Error processing {filename} for PDF: {e}")
            continue

    # Create an in-memory byte stream for the PDF
    pdf_buffer = io.BytesIO(pdf.output(dest='S').encode('latin1'))
    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name='document.pdf',
        mimetype='application/pdf'
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000)
