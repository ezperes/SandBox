# Testing RNA with equation X^3+X^2+7=0

import pandas as pd

dataset = pd.read_csv('Dados1.csv', sep=';')

X = dataset.loc[:, 'x'].values  # Independent variables (attributes/columns)
y = dataset.loc[:, 'y'].values  # Dependent variable (the last column) (the class to be "guessed")

# #### PREPROCESSING #### #

# #### SPLITTING DATASET INTO TRAIN AND TEST SETS #### #

from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)


# #### SCALING DATA #### #

from sklearn.preprocessing import StandardScaler

sc = StandardScaler()
X_train = sc.fit_transform(X_train)
X_test = sc.fit_transform(X_test)


# #### CREATING THE ANN WITH TENSORFLOW/KERAS #### #

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense

# Instantiates a Sequential ANN
classifier = Sequential()

# Creates (add) a hidden layer in the ANN, with 6 perceptrons, uniform weight initialization and, wheres this is the
# first Hiddent layer of ANN, we inform the number of input parameters for this ANN (11 in this case)
# activation function is Rectified Linear Unit Activation function (relu)
# The amount 6 is the average of 11 inputs with 1 output
classifier.add(Dense(units=10, kernel_initializer='uniform', activation='relu', input_dim=1))

# Creates (add) a sequential hidden layer in the ANN, similar to the first one, unless for this has no input information
# (as long as the Sequential ANN already knows that this layer succeeds the previous created one)
# classifier.add(Dense(units=6, kernel_initializer='uniform', activation='relu'))

# Creates the output layer of the ANN. As long as this is a linear regression, output has a single neuron, and the
# activation function is Sigmoid instead
classifier.add(Dense(units=1, kernel_initializer='uniform', activation='sigmoid'))


# #### TRAINING THE MODEL #### #

# Compiles the ANN, with following parameters
# optimizer: the optimization method. 'adam' optimization is a stochastic gradient descent method that is based on
#               adaptive estimation of first-order and second-order moments.
# loss: loss function calculator. Computes the cross-entropy loss between true labels and predicted labels.
#       Use this cross-entropy loss when there are only two label classes, use categorical_crossentropy otherwise
# metrics: the performance classification method (as a list) . The Accuracy Calculates how often predictions equals
#           labels.
classifier.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])

# Trains the compiled ANN with given data (X_train, y_train, X_test, y_test)
# batch size: number of samples per gradient update.
# epochs: number of iterations over train data
classifier.fit(X_train, y_train, batch_size=10, epochs=100)


# #### PREDICTING #### #

y_pred = classifier.predict(X_test)

# Turning the percentual prediction in a true/false array with threshold of 50%
y_pred_bool = (y_pred > 0.5)


# #### CONFUSION MATRIX #### #

from sklearn.metrics import confusion_matrix

cm = confusion_matrix(y_test, y_pred_bool)

pass
