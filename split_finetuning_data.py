import json
import random

# Load your dataset from the file (adjust path as needed)
with open('fine_tuning_corrected.jsonl', 'r') as file:
    data = [json.loads(line) for line in file]

# Shuffle the data
random.shuffle(data)

# Split the data into 80% training and 20% validation
split_index = int(0.8 * len(data))
training_data = data[:split_index]
validation_data = data[split_index:]

# Save the training and validation data to separate files
with open('training_data.jsonl', 'w') as train_file:
    for entry in training_data:
        train_file.write(json.dumps(entry) + '\n')

with open('validation_data.jsonl', 'w') as val_file:
    for entry in validation_data:
        val_file.write(json.dumps(entry) + '\n')