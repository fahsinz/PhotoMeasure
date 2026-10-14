# Architecture

The Streamlit app owns transient session state. Uploaded bytes stay in memory.
Pillow validates JPEG/PNG content, applies EXIF orientation and composites alpha
onto white. The resulting original-oriented RGB image is retained for exports.
One resized RGB analysis image feeds both corner selection and detectors.

Every corner is an (x,y) location in analysis pixels. The annotation component
uses its rendered CSS rectangle to translate pointer locations back to analysis
pixels; display size and device pixel ratio do not set the measurement scale.
Actual horizontal and vertical resize ratios are recorded separately because
integer image dimensions can round differently. Original-image overlays use
the inverse ratios. See interfaces.md for signatures and field names.

Geometry is independent of Streamlit and detectors. It validates perimeter
polygons, normalizes ordering, solves a normalized planar transformation and
maps target vertices into millimetres. Detection only proposes coordinates;
the user confirms the actual reference and target. An automatic failure does
not imply that manual geometry is invalid, and a detection success does not
establish physical accuracy.

The small annotation component is bundled static HTML/JavaScript with no CDN
or frontend service. Only Streamlit is the local server. NumPy provides double
precision linear algebra, OpenCV headless contrib provides ArUco and contour
processing, Pillow provides decoding/annotation, and Matplotlib provides saved
evaluation plots. Install only the pinned contrib headless OpenCV wheel.

JSON preserves full metadata, while CSV is a summary for spreadsheets. Reusable
annotation files contain coordinates plus image identity and processing settings.
Batch evaluation checks those identities before measuring. Private photographs
and generated result directories are excluded from Git by default.

Official references: [Streamlit components](https://docs.streamlit.io/develop/concepts/custom-components/components-v1/intro),
[OpenCV homography](https://docs.opencv.org/4.13.0/d9/dab/tutorial_homography.html),
[OpenCV ArUco](https://docs.opencv.org/4.13.0/d5/dae/tutorial_aruco_detection.html).
