# Monthly Report Automator

This tool automates the creation of FM01 MET and FM02 IT monthly operational reports.

## Setup Instructions

1.  **Templates**: Prepare two Word document templates (`.docx`).
    -   In the templates, use the following placeholders:
        -   `{{Month}}`: Full name of the month (e.g., January).
        -   `{{YYYY}}`: The year (e.g., 2025).
        -   `{{work_logs}}`: The content from the "Work Log" text area.
        -   `{{img1}}`, `{{img2}}`, ..., `{{img8}}`: Placeholders for the 8 photos. These should be placed where you want the images to appear.

2.  **Running the Program**:
    -   Ensure you have Python installed.
    -   Install dependencies: `pip install -r requirements.txt`
    -   Run the program: `python app.py`
    -   Open your browser to `http://127.0.0.1:5000`.

## Features

-   **Report Type Selection**: Quickly switch between FM01 and FM02.
-   **Persistent Settings**: Template paths and separate output base directories for FM01 and FM02 are saved for next time.
-   **Smart Date Auto-fill**: Automatically sets the report date to the previous month.
-   **Advanced Image Processing**: 
    -   Upload 8 photos (bulk or one-by-one).
    -   Images are resized to 328x278.
    -   Added blurred background to maintain aspect ratio without empty space.
    -   Drag and drop to reorder photos 1 to 8.
-   **Automated Filing**: Reports are saved in `Base_Dir\YYYY\MM\FM0x ... .docx`.
-   **Status & Progress**: Visual feedback with a progress bar and emoji logs.

## Dependencies

-   Flask: Web backend.
-   docxtpl: Word document manipulation with Jinja2 templates.
-   Pillow: Image processing (resizing and blurring).
-   tkinter: Native file/folder pickers.
