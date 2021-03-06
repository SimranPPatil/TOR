import csv
import re
import numpy as np
from random import shuffle
from sklearn.linear_model import LogisticRegression
from sklearn.linear_model import Perceptron
from sklearn.metrics import confusion_matrix
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.preprocessing import normalize
from sklearn.preprocessing import StandardScaler
from dataGraph import generateGraph


def reformatFeaturePlatform(value):
    return value.split(" ")[-1]


FEATURE_BLACKLIST = {"last_restarted", "version"}

if __name__ == "__main__":
    feature_dict = {}
    reformatted = []
    real_features = set()
    categorical_features = set()
    categorical_cardinality = {}
    categorical_one_card = set()
    categorical_mapper = {}  # maps category values to numbers

    # "platform"
    with open("datanf.csv") as csvfile:
        data = csv.reader(csvfile)
        feature_names = next(data)

        # index the feature names for the future
        for i in range(len(feature_names)):
            feature_dict[feature_names[i]] = i

        for row in data:
            sample = {}
            for i in range(len(feature_names)):
                fname = feature_names[i]
                fvalue = row[i].lower()
                if fvalue == "na" or fname in FEATURE_BLACKLIST:
                    continue
                try:
                    fvalue = float(fvalue)
                    real_features.add(fname)
                    sample[fname] = fvalue
                except ValueError:
                    categorical_features.add(fname)
                    sample[fname] = fvalue
            reformatted.append(sample)

    with open("data3nf.csv") as csvfile:
        data = csv.reader(csvfile)
        feature_names = next(data)

        for row in data:
            sample = {}
            for i in range(len(feature_names)):
                fname = feature_names[i]
                fvalue = row[i].lower()
                if fvalue == "na" or fname in FEATURE_BLACKLIST:
                    continue
                try:
                    fvalue = float(fvalue)
                    real_features.add(fname)
                    sample[fname] = fvalue
                except ValueError:
                    categorical_features.add(fname)
                    sample[fname] = fvalue
            reformatted.append(sample)

    # Construct each set for possible values for a feature
    for cf in categorical_features:
        categorical_cardinality[cf] = set()

    for sample in reformatted:
        for cf in categorical_features:
            if cf not in sample:
                continue
            value = sample[cf]
            if cf == "platform":
                value = reformatFeaturePlatform(value)
                sample[cf] = value
            categorical_cardinality[cf].add(sample[cf])

    # Create a mapping between value of categorical value to an int
    for k, v in categorical_cardinality.items():
        ordered = list(v)
        ordered.sort()
        categorical_mapper[k] = {}
        categorical_mapper[k]["toString"] = {
            i: ch for i, ch in enumerate(ordered)}
        categorical_mapper[k]["toInt"] = {
            ch: i for i, ch in enumerate(ordered)}

    # find features that only has one value (uninteresting features)
    for k, v in categorical_cardinality.items():
        if len(v) == 1:
            categorical_one_card.add(k)
    cat_feat = categorical_features.difference(categorical_one_card)
    ordered_features = list(real_features) + list(cat_feat)
    ordered_features.sort()

    # insert graph generating hook
    '''
    generateGraph(reformatted, real_features, cat_feat)
    exit()
    '''

    guard_dataset = []
    exit_dataset = []
    middle_dataset = []

    # generate numpy array
    for sample in reformatted:
        entry = []
        label = None
        for feature in ordered_features:
            if feature in categorical_features:
                cardinality = len(categorical_cardinality[feature])
                array = np.zeros(cardinality)
                index = 0
                if feature in sample:
                    index = categorical_mapper[feature]["toInt"][sample[feature]]
                    array[index] = 1
                if feature == "label":
                    label = index
                else:
                    entry.append(array)
            elif feature in real_features:
                array = np.zeros(1)
                if feature in sample:
                    array[0] = sample[feature]
                entry.append(array)
        entry = np.concatenate(entry)
        label_string = categorical_mapper["label"]["toString"][label]
        if "exit" in label_string:
            exit_dataset.append((entry, label))
        elif "guard" in label_string:
            guard_dataset.append((entry, label))
        elif "middle" in label_string:
            middle_dataset.append((entry, label))

    total_dataset = [exit_dataset, guard_dataset, middle_dataset]

    for dataset in total_dataset:
        shuffle(dataset)
        X = []
        Y = []
        for s in dataset:
            X.append(s[0])
            Y.append(s[1])
        # X = normalize(X)
        scaler = StandardScaler()
        scaler.fit(X)
        X = scaler.transform(X)

        train_len = int(len(dataset) * 0.75)
        test_len = len(dataset) - train_len

        train_set = dataset[:train_len]
        test_set = dataset[train_len:]

        X_tr = X[:train_len]
        Y_tr = Y[:train_len]
        X_te = X[train_len:]
        Y_te = Y[train_len:]

        # model = LogisticRegression(random_state=0, solver='lbfgs', multi_class='multinomial', max_iter=100, class_weight="balanced")
        model = SVC(C=1.0, cache_size=200, coef0=0.0, decision_function_shape='ovr', degree=3, gamma='auto', kernel='rbf', max_iter=10, probability=False, random_state=None, shrinking=True, tol=0.001, verbose=False,class_weight="balanced")
        # model = RandomForestClassifier(n_estimators=100, max_depth=3, random_state=0, class_weight="balanced")
        # model = Perceptron(tol=1e-3, random_state=0, class_weight="balanced")
        model.fit(X_tr, Y_tr)
        Yp = model.predict(X_te)
        correct = 0.0
        confusion_mat = confusion_matrix(Y_te, Yp)
        print(confusion_mat)
        for i in range(len(confusion_mat)):
            correct += confusion_mat[i][i]
        print("Accuracy: %f" % (correct / len(Yp)))
        print()

        label_dist = {}
        for t in Y_te:
            if t not in label_dist:
                label_dist[t] = 0
            label_dist[t] += 1

        print(label_dist)

        for key, val in label_dist.items():
            label_name = categorical_mapper["label"]["toString"][key]
            print("%d: %s %f" % (key, label_name, float(val) / len(Y_te)))
        print("------------------------------------------------")
