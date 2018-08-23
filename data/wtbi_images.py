import requests

IMG_PATH = '/Users/xingoo/Desktop/wtbi_images/'
print('begin')

photos = set()
lines = []
with open('validate_photo.txt','r') as f:
    ps = f.readlines()
    for p in ps:
        photos.add(p.strip('\n'))

with open('photos/photos.txt','r') as f:
    lines = f.readlines()

total = str(len(lines))
for index, line in enumerate(lines):
    if index > 937:
        id, url = line.strip('\n').split(',')
        if id in photos:
            post_prefix = url.split('/')[-1].split('?')[0].split('.')[-1]
            while True:
                try:
                    r = requests.get(url, timeout=0.8)

                    with open(IMG_PATH + id + '.' + post_prefix, 'wb') as f:
                        f.write(r.content)
                    break
                except IOError as e:
                    print('超时'+url)

        print(str(index) + "/" + total)