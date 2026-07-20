# Get Started
*******************
- npm install



# Run 
*********
# In cmd 
- ipconfig 
copy IPv4 Address
- paste in .env.local
NEXT_PUBLIC_DANGER_PREDICT_URL=http://Your IPv4 Address:8000/predict

# Start API server first
- python -m uvicorn app.ml.main:app --host 0.0.0.0 --port 8000

- "C:\Users\Hsu Sandar Win\AppData\Local\Python\bin\python.exe" -m uvicorn app.ml.main:app --reload --host 0.0.0.0 --port 8000

in another terminal
# other terminal
- npm run dev




# Use python version 3.11 (if API server cannot open or cannot run)
- py -3.11 --version

- py -3.11 -m venv .venv

- source .venv/Scripts/activate

- python -m pip install --upgrade pip

- python -m uvicorn app.ml.main:app --host 0.0.0.0 --port 8000




# Install dependencies
pip install -r app/ml/requirements.txt

# Train model
python app/ml/train_model.py

# Test prediction
python app/ml/predict_sound.py path/to/audio.wav