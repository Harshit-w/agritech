# How to Use Your Own disease.h5 Model in AgriTech

Follow these steps exactly — it takes about 2 minutes.

---

## Step 1 — Install Required Packages

Open Command Prompt inside your `agritech_final` folder and run:

```
venv\Scripts\activate
pip install tensorflow pillow numpy
```

> If your PC is old or has no GPU, use the lighter version:
> ```
> pip install tensorflow-cpu pillow numpy
> ```

---

## Step 2 — Copy Your Model File

Copy your `disease.h5` (or whatever it is named) into the `models\` folder and **rename it to `disease_model.h5`**.

**Option A — File Explorer (easiest):**
1. Open File Explorer
2. Navigate to your `agritech_final\models\` folder
3. Copy-paste your `.h5` file in there
4. Rename it to `disease_model.h5`

**Option B — Command Prompt:**
```
copy "C:\Users\harsh\Downloads\disease.h5" models\disease_model.h5
```

After this, your folder should look like:
```
agritech_final\
  models\
    disease_model.h5     ← your file here
    .gitkeep
```

---

## Step 3 — Run the Inspection Script

This script reads your model and configures AgriTech to use it correctly:

```
python scripts/inspect_model.py
```

It will show you something like this:

```
📂  Loading: disease_model.h5  (86.2 MB)

✅  TensorFlow 2.13.0 found
✅  Model loaded successfully

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  MODEL INSPECTION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  File:          disease_model.h5
  Input shape:   (None, 224, 224, 3)  → expects 224×224 images
  Output shape:  (None, 6)            → predicts 6 classes
  Parameters:    25,600,000

  ✅  Matching preset found for 6 classes:
       [0] Blight
       [1] Healthy
       [2] Leaf Spot
       [3] Powdery Mildew
       [4] Rust
       [5] Wilt
```

**If it shows a preset automatically** → just press Enter to confirm, done!

**If it asks you to enter class names** → type the disease name for each index.
You should know this from how you trained the model (check your training folder for a `classes.txt`, `labels.txt`, or the folder names you used as training data).

---

## Step 4 — Restart the App

```
python app.py
```

You will see this line in the terminal confirming it worked:
```
✅  disease_model.h5 loaded — 6 classes, input (None, 224, 224, 3)
```

---

## Step 5 — Test It

1. Open `http://127.0.0.1:5000`
2. Go to **Disease AI** tab
3. Select the crop type
4. Upload a leaf photo (JPG or PNG)
5. Click **Analyse Image**

The result card at the bottom will now say:
```
CNN model (6 classes)
```
instead of "Colour analysis" — that confirms your model is being used.

---

## Troubleshooting

### ❌ `ModuleNotFoundError: No module named 'tensorflow'`
```
pip install tensorflow
```

### ❌ `Failed to load model: ...version...`
Your model was trained with a different TensorFlow version. Try:
```
pip install tensorflow==2.13.0
```
or the exact version you trained with.

### ❌ Wrong class names / wrong predictions
Your class label order doesn't match. Open `models\disease_classes.json` and fix the class names:
```json
{
  "classes": {
    "0": "Healthy",
    "1": "Blight",
    "2": "Rust"
  }
}
```
Match these exactly to the folder names / class order you used when training.

### ❌ `Input size mismatch`
Your model expects a different image size (e.g. 256×256 instead of 224×224).
The `inspect_model.py` script reads the correct size automatically and saves it.
Just re-run:
```
python scripts/inspect_model.py
python app.py
```

### ❌ Still seeing "Colour analysis" in results
The model file is not found. Check:
- File is named exactly `disease_model.h5` (not `disease.h5` or `model.h5`)
- File is in the `models\` folder (not in the root folder)
- Run `python scripts/inspect_model.py` and it should confirm it found the file

---

## What the class labels should match

The class labels you enter must match the **exact order your model was trained on**.

For example, if you trained on these folders in alphabetical order:
```
dataset/
  Blight/
  Healthy/
  LeafSpot/
  Rust/
```
Then the class mapping is:
```
[0] Blight
[1] Healthy
[2] Leaf Spot
[3] Rust
```

**Common training datasets and their class orders:**

| Dataset | Classes |
|---------|---------|
| PlantVillage (38 classes) | Alphabetical by crop then disease |
| Rice Disease (9 classes) | Bacterial Blight, Blast, Brown Spot, Healthy, Hispa, Narrow Brown Spot, Sheath Blight, Sheath Rot, Tungro |
| Custom 6-class | Depends on your folder/label order |

---

## Files changed by this process

| File | What changes |
|------|-------------|
| `models/disease_model.h5` | Your model file (you add this) |
| `models/disease_classes.json` | Auto-created by inspect script |

Nothing else in the project is modified.
