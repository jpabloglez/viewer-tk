# Image viewer

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?style=flat&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg)

Application for medical imaging pixel and metadata visualization. 

## Features

- DICOM file loading and parsing
- Pixel data visualization
- Metadata extraction and display
- User-friendly GUI interface

## Project Structure

```
├── README.md
├── image-viewer.py
├── sample

```

## Prerequisites

- Python 3.9 or higher

## Installation

1. Clone the repository:
```bash
git clone https://github.com/jpabloglez/image-viewer.git
cd image-viewer
```

2. Create and activate a virtual environment:

Using venv:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Using conda:
```bash
conda create my-env python=3.10
conda activate my-env
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python3 image-viewer.py

Or

python3 image-viewer.py /path/to/dicom/folder
```


## Usage

1. Launch the application
2. Use the File menu to open DICOM files
3. View image data and metadata in the main window
4. Use the toolbar for common operations like zoom, pan, and window/level adjustment

## Development

### Adding New Features

1. Create a new branch for your feature
2. Implement the feature following the project structure
3. Add tests in the appropriate test directory
4. Submit a pull request

### Running Tests

```bash
python -m pytest tests/
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- DICOM standard documentation
- PyDICOM library
- Contributors and maintainers

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.