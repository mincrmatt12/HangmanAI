import string
from operator import attrgetter
import pygame
import pygame.freetype
import collections

import re

pygame.init()

content = open('words.txt')
popularity = open('word_counts.txt')
raw_bits = open('common_bits.txt').readlines()

bits = []
for i in raw_bits:
    bit = i[1:]
    bit = bit.strip("\n")
   # print i[0], i[0] == "-", i
    suf = i[0] == "-"
    bits.append((suf, bit))

words = content.readlines()
letter_count_by_length = {}
word_popularity = collections.defaultdict(lambda: 0)
low = 2
for i in popularity.readlines():
    wordy = i.split(" ")[0]
    valy = float(i.split(" ")[1].strip("\n"))
    word_popularity[wordy] = valy
    low = min(low, valy)
word_popularity.default_factory = lambda: low

last = ''
print "- Loading word dictionary..."
print "  = Loading words by letter count"

words_by_length = {}
wrongs = 0
rights = 0

for word in words:
    word = word.strip("\n").lower()
    if len(word) == 0:
        continue

    if "-" in word:
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
possible_weighted = {}
status = []

surf = pygame.display.set_mode([1024, 768])
pygame.display.set_caption("HangmanAI")

font = pygame.freetype.Font("OpenSans-Regular.ttf")
mono = pygame.freetype.Font("LiberationMono-Regular.ttf")

editor_selected = 3


def display_state():
    global surf, status

    filed = "".join(("-" if x == "." else x for x in status))
    # print filed
    sized = mono.get_rect(filed, size=52)
    sized.width += sized.x
    sized.height += 15
    posy = 15
    posx = 512 - sized.width / 2

    bg = pygame.Surface(sized.size, pygame.SRCALPHA)
    if editor_selected > -1:
        sizy = mono.get_rect(" " * editor_selected, size=52)
        x = sizy.width + sizy.x
        mono_underscore = mono.get_rect("_", size=52)
        bg.fill((127, 127, 255), (x, sized.height - 10, mono_underscore.width - 2, 10))

    mono.render_to(bg, (0, 0), filed, fgcolor=(0, 0, 0), bgcolor=(0, 0, 0, 0), size=52)
    surf.blit(bg, (posx, posy))


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

    def __eq__(self, other):
        return self.equals(other)

    def falsify(self):
        self.false = True
        self.true = False
        for child in self.childs:
            all_predictions_ever[child].falsify()

    def good(self):
        return False

    def notgood(self):
        return False

    def pretty(self):
        return "Blank"


class NotPrediction(Prediction):
    def __init__(self, pos, mal):
        super(NotPrediction, self).__init__()
        self.pos = pos
        self.mal = mal

    def valid_for(self, word):
        for w, a in zip(word, self.pos):
            if w == self.mal and not a:
                return False
            elif w != self.mal and a:
                return False
        return True

    def depends_on(self, other):
        if type(other) == ContainsPrediction:
            if other.segment == self.mal:
                return True
        return False

    def equals(self, other):
        if type(other) == NotPrediction:
            if other.mal == self.mal and other.pos == self.pos:
                return True
        return False

    def weight_scale(self):
        return 1.0

    def good(self):
        return self.valid_for("".join(status))

    def pretty(self):
        return "Contains specific letters"


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

    def pretty(self):
        return "Word contains {}".format(self.segment)


class UsesBitPrediction(Prediction):
    def __init__(self, bit_):
        super(UsesBitPrediction, self).__init__()
        self.bit = bit_

    def valid_for(self, word):
        if self.bit[0]:
            return word.endswith(self.bit[1])
        else:
            return word.startswith(self.bit[1])

    def good(self):
        return self.valid_for(''.join(status))

    def depends_on(self, other):
        if type(other) == ContainsPrediction:
            return other.segment in self.bit[1]
        return False

    def equals(self, other):
        if type(other) == UsesBitPrediction:
            return other.bit == self.bit
        return False

    def weight_scale(self):
        return 0.125 + 0.075*len(self.bit[1])

    def pretty(self):
        return "Word {} with {}".format("ends" if self.bit[0] else "starts", self.bit[1])


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

    def pretty(self):
        return "Word matches regex {}".format(self.plain)


