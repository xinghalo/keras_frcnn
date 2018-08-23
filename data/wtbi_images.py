import os
import requests

IMG_PATH = '/Users/xingoo/Desktop/wtbi_images/'

with open('photos/photos.txt','r') as f:
    lines = f.readlines()
    total = str(len(lines))
    for index, line in enumerate(lines):
        if index > -1 :
            id, url = line.strip('\n').split(',')
            post_prefix = url.split('/')[-1].split('?')[0].split('.')[-1]

            r = requests.request('get', url)

            with open(IMG_PATH + id+'.'+post_prefix, 'wb') as f:
                f.write(r.content)
            f.close()

            print(str(index) + "/" + total)