import random

import numpy as np
import tensorflow as tf
from tensorflow.python.ops.rnn_cell import GRUCell

SEQ_LEN = 48
BATCH_SIZE = 32
VOCABULARY_SIZE = 10
HIDDEN_SIZE = 4
NUM_BATCH = 1024
LEARNING_RATE_START = 1e-2
LEARNING_RATE_MIN = 1e-6
LEARNING_RATE_CUT_EPOCH = 3
NUM_EPOCH = 100
NUM_ZEROS = 16
random_data = np.zeros([NUM_BATCH, BATCH_SIZE, SEQ_LEN], dtype=np.int32)

for batch_idx in range(NUM_BATCH):
    for example_idx in range(BATCH_SIZE):
        repeated_digit = random.randint(0, 9)
        for seq_idx in range(SEQ_LEN):
            if seq_idx % NUM_ZEROS == 0:
                label = repeated_digit
            else:
                label = 0
            random_data[batch_idx, example_idx, seq_idx] = label


def make_batch(random_batch):
    xs = random_batch[:, :SEQ_LEN - 1]
    ys = random_batch[:, 1:]

    return xs, ys


rnn_cell = GRUCell(HIDDEN_SIZE)

input_placeholder = tf.placeholder(dtype=tf.int32, shape=[None, SEQ_LEN - 1], name="input")

target_placeholder = tf.placeholder(dtype=tf.int32, shape=[None, SEQ_LEN - 1], name="target")
learning_rate_placeholder = tf.placeholder(dtype=tf.float32, shape=None)

outputs = []
state = rnn_cell.zero_state(BATCH_SIZE, dtype=tf.float32)
states = []

with tf.variable_scope("RNN"):
    with tf.variable_scope("embedding"):
        embedding_matrix = tf.get_variable(
            "weights",
            shape=[VOCABULARY_SIZE, HIDDEN_SIZE],
            initializer=tf.random_normal_initializer()
        )
    with tf.variable_scope("softmax"):
        softmax_w = tf.get_variable(
            "weight",
            shape=[HIDDEN_SIZE, VOCABULARY_SIZE],
            initializer=tf.random_normal_initializer()
        )
        softmax_b = tf.get_variable("bias", shape=[VOCABULARY_SIZE], initializer=tf.constant_initializer(0.1))
    for time_step in range(SEQ_LEN - 1):
        if time_step > 0:
            tf.get_variable_scope().reuse_variables()

        digit_embeddings = tf.nn.embedding_lookup(embedding_matrix, input_placeholder[:, time_step])
        (cell_output, state) = rnn_cell(digit_embeddings, state)
        logits = tf.matmul(cell_output, softmax_w) + softmax_b
        outputs.append(logits)
        states.append(state)

    output = tf.reshape(tf.concat_v2(outputs, axis=1), [-1, VOCABULARY_SIZE])
    hidden_states = tf.reshape(tf.concat_v2(states, axis=1), [-1, SEQ_LEN - 1, HIDDEN_SIZE])

    labels_batched = tf.reshape(target_placeholder, [-1])
    target_weights = tf.ones([BATCH_SIZE * (SEQ_LEN - 1)])

    softmax_outputs = tf.reshape(tf.nn.softmax(output), [-1, SEQ_LEN - 1, VOCABULARY_SIZE])
    loss = tf.contrib.legacy_seq2seq.sequence_loss(
        [output],
        [labels_batched],
        [target_weights])

optimizer = tf.train.AdamOptimizer(learning_rate_placeholder)
grads_and_vars = optimizer.compute_gradients(loss)
train_step = optimizer.apply_gradients(grads_and_vars)

sess = tf.Session()
sess.run(tf.global_variables_initializer())
learning_rate = LEARNING_RATE_START

best_loss = np.inf
epochs_without_improvement = 0

for epoch_idx in range(NUM_EPOCH):
    if epochs_without_improvement >= LEARNING_RATE_CUT_EPOCH:
        epochs_without_improvement = 0
        learning_rate /= 10
        print("Cutting learning rate to", learning_rate)
    if learning_rate <= LEARNING_RATE_MIN:
        print("Ending training since model is not learning")
        break
    for batch_idx in range(NUM_BATCH):
        batch_input, batch_output = make_batch(random_data[batch_idx])
        fetch_output, fetch_labels, fetch_softmax, fetch_states, fetch_loss, fetch_grad_vars, _ = sess.run(
            [output, labels_batched, softmax_outputs, hidden_states, loss, grads_and_vars, train_step],
            feed_dict={
                input_placeholder: batch_input,
                target_placeholder: batch_output,
                learning_rate_placeholder: learning_rate,
            }
        )
    if best_loss * 0.999 < fetch_loss:
        print("Current loss ", fetch_loss, "was not significantly better than best loss of", best_loss)
        epochs_without_improvement += 1
        print("Now at", epochs_without_improvement, "epoch(s) without improvement out of", LEARNING_RATE_CUT_EPOCH)
    else:
        best_loss = fetch_loss
        epochs_without_improvement = 0
        print("Got new best loss of: ", best_loss)

    if not fetch_loss:
        raise Exception("You set either NUM_EPOCH or NUM_BATCH to 0")
    else:
        print("Epoch:", epoch_idx, "Loss:", fetch_loss, "LR:", learning_rate)

print("Training completed - attained loss", best_loss)
