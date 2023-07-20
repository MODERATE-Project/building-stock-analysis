#!/usr/bin/env python
# coding: utf-8

# %%

#----    settings    ----
from pathlib import Path
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import re

from sklearn.metrics import confusion_matrix, precision_score, recall_score,\
    fbeta_score, make_scorer, f1_score, balanced_accuracy_score


# Custom modules
from src.utils import my_utils

# my_env object containing environmental variables is passed in the analysis scripts

#----    get_confusion_matrix   ----

def get_confusion_matrix(
        y_true,
        y_pred,
        encoder = None,
        normalize:str = None):
    """
    """
    conf_matrix = confusion_matrix(
        y_true = y_true,
        y_pred = y_pred,
        normalize = normalize
    )

    if encoder is not None:
        labels = encoder.classes_
    else:
        labels = None


    res = pd.DataFrame(
        data = conf_matrix,
        columns = labels,
        index = labels
    )
    
    res.index = res.index.rename('True')

    return res

#----    get_scores    ----

def get_scores(
        y_true,
        y_pred,
        sample_weight = None,
        encoder = None,
        verbose:bool = False
    ):
    """
    """

    confusion_matrix = get_confusion_matrix(
    y_true=y_true,
    y_pred=y_pred,
    encoder= encoder
    )

    micro_scores = pd.DataFrame({
        'Precision':  precision_score(y_true=y_true, y_pred=y_pred, average=None),
        'Recall':  recall_score(y_true=y_true, y_pred=y_pred, average=None),
        'F1 Score':  f1_score(y_true=y_true, y_pred=y_pred, average=None)
    }, index=encoder.classes_).T


    macro_scores = pd.DataFrame({
        'Score': [
            balanced_accuracy_score(y_true=y_true, y_pred=y_pred,
                                    sample_weight = sample_weight),
            f1_score(y_true=y_true, y_pred=y_pred, average='macro'),
            f1_score(y_true=y_true, y_pred=y_pred, 
                     average='weighted', sample_weight = sample_weight)
            ]
    }, index=['Accuracy Balanced', 'F1 Score Macro', 'F1 Score Weighted'])

    res = {
        'confusion_matrix':confusion_matrix,
        'micro_scores':micro_scores,
        'macro_scores':macro_scores
    }

    if verbose:
        print('Confusion Matrix')
        print(confusion_matrix.round(3))

        print('\nSingle class scores')
        print(micro_scores.round(3))

        print('\nOverall scores')
        print(macro_scores.round(3))

    return res



#====
