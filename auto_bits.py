content = [x.strip("\n") for x in open('words.txt').readlines()]
bits = {}

total = float(len(content))

MAX_L = 4
MIN_L = 2
print total
for idfg, word in enumerate(content):
    if len(word) < 7:
        continue
    for bit in bits:
        bit_d = bits[bit]
        if not bit_d[0]:
            if word.startswith(bit):
                bits[bit][1] += 1
        else:
            if word.endswith(bit):
                bits[bit][1] += 1
    for i in range(MIN_L, MAX_L+1):
        test_bit = word[-i:]
        if test_bit in bits:
            continue
        else:
            bits[test_bit] = [True, 1]
        test_bit = word[:i]
        if test_bit in bits:
            continue
        else:
            bits[test_bit] = [False, 1]
    if idfg % 150 == 0:
        print idfg
    if idfg % 15000 == 0:
        r = []
        for bit in bits:
            if bits[bit][1] < 700:
                r.append(bit)
        for i in r:
            del bits[i]

THRESH = 0.0025
final_bits = {}
for i in bits:
    percent = bits[i][1] / total
    if percent >= THRESH:
        final_bits[i] = bits[i]
out = open('new_cbit.txt', 'w')
for bit in final_bits:
    if final_bits[bit][0]:
        out.write("-")
    else:
        out.write("+")
    out.write(bit + "\n")
out.close()