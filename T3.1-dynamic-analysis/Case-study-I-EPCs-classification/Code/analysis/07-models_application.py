#!/usr/bin/env python
# coding: utf-8

# %%
#----    Settings    ----
from pathlib import Path
import os
from dotenv import load_dotenv
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.preprocessing import MinMaxScaler
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import SGDClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import confusion_matrix, precision_score, recall_score
from sklearn.metrics import fbeta_score, make_scorer, f1_score, balanced_accuracy_score
from sklearn.utils import class_weight
import xgboost as xgb
from sklearn.model_selection import StratifiedKFold, KFold, GridSearchCV
import matplotlib.pyplot as plt
import seaborn as sns

# Custom modules
from src.utils import my_utils
from src.utils import models_utils

if my_utils.in_ipython():
    # Automatic reload custom module to allow interactive development
    # https://stackoverflow.com/a/35597119/12481476
    from IPython import get_ipython
    get_ipython().run_line_magic('reload_ext', 'autoreload')
    get_ipython().run_line_magic('aimport', 'src.utils.models_utils')
    get_ipython().run_line_magic('autoreload', '1')


# load environment variables
from py_config_env import EnvironmentLoader

env_loader = EnvironmentLoader(
    env_file='my-env',  # File to load
    env_path='environments'  # Path where files are contained
)

# Object containing loaded environmental variables
my_env = env_loader.configuration.get('my_env')

# Pass environment variables to custom module


# %%
#----    Load Data    ----

print('Loading data...')

# read data
data = pd.read_csv(my_env.DATAANALYSIS)
data = data.rename(columns={
    'temp_winter':'winter_temp',
    'temp_summer':'summer_temp'
})

# Select columns
winter_col = list(data.filter(regex = 'winter_').columns)
summer_col = list(data.filter(regex = 'summer_').columns)

selected_col = ['YEAR_BUILD', 'ENER_CLASS'] + winter_col + summer_col
selected_col

data = data[selected_col].copy()


# %%
#----    Data Encoding    ----

print('Data encoding...')

# Check distribution energy classes
data['ENER_CLASS'] = pd.Categorical(
    data['ENER_CLASS'], 
    categories = ['A', 'B', 'C', 'D', 'E', 'F', 'G'], 
    ordered = True
    )
print(data['ENER_CLASS'].value_counts(sort = False))

# Encode labels
ener_class_encoder = LabelEncoder()
data['ENER_CLASS'] = ener_class_encoder.fit_transform(data['ENER_CLASS'])

year_encoder = LabelEncoder()
data['YEAR_BUILD'] = year_encoder.fit_transform(data['YEAR_BUILD'])


# Divide into training and test set (with stratification)
split = StratifiedShuffleSplit(
    n_splits = 1, 
    test_size = 0.2, 
    random_state = 2022
    )

for train_index, test_index in split.split(data, data['ENER_CLASS']):
    train_set = data.loc[train_index]
    test_set = data.loc[test_index]


# Normalize data according to training set
features = winter_col + summer_col
minmax_scaler = MinMaxScaler()
train_set[features] = minmax_scaler.fit_transform(train_set[features])
test_set[features] = minmax_scaler.transform(test_set[features])

# Divide data for the models
train_set_y = train_set['ENER_CLASS']
train_set = train_set.drop(['ENER_CLASS', 'YEAR_BUILD'], axis=1)

test_set_y = test_set['ENER_CLASS']
test_set = test_set.drop(['ENER_CLASS', 'YEAR_BUILD'], axis=1)

# Classes weights
classes_weights = class_weight.compute_sample_weight(
    class_weight='balanced',
    y=train_set_y
)
classes_weights_test = class_weight.compute_sample_weight(
    class_weight='balanced',
    y=test_set_y
)

# %%
#----    Model 1: Gaussian NB    ----

print('Training gaussian naive bayes model...\n')

gaussian_model = GaussianNB()
gaussian_model.fit(train_set, train_set_y)
gaussian_predictions = gaussian_model.predict(test_set)

# %%
gaussian_scores = models_utils.get_scores(
    y_true = test_set_y,
    y_pred = gaussian_predictions,
    sample_weight = classes_weights_test,
    encoder = ener_class_encoder,
    verbose=True
)

# %%
#----    Model 2: Gradient Boosting    ----

print('Training gradient boosting classifier...')

gb_model = GradientBoostingClassifier()
gb_model.fit(train_set, train_set_y)
gb_predictions = gb_model.predict(test_set)

# %%
gb_scores = models_utils.get_scores(
    y_true = test_set_y,
    y_pred = gb_predictions,
    sample_weight = classes_weights_test,
    encoder = ener_class_encoder,
    verbose=True
)

# %%
#----    Model 3: Random Forest    ----

print('Training random forest model...')

rf_model = RandomForestClassifier(class_weight="balanced")
rf_model.fit(train_set, train_set_y)
rf_predictions = rf_model.predict(test_set)

