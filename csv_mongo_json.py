import re

out1 = "sample_full.json"
out2 = "full_text3.json"

inp1 = "sample_full2.csv"
inp2 = "full_text2.csv"

with open(inp2, "r") as fr:
    with open(out2, "w") as fw:
        fr.next()  # ignore the header line of csv
        for line in fr:
            temp = re.split(r',', line)  # time, lat, long
            fw.write('{time: "%s", loc: [%s, %s]}\n' % (
            temp[0].strip(), temp[2].strip(), temp[1].strip()))  # longitude, latitude