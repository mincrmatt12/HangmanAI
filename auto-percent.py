from decimal import Decimal
import decimal

popularity = open('counts_un.txt')

word_popularity = []
for i in popularity.readlines():
    word_popularity.append((i.split("\t")[0], int(i.split("\t")[1].strip("\n"))))

a = float(word_popularity[0][1])
better_listypoo = {}
for i in word_popularity:
    better_listypoo[i[0]] = i[1] / a

output = open('new_counts.txt', 'w')
for i in better_listypoo:
    output.write(i + " " + str(better_listypoo[i]) + "\n")

output.close()