# %%
rf_scores = models_utils.get_scores(
    y_true = test_set_y,
    y_pred = rf_predictions,
    sample_weight = classes_weights_test,
    encoder = ener_class_encoder,
    verbose=True
)

# %%
#----    Model 4: XGB Model    ----

f1_score_weighted = make_scorer(
    f1_score, 
    average='weighted', 
    sample_weight = classes_weights
    )
f1_score_macro = make_scorer(
    f1_score, 
    average='macro'
    )
    
# %%
# First trial xgboost

xgb_model = xgb.XGBClassifier(
    n_estimators = 150,
    objective = 'multi:softmax',
    max_depth = 6,
    colsample_bylevel = 0.5,
    eval_metric = f1_score_weighted,
    seed = 2022,
    n_jobs = 5
    ).fit(train_set, train_set_y, sample_weight = classes_weights)

xgb_predictions = xgb_model.predict(test_set)

# %%
xgb_scores = models_utils.get_scores(
    y_true = test_set_y,
    y_pred = xgb_predictions,
    sample_weight = classes_weights_test,
    encoder = ener_class_encoder,
    verbose=True
)

# %%
#----    04 Grid Search    ----#

# Define grid search
param_grid_I = {
    'n_estimators': [80, 100, 120, 150, 200, 250],
    'max_depth' : [6], 
    'learning_rate' : [.3], 
    'gamma' : [0],
    'reg_lambda': [1],
    'scale_pos_weight' : [1]
}

param_grid_II = {
    'max_depth' : [6, 8, 10], 
    'learning_rate' : [.01, .05, .1], 
    'gamma' : [0],
    'reg_lambda': [1],
    'scale_pos_weight' : [1]
}

param_grid_III = {
    'max_depth' : [6], 
    'learning_rate' : [.1], 
    'gamma' : [0, .25, .5],
    'reg_lambda': [1, 10, 20],
    'scale_pos_weight' : [1]
}

param_grid_IV = { # to allow fast compilation
    'max_depth' : [6], 
    'learning_rate' : [.1], 
    'gamma' : [0],
    'reg_lambda': [10],
    'scale_pos_weight' : [1]
}
     
grid_xgb = GridSearchCV(
    xgb.XGBClassifier(
        n_estimators = 120,
        objective = 'multi:softmax',
        eval_metric = f1_score_weighted,
        colsample_bytree = 0.5,
        seed = 2022
    ), 
    param_grid = param_grid_IV,
    scoring = f1_score_macro, 
    cv = StratifiedKFold(5, shuffle = True, random_state = 2022)
)

#%%
## %%time
grid_xgb.fit(train_set, train_set_y, sample_weight = classes_weights)


#%%
# Check Results
grid_xgb_result = pd.DataFrame(grid_xgb.cv_results_).sort_values(by = ['rank_test_score'])

sns.pointplot(data = grid_xgb_result, y = 'mean_test_score', hue = 'param_gamma',
              x = 'param_reg_lambda')

grid_xgb_result


#%%

#----    05 Best Model    ----#

# 'max_depth' : 6; 'learning_rate' : .1; 'gamma' : 0; 'reg_lambda': 10;
best_fit_xgb = xgb.XGBClassifier(
    n_estimators = 120,
    objective = 'multi:softmax',
    max_depth = 6,
    learning_rate = .1,
    gamma = 0,
    reg_lambda = 10,
    colsample_bylevel = 0.5,
    eval_metric = f1_score_weighted,
    seed = 2022,
    n_jobs = 5
    ).fit(train_set, train_set_y, sample_weight = classes_weights)
xgb_predictions = best_fit_xgb.predict(test_set)

# %%
xgb_scores = models_utils.get_scores(
    y_true = test_set_y,
    y_pred = xgb_predictions,
    sample_weight = classes_weights_test,
    encoder = ener_class_encoder,
    verbose=True
)

# %%
# Check Features
best_features = pd.DataFrame({
    'feature':list(train_set.columns),
    'importance':best_fit_xgb.feature_importances_
    }).sort_values(by=['importance'], ascending = False) 

# Plot Features
sns.barplot(data = best_features.head(10), x = 'importance', y = 'feature')

best_features

# %%
from yellowbrick.classifier import ConfusionMatrix

nb_cm = ConfusionMatrix(
    gaussian_model, classes = ener_class_encoder.classes_,
    label_encoder= dict(zip(
        ener_class_encoder.transform(ener_class_encoder.classes_), 
        ener_class_encoder.classes_
        ))
)

nb_cm.score(test_set, test_set_y)
nb_cm.show()

# %%
fig, ax = plt.subplots(nrows=1,ncols=1, figsize=(8, 6))
xgb_cm = ConfusionMatrix(
    best_fit_xgb, classes = ener_class_encoder.classes_,
    label_encoder= dict(zip(
        ener_class_encoder.transform(ener_class_encoder.classes_), 
        ener_class_encoder.classes_
        )),
        ax = ax
        # size=(900, 900),
        # fontsize = 19
)

xgb_cm.score(test_set, test_set_y)
xgb_cm.show(outpath="copnfusion-matrix.pdf")


# %%
