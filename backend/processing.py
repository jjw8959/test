import cv2
import numpy as np

def process_image(image_path):
    """
    Loads an image, detects the largest document-like contour,
    and applies a perspective warp to get a top-down view.

    Returns the warped image or None if no document is found.
    """
    # Read the image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not read image at {image_path}")
        return None

    # For performance, we resize the image. We'll keep the ratio.
    ratio = image.shape[0] / 500.0
    original_image = image.copy()
    image = cv2.resize(image, (int(image.shape[1] / ratio), 500))

    # 1. Grayscale and Edge Detection
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 75, 200)

    # 2. Find Contours
    contours, _ = cv2.findContours(edges.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    # Sort contours by area and keep the largest ones
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    document_contour = None

    # 3. Find the document contour (should be a quadrilateral)
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)

        # If our approximated contour has four points, we can
        # assume that we have found our document
        if len(approx) == 4:
            document_contour = approx
            break

    # 4. Apply the Perspective Transform
    if document_contour is None:
        print("Could not find a 4-point contour, using full image corners.")
        # If no contour is found, use the corners of the entire image
        h, w, _ = original_image.shape
        points = np.array([
            [0, 0],
            [w - 1, 0],
            [w - 1, h - 1],
            [0, h - 1]
        ], dtype="float32")
        # The warped image will just be the original image in this case
        warped = original_image
        rect = points
        s = points.sum(axis=1)
        rect[0] = points[np.argmin(s)]
        rect[2] = points[np.argmax(s)]
        diff = np.diff(points, axis=1)
        rect[1] = points[np.argmin(diff)]
        rect[3] = points[np.argmax(diff)]

        (tl, tr, br, bl) = rect

        # Compute the width of the new image
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        # Compute the height of the new image
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        # Define the destination points for the top-down view
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")

        # Compute the perspective transform matrix and apply it
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(original_image, M, (maxWidth, maxHeight))

    # --- Book Detection & Divider Calculation ---
    is_book = False
    divider = None

    # Heuristic: if width is much larger than height, it's a book
    (tl, tr, br, bl) = rect
    width_top = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    width_bottom = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    height_left = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    height_right = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))

    avg_width = (width_top + width_bottom) / 2
    avg_height = (height_left + height_right) / 2

    if avg_width > avg_height * 1.2: # 1.2 is a tunable threshold
        is_book = True
        # Default divider is the midpoint of top and bottom edges
        top_mid = (tl[0] + tr[0]) / 2, (tl[1] + tr[1]) / 2
        bottom_mid = (bl[0] + br[0]) / 2, (bl[1] + br[1]) / 2
        divider = [list(top_mid), list(bottom_mid)]

    # Return everything
    return {
        "image": warped,
        "corners": rect.tolist(),
        "is_book": is_book,
        "divider": divider
    }
