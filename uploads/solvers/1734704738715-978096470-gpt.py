# -*- coding: utf-8 -*-
"""GPT.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1lM_waoZmSv6A1ykAD7yemVRaxAmKHy7v
"""

import tensorflow as tf
from tensorflow.keras.layers import Dense, Embedding, LayerNormalization, Dropout, MultiHeadAttention
from tensorflow.keras.models import Model
import nltk
from nltk.corpus import reuters
import numpy as np
import os
import pandas as pd
import random

import mohassin

t= 'API-DGHC57VYV4'
response = GPT('how to cook', t, 'gpt4')
print(respone)
"""###using on those 2 datasets to generate some sentences

"""

nltk.download('punkt')
nltk.download('reuters')

class TransformerBlock(tf.keras.layers.Layer):
    def __init__(self, embed_dim, num_heads, ff_dim, rate=0.1):
        super(TransformerBlock, self).__init__()
        self.att = MultiHeadAttention(num_heads=num_heads, key_dim=embed_dim)
        self.ffn = tf.keras.Sequential([
            Dense(ff_dim, activation="relu"),
            Dense(embed_dim),
        ])
        self.layernorm1 = LayerNormalization(epsilon=1e-6)
        self.layernorm2 = LayerNormalization(epsilon=1e-6)
        self.dropout1 = Dropout(rate)
        self.dropout2 = Dropout(rate)

    def call(self, inputs, training=None):
        attn_output = self.att(inputs, inputs, training=training)
        attn_output = self.dropout1(attn_output, training=training)
        out1 = self.layernorm1(inputs + attn_output)
        ffn_output = self.ffn(out1)
        ffn_output = self.dropout2(ffn_output, training=training)
        return self.layernorm2(out1 + ffn_output)

