@echo off
echo Installing dependencies...
pip install --upgrade pip
pip install Flask==2.3.3
pip install Flask-CORS==4.0.0
pip install Pillow==9.5.0
pip install exifread==3.0.0
pip install gunicorn==20.1.0
echo Installation complete!