def status_text(text):
    pygame.event.pump()
    sized = font.get_rect(text, size=32)
    surf.fill((255, 255, 255), (0, 150, 1024, 618))
    sized.width += sized.x
    font.render_to(surf, (512 - sized.width / 2, 200), text, fgcolor=(0, 0, 0), size=32)
    pygame.display.flip()


def update_possible():
    global possible, predictions, possible_weighted
    possible_old = possible[:]
    possible = []
    possible_weight = {}
    possible_weighted = {}

    for i, prediction in enumerate(predictions):
        if i % 8 == 0:
            status_text("Checking forced validity of predictions: {} of {}".format(i, len(predictions)))
        if prediction.false is False and prediction.true is False:
            if prediction.good():
                prediction.true = True
                prediction.false = False
            elif len(possible) > 1:
                tops = topmost(prediction)
                valid = True
                for top in tops:
                    if not (top.true and not top.false):
                        valid = False
                if valid:
                    if not prediction.good():
                        prediction.false = True
                        prediction.true = False

    vals = [0 for x in xrange(len(predictions))]
    a = len(possible_old)
    for position, word in enumerate(possible_old):
        good = True
        possible_weight[word] = 0
        for i, prediction in enumerate(predictions):
            if prediction.valid_for(word):
                vals[i] += word_popularity[word] if "".join(status).count(".") >= max(2, len(status) / 3) else 1.0
                possible_weight[word] += prediction.weight_scale() * word_popularity[word]
                if prediction.false:
                    good = False
                    possible_weight[word] -= prediction.weight_scale() * word_popularity[word]
            else:
                if prediction.true:
                    good = False
        if good:
            possible.append(word)

        if position % 150 == 0:
            status_text("Word validity checking: {} of {}".format(position + 1, a))

    status_text("Word validity checking: {} of {}".format(a, a))

    total = len(possible)
    for i, prediction in enumerate(predictions):
        weight = float(vals[i]) / total
        predictions[i].weight = weight * predictions[i].weight_scale()
        status_text("Prediction weighting: {} of {}".format(i + 1, len(predictions)))

    delme = []

    for i in range(len(predictions)):
        if predictions[i].weight == 0.0:
            delme.append(predictions[i].number)

    total = len(possible_weight)

    for count, i in enumerate(possible_weight):
        if i in possible:
            possible_weighted[i] = possible_weight[i] / float(len(predictions))
        if count % 150 == 0:
            status_text("Word weighting: {} of {}".format(count + 1, total))

    status_text("Word weighting: {} of {}".format(total, total))

    for i in delme:
        predictions.remove(all_predictions_ever[i])


def add_prediction(p):
    global predictions

    for exist in predictions:
        if exist.equals(p) or p.equals(exist):
            print "hi", p, exist
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

    for bit_ in bits:
        add_prediction(UsesBitPrediction(bit_))


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


def mal_create():
    plain = "".join(status)
    ad = []

    for letter in string.ascii_lowercase:
        if letter in plain:
            print letter
            new = []
            for pos in plain:
                if pos == letter:
                    new.append(True)
                else:
                    new.append(False)
            x = NotPrediction(new, letter)
            x.true = True
            ad.append(x)

    return ad


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


modules = [random_common_module, current_board_module, mal_create]


def iterate_modules():
    global predictions
    addable = []
    for module in modules:
        addable.extend(module())
    for ad in addable:
        add_prediction(ad)
    predictions = list(set(predictions))


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
    a, b = best()
    print a.segment
    if len(possible) < 15:
        print "Possible words: ", possible_weighted
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


