import os
import cv2

files = os.listdir("/data1/Users/xingoo/Desktop/wtbi_images/")

images = {}
print("collect ...")
for file in files:
    path = "/data1/Users/xingoo/Desktop/wtbi_images/"+file
    if type(cv2.imread(path)) != type(None):
        images[file.split('.')[0]] = "/data1/Users/xingoo/Desktop/wtbi_images/"+file
labels = []

print("filter ... ")

with open('wtbi_label.txt', 'r') as f:
    lines = f.readlines()
    for line in lines:
        arr = line.strip('\n').split(',')
        if arr[0] in images:
            arr[0] = images[arr[0]]
            labels.append(','.join(arr))

print("write ...")

with open('new_wtbi_label.txt', 'w') as f:
    for label in labels:
        f.write(label+'\n')