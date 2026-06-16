# Danger Sound Detection - ML Integration

## Folder Structure

```
app/
├── database/
│   └── ESC-50-master/
│       ├── audio/              # 2000 WAV audio files (5 sec each)
│       └── meta/
│           └── esc50.csv       # Metadata with filename, fold, target, category
├── ml/
│   ├── train_model.py          # Training script (sklearn SVM)
│   ├── predict_sound.py        # Prediction module
│   ├── main.py                 # FastAPI server
│   ├── danger_sound_model.pkl   # Trained model (generated)
│   └── requirements.txt
└── lib/
    └── MicrophoneProvider.tsx    # React context for audio capture
```

## Dataset Structure (ESC-50)

- **Location**: `app/database/ESC-50-master/audio/`
- **Format**: WAV files (44.1kHz, mono, 5 seconds each)
- **Metadata**: `app/database/ESC-50-master/meta/esc50.csv`
- **Columns**: filename, fold, target, category, esc10, src_file, take

### Category Mapping (Danger Detection)

| Target Label | ESC-50 Categories |
|--------------|---------------------|
| glass_break  | glass_breaking        |
| gunshot      | chainsaw, fireworks   |
| scream       | crying_baby           |
| normal       | All other 46 classes  |

## Step-by-Step Explanation

### Step 1: Install Dependencies
```bash
pip install -r app/ml/requirements.txt
```

### Step 2: Train the Model
```bash
cd app/ml
python train_model.py
```

This script:
1. Loads ESC-50 metadata and maps categories to danger labels
2. Extracts audio features (MFCC + spectral features) using Librosa
3. Trains an SVM classifier with RBF kernel
4. Saves model as `danger_sound_model.pkl`

### Step 3: Start FastAPI Server
```bash
cd app/ml
python main.py
```

API endpoints:
- `POST /predict` - Upload audio file for prediction (wav, mp3, ogg, flac)
- `GET /health` - Health check

### Step 4: Use Prediction Module
```python
from predict_sound import predict
result = predict("path/to/audio.wav")
# Returns: {'prediction': 'gunshot', 'confidence': 0.95, 'probabilities': {...}}
```

## Model Performance

- Training samples: 1600
- Test samples: 400
- Test accuracy: ~83.5%