def display_predictions():
    sorted_pred = tuple(reversed(sorted(predictions, key=attrgetter("weight"))))
    sorted_pred = tuple(x for x in sorted_pred if x.true is False and x.false is False)
    sorted_pred = tuple(reversed(sorted(sorted_pred, key=attrgetter("weight"))))
    sized = font.render_to(surf, (5, 220), "Predictions:", size=22, fgcolor=(0, 0, 255))
    y = sized.height + sized.y + 225
    i = 0
    while y < 700 and i < len(sorted_pred):
        pred = sorted_pred[i]

        dist = 255 - max(0, min(255, int((700 - 225 - y) * 1.462)))
        sized = font.render_to(surf, (5, y), pred.pretty(), size=16, fgcolor=(dist, dist, dist))
        i += 1
        y += sized.height + 5


def display_words():
    sorted_words = tuple(sorted(possible_weighted, key=possible_weighted.get, reverse=True))
    sized = font.get_rect("Words:", size=22)

    sized = font.render_to(surf, (1024-5-sized.x-sized.width, 220), "Words:", size=22, fgcolor=(0, 0, 255))
    y = sized.height + sized.y + 225
    i = 0
    while y < 700 and i < len(sorted_words):

        dist = 255 - max(0, min(255, int((700 - 225 - y) * 0.862)))
        sized = font.get_rect(sorted_words[i], size=16)
        sized = font.render_to(surf, (1024-5-sized.x-sized.width, y), sorted_words[i], size=16, fgcolor=(dist, dist,
                                                                                                         dist))
        i += 1
        y += sized.height + 5


estate = 0

ga, gb = None, None

yn_c = True


def display_input_guess():
    global ga, gb

    font.render_to(surf, (25, 150), "Guess: {}".format(ga.segment), size=48)
    met = font.get_rect("Correct? {}".format("Y" if yn_c else "N"), size=48)
    x = met.x + met.width
    font.render_to(surf, (1024-25-x, 150), None, fgcolor=(0, 255, 0), size=48)


def end_game():
    font.render_to(surf, (5, 200), "Correct guesses: {}".format(rights), size=16, fgcolor=(25, 140, 25))
    font.render_to(surf, (5, 236), "Wrong guesses: {}".format(wrongs), size=16, fgcolor=(255, 127, 127))
    font.render_to(surf, (7, 280), "Guesses: {}".format(rights+wrongs), size=40, fgcolor=(70, 70, 70))

if __name__ == "__main__":
    while True:
        surf.fill([255, 255, 255])
        display_state()
        if estate == 0:
            editor_selected = -1
            iterate_modules()
            update_possible()
            update_possible()
            if "." not in status:
                estate = 2
                continue
            status_text("")
            ga, gb = best()

            estate = 1
            pygame.display.flip()
        elif estate == 1:
            display_input_guess()
            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        yn_c = not yn_c
                    elif event.key == pygame.K_LEFT:
                        editor_selected -= 1
                        editor_selected = max(0, editor_selected)
                    elif event.key == pygame.K_RIGHT:
                        editor_selected += 1
                        editor_selected = min(len(status)-1, editor_selected)
                    elif event.key == pygame.K_BACKSPACE and editor_selected != -1:
                        status[editor_selected] = "."
                    elif event.key == pygame.K_RETURN:
                        tried.append(ga.number)
                        if yn_c:
                            all_predictions_ever[ga.number].true = True
                            shuffle_up(ga)
                            rights += 1
                        else:
                            all_predictions_ever[ga.number].falsify()
                            wrongs += 1
                        estate = 0
                    else:
                        try:
                            val = chr(event.key)
                            if val in string.ascii_lowercase and editor_selected != -1:
                                status[editor_selected] = val
                        except ValueError:
                            pass
                elif event.type == pygame.QUIT:
                    pygame.quit()
        elif estate == 2:
            end_game()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
        if estate != 2:
            display_words()
            display_predictions()

        pygame.display.flip()
       # do_guess()
