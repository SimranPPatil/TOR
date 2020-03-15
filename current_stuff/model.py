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
from sklearn import tree
import math
from sklearn.preprocessing import StandardScaler
from dataGraph import generateGraph
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.autograd import grad
from torch.autograd import Variable

def get_entropy(portion):
    if portion == 0:
        return 0
    return -1*portion*math.log(portion,2)

def get_all_entropy(pportion, nportion):
    return get_entropy(pportion) + get_entropy(nportion)

def get_info_gain(feature_index, X, Y):
    p = 0
    n = 0

    pc = 0 # total number of examples that have the attribute
    ppc = 0 # number of positive examples that have the attribute
    pnc = 0 # number of neg examples that have the attr

    npc = 0
    nppc = 0
    npnc = 0

    for i in range(len(X)):
        if Y[i] == 1:
            p += 1
        elif Y[i] == 0:
            n += 1
        if X[i][feature_index] == 1:
            pc += 1
            if Y[i] == 1:
                ppc += 1
            else:
                pnc += 1
        else:
            npc += 1
            if Y[i] == 1:
                nppc += 1
            else:
                npnc += 1
    if p +n != len(X):
        return 0
    base_entropy = get_all_entropy((float(p)+1)/(len(X)+1), (float(n)+1)/(len(X)+1))
    right_portion = float(pc)/len(X)
    right_entropy = get_all_entropy((float(ppc)+1)/(pc+1), (float(pnc)+1)/(pc+1))
    left_portion = 1- right_portion
    left_entropy = get_all_entropy((float(nppc)+1)/(npc+1), (float(npnc)+1)/(npc+1))
    return  base_entropy - right_portion*right_entropy - left_portion*left_entropy


class Simple3LNN(nn.Module):

    def __init__(self, input_dim, embed_dim, output_dim, cuda):
        super(Simple3LNN, self).__init__()

        self.on_cuda = cuda
        self.layer1 = nn.Linear(input_dim, embed_dim)
        self.layer2 = nn.Linear(embed_dim, embed_dim)
        self.layer3 = nn.Linear(embed_dim, output_dim)

        if cuda:
            self.layer1 = self.layer1.cuda()
            self.layer2 = self.layer2.cuda()
            self.layer3 = self.layer3.cuda()

    def forward(self, x):
        x = F.relu(self.layer1(x))
        x = F.relu(self.layer2(x))
        x = self.layer3(x)
        return x

    def predict(self, X):
        output = []
        for x in X:
            x = torch.tensor(x).float()
            if self.on_cuda:
                x = x.cuda()
            yp = self.forward(x)
            _, i = yp.max(0)
            output.append(i.item())
        return output


def pytorch_train(torch_model, X, Y, epoch, cuda):
    label_dist = np.zeros(2)
    for y in Y:
        label_dist[y] += 1
    label_weight = [1/(label_dist[0]/len(Y)), 1/(label_dist[1]/len(Y))]
    label_weight = torch.tensor(label_weight)
    if cuda:
        label_weight = label_weight.cuda()
    loss_fn = nn.CrossEntropyLoss(weight=label_weight)
    optimiser = optim.Adam(torch_model.parameters())

    for e in range(epoch):
        for i in range(len(X)):
            torch_model.zero_grad()

            x = torch.tensor(X[i]).float().view(1,-1)
            y = torch.tensor([Y[i]])

            if cuda:
                x = x.cuda()
                y = y.cuda()

            yp = torch_model(x)
            loss = loss_fn(yp, y)
            loss.backward()
            optimiser.step()

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
        if "good" in label_string:
            label = 0
        elif "bad" in label_string:
            label = 1
            print("THIS SHOLD NOT HAPPEN")
            exit()

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
        best = 0 
        name = ""
        print(len(X))
        for index, t in categorical_mapper.items():
            for k,v in t["toInt"].items():
                temp = get_info_gain(v, X,Y)
                if best < temp:
                    best = temp
                    name = k
        print("Best info gain is %f at attribute %s"%(best, name))
        continue
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

        model = None
        pytorch = True
        if pytorch:
            # use pytorch
            input_dim = len(X_tr[0])
            embed_dim = 200
            output_dim = 2
            epoch = 5
            cuda = True
            model = Simple3LNN(input_dim, embed_dim, output_dim, cuda)
            pytorch_train(model, X_tr, Y_tr, epoch, cuda)

        if not pytorch:
            #model = LogisticRegression(random_state=0, solver='lbfgs', multi_class='multinomial', max_iter=100, class_weight="balanced")
            model = SVC(C=1.0, cache_size=200, coef0=0.0, decision_function_shape='ovr', degree=3, gamma='auto', kernel='rbf', max_iter=1000, probability=False, random_state=None, shrinking=True, tol=0.001, verbose=False,class_weight="balanced")
            #model = RandomForestClassifier(n_estimators=200, max_depth=3, random_state=0, class_weight="balanced")
            #model = Perceptron(tol=1e-3, random_state=0, class_weight="balanced")
            model.fit(X_tr, Y_tr)

        Yp = model.predict(X_te)
        correct = 0.0
        recall = 0.0
        confusion_mat = confusion_matrix(Y_te, Yp)
        print(confusion_mat)
        for i in range(len(confusion_mat)):
            correct += confusion_mat[i][i]
        print("Accuracy: %f" % (correct / len(Yp)))
        print("Precision: %f" % (confusion_mat[0][0] / np.sum(confusion_mat, axis=0)[0]))
        print("FNR: %f" % (confusion_mat[0][1] / sum(confusion_mat[0])))

        label_dist = {}
        for t in Y_te:
            if t not in label_dist:
                label_dist[t] = 0
            label_dist[t] += 1

        print(label_dist)

        for key, val in label_dist.items():
            if key == 0:
                label_name = "good"
            elif key == 1:
                label_name = "bad"
            print("%d: %s %f" % (key, label_name, float(val) / len(Y_te)))
        print("------------------------------------------------")
