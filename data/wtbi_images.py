import os
import requests

IMG_PATH = '/Users/xingoo/Desktop/wtbi_images/'

with open('photos/photos.txt','r') as f:
    lines = f.readlines()
    total = str(len(lines))
    for index, line in enumerate(lines):
        if index > 343 :
            id, url = line.split(',')
            r = requests.request('get', url)

            with open(IMG_PATH + str(id) + '.jpg', 'wb') as f:
                f.write(r.content)
            f.close()

            print(str(index) + "/" + total)