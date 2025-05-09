import json
import random
import spacy
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import MultiLabelBinarizer

# Fungsi untuk memisahkan data menjadi train dan test set
def split_data(data, train_ratio=0.8):
    random.shuffle(data)
    train_size = int(len(data) * train_ratio)
    train_data = data[:train_size]
    test_data = data[train_size:]
    return train_data, test_data

# Load dataset yang sudah diseimbangkan
with open("trainfix.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

# Pisahkan data menjadi train dan test set
train_data, test_data = split_data(data)

# Simpan data train dan test set ke file JSON
train_file = "train_set.json"
test_file = "test_set.json"

with open(train_file, 'w', encoding='utf-8') as f:
    json.dump(train_data, f, ensure_ascii=False, indent=2)

with open(test_file, 'w', encoding='utf-8') as f:
    json.dump(test_data, f, ensure_ascii=False, indent=2)

# Muat model yang sudah dilatih
nlp = spacy.load("intent_model_ft_v2")

# Evaluasi model dengan test set
y_true = []
y_pred = []

for text, annotations in test_data:
    doc = nlp(text)
    true_labels = [label for label, score in annotations["cats"].items() if score == 1.0]
    predicted_labels = [label for label, score in doc.cats.items() if score == 1.0]
    
    y_true.append(true_labels)
    y_pred.append(predicted_labels)

# Gunakan MultiLabelBinarizer untuk mengonversi ke format biner
mlb = MultiLabelBinarizer()
y_true_bin = mlb.fit_transform(y_true)
y_pred_bin = mlb.transform(y_pred)

# Evaluasi menggunakan classification_report dan confusion_matrix
print("Classification Report:")
print(classification_report(y_true_bin, y_pred_bin, target_names=mlb.classes_))

# Perbaikan untuk confusion matrix
try:
    cm = confusion_matrix(y_true_bin.argmax(axis=1), y_pred_bin.argmax(axis=1))
    print("\nConfusion Matrix:")
    print(cm)
except ValueError as e:
    print(f"Error generating confusion matrix: {e}")
