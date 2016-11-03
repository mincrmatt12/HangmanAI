import string
from operator import attrgetter
import difflib

import re

content = open('words.txt')
raw_bits = open('common_bits.txt').readlines()

bits = []
for i in raw_bits:
    bit = i[1:]
    suf = i[0] == "-"
    bits.append((suf, bit))

words = content.readlines()
letter_count_by_length = {}
last = ''
print "- Loading word dictionary..."
print "  = Loading words by letter count"

words_by_length = {}

for word in words:
    word = word.strip("\n")
    if len(word) == 0:
        continue
    if word[0] != last:
        print "     ~ Completed letter", last
        last = word[0]

    if len(word) not in words_by_length:
        words_by_length[len(word)] = []
    words_by_length[len(word)].append(word)
print "     ~ Completed letter z"
print "- Done loading word dictionary"

length = 0
all_predictions_ever = []
predictions = []
remaining = -1
global_number = 0
possible = []
status = []


class Prediction(object):
    def __init__(self):
        global global_number
        self.childs = []
        self.weight = 0
        self.true = False
        self.false = False
        self.number = global_number
        all_predictions_ever.append(self)
        global_number += 1

    def valid_for(self, word):
        return True

    def depends_on(self, other):
        pass

    def equals(self, other):
        return False

    def weight_scale(self):
        return 1.0

    def falsify(self):
        self.false = True
        self.true = False
        for child in self.childs:
            all_predictions_ever[child].falsify()

    def good(self):
        return False

    def notgood(self):
        return False


class ContainsPrediction(Prediction):
    def __init__(self, segment):
        super(ContainsPrediction, self).__init__()

        self.segment = segment

    def valid_for(self, word):
        return self.segment in word

    def depends_on(self, other):
        if type(other) == ContainsPrediction:
            return other.segment in self.segment
        return False

    def equals(self, other):
        if type(other) == ContainsPrediction:
            return self.segment == other.segment
        else:
            return False

    def weight_scale(self):
        return 0.1 * len(self.segment) + 0.1

    def good(self):
        return self.segment in ''.join(status)

    def __repr__(self):
        return "CP: " + self.segment


class MatchesRegexPrediction(Prediction):
    def __init__(self, r):
        super(MatchesRegexPrediction, self).__init__()

        self.regex = re.compile(r)
        self.plain = r

    def valid_for(self, word):
        return bool(self.regex.match(word))

    def good(self):
        return self.valid_for(''.join(status).replace('.', 'A'))

    @staticmethod
    def overlap(a, b):
        good = True
        for i, j in zip(a, b):
            if i == j:
                good = True
            elif i == "." and j != ".":
                good = True
            elif i != "." and j == ".":
                good = True
            else:
                good = False
        return good

    def depends_on(self, other):
        if type(other) == MatchesRegexPrediction:
            if MatchesRegexPrediction.overlap(self.plain, other.plain):
                return len(self.plain) - self.plain.count('.') <= len(other.plain) - other.plain.count('.')
            else:
                return False
        if type(other) == ContainsPrediction:
            return other.segment in self.plain

    def equals(self, other):
        if type(other) == MatchesRegexPrediction:
            return self.plain == other.plain
        return False

    def weight_scale(self):
        return 0.15 * len(self.plain) - self.plain.count('.') + 0.2


def update_possible():
    global possible, predictions
    possible_old = possible[:]
    possible = []

    for prediction in predictions:
        if prediction.false is False and prediction.true is False:
            if prediction.good():
                prediction.true = True
                prediction.false = False

    vals = [0 for x in xrange(len(predictions))]
    for word in possible_old:
        good = True
        for i, prediction in enumerate(predictions):
            if prediction.valid_for(word):
                vals[i] += 1
                if prediction.false:
                    good = False
            else:
                if prediction.true:
                    good = False
        if good:
            possible.append(word)

    total = len(possible)
    for i, prediction in enumerate(predictions):
        weight = float(vals[i]) / total
        predictions[i].weight = weight * predictions[i].weight_scale()

    delme = []

    for i in range(len(predictions)):
        if predictions[i].weight == 0.0:
            delme.append(predictions[i].number)

    for i in delme:
        predictions.remove(all_predictions_ever[i])