class GPT(Model):
    def __init__(self, vocab_size, max_seq_len, embed_dim, num_heads, ff_dim, num_layers, rate=0.1):
        super(GPT, self).__init__()
        self.embedding = Embedding(input_dim=vocab_size, output_dim=embed_dim)
        self.positional_encoding = self.get_positional_encoding(max_seq_len, embed_dim)
        self.dropout = Dropout(rate)
        self.transformer_blocks = [
            TransformerBlock(embed_dim, num_heads, ff_dim, rate) for _ in range(num_layers)
        ]
        self.dense = Dense(vocab_size)

    def call(self, inputs, training=None):
        seq_len = tf.shape(inputs)[-1]
        embeddings = self.embedding(inputs)
        embeddings += self.positional_encoding[:seq_len, :]
        x = self.dropout(embeddings, training=training)

        for transformer_block in self.transformer_blocks:
            x = transformer_block(x, training=training)

        logits = self.dense(x)
        return logits

    def get_positional_encoding(self, seq_len, embed_dim):
        angle_rads = self.get_angles(
            tf.range(seq_len, dtype=tf.float32)[:, tf.newaxis],
            tf.range(embed_dim, dtype=tf.float32)[tf.newaxis, :],
            embed_dim
        )

        sines = tf.math.sin(angle_rads[:, 0::2])
        cosines = tf.math.cos(angle_rads[:, 1::2])

        pos_encoding = tf.concat([sines, cosines], axis=-1)
        return tf.cast(pos_encoding, dtype=tf.float32)

    def get_angles(self, pos, i, embed_dim):
        pos = tf.cast(pos, dtype=tf.float32)
        i = tf.cast(i, dtype=tf.float32)
        angle_rates = 1 / tf.pow(10000, (2 * (i // 2)) / tf.cast(embed_dim, tf.float32))
        return pos * angle_rates

#hyperparams
vocab_size = 5000
max_seq_len = 100
embed_dim = 512
num_heads = 8
ff_dim = 2048
num_layers = 6
rate = 0.1

gpt_model = GPT(vocab_size, max_seq_len, embed_dim, num_heads, ff_dim, num_layers, rate)
gpt_model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
                  loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                  metrics=["accuracy"])

gpt_model.build(input_shape=(None, max_seq_len))
gpt_model.summary()

words = nltk.word_tokenize(" ".join(reuters.words(categories=['acq'])))
unique_words = list(set(words))
vocab = {word: idx for idx, word in enumerate(unique_words)}
id_to_word = {idx: word for word, idx in vocab.items()}

example_sentence = words[:max_seq_len]
example_input = tf.constant([[vocab[word] for word in example_sentence]])
example_output = gpt_model(example_input, training=False)

example_output

probabilities = tf.nn.softmax(example_output, axis=-1)
predicted_tokens = tf.argmax(probabilities, axis=-1)
predicted_words = [[id_to_word[int(token)] for token in sequence] for sequence in predicted_tokens]

cleaned_sentences = [" ".join(words) for words in predicted_words]
for idx, sentence in enumerate(cleaned_sentences):
    print(f"Generated Sentence {idx + 1}: {sentence}")

"""###OUR dataset"""

!pip install -q kaggle
from google.colab import files
files.upload()
!mkdir ~/.kaggle
!cp kaggle.json ~/.kaggle/
!chmod 600 ~/.kaggle/kaggle.json
!kaggle datasets download -d alexteboul/diabetes-health-indicators-dataset
!mkdir patient_data
!unzip diabetes-health-indicators-dataset.zip -d patient_data

file_path = "patient_data/diabetes_binary_5050split_health_indicators_BRFSS2015.csv"
data = pd.read_csv(file_path)
data['diet_plan'] = ["Example diet plan" for _ in range(len(data))]

features = data.drop(columns=['diet_plan']).values

diet_plan_text = (
    "Breakfast: Oatmeal with skim milk, topped with berries (300 calories) - Focus on high fiber to regulate blood sugar. "
    "Lunch: Grilled chicken salad with olive oil dressing (400 calories) - Include lean proteins and healthy fats. "
    "Dinner: Steamed salmon with broccoli and quinoa (500 calories) - Low-sodium meal with balanced macros. "
    "Snacks: Carrot sticks with hummus (150 calories) - Avoid processed snacks."
)
data.at[0, 'diet_plan'] = diet_plan_text

with pd.option_context('display.max_columns', None):
    print(data['diet_plan'].head(1))

"""###Data Augmentation"""

def generate_labels_for_data(data, base_diet_plan, variations):
    def generate_augmented_plan(base_plan):
        augmented_plan = base_plan
        for key, synonyms in variations.items():
            if key in augmented_plan:
                augmented_plan = augmented_plan.replace(key, random.choice(synonyms))
        meals = augmented_plan.split(". ")
        random.shuffle(meals)
        return ". ".join(meals).strip(".")

    for i in range(len(data)):
        data.at[i, 'diet_plan'] = generate_augmented_plan(base_diet_plan)

base_diet_plan = (
    "Breakfast: Oatmeal with skim milk, topped with berries (300 calories) - Focus on high fiber to regulate blood sugar. "
    "Lunch: Grilled chicken salad with olive oil dressing (400 calories) - Include lean proteins and healthy fats. "
    "Dinner: Steamed salmon with broccoli and quinoa (500 calories) - Low-sodium meal with balanced macros. "
    "Snacks: Carrot sticks with hummus (150 calories) - Avoid processed snacks."
)

variations = {
    "skim milk": ["low-fat milk", "almond milk"],
    "berries": ["blueberries", "strawberries"],
    "grilled chicken": ["roasted chicken", "grilled turkey"],
    "broccoli": ["spinach", "asparagus"],
    "carrot sticks": ["celery sticks", "cucumber slices"],
}

generate_labels_for_data(data, base_diet_plan, variations)

print(data[['diet_plan']].head())

tokenizer = tf.keras.preprocessing.text.Tokenizer()
tokenizer.fit_on_texts(data['diet_plan'])
labels = tokenizer.texts_to_sequences(data['diet_plan'])
labels = tf.keras.preprocessing.sequence.pad_sequences(labels, padding="post")

labels

#hyperparams
vocab_size = len(tokenizer.word_index) + 1
max_seq_len = labels.shape[1]
embed_dim = 128
num_heads = 8
ff_dim = 512
num_layers = 4
batch_size = 32
epochs = 10

gpt_model = GPT(vocab_size, max_seq_len, embed_dim, num_heads, ff_dim, num_layers, rate=0.1)
gpt_model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
                  loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
                  metrics=['accuracy'])

dataset = tf.data.Dataset.from_tensor_slices((features, labels))
dataset = dataset.shuffle(buffer_size=1024).batch(batch_size)

gpt_model.fit(dataset, epochs=epochs)

