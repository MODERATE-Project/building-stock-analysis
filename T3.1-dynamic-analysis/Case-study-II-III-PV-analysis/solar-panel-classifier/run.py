import fire
from solarnet.run import RunTask


if __name__ == '__main__':
    
    # RunTask().make_masks()
    # RunTask().split_images()
    # RunTask().train_classifier(retrain=True, warmup=2, max_epochs=100, patience=5)
    # RunTask().train_both()
    # RunTask().classify_new_data(retrained=True)
    RunTask().segment_new_data()
    # fire.Fire(RunTask)