def add_prediction(p):
    global predictions

    for exist in predictions:
        if exist.equals(p):
            return
        if p.depends_on(exist):
            exist.childs.append(p.number)
            p.false = exist.false

    predictions.append(p)


def init_with_length(l):
    global length, predictions, possible, remaining, status

    length = l
    predictions = []
    possible = words_by_length[l]
    remaining = 7
    status = ["." for x in range(length)]

    for letter in string.ascii_lowercase:
        add_prediction(ContainsPrediction(letter))


def shuffle_up(at):
    orig = at.childs[:]

    for i in orig:
        predictions.append(all_predictions_ever[i])


def depends(at):
    f = []
    for i in all_predictions_ever:
        if at.number in i.childs:
            f.append(i)
    return f

tried = []


def best():
    good = False
    gd = -1
    predco = predictions[:]
    pp = -1
    while not good:
        better = (x for x in predco if (x.true is False and x.false is False))
        first = max(better, key=attrgetter('weight'))
        again = topmost(first)
        better_again = list((x for x in again if (x.true is False and x.false is False)))
        if len(better_again) == 0:
            predco.remove(first)
            continue
        else:
            proper = max(better_again, key=attrgetter('weight'))
            if proper.number in tried:
                predco.remove(first)
            good = True
            gd = max(better_again, key=attrgetter('weight'))
            pp = first

    return gd, pp


def best2():
    good = False
    gd = -1
    predco = predictions[:]
    while not good:
        better = (x for x in predco if (x.true is False and x.false is False))
        first = max(better, key=attrgetter('weight'))
        again = topmost(first)
        better_again = list((x for x in again if (x.true is False and x.false is False)))
        if len(better_again) == 0:
            predco.remove(first)
            continue
        else:
            proper = max(better_again, key=attrgetter('weight'))
            if proper.number in tried:
                predco.remove(first)
                continue
            good = True
            gd = first

    return gd


def current_board_module():
    m = MatchesRegexPrediction("".join(status))
    m.true = True
    return [m]


def random_common_module():
    DEPTH = 2

    added = []

    for prediction in predictions:
        if prediction.true == False and prediction.false == False:
            if type(prediction) == ContainsPrediction:
                vals = [0 for x in range(len(string.ascii_lowercase))]
                for word in possible:
                    if prediction.valid_for(word):
                        for i, j in enumerate(word):
                            if i == len(word) - len(prediction.segment):
                                break
                            else:
                                if j == prediction.segment:
                                    nxt = word[i + len(prediction.segment)]
                                    if nxt not in string.ascii_lowercase:
                                        continue
                                    vals[string.ascii_lowercase.index(nxt)] += 1
                for i in range(DEPTH):
                    let = vals.index(max(vals))
                    asc = string.ascii_lowercase[let]
                    added.append(ContainsPrediction(prediction.segment + asc))
                    vals.pop(let)

    return added


modules = [random_common_module, current_board_module]


def iterate_modules():
    addable = []
    for module in modules:
        addable.extend(module())
    for ad in addable:
        add_prediction(ad)


def topmost(a, v=0):
    all_pos = []
    for i in depends(a):
        if len(depends(all_predictions_ever[i.number])) == 0:
            all_pos.append(i)
        else:
            all_pos.extend(topmost(all_predictions_ever[i.number], v=1))
    if len(depends(a)) == 0 and v == 0:
        all_pos = [a]
    return list(set(all_pos))


init_with_length(int(raw_input("l: ")))


def do_guess():
    global status
    iterate_modules()
    update_possible()
    a, b = best()
    print a.segment
    if len(possible) < 15:
        print "Possible words: ", possible
    status = raw_input("> ").split("/")
    truth = raw_input("T? ").lower()
    tried.append(a.number)
    if truth == 'y':
        all_predictions_ever[a.number].true = True
        shuffle_up(a)
    elif truth == 'n':
        all_predictions_ever[a.number].falsify()
    elif truth == 'w':
        init_with_length(raw_input("l; "))


while True:
    do_guess()
