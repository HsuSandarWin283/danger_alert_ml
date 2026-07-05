# Get Started
*******************
- npm install
- npm run dev



# Run 
*********
# Start API server first
- python -m uvicorn app.ml.main:app --host 0.0.0.0 --port 8000

in another terminal
# other terminal
- npm run dev



# Install dependencies
pip install -r app/ml/requirements.txt

# Train model
python app/ml/train_model.py








# Test prediction
python app/ml/predict_sound.py path/to/audio.wav