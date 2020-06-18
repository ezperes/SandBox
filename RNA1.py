import pandas as pd

dataset = pd.read_csv('Churn_Modelling.csv')

x = dataset.iloc[:, 3:13].values  # Independent variables (attributes/columns)
y = dataset.iloc[:, 13].values  # Dependent variable (the last column) (the class to be "guessed")

# PREPROCESSING



pass
